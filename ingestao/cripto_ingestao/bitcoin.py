"""Conversa com o Bitcoin Core: RPC para blocos e transações, leitura do formato bruto."""

import io
import os

import httpx
from embit.transaction import Transaction

from .carteiras import REDES

ZERO = bytes(32)


class Rpc:
    def __init__(self, rede, cliente=None):
        self.url = os.getenv(f"CRIPTO_RPC_{rede.upper()}", "http://127.0.0.1:18443")
        usuario, senha = os.getenv("CRIPTO_RPC_USUARIO", "cripto"), os.environ.get("CRIPTO_RPC_SENHA", "")
        self.cliente = cliente or httpx.Client(timeout=60, auth=(usuario, senha))

    def __call__(self, metodo, *parametros):
        r = self.cliente.post(self.url, json={"jsonrpc": "1.0", "id": metodo, "method": metodo, "params": list(parametros)})
        corpo = r.json()
        if corpo.get("error"):
            raise RuntimeError(f"{metodo}: {corpo['error'].get('message')}")
        return corpo["result"]

    def lote(self, metodo, listas_de_parametros):
        """Várias chamadas num pedido só: a mempool inteira não pode virar cem mil idas e voltas."""
        if not listas_de_parametros:
            return []
        r = self.cliente.post(self.url, json=[{"jsonrpc": "1.0", "id": i, "method": metodo, "params": list(p)} for i, p in enumerate(listas_de_parametros)])
        respostas = sorted(r.json(), key=lambda c: c["id"])
        return [None if c.get("error") else c["result"] for c in respostas]

    def bloco_bruto(self, hash_):
        return bytes.fromhex(self("getblock", hash_, 0))

    def transacao_bruta(self, txid):
        return bytes.fromhex(self("getrawtransaction", txid, False))


def _endereco(saida, rede):
    try:
        return saida.script_pubkey.address(REDES[rede])
    except Exception:
        # OP_RETURN, chave pública nua e scripts sem endereço: ninguém acompanha esses.
        return None


def ler_transacao(bruto, rede):
    t = bruto if isinstance(bruto, Transaction) else Transaction.parse(bruto)
    return {
        "txid": t.txid().hex(),
        "entradas": [None if e.txid == ZERO else (e.txid.hex(), e.vout) for e in t.vin],
        "saidas": [{"endereco": _endereco(s, rede), "valor_sats": s.value} for s in t.vout],
    }


def _tamanho(fluxo):
    primeiro = fluxo.read(1)[0]
    if primeiro < 0xFD:
        return primeiro
    return int.from_bytes(fluxo.read({0xFD: 2, 0xFE: 4, 0xFF: 8}[primeiro]), "little")


def ler_bloco(bruto, rede):
    """Devolve o hash do bloco anterior e as transações, na ordem do bloco."""
    fluxo = io.BytesIO(bruto)
    cabecalho = fluxo.read(80)
    anterior = cabecalho[4:36][::-1].hex()
    hora = int.from_bytes(cabecalho[68:72], "little")
    return anterior, hora, [ler_transacao(Transaction.read_from(fluxo), rede) for _ in range(_tamanho(fluxo))]
