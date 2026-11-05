"""Com um Bitcoin Core de verdade, em regtest: pagamento, gasto, confirmação, reorganização e ponto de partida.

A carteira acompanhada é a do vetor de teste do BIP84. As chaves privadas dela são públicas e só entram
numa carteira do próprio nó de teste, para conseguir gastar.
"""

import os

import pytest
from embit import bip32, bip39
from embit.networks import NETWORKS

from cripto_ingestao import avaliador, carteiras, tarefas
from cripto_ingestao.bitcoin import Rpc
from cripto_ingestao.ingestor import alcancar, ler_mempool, resolvedor

from conftest import criar_carteira

FRASE = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"


@pytest.fixture(scope="module")
def no():
    os.environ.setdefault("CRIPTO_RPC_REGTEST", "http://127.0.0.1:18443")
    rpc = Rpc("regtest")
    try:
        if rpc("getblockchaininfo")["chain"] != "regtest":
            pytest.skip("o nó não está em regtest")
    except Exception:
        pytest.skip("sem nó regtest")
    return rpc


def _carteira_do_no(rpc, nome):
    if nome not in rpc("listwallets"):
        try:
            rpc("loadwallet", nome)
        except RuntimeError:
            rpc("createwallet", nome)
    return _NaCarteira(rpc, nome)


class _NaCarteira:
    def __init__(self, rpc, nome):
        self.rpc, self.url = rpc, f"{rpc.url}/wallet/{nome}"

    def __call__(self, metodo, *parametros):
        corpo = self.rpc.cliente.post(self.url, json={"jsonrpc": "1.0", "id": metodo, "method": metodo, "params": list(parametros)}).json()
        if corpo.get("error"):
            raise RuntimeError(f"{metodo}: {corpo['error'].get('message')}")
        return corpo["result"]


@pytest.fixture(scope="module")
def pagador(no):
    p = _carteira_do_no(no, "pagador")
    p("generatetoaddress", 101, p("getnewaddress"))
    return p


def _vetor_no_no(no):
    """A carteira do vetor, com chave privada, dentro do nó de teste."""
    v = _carteira_do_no(no, "vetor")
    raiz = bip32.HDKey.from_seed(bip39.mnemonic_to_seed(FRASE), version=NETWORKS["regtest"]["xprv"])
    privado = raiz.derive("m/84h/1h/0h").to_string(version=NETWORKS["regtest"]["xprv"])
    descritores = [no("getdescriptorinfo", f"wpkh([{raiz.my_fingerprint.hex()}/84h/1h/0h]{privado}/{r}/*)")["checksum"] for r in (0, 1)]
    v("importdescriptors", [{"desc": f"wpkh([{raiz.my_fingerprint.hex()}/84h/1h/0h]{privado}/{r}/*)#{c}", "timestamp": 0, "active": True, "internal": r == 1, "range": [0, 50]}
                            for r, c in zip((0, 1), descritores)])
    return v


def _processar(con, no):
    resolver = resolvedor(no, "regtest")
    alcancar(con, "regtest", no, resolver)
    ler_mempool(con, "regtest", no, resolver)
    con.commit()
    while avaliador.rodada(con):
        pass


def test_do_pagamento_a_reorganizacao(con, organizacao, no, pagador):
    con.execute("DELETE FROM fila_transacoes")
    con.execute("DELETE FROM blocos WHERE rede = 'regtest'")
    con.commit()
    alcancar(con, "regtest", no)
    con.commit()
    carteira = criar_carteira(con, organizacao, rede="regtest")
    receber = carteiras.derivar(carteira["descritor"], "regtest", 0, 0)
    origem = pagador("getnewaddress")

    txid = pagador("sendtoaddress", receber, 1.5)
    _processar(con, no)
    m = con.execute("SELECT tipo, valor_sats, estado, contrapartes FROM movimentos WHERE carteira_id = %s AND transacao = %s", (carteira["id"], txid)).fetchone()
    assert (m["tipo"], m["valor_sats"], m["estado"]) == ("entrada", 150_000_000, "mempool")
    assert m["contrapartes"], "a origem do pagamento deveria vir do nó"

    blocos = pagador("generatetoaddress", 1, origem)
    _processar(con, no)
    assert con.execute("SELECT estado FROM movimentos WHERE carteira_id = %s AND transacao = %s", (carteira["id"], txid)).fetchone()["estado"] == "confirmada"

    # Reorganização: o bloco some e a transação volta a ser pendente.
    no("invalidateblock", blocos[0])
    _processar(con, no)
    assert con.execute("SELECT estado FROM movimentos WHERE carteira_id = %s AND transacao = %s", (carteira["id"], txid)).fetchone()["estado"] == "mempool"
    no("reconsiderblock", blocos[0])
    _processar(con, no)
    assert con.execute("SELECT estado FROM movimentos WHERE carteira_id = %s AND transacao = %s", (carteira["id"], txid)).fetchone()["estado"] == "confirmada"

    # Gasto: a chave está no nó de teste; o Panthera só vê o fluxo.
    vetor = _vetor_no_no(no)
    destino = pagador("getnewaddress")
    gasto = vetor("sendtoaddress", destino, 0.4)
    _processar(con, no)
    m = con.execute("SELECT tipo, valor_sats, taxa_sats FROM movimentos WHERE carteira_id = %s AND transacao = %s", (carteira["id"], gasto)).fetchone()
    assert (m["tipo"], m["valor_sats"]) == ("saida", 40_000_000) and m["taxa_sats"] > 0
    alerta = con.execute("SELECT severidade, motivos FROM alertas a JOIN movimentos m ON m.organizacao_id = a.organizacao_id AND m.id = a.movimento_id "
                         "WHERE m.transacao = %s AND a.carteira_id = %s", (gasto, carteira["id"])).fetchone()
    assert alerta["severidade"] == "alta" and "Destino fora dos endereços conferidos" in alerta["motivos"]
    pagador("generatetoaddress", 1, origem)
    _processar(con, no)


def test_ponto_de_partida_pelo_no_em_lote(con, organizacao, no, pagador):
    """Duas carteiras novas numa leitura só do conjunto de saídas."""
    con.execute("DELETE FROM fila_tarefas")
    a = criar_carteira(con, organizacao, rede="regtest", nome="Partida A")
    soltos = pagador("getnewaddress")
    con.execute("INSERT INTO carteiras (organizacao_id, nome, rede) VALUES (%s, 'Partida B', 'regtest') RETURNING id", (organizacao,))
    b = con.execute("SELECT * FROM carteiras WHERE organizacao_id = %s AND nome = 'Partida B'", (organizacao,)).fetchone()
    con.execute("INSERT INTO enderecos (endereco, carteira_id, organizacao_id, rede) VALUES (%s, %s, %s, 'regtest')", (soltos, b["id"], organizacao))
    distante = carteiras.derivar(a["descritor"], "regtest", 0, 35)
    pagador("sendtoaddress", distante, 0.25)
    pagador("sendtoaddress", soltos, 0.1)
    pagador("generatetoaddress", 1, pagador("getnewaddress"))
    con.execute("UPDATE carteiras SET estado = 'historico' WHERE id = ANY(%s)", ([a["id"], b["id"]],))
    con.execute("INSERT INTO fila_tarefas (tipo, carteira_id) VALUES ('historico', %s), ('historico', %s)", (a["id"], b["id"]))
    con.commit()
    assert tarefas.rodada(con, {"regtest": no}) == 2
    saldo = lambda c: con.execute("SELECT COALESCE(sum(valor_sats), 0) AS s FROM saidas WHERE carteira_id = %s AND gasta_por IS NULL", (c["id"],)).fetchone()["s"]  # noqa: E731
    assert saldo(a) >= 25_000_000 and saldo(b) == 10_000_000
    # O endereço 35 estava além da folga: virou usado e abriu folga depois dele.
    assert con.execute("SELECT max(indice) AS m FROM enderecos WHERE carteira_id = %s AND ramo = 0", (a["id"],)).fetchone()["m"] == 35 + carteiras.FOLGA
    assert {c["estado"] for c in con.execute("SELECT estado FROM carteiras WHERE id = ANY(%s)", ([a["id"], b["id"]],))} == {"acompanhando"}
