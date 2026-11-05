"""Enche o banco com uma organização de exemplo, para ver a tela sem nó.

    python -m cripto_api.demonstracao

O acesso fica em /opt/panthera-crypto/demonstracao.txt, ou em CRIPTO_DEMONSTRACAO; com "-", sai na tela. As carteiras usam as chaves
públicas dos vetores de teste do BIP84, que são de conhecimento público: nada aqui guarda valor de verdade.
"""

import os
import random
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from embit import bip32, bip39
from embit.descriptor.checksum import add_checksum
from embit.networks import NETWORKS

from cripto_ingestao import carteiras
from cripto_ingestao.banco import Jsonb, conectar

from . import contas

VETOR = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
OUTRO = "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo wrong"
SANCIONADO = "123WBUDmSJv4GctdVEz6Qq6z8nXSKrJ4KX"
ORGANIZACAO = "Demonstração"


def _descritor(frase, conta):
    raiz = bip32.HDKey.from_seed(bip39.mnemonic_to_seed(frase), version=NETWORKS["main"]["xprv"])
    publica = raiz.derive(f"m/84h/0h/{conta}h").to_public()
    return add_checksum(f"wpkh([{raiz.my_fingerprint.hex()}/84h/0h/{conta}h]{publica.to_string()}/<0;1>/*)")


def semear(con, organizacao):
    sorteio = random.Random(7)
    eventos = []
    agora = datetime.now(timezone.utc).replace(microsecond=0)
    terceiros = _descritor(OUTRO, 0)
    destinos = [carteiras.derivar(terceiros, "bitcoin", 0, i) for i in range(12)]
    for tabela in ("carteiras", "agenda", "canais"):
        con.execute(f"DELETE FROM {tabela} WHERE organizacao_id = %s", (organizacao,))
    con.execute("INSERT INTO agenda (organizacao_id, endereco, rotulo) VALUES (%s, %s, %s), (%s, %s, %s), (%s, %s, %s)",
                (organizacao, destinos[0], "Exchange, conta da empresa", organizacao, destinos[1], "Fornecedor de hardware", organizacao, destinos[2], "Tesouraria multisig"))
    con.execute("INSERT INTO listas (endereco, lista) VALUES (%s, 'OFAC') ON CONFLICT DO NOTHING", (SANCIONADO,))
    con.execute("INSERT INTO listas_atualizacao (lista, total, atualizada_em) VALUES ('OFAC', 532, %s) ON CONFLICT (lista) DO NOTHING", (agora - timedelta(hours=3),))
    con.execute("INSERT INTO canais (organizacao_id, nome, tipo, url, severidade_minima, ultimo_envio_em) VALUES (%s, %s, 'ntfy', %s, 'alta', %s), (%s, %s, 'webhook', %s, 'media', NULL)",
                (organizacao, "Celular da equipe", "https://ntfy.exemplo.test/panthera-crypto", agora - timedelta(hours=5),
                 organizacao, "Sistema de chamados", "https://chamados.exemplo.test/api/webhook"))

    for nome, conta, limite in [("Fria principal", 0, 50_000_000), ("Quente operações", 1, 2_000_000), ("Reserva de herança", 2, None)]:
        descritor = _descritor(VETOR, conta)
        carteira = {"descritor": descritor, "rede": "bitcoin", "organizacao_id": organizacao}
        carteira["id"] = con.execute(
            "INSERT INTO carteiras (organizacao_id, nome, rede, descritor, limite_sats, estado, sincronizada_em, criada_em) VALUES (%s, %s, 'bitcoin', %s, %s, 'acompanhando', %s, %s) RETURNING id",
            (organizacao, nome, descritor, limite, agora - timedelta(days=60), agora - timedelta(days=60))).fetchone()["id"]
        carteiras.completar(con, carteira)
        for indice in range(sorteio.randint(3, 8)):
            endereco = carteiras.derivar(descritor, "bitcoin", 0, indice)
            con.execute("UPDATE enderecos SET usado = true WHERE carteira_id = %s AND endereco = %s", (carteira["id"], endereco))
            con.execute("INSERT INTO saidas (rede, transacao, posicao, carteira_id, organizacao_id, endereco, valor_sats) VALUES ('bitcoin', %s, 0, %s, %s, %s, %s)",
                        (secrets.token_hex(32), carteira["id"], organizacao, endereco, sorteio.randint(10_000, 40_000_000 if conta == 0 else 1_500_000)))
        carteiras.completar(con, carteira)

        for dia in range(30, -1, -1):
            for _ in range(sorteio.choice([0, 0, 1, 1, 2, 3]) if conta < 2 else sorteio.choice([0] * 9 + [1])):
                momento = agora - timedelta(days=dia, hours=sorteio.randint(0, 20), minutes=sorteio.randint(0, 59))
                if momento > agora:
                    continue
                tipo = sorteio.choice(["entrada", "saida", "saida"] if conta == 1 else ["entrada", "entrada", "saida"])
                valor = sorteio.randint(50_000, 3_000_000 if conta == 1 else 80_000_000)
                if tipo == "entrada":
                    contrapartes = [{"endereco": sorteio.choice(destinos[3:])}]
                    severidade, titulo, motivos = "baixa", "Entrada na carteira", ["Entrada na carteira"]
                else:
                    destino = sorteio.choice(destinos[:3] if sorteio.random() < 0.7 else destinos[3:])
                    contrapartes = [{"endereco": destino, "valor_sats": valor}]
                    if destino in destinos[:3]:
                        severidade, titulo, motivos = "media", "Saída da carteira", ["Destino entre os endereços conferidos"]
                    else:
                        severidade, titulo, motivos = "alta", "Saída da carteira", ["Destino fora dos endereços conferidos"]
                    if limite and valor > limite:
                        severidade, motivos = "alta", motivos + ["Valor acima do limite da carteira"]
                eventos.append((carteira["id"], tipo, valor, contrapartes, momento, severidade, titulo, motivos, {"tratado": dia > 2 and sorteio.random() < 0.8}))

        if conta == 1:
            eventos.append((carteira["id"], "saida", 1_250_000, [{"endereco": SANCIONADO, "valor_sats": 1_250_000}], agora - timedelta(hours=2),
                    "critica", "Movimento com endereço em lista", [f"{SANCIONADO} está na lista OFAC", "Destino fora dos endereços conferidos"], {"estado": "mempool"}))
        if conta == 0:
            isca = destinos[0][:8] + "x" * (len(destinos[0]) - 12) + destinos[0][-4:]
            eventos.append((carteira["id"], "entrada", 546, [{"endereco": isca}], agora - timedelta(hours=7), "media", "Possível envenenamento de endereço",
                    ["Valor mínimo vindo de endereço parecido com um conferido: possível envenenamento de endereço"], {}))
            eventos.append((carteira["id"], "saida", 62_000_000, [{"endereco": destinos[5], "valor_sats": 62_000_000}], agora - timedelta(minutes=25),
                    "alta", "Saída da carteira", ["Destino fora dos endereços conferidos", "Valor acima do limite da carteira"], {"estado": "mempool"}))

    # Grava na ordem do tempo, como acontece de verdade: o número do alerta cresce junto com a data.
    altura = 900_000
    for carteira_id, tipo, valor, contrapartes, momento, severidade, titulo, motivos, extra in sorted(eventos, key=lambda e: e[4]):
        altura += 1
        _gravar(con, organizacao, carteira_id, tipo, valor, contrapartes, momento, severidade, titulo, motivos, bloco=altura, **extra)


def _gravar(con, organizacao, carteira, tipo, valor, contrapartes, momento, severidade, titulo, motivos, bloco, tratado=False, estado="confirmada"):
    movimento = con.execute(
        "INSERT INTO movimentos (organizacao_id, carteira_id, transacao, tipo, valor_sats, taxa_sats, contrapartes, estado, bloco, visto_em, confirmada_em) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (organizacao, carteira, secrets.token_hex(32), tipo, valor, random.randint(300, 4000), Jsonb(contrapartes), estado,
         bloco if estado == "confirmada" else None, momento, momento if estado == "confirmada" else None)).fetchone()["id"]
    con.execute("INSERT INTO alertas (organizacao_id, carteira_id, movimento_id, severidade, titulo, motivos, criado_em, tratado_em, tratado_por, nota) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (organizacao, carteira, movimento, severidade, titulo, Jsonb(motivos), momento,
                 momento + timedelta(minutes=30) if tratado else None, "Demonstração" if tratado else None, "Conferido com a equipe." if tratado else None))


def main():
    with conectar("servicos") as con:
        organizacao, senha = contas.criar(con, ORGANIZACAO, "demonstracao@exemplo.test", "Demonstração")
        with con.transaction():
            semear(con, organizacao)
    acesso = f"E-mail: demonstracao@exemplo.test\nSenha: {senha}\n"
    destino = os.getenv("CRIPTO_DEMONSTRACAO", "/opt/panthera-crypto/demonstracao.txt")
    # Dentro do contêiner não há onde guardar: "-" devolve o acesso para quem chamou gravar fora.
    if destino == "-":
        print(acesso, end="")
        return
    arquivo = Path(destino)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(acesso, encoding="utf-8")
    arquivo.chmod(0o600)
    print(f"Pronto. O acesso está em {arquivo}")


if __name__ == "__main__":
    main()
