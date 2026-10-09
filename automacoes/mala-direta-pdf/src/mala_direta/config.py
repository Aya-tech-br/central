"""Configuração declarativa (arquivo TOML) e credenciais (variáveis de ambiente).

O TOML descreve o que é público e versionável: onde está a planilha, onde cada
campo entra no PDF, qual é o texto do e-mail. Credenciais nunca entram nele.
"""

from __future__ import annotations

import os
import re
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from mala_direta.erros import ConfiguracaoInvalidaError

HEX_COR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class Alinhamento(StrEnum):
    ESQUERDA = "esquerda"
    CENTRO = "centro"
    DIREITA = "direita"


class Campo(BaseModel):
    """Um texto variável posicionado sobre o PDF modelo.

    `texto` é um molde com os `{placeholders}` das colunas, então um campo pode
    combinar colunas ("{Nome} {Sobrenome}") ou envolver o valor em texto fixo
    ("{horas} horas"). As coordenadas seguem o padrão do PDF: origem no canto
    inferior esquerdo da página, em pontos (1 pt = 1/72 pol). O comando `grade`
    imprime uma régua sobre o seu modelo para você ler os valores de x e y.
    """

    model_config = ConfigDict(extra="forbid")

    texto: str
    x: float
    y: float
    pagina: int = Field(default=1, ge=1)
    fonte: str = "Helvetica"
    tamanho: float = Field(default=12.0, gt=0)
    cor: str = "#000000"
    alinhamento: Alinhamento = Alinhamento.ESQUERDA
    largura_maxima: float | None = Field(default=None, gt=0)
    tamanho_minimo: float = Field(default=6.0, gt=0)
    dividir_por: str | None = None
    pedaco: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validar_pedaco(self) -> Campo:
        """Serve para preencher dia, mês e ano em espaços separados do modelo."""
        if self.pedaco is not None and not self.dividir_por:
            raise ValueError('pedaco exige dividir_por, ex.: dividir_por = "/" com pedaco = 1')
        return self

    @field_validator("cor")
    @classmethod
    def _validar_cor(cls, valor: str) -> str:
        if not HEX_COR.match(valor):
            raise ValueError(f"cor deve ser hexadecimal (ex.: #1a1a1a), recebido: {valor!r}")
        return valor


class Fonte(BaseModel):
    """Fonte TrueType adicional registrada antes de desenhar os campos."""

    model_config = ConfigDict(extra="forbid")

    nome: str
    arquivo: Path


class ConfigPlanilha(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arquivo: Path
    aba: str | None = None
    coluna_email: str = "email"


class ConfigPdf(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modelo: Path
    diretorio_saida: Path = Path("saida/pdfs")
    nome_arquivo: str = "{email}.pdf"
    fontes: list[Fonte] = Field(default_factory=list)
    campos: list[Campo] = Field(min_length=1)


class ConfigMensagem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assunto: str
    corpo_texto: Path
    corpo_html: Path | None = None
    remetente_nome: str | None = None
    responder_para: str | None = None
    nome_anexo: str | None = None


class ConfigEnvio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pausa_segundos: float = Field(default=2.0, ge=0)
    registro: Path = Path("saida/registro.csv")


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planilha: ConfigPlanilha
    pdf: ConfigPdf
    mensagem: ConfigMensagem
    envio: ConfigEnvio = Field(default_factory=ConfigEnvio)
    valores: dict[str, str] = Field(default_factory=dict)
    """Valores iguais para todas as linhas (data da turma, carga horária).

    Funcionam como qualquer coluna nos moldes. A planilha tem precedência: se a
    coluna existir lá, o valor da linha é o que vale.
    """

    @property
    def moldes_do_pdf(self) -> list[str]:
        return [campo.texto for campo in self.pdf.campos]


def carregar_config(caminho: Path) -> Config:
    """Lê e valida o TOML. Caminhos relativos resolvem a partir da pasta do arquivo."""
    if not caminho.is_file():
        raise ConfiguracaoInvalidaError(f"Arquivo de configuração não encontrado: {caminho}")

    with caminho.open("rb") as arquivo:
        try:
            bruto: dict[str, Any] = tomllib.load(arquivo)
        except tomllib.TOMLDecodeError as erro:
            raise ConfiguracaoInvalidaError(f"TOML inválido em {caminho}: {erro}") from erro

    try:
        config = Config.model_validate(bruto)
    except ValidationError as erro:
        raise ConfiguracaoInvalidaError(f"Configuração inválida em {caminho}:\n{erro}") from erro

    return _resolver_caminhos(config, caminho.parent.resolve())


def _resolver_caminhos(config: Config, base: Path) -> Config:
    config.planilha.arquivo = _absoluto(base, config.planilha.arquivo)
    config.pdf.modelo = _absoluto(base, config.pdf.modelo)
    config.pdf.diretorio_saida = _absoluto(base, config.pdf.diretorio_saida)
    config.mensagem.corpo_texto = _absoluto(base, config.mensagem.corpo_texto)
    config.envio.registro = _absoluto(base, config.envio.registro)
    if config.mensagem.corpo_html is not None:
        config.mensagem.corpo_html = _absoluto(base, config.mensagem.corpo_html)
    for fonte in config.pdf.fontes:
        fonte.arquivo = _absoluto(base, fonte.arquivo)
    return config


def _absoluto(base: Path, caminho: Path) -> Path:
    return caminho if caminho.is_absolute() else (base / caminho).resolve()


class CredenciaisSmtp(BaseModel):
    """Credenciais de envio, sempre vindas do ambiente e nunca do repositório."""

    model_config = ConfigDict(extra="forbid")

    host: str = "smtp.gmail.com"
    porta: int = 587
    usuario: str
    senha: str
    remetente: str
    tls: bool = True


def carregar_credenciais_smtp(ambiente: dict[str, str] | None = None) -> CredenciaisSmtp:
    """Monta as credenciais a partir das variáveis SMTP_*, falhando cedo se faltar alguma."""
    ambiente = dict(os.environ if ambiente is None else ambiente)

    faltando = [nome for nome in ("SMTP_USUARIO", "SMTP_SENHA") if not ambiente.get(nome)]
    if faltando:
        raise ConfiguracaoInvalidaError(
            "Variáveis de ambiente ausentes: "
            + ", ".join(faltando)
            + ". Copie .env.exemplo para .env e preencha antes de enviar."
        )

    usuario = ambiente["SMTP_USUARIO"]
    return CredenciaisSmtp(
        host=ambiente.get("SMTP_HOST", "smtp.gmail.com"),
        porta=int(ambiente.get("SMTP_PORTA", "587")),
        usuario=usuario,
        senha=ambiente["SMTP_SENHA"],
        remetente=ambiente.get("SMTP_REMETENTE") or usuario,
        tls=ambiente.get("SMTP_TLS", "1").lower() not in {"0", "false", "nao", "não"},
    )


def carregar_arquivo_env(caminho: Path) -> None:
    """Carrega um .env simples no ambiente, sem sobrescrever o que já está definido."""
    if not caminho.is_file():
        return

    for linha in caminho.read_text(encoding="utf-8").splitlines():
        conteudo = linha.strip()
        if not conteudo or conteudo.startswith("#") or "=" not in conteudo:
            continue
        chave, _, valor = conteudo.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip("'\""))
