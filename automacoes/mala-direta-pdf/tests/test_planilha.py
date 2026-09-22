from pathlib import Path

import pytest
from openpyxl import Workbook

from mala_direta.config import ConfigPlanilha
from mala_direta.erros import PlanilhaInvalidaError
from mala_direta.planilha import emails_repetidos, ler_destinatarios


def test_le_csv_e_aceita_cabecalho_com_variacao_de_grafia(projeto: Path):
    destinatarios = ler_destinatarios(
        ConfigPlanilha(arquivo=projeto / "planilha.csv"), ["nome", "curso"]
    )

    assert [d.email for d in destinatarios] == ["ana@exemplo.com", "carlos@exemplo.com"]
    assert destinatarios[0].linha == 2
    assert destinatarios[0].valor("Nome") == "Ana Ribeiro"
    assert destinatarios[0].valor("carga_horaria") == "16"


def test_coluna_ausente_lista_o_que_existe(projeto: Path):
    with pytest.raises(PlanilhaInvalidaError, match="turma"):
        ler_destinatarios(ConfigPlanilha(arquivo=projeto / "planilha.csv"), ["turma"])


def test_email_invalido_falha_apontando_a_linha(tmp_path: Path):
    arquivo = tmp_path / "planilha.csv"
    arquivo.write_text("nome,email\nAna,ana-arroba-exemplo\n", encoding="utf-8")

    with pytest.raises(PlanilhaInvalidaError, match="linha 2"):
        ler_destinatarios(ConfigPlanilha(arquivo=arquivo), ["nome"])


def test_linhas_vazias_sao_ignoradas(tmp_path: Path):
    arquivo = tmp_path / "planilha.csv"
    arquivo.write_text("nome,email\nAna,ana@exemplo.com\n,\n", encoding="utf-8")

    assert len(ler_destinatarios(ConfigPlanilha(arquivo=arquivo), ["nome"])) == 1


def test_le_xlsx_formatando_data_e_numero(tmp_path: Path):
    import datetime as dt

    arquivo = tmp_path / "planilha.xlsx"
    planilha = Workbook()
    planilha.active.append(["nome", "email", "data", "horas"])
    planilha.active.append(["Ana", "ana@exemplo.com", dt.datetime(2026, 9, 12), 16.0])
    planilha.save(arquivo)

    destinatario = ler_destinatarios(ConfigPlanilha(arquivo=arquivo), ["data", "horas"])[0]

    assert destinatario.valor("data") == "12/09/2026"
    assert destinatario.valor("horas") == "16"


def test_aba_inexistente_lista_as_disponiveis(tmp_path: Path):
    arquivo = tmp_path / "planilha.xlsx"
    planilha = Workbook()
    planilha.active.title = "Participantes"
    planilha.active.append(["nome", "email"])
    planilha.save(arquivo)

    with pytest.raises(PlanilhaInvalidaError, match="Participantes"):
        ler_destinatarios(ConfigPlanilha(arquivo=arquivo, aba="Turma 2"), ["nome"])


def test_emails_repetidos(projeto: Path, tmp_path: Path):
    arquivo = tmp_path / "repetida.csv"
    arquivo.write_text(
        "nome,email\nAna,ana@exemplo.com\nAna Maria,ANA@exemplo.com\n", encoding="utf-8"
    )
    destinatarios = ler_destinatarios(ConfigPlanilha(arquivo=arquivo), ["nome"])

    assert emails_repetidos(destinatarios) == ["ana@exemplo.com"]
