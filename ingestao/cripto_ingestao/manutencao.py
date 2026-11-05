"""Atualiza as listas uma vez por dia e limpa o que venceu.

    python -m cripto_ingestao.manutencao
"""

import time

from . import listas
from .banco import batida, conectar

INTERVALO = 3600


def rodada(con):
    erros = []
    # Uma cópia por vez, mesmo que rodem várias.
    if not con.execute("SELECT pg_try_advisory_xact_lock(hashtext('cripto:manutencao')) AS ok").fetchone()["ok"]:
        con.commit()
        return erros
    vencidas = con.execute(
        "SELECT %s::text[] AS todas, array_agg(lista) FILTER (WHERE atualizada_em > now() - interval '1 day') AS frescas FROM listas_atualizacao",
        (list(listas.FONTES),)).fetchone()
    for lista in set(vencidas["todas"]) - set(vencidas["frescas"] or []):
        try:
            listas.atualizar(con, lista)
        except Exception as erro:
            erros.append(f"Lista {lista}: {erro}")
    con.execute("DELETE FROM sessoes WHERE expira_em < now()")
    con.execute("DELETE FROM servicos WHERE visto_em < now() - interval '7 days'")
    con.commit()
    return erros


def main():
    con = conectar()
    while True:
        erros = rodada(con)
        for erro in erros:
            print(erro, flush=True)
        batida(con, "manutencao", erros=erros)
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
