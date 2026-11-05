"""Manda o alerta para quem precisa saber. A mensagem leva o evento, nunca o descritor nem o saldo."""

import ipaddress
import os
import socket
from urllib.parse import urlsplit

import httpx

PRIORIDADE_NTFY = {"critica": "5", "alta": "4", "media": "3", "baixa": "2"}
NOMES = {"critica": "Crítica", "alta": "Alta", "media": "Média", "baixa": "Baixa"}


class Proibido(ValueError):
    pass


def btc(sats):
    return f"{sats / 100_000_000:.8f}".replace(".", ",") + " BTC"


def conferir_destino(url):
    """Quem cadastra o canal é a organização: o endereço não pode apontar para dentro da instalação."""
    if os.getenv("CRIPTO_AVISOS_REDE_INTERNA") == "1":
        return
    partes = urlsplit(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise Proibido("Endereço do canal inválido.")
    try:
        enderecos = {i[4][0] for i in socket.getaddrinfo(partes.hostname, partes.port or 443)}
    except socket.gaierror:
        raise Proibido("Não foi possível encontrar o endereço do canal.") from None
    for e in enderecos:
        ip = ipaddress.ip_address(e.split("%")[0])
        if not ip.is_global:
            raise Proibido("O canal aponta para um endereço interno.")


def mensagem(alerta, carteira, movimento):
    linhas = [f"{carteira['nome']}: {btc(movimento['valor_sats'])}" if movimento else carteira["nome"]]
    linhas += alerta["motivos"]
    if movimento:
        linhas.append(f"Transação {movimento['transacao']}")
    return "\n".join(linhas)


def enviar(canal, alerta, carteira, movimento, cliente=None):
    conferir_destino(canal["url"])
    # Sem seguir redirecionamento: seria um jeito de sair da conferência acima.
    cliente = cliente or httpx.Client(timeout=10, follow_redirects=False)
    if canal["tipo"] == "ntfy":
        r = cliente.post(canal["url"], content=mensagem(alerta, carteira, movimento).encode(),
                         headers={"Title": f"{NOMES[alerta['severidade']]}: {alerta['titulo']}".encode(),
                                  "Priority": PRIORIDADE_NTFY[alerta["severidade"]], "Tags": "panthera-crypto"})
    else:
        r = cliente.post(canal["url"], json={
            "origem": "panthera-crypto",
            "alerta": alerta["id"],
            "severidade": alerta["severidade"],
            "titulo": alerta["titulo"],
            "motivos": alerta["motivos"],
            "carteira": carteira["nome"],
            "rede": carteira["rede"],
            "movimento": None if not movimento else {
                "tipo": movimento["tipo"], "transacao": movimento["transacao"], "estado": movimento["estado"],
                "valor_sats": movimento["valor_sats"], "contrapartes": movimento["contrapartes"],
            },
            "criado_em": alerta["criado_em"].isoformat() if hasattr(alerta["criado_em"], "isoformat") else alerta["criado_em"],
        })
    r.raise_for_status()
