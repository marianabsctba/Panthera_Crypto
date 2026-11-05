from cripto_ingestao import regras
from cripto_ingestao.movimentos import classificar

from conftest import FORA, RECEBER_0, TROCO_0

CARTEIRA = {"limite_sats": 100_000}


def _tx(entradas, saidas, estado="confirmada"):
    return {"txid": "ab" * 32, "estado": estado, "bloco": 1, "hora": 1_700_000_000, "taxa_sats": 200,
            "entradas": [{"endereco": e, "valor_sats": v} for e, v in entradas],
            "saidas": [{"endereco": e, "valor_sats": v} for e, v in saidas]}


def test_entrada():
    m = classificar(_tx([(FORA, 60_000)], [(RECEBER_0, 50_000), (FORA, 9_800)]), {RECEBER_0, TROCO_0})
    assert (m["tipo"], m["valor_sats"], m["contrapartes"]) == ("entrada", 50_000, [{"endereco": FORA}])


def test_entrada_com_origem_desconhecida():
    m = classificar(_tx([(None, None)], [(RECEBER_0, 50_000)]), {RECEBER_0})
    assert (m["tipo"], m["valor_sats"], m["contrapartes"]) == ("entrada", 50_000, [])


def test_saida_desconta_troco():
    m = classificar(_tx([(RECEBER_0, 50_000)], [(FORA, 30_000), (TROCO_0, 19_800)], "mempool"), {RECEBER_0, TROCO_0})
    assert (m["tipo"], m["valor_sats"], m["estado"]) == ("saida", 30_000, "mempool")
    assert m["contrapartes"] == [{"endereco": FORA, "valor_sats": 30_000}]


def test_interno():
    m = classificar(_tx([(RECEBER_0, 50_000)], [(TROCO_0, 49_800)]), {RECEBER_0, TROCO_0})
    assert (m["tipo"], m["valor_sats"]) == ("interno", 200)
    assert regras.avaliar(m, CARTEIRA, set(), lambda e: None) is None


def _saida(destino, valor=30_000):
    return {"tipo": "saida", "valor_sats": valor, "contrapartes": [{"endereco": destino, "valor_sats": valor}]}


def test_saida_para_conferido_e_media():
    assert regras.avaliar(_saida(FORA), CARTEIRA, {FORA}, lambda e: None)[0] == "media"


def test_saida_para_fora_da_agenda_e_alta():
    severidade, _, motivos = regras.avaliar(_saida(FORA), CARTEIRA, set(), lambda e: None)
    assert severidade == "alta" and motivos == ["Destino fora dos endereços conferidos"]


def test_acima_do_limite_sobe_mesmo_para_conferido():
    severidade, _, motivos = regras.avaliar(_saida(FORA, 200_000), CARTEIRA, {FORA}, lambda e: None)
    assert severidade == "alta" and "Valor acima do limite da carteira" in motivos


def test_endereco_em_lista_e_critico_nos_dois_sentidos():
    em_lista = {FORA: "OFAC"}.get
    assert regras.avaliar(_saida(FORA), CARTEIRA, {FORA}, em_lista)[0] == "critica"
    entrada = {"tipo": "entrada", "valor_sats": 5_000, "contrapartes": [{"endereco": FORA}]}
    assert regras.avaliar(entrada, CARTEIRA, set(), em_lista)[:2] == ("critica", "Movimento com endereço em lista")


def test_poeira_de_endereco_parecido_e_envenenamento():
    conferido = "bc1qa5wkgaew2dkv56kfvj49j0av5nml45x9ek9hz6"
    isca = "bc1qa5wkzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz9hz6"
    entrada = {"tipo": "entrada", "valor_sats": 546, "contrapartes": [{"endereco": isca}]}
    assert regras.avaliar(entrada, CARTEIRA, {conferido}, lambda e: None)[:2] == ("media", "Possível envenenamento de endereço")
    entrada["valor_sats"] = 50_000
    assert regras.avaliar(entrada, CARTEIRA, {conferido}, lambda e: None)[0] == "baixa"


def test_parecido_nao_confunde_o_proprio_nem_outro_qualquer():
    assert not regras.parecido(RECEBER_0, RECEBER_0)
    assert not regras.parecido(RECEBER_0, TROCO_0)
