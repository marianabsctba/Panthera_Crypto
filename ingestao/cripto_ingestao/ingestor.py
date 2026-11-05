"""Lê o fluxo do nó e põe na fila só as transações que tocam endereços acompanhados.

    python -m cripto_ingestao.ingestor --rede bitcoin

O custo segue o volume da rede, não o número de endereços: cada transação é lida uma vez e
casada com todos os endereços de todas as organizações numa consulta só por lote.
Uma cópia por rede fica ativa; as outras esperam na trava e assumem se ela cair.
"""

import argparse
import os
import time
from collections import defaultdict
from functools import lru_cache

from .banco import Jsonb, batida, conectar
from .bitcoin import Rpc, ler_bloco, ler_transacao

LOTE_MAXIMO = 500
ESPERA_DO_LOTE = 0.5
BLOCOS_GUARDADOS = 1000


def casar(con, rede, transacoes, estado, bloco=None, hora=None, resolver=None):
    """Acha, num lote, as transações que tocam endereços acompanhados e põe na fila. Devolve quantas."""
    enderecos = {s["endereco"] for t in transacoes for s in t["saidas"] if s["endereco"]}
    gastos = {e for t in transacoes for e in t["entradas"] if e}
    acompanhados = defaultdict(set)
    if enderecos:
        for l in con.execute("SELECT endereco, carteira_id, organizacao_id FROM enderecos WHERE rede = %s AND endereco = ANY(%s)", (rede, list(enderecos))):
            acompanhados[l["endereco"]].add((l["carteira_id"], l["organizacao_id"]))
    conhecidas = defaultdict(list)
    if gastos:
        txids, posicoes = zip(*gastos)
        for l in con.execute(
                "SELECT transacao, posicao, carteira_id, organizacao_id, endereco, valor_sats FROM saidas "
                "WHERE rede = %s AND (transacao, posicao) IN (SELECT * FROM unnest(%s::text[], %s::int[]))", (rede, list(txids), list(posicoes))):
            conhecidas[(l["transacao"], l["posicao"])].append(l)

    novas, gastas, fila = [], [], []
    for t in transacoes:
        carteiras = {}
        entradas = []
        for e in t["entradas"]:
            donos = conhecidas.get(e) if e else None
            if donos:
                entradas.append({"endereco": donos[0]["endereco"], "valor_sats": donos[0]["valor_sats"]})
                for d in donos:
                    carteiras[d["carteira_id"]] = d["organizacao_id"]
                    gastas.append((t["txid"], rede, e[0], e[1], d["carteira_id"]))
            else:
                entradas.append({"endereco": None, "valor_sats": None, "ref": e})
        for posicao, s in enumerate(t["saidas"]):
            for carteira, organizacao in acompanhados.get(s["endereco"], ()):
                carteiras[carteira] = organizacao
                novas.append((rede, t["txid"], posicao, carteira, organizacao, s["endereco"], s["valor_sats"]))
                # Uma transação do mesmo lote pode gastar esta saída.
                conhecidas[(t["txid"], posicao)].append({"carteira_id": carteira, "organizacao_id": organizacao, "endereco": s["endereco"], "valor_sats": s["valor_sats"]})
        if not carteiras:
            continue
        if resolver:
            # A origem de um pagamento importa (lista de sanções, envenenamento de endereço): só aqui vale perguntar ao nó.
            for entrada in entradas[:20]:
                if entrada.get("ref"):
                    anterior = resolver(entrada["ref"][0])
                    if anterior and entrada["ref"][1] < len(anterior["saidas"]):
                        entrada.update(anterior["saidas"][entrada["ref"][1]])
        for entrada in entradas:
            entrada.pop("ref", None)
        taxa = None
        if all(e["valor_sats"] is not None for e in entradas) and entradas and t["entradas"][0] is not None:
            taxa = sum(e["valor_sats"] for e in entradas) - sum(s["valor_sats"] for s in t["saidas"])
        dados = {"txid": t["txid"], "estado": estado, "bloco": bloco, "hora": hora, "taxa_sats": taxa, "entradas": entradas, "saidas": t["saidas"]}
        fila.append((rede, t["txid"], list(carteiras), Jsonb(dados)))

    with con.cursor() as cursor:
        if novas:
            cursor.executemany("INSERT INTO saidas (rede, transacao, posicao, carteira_id, organizacao_id, endereco, valor_sats) "
                               "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", novas)
        if gastas:
            cursor.executemany("UPDATE saidas SET gasta_por = %s WHERE rede = %s AND transacao = %s AND posicao = %s AND carteira_id = %s", gastas)
        if fila:
            cursor.executemany("INSERT INTO fila_transacoes (rede, transacao, carteiras, dados) VALUES (%s, %s, %s, %s)", fila)
    return len(fila)


def desfazer(con, rede, rpc):
    """Reorganização: volta até o último bloco que o nó ainda reconhece."""
    altura_do_no = rpc("getblockcount")
    while True:
        topo = con.execute("SELECT altura, hash FROM blocos WHERE rede = %s ORDER BY altura DESC LIMIT 1", (rede,)).fetchone()
        if not topo or (topo["altura"] <= altura_do_no and rpc("getblockhash", topo["altura"]) == topo["hash"]):
            return
        con.execute("DELETE FROM blocos WHERE rede = %s AND altura = %s", (rede, topo["altura"]))
        # A transação volta a ser pendente; se for minerada de novo, confirma de novo.
        con.execute("UPDATE movimentos m SET estado = 'mempool', bloco = NULL, confirmada_em = NULL FROM carteiras c "
                    "WHERE m.carteira_id = c.id AND c.rede = %s AND m.bloco = %s", (rede, topo["altura"]))


def alcancar(con, rede, rpc, resolver=None):
    """Lê os blocos que faltam até o topo. Devolve quantos leu."""
    lidos = 0
    while True:
        topo = rpc("getblockcount")
        salvo = con.execute("SELECT altura, hash FROM blocos WHERE rede = %s ORDER BY altura DESC LIMIT 1", (rede,)).fetchone()
        # O nó pode ter trocado o último bloco que lemos sem que ainda exista um bloco novo em cima.
        if salvo and (salvo["altura"] > topo or rpc("getblockhash", salvo["altura"]) != salvo["hash"]):
            desfazer(con, rede, rpc)
            con.commit()
            continue
        # Primeira vez: começa do topo. O ponto de partida de cada carteira vem do nó, pela tarefa de partida.
        ultimo = salvo["altura"] if salvo else topo - 1
        if ultimo >= topo:
            return lidos
        altura = ultimo + 1
        hash_ = rpc("getblockhash", altura)
        anterior, hora, transacoes = ler_bloco(rpc.bloco_bruto(hash_), rede)
        salvo = con.execute("SELECT hash FROM blocos WHERE rede = %s AND altura = %s", (rede, altura - 1)).fetchone()
        if salvo and salvo["hash"] != anterior:
            desfazer(con, rede, rpc)
            con.commit()
            continue
        casar(con, rede, transacoes, "confirmada", altura, hora, resolver)
        con.execute("INSERT INTO blocos (rede, altura, hash) VALUES (%s, %s, %s) ON CONFLICT (rede, altura) DO UPDATE SET hash = excluded.hash",
                    (rede, altura, hash_))
        con.execute("DELETE FROM blocos WHERE rede = %s AND altura < %s", (rede, altura - BLOCOS_GUARDADOS))
        con.commit()
        lidos += 1


def ler_mempool(con, rede, rpc, resolver=None):
    """Na partida, o que já está na mempool. Em lotes, para não segurar memória nem o nó."""
    txids = rpc("getrawmempool")
    for i in range(0, len(txids), LOTE_MAXIMO):
        brutos = rpc.lote("getrawtransaction", [(t, False) for t in txids[i:i + LOTE_MAXIMO]])
        casar(con, rede, [ler_transacao(bytes.fromhex(b), rede) for b in brutos if b], "mempool", resolver=resolver)
        con.commit()
    return len(txids)


def resolvedor(rpc, rede):
    """Pergunta ao nó pela transação anterior, guardando as últimas: o troco costuma ser gasto logo em seguida."""
    @lru_cache(maxsize=20_000)
    def resolver(txid):
        try:
            return ler_transacao(rpc.transacao_bruta(txid), rede)
        except Exception:
            return None
    return resolver


def rodar(rede):
    import zmq

    rpc = Rpc(rede)
    resolver = resolvedor(rpc, rede)
    trava = conectar(autocommit=True)
    print(f"Esperando a vez de ler {rede}", flush=True)
    trava.execute("SELECT pg_advisory_lock(hashtext(%s))", (f"cripto:ingestor:{rede}",))
    con = conectar()
    contexto = zmq.Context()
    assinatura = contexto.socket(zmq.SUB)
    assinatura.connect(os.getenv(f"CRIPTO_ZMQ_{rede.upper()}", "tcp://127.0.0.1:28332"))
    for topico in (b"rawtx", b"hashblock"):
        assinatura.setsockopt(zmq.SUBSCRIBE, topico)
    # Assina antes de ler: o que chegar durante a leitura inicial fica esperando no socket.
    alcancar(con, rede, rpc, resolver)
    print(f"Mempool inicial: {ler_mempool(con, rede, rpc, resolver)} transações", flush=True)

    lote, inicio_do_lote, ultima_batida = [], time.monotonic(), 0.0
    contagem = {"transacoes": 0, "casadas": 0}
    while True:
        if assinatura.poll(int(ESPERA_DO_LOTE * 1000)):
            topico, corpo, _ = assinatura.recv_multipart()
            if topico == b"rawtx":
                lote.append(ler_transacao(corpo, rede))
            else:
                # O que veio antes do bloco entra primeiro, para a confirmação chegar depois da pendência.
                contagem["casadas"] += casar(con, rede, lote, "mempool", resolver=resolver)
                con.commit()
                lote = []
                alcancar(con, rede, rpc, resolver)
        if lote and (len(lote) >= LOTE_MAXIMO or time.monotonic() - inicio_do_lote >= ESPERA_DO_LOTE):
            contagem["transacoes"] += len(lote)
            contagem["casadas"] += casar(con, rede, lote, "mempool", resolver=resolver)
            con.commit()
            lote, inicio_do_lote = [], time.monotonic()
        if not lote:
            inicio_do_lote = time.monotonic()
        if time.monotonic() - ultima_batida > 30:
            altura = con.execute("SELECT max(altura) AS a FROM blocos WHERE rede = %s", (rede,)).fetchone()["a"]
            batida(con, f"ingestor-{rede}", altura=altura, **contagem)
            ultima_batida = time.monotonic()


def main():
    argumentos = argparse.ArgumentParser(description="Ingestor do Panthera Crypto")
    argumentos.add_argument("--rede", required=True, choices=["bitcoin", "testnet4", "signet", "regtest"])
    rodar(argumentos.parse_args().rede)


if __name__ == "__main__":
    main()
