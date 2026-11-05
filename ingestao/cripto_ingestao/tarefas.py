"""Trabalho pesado e raro: o ponto de partida de carteira nova e a folga de endereços.

    python -m cripto_ingestao.tarefas

O ponto de partida é o que a carteira tem agora: as saídas não gastas, lidas do próprio nó com scantxoutset.
Uma leitura do conjunto de saídas serve para muitas carteiras de uma vez, e o nó só aceita uma por vez:
por isso as tarefas da mesma rede andam em lote, uma cópia por rede de cada vez.
"""

import os
import re
import time

from embit.script import Script

from . import carteiras
from .banco import batida, conectar
from .bitcoin import Rpc

LOTE = 50
ALCANCE = int(os.getenv("CRIPTO_PARTIDA_ALCANCE", "1000"))
MULTIPLO = re.compile(r"<(\d+);(\d+)>")
CAMINHO = re.compile(r"\[[0-9a-f]{8}((?:/\d+h?)*)\]")


def objetos_de_busca(carteira, ate):
    if carteira["descritor"]:
        base = carteira["descritor"].split("#")[0]
        ramos = MULTIPLO.search(base)
        textos = [MULTIPLO.sub(r, base, count=1) for r in ramos.groups()] if ramos else [base]
        return [{"desc": t, "range": [0, ate]} for t in textos]
    return []


def _ramo_e_indice(descricao):
    """O nó devolve o caminho de cada saída achada: os dois últimos passos são ramo e índice."""
    caminho = CAMINHO.search(descricao)
    if not caminho:
        return None
    passos = [p for p in caminho.group(1).split("/") if p]
    if len(passos) < 2 or passos[-1].endswith("h") or passos[-2].endswith("h"):
        return None
    return int(passos[-2]), int(passos[-1])


def partida(con, rpc, rede, lote):
    """Lê as saídas não gastas de um lote de carteiras numa passada só."""
    alcance = {}
    objetos = []
    for c in lote:
        maior = con.execute("SELECT max(indice) AS m FROM enderecos WHERE carteira_id = %s", (c["id"],)).fetchone()["m"] or 0
        alcance[c["id"]] = max(ALCANCE, maior)
        objetos += objetos_de_busca(c, alcance[c["id"]])
    soltos = {}
    for l in con.execute("SELECT endereco, carteira_id FROM enderecos WHERE carteira_id = ANY(%s) AND ramo IS NULL", ([c["id"] for c in lote],)):
        soltos.setdefault(l["endereco"], []).append(l["carteira_id"])
    objetos += [f"addr({e})" for e in soltos]
    if not objetos:
        return {}
    resultado = rpc("scantxoutset", "start", objetos)
    if not resultado or not resultado.get("success"):
        raise RuntimeError("O nó não concluiu a leitura das saídas.")

    por_carteira = {c["id"]: [] for c in lote}
    for u in resultado["unspents"]:
        endereco = Script(bytes.fromhex(u["scriptPubKey"])).address(carteiras.REDES[rede])
        donos = [(cid, None, None) for cid in soltos.get(endereco, [])]
        posicao = _ramo_e_indice(u["desc"])
        if posicao:
            # Duas carteiras do lote podem ter o mesmo caminho: confere o endereço em cada uma.
            donos += [(c["id"], *posicao) for c in lote if c["descritor"] and posicao[0] < carteiras.ramos(c["descritor"])
                      and carteiras.derivar(c["descritor"], rede, *posicao) == endereco]
        for carteira_id, ramo, indice in donos:
            por_carteira[carteira_id].append({"endereco": endereco, "ramo": ramo, "indice": indice, "transacao": u["txid"], "posicao": u["vout"],
                                              "valor_sats": round(u["amount"] * 100_000_000)})
    return por_carteira


def gravar_partida(con, carteira, achadas):
    for a in achadas:
        if a["ramo"] is not None:
            con.execute("INSERT INTO enderecos (endereco, carteira_id, organizacao_id, rede, ramo, indice, usado) VALUES (%s, %s, %s, %s, %s, %s, true) "
                        "ON CONFLICT (endereco, carteira_id) DO UPDATE SET usado = true",
                        (a["endereco"], carteira["id"], carteira["organizacao_id"], carteira["rede"], a["ramo"], a["indice"]))
        else:
            con.execute("UPDATE enderecos SET usado = true WHERE carteira_id = %s AND endereco = %s", (carteira["id"], a["endereco"]))
        con.execute("INSERT INTO saidas (rede, transacao, posicao, carteira_id, organizacao_id, endereco, valor_sats) VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT DO NOTHING", (carteira["rede"], a["transacao"], a["posicao"], carteira["id"], carteira["organizacao_id"], a["endereco"], a["valor_sats"]))
    carteiras.completar(con, carteira)
    con.execute("UPDATE carteiras SET estado = 'acompanhando', sincronizada_em = now() WHERE id = %s", (carteira["id"],))


def rodada(con, rpcs):
    with con.transaction():
        primeira = con.execute("SELECT t.tipo, c.rede FROM fila_tarefas t JOIN carteiras c ON c.id = t.carteira_id WHERE t.disponivel_em <= now() "
                               "ORDER BY t.id LIMIT 1 FOR UPDATE OF t SKIP LOCKED").fetchone()
        if not primeira:
            return 0
        rede = primeira["rede"]
        if not con.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s)) AS ok", (f"cripto:partida:{rede}",)).fetchone()["ok"]:
            return 0
        tarefas = con.execute(
            "SELECT t.id, t.tipo, t.tentativas, row_to_json(c) AS carteira FROM fila_tarefas t JOIN carteiras c ON c.id = t.carteira_id "
            "WHERE t.disponivel_em <= now() AND c.rede = %s ORDER BY t.id LIMIT %s FOR UPDATE OF t SKIP LOCKED", (rede, LOTE)).fetchall()
        rpc = rpcs.setdefault(rede, Rpc(rede))
        # Folga só precisa derivar mais endereços: o que chegar neles vem do fluxo do nó.
        for t in [t for t in tarefas if t["tipo"] == "folga"]:
            carteiras.completar(con, t["carteira"])
        lote = [t for t in tarefas if t["tipo"] == "historico"]
        try:
            with con.transaction():
                achadas = partida(con, rpc, rede, [t["carteira"] for t in lote]) if lote else {}
                for t in lote:
                    gravar_partida(con, t["carteira"], achadas.get(t["carteira"]["id"], []))
            con.execute("DELETE FROM fila_tarefas WHERE id = ANY(%s)", ([t["id"] for t in tarefas],))
        except Exception as erro:
            con.execute("DELETE FROM fila_tarefas WHERE id = ANY(%s)", ([t["id"] for t in tarefas if t["tipo"] == "folga"],))
            con.execute("UPDATE fila_tarefas SET tentativas = tentativas + 1, erro = %s, disponivel_em = now() + make_interval(secs => least(3600, 30 * 2 ^ tentativas)) "
                        "WHERE id = ANY(%s)", (str(erro)[:300], [t["id"] for t in lote]))
    return len(tarefas)


def main():
    con = conectar()
    rpcs, feitas, ultima_batida = {}, 0, 0.0
    while True:
        andou = rodada(con, rpcs)
        feitas += andou
        if time.monotonic() - ultima_batida > 30:
            fila = con.execute("SELECT count(*) AS n FROM fila_tarefas").fetchone()["n"]
            batida(con, "tarefas", feitas=feitas, fila=fila)
            ultima_batida = time.monotonic()
        if not andou:
            time.sleep(2)


if __name__ == "__main__":
    main()
