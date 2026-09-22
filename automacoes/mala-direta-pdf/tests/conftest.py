"""Fixtures que montam um projeto completo em diretório temporário."""

from __future__ import annotations

from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from mala_direta.config import carregar_config

PLANILHA = """nome,E-mail,curso,carga horaria
Ana Ribeiro,ana@exemplo.com,Claude for Business,16
Carlos Mendes,carlos@exemplo.com,Claude for Business,8
"""

CONFIG = """
[planilha]
arquivo = "planilha.csv"
coluna_email = "email"

[pdf]
modelo = "modelo.pdf"
diretorio_saida = "saida/pdfs"
nome_arquivo = "certificado-{nome}.pdf"

[[pdf.campos]]
coluna = "nome"
x = 100
y = 400
tamanho = 20

[[pdf.campos]]
coluna = "curso"
x = 100
y = 360

[mensagem]
assunto = "Certificado de {curso}"
corpo_texto = "corpo.txt"
remetente_nome = "AYA Academy"

[envio]
pausa_segundos = 0
registro = "saida/registro.csv"
"""


@pytest.fixture
def modelo_pdf(tmp_path: Path) -> Path:
    destino = tmp_path / "modelo.pdf"
    folha = canvas.Canvas(str(destino), pagesize=A4)
    folha.drawString(72, 500, "Certificado")
    folha.save()
    return destino


@pytest.fixture
def projeto(tmp_path: Path, modelo_pdf: Path) -> Path:
    (tmp_path / "planilha.csv").write_text(PLANILHA, encoding="utf-8")
    (tmp_path / "corpo.txt").write_text("Olá, {nome}! Segue o certificado.\n", encoding="utf-8")
    (tmp_path / "config.toml").write_text(CONFIG, encoding="utf-8")
    return tmp_path


@pytest.fixture
def config(projeto: Path):
    return carregar_config(projeto / "config.toml")
