"""Catálogo dos modelos de certificado disponíveis na interface.

Cada modelo é uma pasta com um config.toml. Para adicionar o "Claude For
Business", basta criar a pasta com o seu config.toml e o modelo aparece na
interface, sem mexer em código.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mala_direta.config import Config, carregar_config
from mala_direta.erros import ConfiguracaoInvalidaError

IGNORADAS = ("src", "tests", "saida", "modelos", "exemplos")


@dataclass(frozen=True)
class Modelo:
    """Um modelo de certificado pronto para usar."""

    chave: str
    nome: str
    caminho_config: Path
    config: Config

    @property
    def campos_fixos(self) -> list[str]:
        """Os valores iguais para a turma, que a pessoa preenche na interface."""
        return list(self.config.valores)


def descobrir_modelos(raiz: Path) -> dict[str, Modelo]:
    """Procura pastas com config.toml dentro da raiz informada."""
    modelos: dict[str, Modelo] = {}

    for caminho in sorted(raiz.glob("*/config.toml")):
        chave = caminho.parent.name
        if chave.startswith((".", "_")) or chave in IGNORADAS:
            continue
        config = carregar_config(caminho)
        modelos[chave] = Modelo(
            chave=chave,
            nome=config.nome or chave.replace("-", " ").title(),
            caminho_config=caminho,
            config=config,
        )

    if not modelos:
        raise ConfiguracaoInvalidaError(
            f"Nenhum modelo encontrado em {raiz}. Cada modelo é uma pasta com um config.toml."
        )
    return modelos
