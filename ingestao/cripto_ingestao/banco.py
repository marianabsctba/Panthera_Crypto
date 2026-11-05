"""Conexão com o Postgres e migrações.

    python -m cripto_ingestao.banco migrar
"""

import os
import socket
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

MIGRACOES = Path(__file__).resolve().parents[2] / "banco" / "migracoes"
__all__ = ["Jsonb", "conectar", "migrar", "pool", "url", "batida"]


def url(papel):
    """Cada serviço entra com o próprio papel e só tem as permissões dele."""
    senha = os.environ[f"CRIPTO_SENHA_{papel.upper()}"]
    return f"postgresql://cripto_{papel}:{senha}@{os.getenv('CRIPTO_BANCO', '127.0.0.1:5444')}/{os.getenv('CRIPTO_BANCO_NOME', 'cripto')}"


def conectar(papel="servicos", **opcoes):
    return psycopg.connect(url(papel), row_factory=dict_row, **opcoes)


def pool(papel, minimo=1, maximo=10):
    return ConnectionPool(url(papel), min_size=minimo, max_size=maximo, open=True, kwargs={"row_factory": dict_row})


def migrar(con):
    con.execute("CREATE TABLE IF NOT EXISTS migracoes (nome text PRIMARY KEY, feita_em timestamptz NOT NULL DEFAULT now())")
    # Duas instalações ao mesmo tempo não podem aplicar a mesma migração duas vezes.
    con.execute("SELECT pg_advisory_xact_lock(hashtext('cripto:migrar'))")
    feitas = {l["nome"] for l in con.execute("SELECT nome FROM migracoes")}
    aplicadas = []
    for arquivo in sorted(MIGRACOES.glob("*.sql")):
        if arquivo.name in feitas:
            continue
        con.execute(arquivo.read_text(encoding="utf-8"))
        con.execute("INSERT INTO migracoes (nome) VALUES (%s)", (arquivo.name,))
        aplicadas.append(arquivo.name)
    con.commit()
    return aplicadas


def batida(con, nome, **detalhe):
    """O serviço avisa que está vivo. Um nome por cópia: host e processo."""
    con.execute("INSERT INTO servicos (nome, visto_em, detalhe) VALUES (%s, now(), %s) "
                "ON CONFLICT (nome) DO UPDATE SET visto_em = now(), detalhe = excluded.detalhe",
                (f"{nome}@{socket.gethostname()}:{os.getpid()}", Jsonb(detalhe)))
    con.commit()


def main():
    if sys.argv[1:] != ["migrar"]:
        sys.exit("uso: python -m cripto_ingestao.banco migrar")
    with conectar("dono") as con:
        for nome in migrar(con):
            print(f"Aplicada {nome}")


if __name__ == "__main__":
    main()
