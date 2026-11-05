"""Os testes de banco criam um banco novo a cada rodada, no mesmo Postgres da instalação de teste.

    sudo bash infra/subir.sh --rede regtest
    sudo sh -c 'set -a; . /opt/panthera-crypto/.env; set +a; .venv/bin/python -m pytest testes'
"""

import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "api"), str(RAIZ / "ingestao")]

# Vetor de teste do BIP84: chave pública conhecida, endereços conhecidos.
TPUB = "tpubDC8msFGeGuwnKG9Upg7DM2b4DaRqg3CUZa5g8v2SRQ6K4NSkxUgd7HsL2XVWbVm39yBA4LAxysQAm397zwQSQoQgewGiYZqrA9DsP4zbQ1M"
DESCRITOR = f"wpkh([73c5da0a/84h/1h/0h]{TPUB}/<0;1>/*)"
RECEBER_0 = "tb1q6rz28mcfaxtmd6v789l9rrlrusdprr9pqcpvkl"
TROCO_0 = "tb1q9u62588spffmq4dzjxsr5l297znf3z6j5p2688"
FORA = "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx"
BANCO_DE_TESTE = "cripto_teste"


@pytest.fixture(scope="session")
def banco_de_teste():
    if "CRIPTO_SENHA_DONO" not in os.environ:
        pytest.skip("sem banco: carregue o .env da instalação de teste")
    import psycopg

    from cripto_ingestao.banco import conectar, migrar

    endereco = os.getenv("CRIPTO_BANCO", "127.0.0.1:5444")
    with psycopg.connect(f"postgresql://cripto_dono:{os.environ['CRIPTO_SENHA_DONO']}@{endereco}/postgres", autocommit=True) as con:
        con.execute(f"DROP DATABASE IF EXISTS {BANCO_DE_TESTE} WITH (FORCE)")
        con.execute(f"CREATE DATABASE {BANCO_DE_TESTE}")
    os.environ["CRIPTO_BANCO_NOME"] = BANCO_DE_TESTE
    with conectar("dono") as con:
        con.execute(f"GRANT CONNECT ON DATABASE {BANCO_DE_TESTE} TO cripto_api, cripto_servicos")
        con.execute("GRANT USAGE ON SCHEMA public TO cripto_api, cripto_servicos")
        con.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO cripto_api, cripto_servicos")
        migrar(con)
    yield


@pytest.fixture
def con(banco_de_teste):
    from cripto_ingestao.banco import conectar

    with conectar("servicos") as c:
        yield c


@pytest.fixture
def organizacao(con):
    import uuid

    return con.execute("INSERT INTO organizacoes (nome) VALUES (%s) RETURNING id", (f"teste-{uuid.uuid4().hex[:8]}",)).fetchone()["id"]


def criar_carteira(con, organizacao, rede="testnet4", descritor=DESCRITOR, limite=None, nome="Fria"):
    from cripto_ingestao import carteiras

    d = carteiras.ler_descritor(descritor, rede)
    c = con.execute("INSERT INTO carteiras (organizacao_id, nome, rede, descritor, limite_sats, estado) VALUES (%s, %s, %s, %s, %s, 'acompanhando') RETURNING *",
                    (organizacao, nome, rede, d, limite)).fetchone()
    carteiras.completar(con, c)
    con.commit()
    return c
