"""Listas de endereços que não se deve tocar. Valem para todas as organizações."""

import httpx

FONTES = {
    "OFAC": "https://raw.githubusercontent.com/0xB10C/ofac-sanctioned-digital-currency-addresses/lists/sanctioned_addresses_XBT.txt",
}


def atualizar(con, lista="OFAC", cliente=None):
    cliente = cliente or httpx.Client(timeout=30, follow_redirects=True)
    r = cliente.get(FONTES[lista])
    r.raise_for_status()
    enderecos = sorted({l.strip() for l in r.text.splitlines() if l.strip() and not l.startswith("#")})
    if not enderecos:
        # Lista vazia é falha da fonte, não ausência de sanções: mantém a anterior.
        raise ValueError("A fonte devolveu uma lista vazia.")
    with con.transaction():
        con.execute("DELETE FROM listas WHERE lista = %s", (lista,))
        with con.cursor() as cursor:
            cursor.executemany("INSERT INTO listas (endereco, lista) VALUES (%s, %s)", [(e, lista) for e in enderecos])
        con.execute("INSERT INTO listas_atualizacao (lista, total, atualizada_em) VALUES (%s, %s, now()) "
                    "ON CONFLICT (lista) DO UPDATE SET total = excluded.total, atualizada_em = excluded.atualizada_em", (lista, len(enderecos)))
    return len(enderecos)


def em_listas(con, enderecos):
    """Um pedido só para todos os endereços de uma transação."""
    if not enderecos:
        return {}
    linhas = con.execute("SELECT endereco, string_agg(lista, ', ' ORDER BY lista) AS listas FROM listas WHERE endereco = ANY(%s) GROUP BY endereco",
                         (list(enderecos),)).fetchall()
    return {l["endereco"]: l["listas"] for l in linhas}
