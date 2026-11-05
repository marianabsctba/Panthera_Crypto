"""Cria organizações e acessos. A senha aparece uma vez só, no terminal.

    python -m cripto_api.contas criar --organizacao "Acme" --email pessoa@exemplo.test --nome "Pessoa"
"""

import argparse
import secrets

from argon2 import PasswordHasher

from cripto_ingestao.banco import conectar


def criar(con, organizacao, email, nome, senha=None):
    senha = senha or secrets.token_urlsafe(12)
    with con.transaction():
        org = con.execute("INSERT INTO organizacoes (nome) VALUES (%s) ON CONFLICT (nome) DO UPDATE SET nome = excluded.nome RETURNING id", (organizacao.strip(),)).fetchone()["id"]
        con.execute("INSERT INTO usuarios (organizacao_id, email, nome, senha) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (email) DO UPDATE SET nome = excluded.nome, senha = excluded.senha",
                    (org, email.strip().lower(), nome.strip(), PasswordHasher().hash(senha)))
    return org, senha


def main():
    argumentos = argparse.ArgumentParser(description="Acesso ao Panthera Crypto")
    sub = argumentos.add_subparsers(dest="acao", required=True)
    novo = sub.add_parser("criar", help="cria o acesso, e a organização se ainda não existir; para quem já existe, troca a senha")
    novo.add_argument("--organizacao", required=True)
    novo.add_argument("--email", required=True)
    novo.add_argument("--nome", required=True)
    opcoes = argumentos.parse_args()
    # O dono das tabelas também passa pelo isolamento por organização: quem cria é o papel dos serviços.
    with conectar("servicos") as con:
        _, senha = criar(con, opcoes.organizacao, opcoes.email, opcoes.nome)
    print(f"Acesso de {opcoes.email.strip().lower()} pronto. Senha: {senha}")


if __name__ == "__main__":
    main()
