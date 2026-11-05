"""Decide se um movimento vira alerta e com que gravidade."""

ORDEM = ["baixa", "media", "alta", "critica"]
# Abaixo disso, uma entrada vinda de endereço parecido com um da agenda é isca, não pagamento.
POEIRA_SATS = 1000


def mais_grave(a, b):
    return a if ORDEM.index(a) >= ORDEM.index(b) else b


def _corpo(endereco):
    """Parte do endereço que muda de um para outro, sem o prefixo da rede."""
    endereco = endereco.lower()
    for prefixo in ("bc1p", "bc1q", "tb1p", "tb1q"):
        if endereco.startswith(prefixo):
            return endereco[len(prefixo):]
    return endereco[1:]


def parecido(a, b):
    """Quem envenena endereço copia o começo e o fim, que é o que as pessoas conferem."""
    if a == b:
        return False
    ca, cb = _corpo(a), _corpo(b)
    return len(ca) > 10 and ca[:4] == cb[:4] and ca[-4:] == cb[-4:]


def avaliar(movimento, carteira, agenda, em_lista):
    """Devolve (severidade, título, motivos) ou None.

    `agenda` é o conjunto de endereços conferidos e `em_lista` uma função que diz em que lista um endereço está.
    """
    contrapartes = [c["endereco"] for c in movimento["contrapartes"]]
    motivos = []
    severidade = None

    def somar(nivel, texto):
        nonlocal severidade
        severidade = nivel if severidade is None else mais_grave(severidade, nivel)
        motivos.append(texto)

    for endereco in contrapartes:
        lista = em_lista(endereco)
        if lista:
            somar("critica", f"{endereco} está na lista {lista}")

    if movimento["tipo"] == "saida":
        fora = [e for e in contrapartes if e not in agenda]
        if fora:
            somar("alta", "Destino fora dos endereços conferidos" if len(fora) == 1 else f"{len(fora)} destinos fora dos endereços conferidos")
        else:
            somar("media", "Destino entre os endereços conferidos")
        limite = carteira["limite_sats"]
        if limite and movimento["valor_sats"] > limite:
            somar("alta", "Valor acima do limite da carteira")
        titulo = "Saída da carteira"
    elif movimento["tipo"] == "entrada":
        iscas = [e for e in contrapartes if any(parecido(e, a) for a in agenda)]
        if iscas and movimento["valor_sats"] <= POEIRA_SATS:
            somar("media", "Valor mínimo vindo de endereço parecido com um conferido: possível envenenamento de endereço")
            titulo = "Possível envenenamento de endereço"
        else:
            somar("baixa", "Entrada na carteira")
            titulo = "Entrada na carteira"
    else:
        return None

    if severidade == "critica":
        titulo = "Movimento com endereço em lista"
    return severidade, titulo, motivos
