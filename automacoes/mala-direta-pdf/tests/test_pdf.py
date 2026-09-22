from pathlib import Path

import pytest
from pypdf import PdfReader

from mala_direta.config import Alinhamento, Campo
from mala_direta.erros import ModeloPdfInvalidoError
from mala_direta.pdf import PreenchedorPdf, gerar_grade, inspecionar
from mala_direta.planilha import Destinatario

ANA = Destinatario(linha=2, email="ana@exemplo.com", valores={"nome": "Ana Ribeiro", "vazio": ""})


def test_inspecionar_reporta_dimensoes_da_pagina(modelo_pdf: Path):
    info = inspecionar(modelo_pdf)

    assert len(info.paginas) == 1
    assert round(info.paginas[0].largura_mm) == 210
    assert info.campos_de_formulario == []


def test_gera_pdf_com_o_valor_da_linha(modelo_pdf: Path, tmp_path: Path):
    preenchedor = PreenchedorPdf(modelo_pdf, [Campo(coluna="nome", x=72, y=400)])
    destino = preenchedor.gerar(ANA, tmp_path / "saida" / "ana.pdf")

    texto = PdfReader(destino).pages[0].extract_text()
    assert "Ana Ribeiro" in texto
    assert "Certificado" in texto, "o conteúdo do modelo precisa ser preservado"


def test_formato_envolve_o_valor_em_texto_fixo(modelo_pdf: Path, tmp_path: Path):
    campo = Campo(coluna="nome", x=72, y=400, formato="Aluna: {valor}")
    destino = PreenchedorPdf(modelo_pdf, [campo]).gerar(ANA, tmp_path / "ana.pdf")

    assert "Aluna: Ana Ribeiro" in PdfReader(destino).pages[0].extract_text()


def test_valor_vazio_nao_desenha_nada(modelo_pdf: Path, tmp_path: Path):
    campo = Campo(coluna="vazio", x=72, y=400, formato="Turma: {valor}")
    destino = PreenchedorPdf(modelo_pdf, [campo]).gerar(ANA, tmp_path / "ana.pdf")

    assert "Turma" not in PdfReader(destino).pages[0].extract_text()


def test_largura_maxima_reduz_a_fonte_ate_caber(modelo_pdf: Path, tmp_path: Path):
    from reportlab.pdfbase import pdfmetrics

    campo = Campo(coluna="nome", x=72, y=400, tamanho=40, largura_maxima=100)
    PreenchedorPdf(modelo_pdf, [campo]).gerar(ANA, tmp_path / "ana.pdf")

    from mala_direta.pdf import _tamanho_que_cabe

    tamanho = _tamanho_que_cabe("Ana Ribeiro", campo)
    assert tamanho < 40
    assert pdfmetrics.stringWidth("Ana Ribeiro", campo.fonte, tamanho) <= 100


def test_pagina_inexistente_falha_na_construcao(modelo_pdf: Path):
    with pytest.raises(ModeloPdfInvalidoError, match="página"):
        PreenchedorPdf(modelo_pdf, [Campo(coluna="nome", x=1, y=1, pagina=3)])


def test_fonte_desconhecida_falha_na_construcao(modelo_pdf: Path):
    with pytest.raises(ModeloPdfInvalidoError, match="Fonte"):
        PreenchedorPdf(modelo_pdf, [Campo(coluna="nome", x=1, y=1, fonte="Comic Sans")])


def test_modelo_inexistente_falha_com_caminho(tmp_path: Path):
    with pytest.raises(ModeloPdfInvalidoError, match="não encontrado"):
        PreenchedorPdf(tmp_path / "ausente.pdf", [Campo(coluna="nome", x=1, y=1)])


def test_alinhamento_direita_desloca_o_texto(modelo_pdf: Path, tmp_path: Path):
    campo = Campo(coluna="nome", x=500, y=400, alinhamento=Alinhamento.DIREITA)
    destino = PreenchedorPdf(modelo_pdf, [campo]).gerar(ANA, tmp_path / "ana.pdf")

    assert "Ana Ribeiro" in PdfReader(destino).pages[0].extract_text()


def test_grade_gera_regua_sobre_o_modelo(modelo_pdf: Path, tmp_path: Path):
    destino = gerar_grade(modelo_pdf, tmp_path / "grade.pdf", espacamento=100)

    texto = PdfReader(destino).pages[0].extract_text()
    assert "100" in texto and "Certificado" in texto
