"""Transforma uma transação no que ela significa para uma carteira.

A transação chega já normalizada, venha do nó ou do histórico:
    {"txid", "estado", "bloco", "hora", "taxa_sats",
     "entradas": [{"endereco", "valor_sats"}], "saidas": [{"endereco", "valor_sats"}]}
Entrada que não pôde ser resolvida vem com endereco None.
"""


def enderecos_de(transacao):
    return {p["endereco"] for p in transacao["entradas"] + transacao["saidas"] if p.get("endereco")}


def classificar(transacao, da_carteira):
    entra = sum(s["valor_sats"] for s in transacao["saidas"] if s["endereco"] in da_carteira)
    sai = sum(e["valor_sats"] for e in transacao["entradas"] if e.get("endereco") in da_carteira)
    origens = sorted({e["endereco"] for e in transacao["entradas"] if e.get("endereco") and e["endereco"] not in da_carteira})
    destinos = {}
    for s in transacao["saidas"]:
        if s["endereco"] and s["endereco"] not in da_carteira:
            destinos[s["endereco"]] = destinos.get(s["endereco"], 0) + s["valor_sats"]
    base = {"transacao": transacao["txid"], "taxa_sats": transacao.get("taxa_sats"), "estado": transacao["estado"],
            "bloco": transacao.get("bloco"), "confirmada_em": transacao.get("hora")}
    if sai == 0:
        return {**base, "tipo": "entrada", "valor_sats": entra, "contrapartes": [{"endereco": o} for o in origens]}
    if not destinos:
        # Só troco e taxa: a carteira moveu para ela mesma.
        return {**base, "tipo": "interno", "valor_sats": sai - entra, "contrapartes": []}
    return {**base, "tipo": "saida", "valor_sats": sum(destinos.values()),
            "contrapartes": [{"endereco": e, "valor_sats": v} for e, v in sorted(destinos.items(), key=lambda i: -i[1])]}
