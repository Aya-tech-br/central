"""Gera o modelo.pdf de exemplo (um certificado em branco, A4 paisagem).

Serve só para a pasta de exemplos funcionar de ponta a ponta. No seu caso real,
o modelo é o PDF fechado que o design já entregou.
"""

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

DESTINO = Path(__file__).parent / "modelo.pdf"


def gerar(destino: Path = DESTINO) -> Path:
    largura, altura = landscape(A4)
    folha = canvas.Canvas(str(destino), pagesize=(largura, altura))

    folha.setStrokeColor(HexColor("#12263f"))
    folha.setLineWidth(3)
    folha.rect(30, 30, largura - 60, altura - 60)

    folha.setFillColor(HexColor("#12263f"))
    folha.setFont("Helvetica-Bold", 34)
    folha.drawCentredString(largura / 2, altura - 130, "CERTIFICADO")

    folha.setFont("Helvetica", 13)
    folha.setFillColor(HexColor("#44546a"))
    folha.drawCentredString(largura / 2, altura - 170, "Certificamos que")
    folha.drawCentredString(largura / 2, 298, "concluiu o treinamento")

    folha.setLineWidth(0.75)
    folha.setStrokeColor(HexColor("#c9d3df"))
    folha.line(180, 195, largura - 180, 195)
    folha.drawCentredString(largura / 2, 178, "Coordenação AYA Academy")

    folha.save()
    return destino


if __name__ == "__main__":
    print(f"Modelo de exemplo gerado em {gerar()}")
