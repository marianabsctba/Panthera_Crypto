"""Descritores e endereços só leitura. Nada aqui aceita chave privada."""

import re

from embit.descriptor import Descriptor
from embit.descriptor.checksum import add_checksum
from embit.networks import NETWORKS
from embit.script import address_to_scriptpubkey

REDES = {"bitcoin": NETWORKS["main"], "testnet4": NETWORKS["test"], "signet": NETWORKS["signet"], "regtest": NETWORKS["regtest"]}
# Endereços sem uso à frente do último usado, como as carteiras fazem.
FOLGA = 20
PRIVADA = re.compile(r"\b[xtyzuv]prv[1-9A-HJ-NP-Za-km-z]{100,}|\b[5KLc9][1-9A-HJ-NP-Za-km-z]{50,51}\b")


class Recusado(ValueError):
    pass


def ler_descritor(texto, rede):
    texto = texto.strip()
    # Confere antes de interpretar: uma chave privada não pode nem chegar ao parser e às mensagens de erro.
    if PRIVADA.search(texto):
        raise Recusado("Este descritor tem chave privada. Use só a parte pública.")
    sem_checksum = texto.split("#")[0]
    try:
        descritor = Descriptor.from_string(sem_checksum)
    except Exception:
        raise Recusado("Descritor inválido.") from None
    if any(k.is_private for k in descritor.keys):
        raise Recusado("Este descritor tem chave privada. Use só a parte pública.")
    if not descritor.is_wildcard:
        raise Recusado("O descritor precisa terminar em /* ou /<0;1>/* para gerar endereços.")
    chave = str(descritor.keys[0].key) if descritor.keys else ""
    if (rede == "bitcoin") != chave.startswith(("xpub", "ypub", "zpub", "Ypub", "Zpub")):
        raise Recusado("A chave do descritor é de outra rede.")
    try:
        descritor.derive(0, branch_index=0).address(REDES[rede])
    except Exception:
        raise Recusado("Não foi possível gerar endereços com este descritor.") from None
    return add_checksum(sem_checksum)


def ramos(descritor):
    return Descriptor.from_string(descritor.split("#")[0]).num_branches


def derivar(descritor, rede, ramo, indice):
    d = Descriptor.from_string(descritor.split("#")[0])
    return d.derive(indice, branch_index=ramo).address(REDES[rede])


def validar_endereco(endereco, rede):
    endereco = endereco.strip()
    try:
        address_to_scriptpubkey(endereco)
    except Exception:
        raise Recusado(f"Endereço inválido: {endereco[:64]}") from None
    principal = endereco.startswith(("1", "3", "bc1"))
    if principal != (rede == "bitcoin"):
        raise Recusado(f"Endereço de outra rede: {endereco[:64]}")
    return endereco


def completar(con, carteira):
    """Garante FOLGA endereços sem uso depois do último usado em cada ramo. Devolve os endereços novos."""
    if not carteira["descritor"]:
        return []
    novos = []
    for ramo in range(ramos(carteira["descritor"])):
        linha = con.execute(
            "SELECT MAX(indice) AS maior, MAX(indice) FILTER (WHERE usado) AS usado FROM enderecos WHERE carteira_id = %s AND ramo = %s",
            (carteira["id"], ramo)).fetchone()
        maior = -1 if linha["maior"] is None else linha["maior"]
        alvo = (-1 if linha["usado"] is None else linha["usado"]) + FOLGA
        for indice in range(maior + 1, alvo + 1):
            novos.append((derivar(carteira["descritor"], carteira["rede"], ramo, indice), carteira["id"], carteira["organizacao_id"], carteira["rede"], ramo, indice))
    if novos:
        with con.cursor() as cursor:
            cursor.executemany("INSERT INTO enderecos (endereco, carteira_id, organizacao_id, rede, ramo, indice) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", novos)
    return [n[0] for n in novos]
