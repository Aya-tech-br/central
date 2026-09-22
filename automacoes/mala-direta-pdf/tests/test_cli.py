from pathlib import Path

import pytest

from mala_direta.cli import main


@pytest.fixture(autouse=True)
def sem_credenciais(monkeypatch: pytest.MonkeyPatch):
    for variavel in ("SMTP_USUARIO", "SMTP_SENHA", "SMTP_HOST", "SMTP_REMETENTE"):
        monkeypatch.delenv(variavel, raising=False)


def executar_cli(projeto: Path, *argumentos: str) -> int:
    return main(
        ["--config", str(projeto / "config.toml"), "--env", str(projeto / ".env"), *argumentos]
    )


def test_conferir_valida_e_gera_amostra(projeto: Path, capsys: pytest.CaptureFixture):
    assert executar_cli(projeto, "conferir") == 0

    saida = capsys.readouterr().out
    assert "2 linhas válidas" in saida
    assert len(list((projeto / "saida" / "pdfs").glob("*.pdf"))) == 1


def test_gerar_produz_um_pdf_por_linha(projeto: Path):
    assert executar_cli(projeto, "gerar") == 0
    assert len(list((projeto / "saida" / "pdfs").glob("*.pdf"))) == 2


def test_enviar_sem_confirmar_apenas_simula(projeto: Path, capsys: pytest.CaptureFixture):
    assert executar_cli(projeto, "enviar") == 0

    saida = capsys.readouterr().out
    assert "SIMULAÇÃO" in saida
    assert "2 simulado" in saida


def test_enviar_confirmado_sem_credenciais_explica_o_que_falta(
    projeto: Path, capsys: pytest.CaptureFixture
):
    assert executar_cli(projeto, "enviar", "--confirmar") == 1
    assert "SMTP_USUARIO" in capsys.readouterr().err


def test_grade_gera_o_pdf_com_regua(projeto: Path):
    assert executar_cli(projeto, "grade") == 0
    assert (projeto / "saida" / "pdfs" / "modelo-com-grade.pdf").is_file()


def test_inspecionar_mostra_dimensoes(projeto: Path, capsys: pytest.CaptureFixture):
    assert executar_cli(projeto, "inspecionar") == 0
    assert "210 x 297 mm" in capsys.readouterr().out


def test_planilha_invalida_retorna_codigo_de_erro(projeto: Path, capsys: pytest.CaptureFixture):
    (projeto / "planilha.csv").write_text(
        "nome,email,curso\nAna,sem-arroba,Claude\n", encoding="utf-8"
    )

    assert executar_cli(projeto, "gerar") == 1
    assert "linha 2" in capsys.readouterr().err
