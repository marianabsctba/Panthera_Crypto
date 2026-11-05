import pytest

from cripto_ingestao import carteiras

from conftest import DESCRITOR, RECEBER_0, TPUB, TROCO_0, criar_carteira

TPRV = "tprv8ZgxMBicQKsPe5YMU9gHen4Ez3ApihUfykaqUorj9t6FDqy3nP6eoXiAo2ssvpAjoLroQxHqr3R5nE3a5dU3DHTjTgJDd7zrbniJr6nrCzd"


def test_deriva_os_enderecos_do_vetor_do_bip84():
    d = carteiras.ler_descritor(DESCRITOR, "testnet4")
    assert d.endswith("#lxek0ef2")
    assert carteiras.derivar(d, "testnet4", 0, 0) == RECEBER_0
    assert carteiras.derivar(d, "testnet4", 1, 0) == TROCO_0


@pytest.mark.parametrize("texto", [
    f"wpkh({TPRV}/84h/1h/0h/<0;1>/*)",
    "wpkh(cVt4o7BGAig1UXywgGSmARhxMdzP5qvQsxKkSsc1XEkw3tDTQFpy)",
])
def test_recusa_chave_privada(texto):
    with pytest.raises(carteiras.Recusado, match="chave privada"):
        carteiras.ler_descritor(texto, "testnet4")


def test_recusa_rede_errada_e_descritor_sem_curinga():
    with pytest.raises(carteiras.Recusado, match="outra rede"):
        carteiras.ler_descritor(DESCRITOR, "bitcoin")
    with pytest.raises(carteiras.Recusado, match="terminar em"):
        carteiras.ler_descritor(f"wpkh({TPUB}/0/0)", "testnet4")


def test_endereco_de_outra_rede():
    with pytest.raises(carteiras.Recusado, match="outra rede"):
        carteiras.validar_endereco(RECEBER_0, "bitcoin")
    with pytest.raises(carteiras.Recusado, match="inválido"):
        carteiras.validar_endereco("tb1qnaoeumendereco", "testnet4")


def test_completar_abre_folga_depois_do_ultimo_usado(con, organizacao):
    carteira = criar_carteira(con, organizacao)
    assert con.execute("SELECT count(*) AS n FROM enderecos WHERE carteira_id = %s", (carteira["id"],)).fetchone()["n"] == 2 * carteiras.FOLGA
    con.execute("UPDATE enderecos SET usado = true WHERE carteira_id = %s AND ramo = 0 AND indice = 5", (carteira["id"],))
    assert len(carteiras.completar(con, carteira)) == 6
    assert carteiras.completar(con, carteira) == []
