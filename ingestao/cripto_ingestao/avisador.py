"""Entrega os alertas nos canais de cada organização.

    python -m cripto_ingestao.avisador

Rode quantas cópias precisar. Canal fora do ar recebe de novo mais tarde; o alerta já está gravado de qualquer jeito.
"""

import time

import httpx

from . import avisos
from .banco import batida, conectar

LOTE = 50
TENTATIVAS = 12


def rodada(con, cliente=None):
    cliente = cliente or httpx.Client(timeout=10, follow_redirects=False)
    with con.transaction():
        envios = con.execute(
            """SELECT f.id, f.tentativas, row_to_json(a) AS alerta, row_to_json(c) AS canal, row_to_json(m) AS movimento,
                      json_build_object('nome', w.nome, 'rede', w.rede) AS carteira
               FROM fila_envios f
               JOIN alertas a ON a.organizacao_id = f.organizacao_id AND a.id = f.alerta_id
               JOIN canais c ON c.id = f.canal_id
               JOIN carteiras w ON w.id = a.carteira_id
               LEFT JOIN movimentos m ON m.organizacao_id = a.organizacao_id AND m.id = a.movimento_id
               WHERE f.disponivel_em <= now() ORDER BY f.id LIMIT %s FOR UPDATE OF f SKIP LOCKED""", (LOTE,)).fetchall()
        for e in envios:
            canal = e["canal"]
            try:
                avisos.enviar(canal, e["alerta"], e["carteira"], e["movimento"], cliente)
                con.execute("DELETE FROM fila_envios WHERE id = %s", (e["id"],))
                con.execute("UPDATE canais SET ultimo_envio_em = now(), ultimo_erro = NULL WHERE id = %s", (canal["id"],))
            except Exception as erro:
                texto = str(erro)[:300]
                con.execute("UPDATE canais SET ultimo_erro = %s WHERE id = %s", (texto, canal["id"]))
                if e["tentativas"] + 1 >= TENTATIVAS or isinstance(erro, avisos.Proibido):
                    con.execute("DELETE FROM fila_envios WHERE id = %s", (e["id"],))
                else:
                    con.execute("UPDATE fila_envios SET tentativas = tentativas + 1, erro = %s, "
                                "disponivel_em = now() + make_interval(secs => least(3600, 30 * 2 ^ tentativas)) WHERE id = %s", (texto, e["id"]))
    return len(envios)


def main():
    con = conectar()
    cliente = httpx.Client(timeout=10, follow_redirects=False)
    enviados, ultima_batida = 0, 0.0
    while True:
        feitos = rodada(con, cliente)
        enviados += feitos
        if time.monotonic() - ultima_batida > 30:
            batida(con, "avisador", enviados=enviados)
            ultima_batida = time.monotonic()
        if not feitos:
            time.sleep(1)


if __name__ == "__main__":
    main()
