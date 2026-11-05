"""Do ingestor ao aviso, com transações montadas à mão."""

import json

import httpx

from cripto_ingestao import avaliador, avisador, carteiras
from cripto_ingestao.ingestor import casar

from conftest import FORA, RECEBER_0, TROCO_0, criar_carteira


def _tx(txid, entradas, saidas):
    return {"txid": txid, "entradas": entradas, "saidas": [{"endereco": e, "valor_sats": v} for e, v in saidas]}


def _limpar_filas(con):
    con.execute("DELETE FROM fila_transacoes")
    con.execute("DELETE FROM fila_envios")
    con.commit()


def test_entrada_e_depois_gasto_reconhecido_sem_perguntar_a_ninguem(con, organizacao):
    _limpar_filas(con)
    carteira = criar_carteira(con, organizacao)
    pagamento = _tx("a1" * 32, [("f0" * 32, 0)], [(RECEBER_0, 90_000), (FORA, 5_000)])
    outra = _tx("a2" * 32, [("f1" * 32, 0)], [(FORA, 1_000)])
    assert casar(con, "testnet4", [pagamento, outra], "mempool") == 1
    con.commit()
    avaliador.rodada(con)
    gasto = _tx("a3" * 32, [("a1" * 32, 0)], [(FORA, 50_000), (TROCO_0, 39_800)])
    assert casar(con, "testnet4", [gasto], "mempool") == 1
    con.commit()
    avaliador.rodada(con)
    movimentos = con.execute("SELECT tipo, valor_sats, taxa_sats FROM movimentos WHERE carteira_id = %s ORDER BY id", (carteira["id"],)).fetchall()
    assert [(m["tipo"], m["valor_sats"]) for m in movimentos] == [("entrada", 90_000), ("saida", 50_000)]
    assert movimentos[1]["taxa_sats"] == 200
    alertas = con.execute("SELECT severidade, titulo FROM alertas WHERE carteira_id = %s ORDER BY id", (carteira["id"],)).fetchall()
    assert [a["severidade"] for a in alertas] == ["baixa", "alta"]
    assert con.execute("SELECT gasta_por FROM saidas WHERE carteira_id = %s AND transacao = %s", (carteira["id"], "a1" * 32)).fetchone()["gasta_por"] == "a3" * 32


def test_gasto_dentro_do_mesmo_bloco(con, organizacao):
    _limpar_filas(con)
    carteira = criar_carteira(con, organizacao)
    pagamento = _tx("b1" * 32, [("f0" * 32, 0)], [(RECEBER_0, 90_000)])
    gasto = _tx("b2" * 32, [("b1" * 32, 0)], [(FORA, 89_000)])
    assert casar(con, "testnet4", [pagamento, gasto], "confirmada", bloco=10, hora=1_700_000_000) == 2
    con.commit()
    avaliador.rodada(con)
    tipos = [m["tipo"] for m in con.execute("SELECT tipo FROM movimentos WHERE carteira_id = %s ORDER BY id", (carteira["id"],))]
    assert tipos == ["entrada", "saida"]


def test_mempool_depois_bloco_so_confirma_e_nao_alerta_de_novo(con, organizacao):
    _limpar_filas(con)
    carteira = criar_carteira(con, organizacao)
    pagamento = _tx("c1" * 32, [("f0" * 32, 0)], [(RECEBER_0, 90_000)])
    casar(con, "testnet4", [pagamento], "mempool")
    con.commit()
    avaliador.rodada(con)
    casar(con, "testnet4", [pagamento], "confirmada", bloco=11, hora=1_700_000_000)
    # O ZMQ manda a transação de novo ao entrar no bloco, e pode chegar depois da confirmação.
    casar(con, "testnet4", [pagamento], "mempool")
    con.commit()
    avaliador.rodada(con)
    m = con.execute("SELECT estado, bloco FROM movimentos WHERE carteira_id = %s", (carteira["id"],)).fetchall()
    assert m == [{"estado": "confirmada", "bloco": 11}]
    assert con.execute("SELECT count(*) AS n FROM alertas WHERE carteira_id = %s", (carteira["id"],)).fetchone()["n"] == 1


def test_mesmo_endereco_em_duas_organizacoes(con, organizacao):
    _limpar_filas(con)
    outra = con.execute("INSERT INTO organizacoes (nome) VALUES (%s) RETURNING id", (f"{organizacao}-b",)).fetchone()["id"]
    a = criar_carteira(con, organizacao)
    b = criar_carteira(con, outra)
    casar(con, "testnet4", [_tx("d1" * 32, [("f0" * 32, 0)], [(RECEBER_0, 1_000)])], "mempool")
    con.commit()
    avaliador.rodada(con)
    for c in (a, b):
        assert con.execute("SELECT count(*) AS n FROM alertas WHERE carteira_id = %s", (c["id"],)).fetchone()["n"] == 1


def test_endereco_usado_abre_folga(con, organizacao):
    _limpar_filas(con)
    carteira = criar_carteira(con, organizacao)
    longe = carteiras.derivar(carteira["descritor"], "testnet4", 0, 19)
    casar(con, "testnet4", [_tx("e1" * 32, [("f0" * 32, 0)], [(longe, 1_000)])], "mempool")
    con.commit()
    avaliador.rodada(con)
    assert con.execute("SELECT tipo FROM fila_tarefas WHERE carteira_id = %s", (carteira["id"],)).fetchone()["tipo"] == "folga"


def test_alerta_vai_para_o_canal_sem_o_descritor(con, organizacao, monkeypatch):
    _limpar_filas(con)
    monkeypatch.setenv("CRIPTO_AVISOS_REDE_INTERNA", "1")
    recebidos = []

    def responder(pedido):
        recebidos.append(json.loads(pedido.content))
        return httpx.Response(200)

    carteira = criar_carteira(con, organizacao)
    con.execute("INSERT INTO canais (organizacao_id, nome, tipo, url, severidade_minima) VALUES (%s, 'w', 'webhook', 'https://exemplo.test/w', 'alta')", (organizacao,))
    con.execute("INSERT INTO listas (endereco, lista) VALUES (%s, 'OFAC') ON CONFLICT DO NOTHING", (FORA,))
    casar(con, "testnet4", [_tx("f2" * 32, [("f0" * 32, 0)], [(RECEBER_0, 8_000)])], "mempool")
    casar(con, "testnet4", [_tx("f3" * 32, [("f0" * 32, 1)], [(RECEBER_0, 9_000)])], "mempool",
          resolver=lambda txid: {"saidas": [{"endereco": FORA, "valor_sats": 1}, {"endereco": FORA, "valor_sats": 10_000}]})
    con.commit()
    avaliador.rodada(con)
    avisador.rodada(con, httpx.Client(transport=httpx.MockTransport(responder)))
    assert [r["severidade"] for r in recebidos] == ["critica"]
    assert carteira["descritor"] not in json.dumps(recebidos)
    con.execute("DELETE FROM listas WHERE endereco = %s", (FORA,))
    con.commit()


def test_canal_interno_e_recusado(monkeypatch):
    from cripto_ingestao import avisos

    monkeypatch.delenv("CRIPTO_AVISOS_REDE_INTERNA", raising=False)
    for url in ("http://127.0.0.1:8700/api", "http://localhost/", "http://10.0.0.5/", "http://[::1]/"):
        try:
            avisos.conferir_destino(url)
        except avisos.Proibido:
            continue
        raise AssertionError(url)
