import pytest

from mala_direta.erros import TextoInvalidoError
from mala_direta.planilha import Destinatario
from mala_direta.texto import nome_de_arquivo, preencher, validar_textos

ANA = Destinatario(
    linha=2,
    email="ana@exemplo.com",
    valores={"Nome Completo": "Ana Ribeiro", "curso": "Claude for Business"},
)


@pytest.mark.parametrize(
    "modelo",
    ["{Nome Completo}", "{nome completo}", "{nome_completo}", "{NOMECOMPLETO}"],
)
def test_placeholder_encontra_a_coluna_apesar_da_grafia(modelo: str):
    assert preencher(modelo, ANA) == "Ana Ribeiro"


def test_placeholder_desconhecido_aponta_as_colunas_disponiveis():
    with pytest.raises(TextoInvalidoError, match="Nome Completo"):
        preencher("Olá, {apelido}", ANA)


def test_validar_textos_reune_todos_os_problemas():
    with pytest.raises(TextoInvalidoError) as erro:
        validar_textos({"assunto": "{turma}", "corpo": "{cidade}"}, ["Nome Completo", "curso"])

    assert "{turma}" in str(erro.value)
    assert "{cidade}" in str(erro.value)


def test_nome_de_arquivo_remove_acento_e_espaco():
    assert nome_de_arquivo("certificado-{Nome Completo}.pdf", ANA) == "certificado-Ana-Ribeiro.pdf"


def test_nome_de_arquivo_sem_extensao_vira_pdf():
    assert nome_de_arquivo("{curso}", ANA) == "Claude-for-Business.pdf"


def test_nome_de_arquivo_nao_escapa_do_diretorio():
    perigoso = Destinatario(linha=2, email="x@exemplo.com", valores={"nome": "../../etc/passwd"})

    assert nome_de_arquivo("{nome}.pdf", perigoso) == "etc-passwd.pdf"
