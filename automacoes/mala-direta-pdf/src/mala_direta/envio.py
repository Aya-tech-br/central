"""Montagem e entrega das mensagens.

O pipeline depende do protocolo `EnviadorEmail`, não do smtplib. Trocar SMTP pela
API do Gmail ou por um serviço transacional é escrever outra implementação deste
protocolo, sem tocar no resto do sistema.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from typing import Protocol

from mala_direta.config import CredenciaisSmtp
from mala_direta.erros import EnvioError


@dataclass(frozen=True)
class Anexo:
    nome: str
    conteudo: bytes

    @classmethod
    def de_arquivo(cls, caminho: Path, nome: str | None = None) -> Anexo:
        return cls(nome=nome or caminho.name, conteudo=caminho.read_bytes())


def montar_mensagem(
    *,
    remetente: str,
    destinatario: str,
    assunto: str,
    corpo_texto: str,
    anexo: Anexo | None = None,
    corpo_html: str | None = None,
    remetente_nome: str | None = None,
    responder_para: str | None = None,
) -> EmailMessage:
    """Monta a mensagem multipart com o PDF anexado."""
    mensagem = EmailMessage()
    mensagem["From"] = _endereco(remetente, remetente_nome)
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto
    if responder_para:
        mensagem["Reply-To"] = responder_para

    mensagem.set_content(corpo_texto)
    if corpo_html:
        mensagem.add_alternative(corpo_html, subtype="html")
    if anexo:
        mensagem.add_attachment(
            anexo.conteudo, maintype="application", subtype="pdf", filename=anexo.nome
        )
    return mensagem


class EnviadorEmail(Protocol):
    """Contrato de entrega. Uma implementação por canal de envio."""

    @property
    def remetente(self) -> str:
        """Endereço que assina as mensagens deste canal."""
        ...

    def enviar(self, mensagem: EmailMessage) -> None: ...

    def fechar(self) -> None: ...


class EnviadorSmtp:
    """Entrega por SMTP autenticado (Gmail/Workspace com senha de app, Outlook, etc.)."""

    def __init__(self, credenciais: CredenciaisSmtp) -> None:
        self._credenciais = credenciais
        self._conexao: smtplib.SMTP | None = None

    @property
    def remetente(self) -> str:
        return self._credenciais.remetente

    def __enter__(self) -> EnviadorSmtp:
        return self

    def __exit__(self, *_: object) -> None:
        self.fechar()

    def enviar(self, mensagem: EmailMessage) -> None:
        try:
            self._conectar().send_message(mensagem)
        except smtplib.SMTPServerDisconnected:
            self.fechar()
            try:
                self._conectar().send_message(mensagem)
            except smtplib.SMTPException as erro:
                raise EnvioError(_explicar(erro)) from erro
        except smtplib.SMTPException as erro:
            raise EnvioError(_explicar(erro)) from erro
        except OSError as erro:
            raise EnvioError(
                f"Falha de rede ao falar com {self._credenciais.host}: {erro}"
            ) from erro

    def fechar(self) -> None:
        if self._conexao is None:
            return
        try:
            self._conexao.quit()
        except smtplib.SMTPException:
            pass
        finally:
            self._conexao = None

    def _conectar(self) -> smtplib.SMTP:
        if self._conexao is not None:
            return self._conexao

        credenciais = self._credenciais
        try:
            conexao = smtplib.SMTP(credenciais.host, credenciais.porta, timeout=30)
            conexao.ehlo()
            if credenciais.tls:
                conexao.starttls()
                conexao.ehlo()
            conexao.login(credenciais.usuario, credenciais.senha)
        except smtplib.SMTPAuthenticationError as erro:
            raise EnvioError(
                "Servidor recusou as credenciais. Em contas Google, use uma senha de app "
                f"(16 caracteres) com a verificação em duas etapas ativa. Detalhe: {erro}"
            ) from erro
        except (smtplib.SMTPException, OSError) as erro:
            raise EnvioError(
                f"Não foi possível conectar em {credenciais.host}:{credenciais.porta} ({erro})"
            ) from erro

        self._conexao = conexao
        return conexao


@dataclass
class EnviadorSimulado:
    """Registra as mensagens em memória, para simulações e testes."""

    remetente: str = "simulacao@exemplo.com"
    enviadas: list[EmailMessage] = field(default_factory=list)

    def enviar(self, mensagem: EmailMessage) -> None:
        self.enviadas.append(mensagem)

    def fechar(self) -> None:
        return None


def _endereco(email: str, nome: str | None) -> str:
    if not nome:
        return email
    usuario, _, dominio = parseaddr(email)[1].partition("@")
    return str(Address(nome, usuario, dominio))


def _explicar(erro: smtplib.SMTPException) -> str:
    if isinstance(erro, smtplib.SMTPRecipientsRefused):
        recusados = ", ".join(erro.recipients)
        return f"Destinatário recusado pelo servidor: {recusados}"
    if isinstance(erro, smtplib.SMTPDataError) and erro.smtp_code == 552:
        return (
            "Mensagem recusada por tamanho: o anexo excede o limite do provedor (25 MB no Gmail)."
        )
    return f"Servidor SMTP recusou a mensagem: {erro}"
