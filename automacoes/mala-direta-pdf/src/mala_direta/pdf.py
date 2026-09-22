"""Geração do PDF personalizado: texto posicionado por coordenadas sobre o modelo fixo."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from mala_direta.config import Alinhamento, Campo, Fonte
from mala_direta.erros import ModeloPdfInvalidoError
from mala_direta.planilha import Destinatario

PONTOS_POR_MM = 72 / 25.4


@dataclass(frozen=True)
class Pagina:
    numero: int
    largura_pt: float
    altura_pt: float

    @property
    def largura_mm(self) -> float:
        return self.largura_pt / PONTOS_POR_MM

    @property
    def altura_mm(self) -> float:
        return self.altura_pt / PONTOS_POR_MM


@dataclass(frozen=True)
class InfoModelo:
    """O que a CLI precisa contar sobre o PDF modelo antes de posicionar os campos."""

    paginas: list[Pagina]
    campos_de_formulario: list[str]


def inspecionar(modelo: Path) -> InfoModelo:
    leitor = _abrir(modelo)
    paginas = [
        Pagina(
            numero=numero,
            largura_pt=float(pagina.mediabox.width),
            altura_pt=float(pagina.mediabox.height),
        )
        for numero, pagina in enumerate(leitor.pages, start=1)
    ]
    campos = sorted((leitor.get_fields() or {}).keys())
    return InfoModelo(paginas=paginas, campos_de_formulario=campos)


class PreenchedorPdf:
    """Sobrepõe os valores de cada linha ao PDF modelo, sem alterar o layout original."""

    def __init__(
        self, modelo: Path, campos: list[Campo], fontes: list[Fonte] | None = None
    ) -> None:
        self._bytes = _ler_bytes(modelo)
        self._campos = campos
        self._modelo = modelo
        self._paginas = inspecionar(modelo).paginas
        _registrar_fontes(fontes or [])
        self._validar_campos()

    def gerar(self, destinatario: Destinatario, destino: Path) -> Path:
        """Escreve o PDF personalizado dessa pessoa e devolve o caminho gerado."""
        escritor = PdfWriter(clone_from=BytesIO(self._bytes))

        for numero, pagina in enumerate(escritor.pages, start=1):
            campos = [campo for campo in self._campos if campo.pagina == numero]
            if not campos:
                continue
            sobreposicao = _desenhar(campos, destinatario, pagina.mediabox)
            pagina.merge_page(PdfReader(sobreposicao).pages[0])

        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open("wb") as arquivo:
            escritor.write(arquivo)
        return destino

    def _validar_campos(self) -> None:
        total = len(self._paginas)
        invalidos = sorted({campo.pagina for campo in self._campos if campo.pagina > total})
        if invalidos:
            raise ModeloPdfInvalidoError(
                f"{self._modelo.name} tem {total} página(s), mas a configuração referencia a(s) "
                f"página(s) {', '.join(str(p) for p in invalidos)}."
            )
        desconhecidas = sorted(
            {campo.fonte for campo in self._campos if not _fonte_disponivel(campo.fonte)}
        )
        if desconhecidas:
            raise ModeloPdfInvalidoError(
                f"Fonte(s) não registrada(s): {', '.join(desconhecidas)}. "
                "Use uma fonte padrão (Helvetica, Times-Roman, Courier e variantes) ou declare o "
                "arquivo .ttf em [[pdf.fontes]]."
            )


def gerar_grade(modelo: Path, destino: Path, espacamento: int = 50) -> Path:
    """Copia o modelo com uma régua de coordenadas, para descobrir o x e o y de cada campo."""
    escritor = PdfWriter(clone_from=BytesIO(_ler_bytes(modelo)))

    for pagina in escritor.pages:
        pagina.merge_page(PdfReader(_desenhar_grade(pagina.mediabox, espacamento)).pages[0])

    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("wb") as arquivo:
        escritor.write(arquivo)
    return destino


def _desenhar(campos: list[Campo], destinatario: Destinatario, mediabox) -> BytesIO:
    buffer = BytesIO()
    largura, altura = float(mediabox.width), float(mediabox.height)
    folha = canvas.Canvas(buffer, pagesize=(largura, altura))
    folha.translate(float(mediabox.left), float(mediabox.bottom))

    for campo in campos:
        valor = destinatario.valor(campo.coluna)
        if not valor:
            continue
        valor = campo.formato.format(valor=valor)
        tamanho = _tamanho_que_cabe(valor, campo)
        folha.setFont(campo.fonte, tamanho)
        folha.setFillColor(HexColor(campo.cor))
        _escrever(folha, campo, valor)

    folha.save()
    buffer.seek(0)
    return buffer


def _escrever(folha: canvas.Canvas, campo: Campo, valor: str) -> None:
    if campo.alinhamento is Alinhamento.CENTRO:
        folha.drawCentredString(campo.x, campo.y, valor)
    elif campo.alinhamento is Alinhamento.DIREITA:
        folha.drawRightString(campo.x, campo.y, valor)
    else:
        folha.drawString(campo.x, campo.y, valor)


def _tamanho_que_cabe(valor: str, campo: Campo) -> float:
    """Reduz a fonte até o texto caber em `largura_maxima`, se ela foi declarada."""
    tamanho = campo.tamanho
    if campo.largura_maxima is None:
        return tamanho
    while tamanho > campo.tamanho_minimo:
        if pdfmetrics.stringWidth(valor, campo.fonte, tamanho) <= campo.largura_maxima:
            break
        tamanho -= 0.5
    return max(tamanho, campo.tamanho_minimo)


def _desenhar_grade(mediabox, espacamento: int) -> BytesIO:
    buffer = BytesIO()
    largura, altura = float(mediabox.width), float(mediabox.height)
    folha = canvas.Canvas(buffer, pagesize=(largura, altura))
    folha.translate(float(mediabox.left), float(mediabox.bottom))
    folha.setFont("Helvetica", 6)

    for x in range(0, int(largura) + 1, espacamento):
        destacado = x % (espacamento * 2) == 0
        folha.setStrokeColor(HexColor("#ff0000" if destacado else "#ff9999"))
        folha.setLineWidth(0.5 if destacado else 0.25)
        folha.line(x, 0, x, altura)
        folha.setFillColor(HexColor("#ff0000"))
        folha.drawString(x + 1, 3, str(x))

    for y in range(0, int(altura) + 1, espacamento):
        destacado = y % (espacamento * 2) == 0
        folha.setStrokeColor(HexColor("#0000ff" if destacado else "#9999ff"))
        folha.setLineWidth(0.5 if destacado else 0.25)
        folha.line(0, y, largura, y)
        folha.setFillColor(HexColor("#0000ff"))
        folha.drawString(3, y + 2, str(y))

    folha.save()
    buffer.seek(0)
    return buffer


def _fonte_disponivel(nome: str) -> bool:
    """As fontes padrão do PDF só aparecem no registro do reportlab quando pedidas."""
    try:
        pdfmetrics.getFont(nome)
    except KeyError:
        return False
    return True


def _registrar_fontes(fontes: list[Fonte]) -> None:
    for fonte in fontes:
        if fonte.nome in pdfmetrics.getRegisteredFontNames():
            continue
        if not fonte.arquivo.is_file():
            raise ModeloPdfInvalidoError(f"Arquivo de fonte não encontrado: {fonte.arquivo}")
        pdfmetrics.registerFont(TTFont(fonte.nome, str(fonte.arquivo)))


def _abrir(modelo: Path) -> PdfReader:
    return PdfReader(BytesIO(_ler_bytes(modelo)))


def _ler_bytes(modelo: Path) -> bytes:
    if not modelo.is_file():
        raise ModeloPdfInvalidoError(f"PDF modelo não encontrado: {modelo}")
    dados = modelo.read_bytes()
    try:
        PdfReader(BytesIO(dados))
    except PdfReadError as erro:
        raise ModeloPdfInvalidoError(f"Não foi possível ler {modelo.name}: {erro}") from erro
    return dados
