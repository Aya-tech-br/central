"""Substituição de placeholders `{coluna}` em assunto, corpo e nome de arquivo."""

from __future__ import annotations

import re
import unicodedata
from string import Formatter

from mala_direta.erros import TextoInvalidoError
from mala_direta.planilha import Destinatario, chave_de_coluna


class _Valores(dict):
    """Mapa de valores que aceita {Nome}, {nome} e {nome_completo} para a mesma coluna."""

    def __init__(self, destinatario: Destinatario) -> None:
        super().__init__(destinatario.valores)
        self._destinatario = destinatario

    def __missing__(self, chave: str) -> str:
        try:
            return self._destinatario.valor(chave)
        except KeyError:
            disponiveis = ", ".join(self._destinatario.valores) or "(nenhuma)"
            raise TextoInvalidoError(
                f"O campo {{{chave}}} não existe na planilha. Colunas disponíveis: {disponiveis}"
            ) from None


def preencher(modelo: str, destinatario: Destinatario) -> str:
    """Troca os `{placeholders}` pelos valores da linha."""
    try:
        return modelo.format_map(_Valores(destinatario))
    except (IndexError, ValueError) as erro:
        raise TextoInvalidoError(
            f"Texto com chaves malformadas: {modelo[:80]!r} ({erro})"
        ) from erro


def placeholders(modelo: str) -> set[str]:
    """Nomes de coluna citados no texto."""
    return {campo for _, campo, _, _ in Formatter().parse(modelo) if campo}


def validar_textos(modelos: dict[str, str], colunas: list[str]) -> None:
    """Falha antes de gerar qualquer PDF se um texto citar coluna inexistente."""
    conhecidas = {chave_de_coluna(coluna) for coluna in colunas}
    problemas = [
        f"{origem}: {{{campo}}}"
        for origem, modelo in modelos.items()
        for campo in sorted(placeholders(modelo))
        if chave_de_coluna(campo) not in conhecidas
    ]
    if problemas:
        raise TextoInvalidoError(
            "Placeholders sem coluna correspondente na planilha:\n"
            + "\n".join(f"  - {problema}" for problema in problemas)
            + f"\nColunas disponíveis: {', '.join(colunas)}"
        )


def nome_de_arquivo(modelo: str, destinatario: Destinatario) -> str:
    """Gera um nome de arquivo previsível e seguro a partir do modelo configurado."""
    bruto = preencher(modelo, destinatario)
    caule, ponto, extensao = bruto.rpartition(".")
    if not ponto:
        caule, extensao = bruto, "pdf"
    limpo = _sanitizar(caule) or _sanitizar(destinatario.email) or "documento"
    return f"{limpo}.{_sanitizar(extensao) or 'pdf'}"


def _sanitizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9._-]+", "-", sem_acento)).strip("-._")
