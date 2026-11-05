import hashlib
import os
import re
import secrets
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cripto_ingestao import avisos, carteiras
from cripto_ingestao.banco import pool
from cripto_ingestao.listas import FONTES, em_listas

ESTATICO = Path(__file__).parent / "estatico"
COOKIE = "crypto_sessao"
HORAS_DE_SESSAO = 12
POR_PAGINA = 200
SEGURANCA = {
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}
TXID = re.compile(r"^[0-9a-f]{64}$")

hasher = PasswordHasher()
HASH_FICTICIO = hasher.hash(secrets.token_hex(16))
falhas_de_login = defaultdict(list)


@asynccontextmanager
async def ciclo_de_vida(app):
    app.state.banco = pool("api", maximo=int(os.getenv("CRIPTO_API_CONEXOES", "10")))
    yield
    app.state.banco.close()


app = FastAPI(title="Panthera Crypto", description="Monitoramento de criptomoedas. Powered by Mariana BS.", lifespan=ciclo_de_vida, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def cabecalhos(request: Request, chamada):
    # Sem cabeçalho Origin é requisição fora do navegador; com ele, precisa ser a própria tela.
    origem = request.headers.get("origin")
    if request.method not in ("GET", "HEAD") and origem and origem.split("://")[-1] != request.headers.get("host"):
        return Response(status_code=403)
    resposta = await chamada(request)
    resposta.headers.update(SEGURANCA)
    chave = getattr(request.state, "chave_de_estilo", None)
    if chave:
        resposta.headers["Content-Security-Policy"] = (
            f"default-src 'self'; style-src 'self' 'nonce-{chave}'; img-src 'self' data:; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    resposta.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
    return resposta


def _hash_do_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class Contexto:
    con: psycopg.Connection
    usuario: dict


def contexto(request: Request):
    """Uma transação por requisição, presa à organização da sessão: o banco não devolve linha de outra."""
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(status_code=401)
    with request.app.state.banco.connection() as con, con.transaction():
        usuario = con.execute(
            "SELECT u.id, u.nome, u.email, u.organizacao_id FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id WHERE s.token = %s AND s.expira_em > now()",
            (_hash_do_token(token),)).fetchone()
        if not usuario:
            raise HTTPException(status_code=401)
        con.execute("SELECT set_config('cripto.organizacao', %s, true)", (str(usuario["organizacao_id"]),))
        yield Contexto(con, usuario)


class Entrada(BaseModel):
    email: str = Field(max_length=200)
    senha: str = Field(max_length=200)


def _origem(request):
    return request.client.host if request.client else "?"


@app.post("/api/entrar")
def entrar(dados: Entrada, request: Request):
    chave = f"{_origem(request)}|{dados.email.lower()}"
    recentes = [t for t in falhas_de_login[chave] if t > time.monotonic() - 900]
    falhas_de_login[chave] = recentes
    if len(recentes) >= 5:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Espere alguns minutos.")
    with request.app.state.banco.connection() as con:
        linha = con.execute("SELECT id, senha FROM usuarios WHERE email = %s", (dados.email.strip().lower(),)).fetchone()
        try:
            # Sem usuário, confere contra um hash qualquer: o tempo de resposta não pode contar quem existe.
            hasher.verify(linha["senha"] if linha else HASH_FICTICIO, dados.senha)
            if not linha:
                raise VerificationError()
        except (VerificationError, InvalidHashError):
            falhas_de_login[chave].append(time.monotonic())
            raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.") from None
        token = secrets.token_urlsafe(32)
        con.execute("INSERT INTO sessoes (token, usuario_id, expira_em) VALUES (%s, %s, now() + make_interval(hours => %s))",
                    (_hash_do_token(token), linha["id"], HORAS_DE_SESSAO))
    saida = Response(status_code=204)
    saida.set_cookie(COOKIE, token, httponly=True, samesite="strict", path="/", secure=os.getenv("CRIPTO_COOKIE_SEGURO", "1") == "1",
                     max_age=HORAS_DE_SESSAO * 3600)
    return saida


@app.post("/api/sair", status_code=204)
def sair(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        with request.app.state.banco.connection() as con:
            con.execute("DELETE FROM sessoes WHERE token = %s", (_hash_do_token(token),))
    response.delete_cookie(COOKIE, path="/")


@app.get("/api/eu")
def eu(ctx: Contexto = Depends(contexto)):
    organizacao = ctx.con.execute("SELECT nome FROM organizacoes").fetchone()
    return {"nome": ctx.usuario["nome"], "email": ctx.usuario["email"], "organizacao": organizacao["nome"],
            "fuso": os.getenv("CRIPTO_FUSO", "America/Sao_Paulo")}


def _servicos(con):
    """Quantas cópias de cada serviço deram sinal de vida no último minuto. Sem nome de máquina."""
    linhas = con.execute(
        """SELECT split_part(nome, '@', 1) AS servico, count(*) FILTER (WHERE visto_em > now() - interval '90 seconds') AS vivas, max(visto_em) AS visto_em
           FROM servicos GROUP BY 1 ORDER BY 1""").fetchall()
    return [dict(l) for l in linhas]


@app.get("/api/panorama")
def panorama(dias: int = 30, ctx: Contexto = Depends(contexto)):
    con = ctx.con
    dias = max(1, min(dias, 365))
    abertos = {l["severidade"]: l["total"] for l in con.execute("SELECT severidade, count(*) AS total FROM alertas WHERE tratado_em IS NULL GROUP BY severidade")}
    por_dia = con.execute(
        """SELECT to_char(date_trunc('day', criado_em AT TIME ZONE %s), 'YYYY-MM-DD') AS dia, severidade, count(*) AS total
           FROM alertas WHERE criado_em >= now() - make_interval(days => %s) GROUP BY 1, 2 ORDER BY 1""",
        (os.getenv("CRIPTO_FUSO", "America/Sao_Paulo"), dias)).fetchall()
    serie = {}
    for l in por_dia:
        serie.setdefault(l["dia"], {"dia": l["dia"], "critica": 0, "alta": 0, "media": 0, "baixa": 0})[l["severidade"]] = l["total"]
    por_carteira = con.execute(
        """SELECT c.id, c.nome, count(*) AS total FROM alertas a JOIN carteiras c ON c.id = a.carteira_id
           WHERE a.tratado_em IS NULL GROUP BY c.id, c.nome ORDER BY total DESC LIMIT 10""").fetchall()
    saidas = con.execute(
        "SELECT count(*) AS total, COALESCE(sum(valor_sats), 0) AS valor FROM movimentos WHERE tipo = 'saida' AND NOT historico AND visto_em >= now() - make_interval(days => %s)",
        (dias,)).fetchone()
    return {
        "carteiras": con.execute("SELECT count(*) AS n FROM carteiras").fetchone()["n"],
        "saldo_sats": con.execute("SELECT COALESCE(sum(valor_sats), 0) AS n FROM saidas WHERE gasta_por IS NULL").fetchone()["n"],
        "abertos": {s: abertos.get(s, 0) for s in ("critica", "alta", "media", "baixa")},
        "saidas": dict(saidas),
        "pendentes": con.execute("SELECT count(*) AS n FROM movimentos WHERE estado = 'mempool'").fetchone()["n"],
        "alertas_por_dia": list(serie.values()),
        "por_carteira": [dict(l) for l in por_carteira],
        "servicos": _servicos(con),
    }


def _filtro_de_busca(busca, valores):
    """Toda busca usa índice: transação exata, endereço exato ou o título."""
    busca = busca.strip()
    if TXID.match(busca.lower()):
        valores.append(busca.lower())
        return "m.transacao = %s"
    if len(busca) >= 26 and " " not in busca:
        valores.append(psycopg.types.json.Jsonb([{"endereco": busca}]))
        return "m.contrapartes @> %s"
    valores.append(f"%{busca}%")
    return "a.titulo ILIKE %s"


@app.get("/api/alertas")
def lista_de_alertas(estado: Literal["abertos", "tratados", "todos"] = "abertos", severidade: str | None = None, carteira: int | None = None,
                     dia: str | None = None, busca: str | None = None, antes: int | None = None, ctx: Contexto = Depends(contexto)):
    filtros, valores = [], []
    if estado == "abertos":
        filtros.append("a.tratado_em IS NULL")
    elif estado == "tratados":
        filtros.append("a.tratado_em IS NOT NULL")
    if severidade:
        filtros.append("a.severidade = %s")
        valores.append(severidade)
    if carteira:
        filtros.append("a.carteira_id = %s")
        valores.append(carteira)
    if dia:
        filtros.append("a.criado_em >= (%s::date AT TIME ZONE %s) AND a.criado_em < ((%s::date + 1) AT TIME ZONE %s)")
        fuso = os.getenv("CRIPTO_FUSO", "America/Sao_Paulo")
        valores += [dia, fuso, dia, fuso]
    if busca:
        filtros.append(_filtro_de_busca(busca, valores))
    if antes:
        filtros.append("a.id < %s")
        valores.append(antes)
    onde = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    linhas = ctx.con.execute(
        f"""SELECT a.id, a.severidade, a.titulo, a.motivos, a.criado_em, a.tratado_em, c.nome AS carteira, c.rede,
                   m.tipo, m.valor_sats, m.estado, m.transacao
            FROM alertas a JOIN carteiras c ON c.id = a.carteira_id
            LEFT JOIN movimentos m ON m.organizacao_id = a.organizacao_id AND m.id = a.movimento_id
            {onde} ORDER BY a.id DESC LIMIT {POR_PAGINA + 1}""", valores).fetchall()
    return {"alertas": linhas[:POR_PAGINA], "ha_mais": len(linhas) > POR_PAGINA}


@app.get("/api/alertas/{identificador}")
def alerta(identificador: int, ctx: Contexto = Depends(contexto)):
    resultado = ctx.con.execute(
        """SELECT a.*, c.nome AS carteira, c.rede, m.tipo, m.valor_sats, m.taxa_sats, m.estado, m.transacao, m.contrapartes, m.visto_em, m.confirmada_em, m.bloco
           FROM alertas a JOIN carteiras c ON c.id = a.carteira_id
           LEFT JOIN movimentos m ON m.organizacao_id = a.organizacao_id AND m.id = a.movimento_id WHERE a.id = %s""", (identificador,)).fetchone()
    if not resultado:
        raise HTTPException(status_code=404)
    contrapartes = resultado.get("contrapartes") or []
    enderecos = [c["endereco"] for c in contrapartes]
    agenda = {l["endereco"]: l["rotulo"] for l in ctx.con.execute("SELECT endereco, rotulo FROM agenda WHERE endereco = ANY(%s)", (enderecos,))}
    listas = em_listas(ctx.con, enderecos)
    for c in contrapartes:
        c["rotulo"] = agenda.get(c["endereco"])
        c["lista"] = listas.get(c["endereco"])
    return resultado


class Tratamento(BaseModel):
    nota: str = Field(default="", max_length=2000)


@app.post("/api/alertas/{identificador}/tratar", status_code=204)
def tratar(identificador: int, dados: Tratamento, ctx: Contexto = Depends(contexto)):
    feito = ctx.con.execute("UPDATE alertas SET tratado_em = now(), tratado_por = %s, nota = %s WHERE id = %s AND tratado_em IS NULL",
                            (ctx.usuario["nome"], dados.nota.strip() or None, identificador)).rowcount
    if not feito:
        raise HTTPException(status_code=409, detail="Este alerta já foi tratado.")


@app.get("/api/movimentos")
def lista_de_movimentos(carteira: int | None = None, tipo: str | None = None, estado: str | None = None, busca: str | None = None,
                        dias: int | None = None, novos: bool = False, antes: int | None = None, ctx: Contexto = Depends(contexto)):
    filtros, valores = [], []
    if dias:
        filtros.append("m.visto_em >= now() - make_interval(days => %s)")
        valores.append(max(1, min(dias, 365)))
    if novos:
        filtros.append("NOT m.historico")
    if carteira:
        filtros.append("m.carteira_id = %s")
        valores.append(carteira)
    if tipo:
        filtros.append("m.tipo = %s")
        valores.append(tipo)
    if estado:
        filtros.append("m.estado = %s")
        valores.append(estado)
    if busca:
        filtro = _filtro_de_busca(busca, valores)
        if filtro.startswith("a."):
            valores.pop()
        else:
            filtros.append(filtro)
    if antes:
        filtros.append("m.id < %s")
        valores.append(antes)
    onde = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    linhas = ctx.con.execute(
        f"""SELECT m.*, c.nome AS carteira, c.rede,
                   (SELECT max(a.id) FROM alertas a WHERE a.organizacao_id = m.organizacao_id AND a.movimento_id = m.id) AS alerta_id
            FROM movimentos m JOIN carteiras c ON c.id = m.carteira_id {onde} ORDER BY m.id DESC LIMIT {POR_PAGINA + 1}""", valores).fetchall()
    return {"movimentos": linhas[:POR_PAGINA], "ha_mais": len(linhas) > POR_PAGINA}


class NovaCarteira(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    rede: Literal["bitcoin", "testnet4", "signet", "regtest"]
    descritor: str | None = Field(default=None, max_length=4000)
    enderecos: list[str] = Field(default_factory=list, max_length=1000)
    limite_sats: int | None = Field(default=None, ge=1)


@app.get("/api/carteiras")
def lista_de_carteiras(ctx: Contexto = Depends(contexto)):
    linhas = ctx.con.execute(
        """SELECT c.id, c.nome, c.rede, c.limite_sats, c.estado, c.sincronizada_em, c.criada_em, c.descritor IS NOT NULL AS tem_descritor,
                  s.saldo_sats, e.enderecos, e.usados, a.alertas_abertos
           FROM carteiras c
           LEFT JOIN LATERAL (SELECT COALESCE(sum(valor_sats), 0) AS saldo_sats FROM saidas WHERE carteira_id = c.id AND gasta_por IS NULL) s ON true
           LEFT JOIN LATERAL (SELECT count(*) AS enderecos, count(*) FILTER (WHERE usado) AS usados FROM enderecos WHERE carteira_id = c.id) e ON true
           LEFT JOIN LATERAL (SELECT count(*) AS alertas_abertos FROM alertas WHERE organizacao_id = c.organizacao_id AND carteira_id = c.id AND tratado_em IS NULL) a ON true
           ORDER BY c.nome""").fetchall()
    return {"carteiras": linhas}


@app.post("/api/carteiras", status_code=201)
def criar_carteira(dados: NovaCarteira, ctx: Contexto = Depends(contexto)):
    tem_descritor = bool(dados.descritor and dados.descritor.strip())
    if tem_descritor == bool([e for e in dados.enderecos if e.strip()]):
        raise HTTPException(status_code=422, detail="Informe um descritor ou uma lista de endereços.")
    try:
        descritor = carteiras.ler_descritor(dados.descritor, dados.rede) if tem_descritor else None
        enderecos = sorted({carteiras.validar_endereco(e, dados.rede) for e in dados.enderecos if e.strip()})
    except carteiras.Recusado as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from None
    organizacao = ctx.usuario["organizacao_id"]
    try:
        with ctx.con.transaction():
            identificador = ctx.con.execute("INSERT INTO carteiras (organizacao_id, nome, rede, descritor, limite_sats) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                                            (organizacao, dados.nome.strip(), dados.rede, descritor, dados.limite_sats)).fetchone()["id"]
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Já existe uma carteira com este nome.") from None
    with ctx.con.cursor() as cursor:
        cursor.executemany("INSERT INTO enderecos (endereco, carteira_id, organizacao_id, rede) VALUES (%s, %s, %s, %s)",
                           [(e, identificador, organizacao, dados.rede) for e in enderecos])
    carteiras.completar(ctx.con, {"id": identificador, "descritor": descritor, "rede": dados.rede, "organizacao_id": organizacao})
    # O ponto de partida sai do nó, em lote com as outras carteiras novas da mesma rede.
    ctx.con.execute("INSERT INTO fila_tarefas (tipo, carteira_id) VALUES ('historico', %s)", (identificador,))
    return {"id": identificador}


@app.get("/api/carteiras/{identificador}")
def carteira(identificador: int, ctx: Contexto = Depends(contexto)):
    linha = ctx.con.execute("SELECT id, nome, rede, descritor, limite_sats, estado, sincronizada_em, criada_em FROM carteiras WHERE id = %s", (identificador,)).fetchone()
    if not linha:
        raise HTTPException(status_code=404)
    enderecos = ctx.con.execute(
        """SELECT e.endereco, e.ramo, e.indice, e.usado, COALESCE(s.saldo, 0) AS saldo_sats
           FROM enderecos e LEFT JOIN (SELECT endereco, sum(valor_sats) AS saldo FROM saidas WHERE carteira_id = %s AND gasta_por IS NULL GROUP BY endereco) s USING (endereco)
           WHERE e.carteira_id = %s ORDER BY COALESCE(s.saldo, 0) DESC, e.usado DESC, e.ramo, e.indice LIMIT 500""", (identificador, identificador)).fetchall()
    return {**linha, "enderecos": enderecos}


class AjusteDeCarteira(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=80)
    limite_sats: int | None = Field(default=None, ge=0)


@app.patch("/api/carteiras/{identificador}", status_code=204)
def ajustar_carteira(identificador: int, dados: AjusteDeCarteira, ctx: Contexto = Depends(contexto)):
    if dados.nome is not None:
        ctx.con.execute("UPDATE carteiras SET nome = %s WHERE id = %s", (dados.nome.strip(), identificador))
    if dados.limite_sats is not None:
        ctx.con.execute("UPDATE carteiras SET limite_sats = %s WHERE id = %s", (dados.limite_sats or None, identificador))


@app.delete("/api/carteiras/{identificador}", status_code=204)
def remover_carteira(identificador: int, ctx: Contexto = Depends(contexto)):
    if not ctx.con.execute("DELETE FROM carteiras WHERE id = %s", (identificador,)).rowcount:
        raise HTTPException(status_code=404)


class NovoConferido(BaseModel):
    endereco: str = Field(min_length=10, max_length=120)
    rotulo: str = Field(min_length=1, max_length=120)


@app.get("/api/agenda")
def agenda(ctx: Contexto = Depends(contexto)):
    linhas = ctx.con.execute("SELECT id, endereco, rotulo, criado_em FROM agenda ORDER BY rotulo").fetchall()
    listas = em_listas(ctx.con, [l["endereco"] for l in linhas])
    return {"enderecos": [{**l, "lista": listas.get(l["endereco"])} for l in linhas]}


@app.post("/api/agenda", status_code=201)
def conferir(dados: NovoConferido, ctx: Contexto = Depends(contexto)):
    endereco = dados.endereco.strip()
    try:
        carteiras.validar_endereco(endereco, "bitcoin" if endereco.startswith(("1", "3", "bc1")) else "testnet4")
    except carteiras.Recusado as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from None
    lista = em_listas(ctx.con, [endereco]).get(endereco)
    if lista:
        raise HTTPException(status_code=422, detail=f"Este endereço está na lista {lista}.")
    try:
        with ctx.con.transaction():
            identificador = ctx.con.execute("INSERT INTO agenda (organizacao_id, endereco, rotulo) VALUES (%s, %s, %s) RETURNING id",
                                            (ctx.usuario["organizacao_id"], endereco, dados.rotulo.strip())).fetchone()["id"]
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Este endereço já está conferido.") from None
    return {"id": identificador}


@app.delete("/api/agenda/{identificador}", status_code=204)
def desconferir(identificador: int, ctx: Contexto = Depends(contexto)):
    ctx.con.execute("DELETE FROM agenda WHERE id = %s", (identificador,))


@app.get("/api/listas")
def resumo_das_listas(ctx: Contexto = Depends(contexto)):
    atualizacoes = {l["lista"]: l for l in ctx.con.execute("SELECT * FROM listas_atualizacao")}
    return {"listas": [{"lista": nome, "fonte": url, "total": atualizacoes.get(nome, {}).get("total", 0),
                        "atualizada_em": atualizacoes.get(nome, {}).get("atualizada_em")} for nome, url in FONTES.items()]}


@app.get("/api/listas/consultar")
def consultar_lista(endereco: str, ctx: Contexto = Depends(contexto)):
    endereco = endereco.strip()
    return {"endereco": endereco, "listas": em_listas(ctx.con, [endereco]).get(endereco)}


class NovoCanal(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    tipo: Literal["ntfy", "webhook"]
    url: str = Field(pattern=r"^https?://", max_length=500)
    severidade_minima: Literal["critica", "alta", "media", "baixa"] = "alta"


@app.get("/api/canais")
def lista_de_canais(ctx: Contexto = Depends(contexto)):
    return {"canais": ctx.con.execute("SELECT * FROM canais ORDER BY nome").fetchall()}


@app.post("/api/canais", status_code=201)
def criar_canal(dados: NovoCanal, ctx: Contexto = Depends(contexto)):
    try:
        avisos.conferir_destino(dados.url.strip())
    except avisos.Proibido as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from None
    identificador = ctx.con.execute("INSERT INTO canais (organizacao_id, nome, tipo, url, severidade_minima) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                                    (ctx.usuario["organizacao_id"], dados.nome.strip(), dados.tipo, dados.url.strip(), dados.severidade_minima)).fetchone()["id"]
    return {"id": identificador}


class AjusteDeCanal(BaseModel):
    ativo: bool | None = None
    severidade_minima: Literal["critica", "alta", "media", "baixa"] | None = None


@app.patch("/api/canais/{identificador}", status_code=204)
def ajustar_canal(identificador: int, dados: AjusteDeCanal, ctx: Contexto = Depends(contexto)):
    if dados.ativo is not None:
        ctx.con.execute("UPDATE canais SET ativo = %s WHERE id = %s", (dados.ativo, identificador))
    if dados.severidade_minima:
        ctx.con.execute("UPDATE canais SET severidade_minima = %s WHERE id = %s", (dados.severidade_minima, identificador))


@app.delete("/api/canais/{identificador}", status_code=204)
def remover_canal(identificador: int, ctx: Contexto = Depends(contexto)):
    ctx.con.execute("DELETE FROM canais WHERE id = %s", (identificador,))


@app.post("/api/canais/{identificador}/testar", status_code=204)
def testar_canal(identificador: int, ctx: Contexto = Depends(contexto)):
    canal = ctx.con.execute("SELECT * FROM canais WHERE id = %s", (identificador,)).fetchone()
    if not canal:
        raise HTTPException(status_code=404)
    teste = {"id": 0, "severidade": "baixa", "titulo": "Teste de aviso", "motivos": ["Se chegou, o canal funciona."], "criado_em": ""}
    try:
        avisos.enviar(canal, teste, {"nome": "Panthera Crypto", "rede": "-"}, None)
    except Exception as erro:
        raise HTTPException(status_code=502, detail=str(erro) if isinstance(erro, avisos.Proibido) else "O canal não respondeu.") from None
    ctx.con.execute("UPDATE canais SET ultimo_envio_em = now(), ultimo_erro = NULL WHERE id = %s", (identificador,))


@app.get("/api/servicos")
def servicos(ctx: Contexto = Depends(contexto)):
    filas = ctx.con.execute("SELECT (SELECT count(*) FROM fila_tarefas WHERE carteira_id IN (SELECT id FROM carteiras)) AS tarefas").fetchone()
    return {"servicos": _servicos(ctx.con), **filas}


app.mount("/estatico", StaticFiles(directory=ESTATICO), name="estatico")


# Fica por último: toda rota da console devolve a mesma página, mas caminho de API desconhecido continua 404.
@app.get("/{resto:path}", include_in_schema=False)
def console(request: Request, resto: str = ""):
    pagina = ESTATICO / "console" / "index.html"
    if resto.split("/")[0] == "api" or "." in resto or not pagina.exists():
        raise HTTPException(status_code=404)
    request.state.chave_de_estilo = secrets.token_urlsafe(18)
    return Response(pagina.read_text(encoding="utf-8").replace("__CHAVE__", request.state.chave_de_estilo), media_type="text/html")
