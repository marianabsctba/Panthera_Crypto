"""Transforma cada transação da fila em movimento de carteira e, quando for o caso, em alerta.

    python -m cripto_ingestao.avaliador

Rode quantas cópias precisar: cada uma pega um lote diferente com FOR UPDATE SKIP LOCKED.
"""

import time
from datetime import datetime, timezone

from . import regras
from .banco import Jsonb, batida, conectar
from .listas import em_listas
from .movimentos import classificar, enderecos_de

LOTE = 200
TENTATIVAS = 10


def _quando(segundos):
    return None if segundos is None else datetime.fromtimestamp(segundos, timezone.utc)


def registrar(con, carteira, transacao, historico):
    """Grava o movimento e devolve o alerta criado, se houver."""
    proprios = {l["endereco"] for l in con.execute(
        "SELECT endereco FROM enderecos WHERE carteira_id = %s AND endereco = ANY(%s)", (carteira["id"], list(enderecos_de(transacao))))}
    if not proprios:
        return None
    movimento = classificar(transacao, proprios)
    # A mesma transação chega da mempool, do bloco e às vezes do histórico: grava uma vez, e depois só deixa confirmar.
    linha = con.execute(
        """INSERT INTO movimentos (organizacao_id, carteira_id, transacao, tipo, valor_sats, taxa_sats, contrapartes, estado, bloco, historico, visto_em, confirmada_em)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, now()), %s)
           ON CONFLICT (organizacao_id, carteira_id, transacao) DO NOTHING RETURNING id""",
        (carteira["organizacao_id"], carteira["id"], movimento["transacao"], movimento["tipo"], movimento["valor_sats"], movimento["taxa_sats"],
         Jsonb(movimento["contrapartes"]), movimento["estado"], movimento["bloco"], historico,
         # O que já estava na carteira antes de ela ser cadastrada leva a data do bloco.
         _quando(movimento["confirmada_em"]) if historico else None, _quando(movimento["confirmada_em"]))).fetchone()
    if not linha and movimento["estado"] == "confirmada":
        con.execute("""UPDATE movimentos SET estado = 'confirmada', bloco = %s, confirmada_em = %s, taxa_sats = COALESCE(taxa_sats, %s)
                       WHERE organizacao_id = %s AND carteira_id = %s AND transacao = %s AND estado = 'mempool'""",
                    (movimento["bloco"], _quando(movimento["confirmada_em"]), movimento["taxa_sats"], carteira["organizacao_id"], carteira["id"], movimento["transacao"]))
    usados = con.execute("UPDATE enderecos SET usado = true WHERE carteira_id = %s AND endereco = ANY(%s) AND NOT usado RETURNING ramo",
                         (carteira["id"], list(proprios))).fetchall()
    if any(u["ramo"] is not None for u in usados):
        con.execute("INSERT INTO fila_tarefas (tipo, carteira_id) VALUES ('folga', %s) ON CONFLICT DO NOTHING", (carteira["id"],))
    if not linha or historico:
        return None

    organizacao = carteira["organizacao_id"]
    agenda = {l["endereco"] for l in con.execute("SELECT endereco FROM agenda WHERE organizacao_id = %s", (organizacao,))}
    listas = em_listas(con, [c["endereco"] for c in movimento["contrapartes"]])
    resultado = regras.avaliar(movimento, carteira, agenda, listas.get)
    if not resultado:
        return None
    severidade, titulo, motivos = resultado
    alerta = con.execute(
        "INSERT INTO alertas (organizacao_id, carteira_id, movimento_id, severidade, titulo, motivos) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, criado_em",
        (organizacao, carteira["id"], linha["id"], severidade, titulo, Jsonb(motivos))).fetchone()
    ordem = regras.ORDEM.index(severidade)
    con.execute(
        """INSERT INTO fila_envios (organizacao_id, alerta_id, canal_id)
           SELECT organizacao_id, %s, id FROM canais
           WHERE organizacao_id = %s AND ativo AND array_position(ARRAY['baixa', 'media', 'alta', 'critica'], severidade_minima) - 1 <= %s""",
        (alerta["id"], organizacao, ordem))
    return {"id": alerta["id"], "severidade": severidade, "titulo": titulo, "motivos": motivos}


def rodada(con):
    """Processa um lote. Devolve quantos itens tratou."""
    with con.transaction():
        itens = con.execute("SELECT * FROM fila_transacoes WHERE disponivel_em <= now() ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED", (LOTE,)).fetchall()
        if not itens:
            return 0
        ids = [i["carteiras"] for i in itens]
        carteiras = {c["id"]: c for c in con.execute("SELECT * FROM carteiras WHERE id = ANY(%s)", (list({c for l in ids for c in l}),))}
        feitos = []
        for item in itens:
            try:
                with con.transaction():
                    for carteira_id in item["carteiras"]:
                        # Carteira removida enquanto a transação esperava na fila.
                        if carteira_id in carteiras:
                            registrar(con, carteiras[carteira_id], item["dados"], item["historico"])
                feitos.append(item["id"])
            except Exception as erro:
                # Um item ruim não trava a fila: tenta de novo mais tarde, cada vez mais espaçado.
                print(f"Falha em {item['transacao']} (tentativa {item['tentativas'] + 1}): {erro}", flush=True)
                if item["tentativas"] + 1 >= TENTATIVAS:
                    print(f"Desistindo de {item['transacao']}: {erro}", flush=True)
                    feitos.append(item["id"])
                else:
                    con.execute("UPDATE fila_transacoes SET tentativas = tentativas + 1, disponivel_em = now() + make_interval(secs => %s) WHERE id = %s",
                                (2 ** item["tentativas"] * 5, item["id"]))
        con.execute("DELETE FROM fila_transacoes WHERE id = ANY(%s)", (feitos,))
    return len(itens)


def main():
    con = conectar()
    tratados, ultima_batida = 0, 0.0
    while True:
        feitos = rodada(con)
        tratados += feitos
        if time.monotonic() - ultima_batida > 30:
            fila = con.execute("SELECT count(*) AS n FROM fila_transacoes").fetchone()["n"]
            batida(con, "avaliador", tratados=tratados, fila=fila)
            ultima_batida = time.monotonic()
        if not feitos:
            time.sleep(0.5)


if __name__ == "__main__":
    main()
