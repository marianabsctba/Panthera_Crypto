import uuid

import pytest
from fastapi.testclient import TestClient

from conftest import DESCRITOR, FORA, criar_carteira


@pytest.fixture
def cliente(banco_de_teste, monkeypatch):
    monkeypatch.setenv("CRIPTO_COOKIE_SEGURO", "0")
    from cripto_api.app import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def pessoa(con):
    from cripto_api import contas

    email = f"{uuid.uuid4().hex[:8]}@exemplo.test"
    organizacao, senha = contas.criar(con, f"org-{email}", email, "Pessoa")
    return {"email": email, "senha": senha, "organizacao": organizacao}


def _entrar(cliente, pessoa):
    assert cliente.post("/api/entrar", json={"email": pessoa["email"], "senha": pessoa["senha"]}).status_code == 204


def test_sem_sessao_nao_entra(cliente, pessoa):
    assert cliente.get("/api/carteiras").status_code == 401
    assert cliente.post("/api/entrar", json={"email": pessoa["email"], "senha": "errada"}).status_code == 401


def test_bloqueia_depois_de_varias_falhas(cliente):
    for _ in range(5):
        cliente.post("/api/entrar", json={"email": "ninguem@exemplo.test", "senha": "x"})
    assert cliente.post("/api/entrar", json={"email": "ninguem@exemplo.test", "senha": "x"}).status_code == 429


def test_carteira_agenda_e_tarefa_de_partida(cliente, pessoa, con):
    _entrar(cliente, pessoa)
    r = cliente.post("/api/carteiras", json={"nome": "Fria", "rede": "testnet4", "descritor": DESCRITOR, "limite_sats": 1000})
    assert r.status_code == 201
    identificador = r.json()["id"]
    assert len(cliente.get(f"/api/carteiras/{identificador}").json()["enderecos"]) == 40
    assert con.execute("SELECT tipo FROM fila_tarefas WHERE carteira_id = %s", (identificador,)).fetchone()["tipo"] == "historico"
    assert cliente.post("/api/carteiras", json={"nome": "Fria", "rede": "testnet4", "enderecos": [FORA]}).status_code == 409
    assert cliente.post("/api/agenda", json={"endereco": FORA, "rotulo": "Exchange"}).status_code == 201
    assert cliente.get("/api/agenda").json()["enderecos"][0]["rotulo"] == "Exchange"


def test_uma_organizacao_nao_ve_a_outra(cliente, pessoa, con):
    outra_org = con.execute("INSERT INTO organizacoes (nome) VALUES (%s) RETURNING id", (f"vizinha-{uuid.uuid4().hex[:6]}",)).fetchone()["id"]
    vizinha = criar_carteira(con, outra_org, nome="Da vizinha")
    con.execute("INSERT INTO alertas (organizacao_id, carteira_id, severidade, titulo) VALUES (%s, %s, 'alta', 'da vizinha') RETURNING id", (outra_org, vizinha["id"]))
    alerta = con.execute("SELECT id FROM alertas WHERE carteira_id = %s", (vizinha["id"],)).fetchone()["id"]
    con.commit()
    _entrar(cliente, pessoa)
    assert all(c["nome"] != "Da vizinha" for c in cliente.get("/api/carteiras").json()["carteiras"])
    assert cliente.get(f"/api/carteiras/{vizinha['id']}").status_code == 404
    assert cliente.get(f"/api/alertas/{alerta}").status_code == 404
    assert cliente.delete(f"/api/carteiras/{vizinha['id']}").status_code == 404
    assert cliente.post(f"/api/alertas/{alerta}/tratar", json={}).status_code == 409


def test_recusa_descritor_com_chave_privada_sem_ecoar_a_chave(cliente, pessoa):
    _entrar(cliente, pessoa)
    privada = "tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ssvpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd"
    r = cliente.post("/api/carteiras", json={"nome": "X", "rede": "testnet4", "descritor": f"wpkh({privada}/84h/1h/0h/<0;1>/*)"})
    assert r.status_code == 422 and privada not in r.text


def test_canal_para_dentro_da_instalacao_e_recusado(cliente, pessoa):
    _entrar(cliente, pessoa)
    r = cliente.post("/api/canais", json={"nome": "x", "tipo": "webhook", "url": "http://127.0.0.1:5434/"})
    assert r.status_code == 422


def test_outra_origem_nao_altera(cliente, pessoa):
    _entrar(cliente, pessoa)
    r = cliente.post("/api/agenda", json={"endereco": FORA, "rotulo": "x"}, headers={"Origin": "https://mau.exemplo.test"})
    assert r.status_code == 403


def test_console_leva_chave_de_estilo(cliente):
    r = cliente.get("/alertas")
    if r.status_code == 404:
        pytest.skip("console ainda não construída")
    assert "__CHAVE__" not in r.text and "nonce-" in r.headers["content-security-policy"]
