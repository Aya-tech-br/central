"""Canais de entrega disponíveis e a escolha entre eles.

Cada canal implementa o protocolo `EnviadorEmail`. O resto do sistema não sabe
qual está em uso: trocar SMTP por API é mudar uma variável de ambiente.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from email.message import EmailMessage

from mala_direta.config import carregar_credenciais_smtp
from mala_direta.envio import EnviadorEmail, EnviadorSmtp
from mala_direta.erros import ConfiguracaoInvalidaError, EnvioError

URL_RESEND = "https://api.resend.com/emails"
TEMPO_LIMITE = 30


def criar_enviador(ambiente: dict[str, str] | None = None) -> EnviadorEmail:
    """Monta o canal indicado por EMAIL_CANAL: 'smtp' (padrão) ou 'resend'."""
    ambiente = dict(os.environ if ambiente is None else ambiente)
    canal = ambiente.get("EMAIL_CANAL", "smtp").strip().lower()

    if canal == "smtp":
        return EnviadorSmtp(carregar_credenciais_smtp(ambiente))
    if canal == "resend":
        return EnviadorResend.do_ambiente(ambiente)
    raise ConfiguracaoInvalidaError(f"EMAIL_CANAL desconhecido: {canal!r}. Use 'smtp' ou 'resend'.")


@dataclass
class EnviadorResend:
    """Entrega pela API da Resend: uma chave no lugar de senha de app.

    Útil quando o domínio do remetente não é o mesmo da conta que autentica, que
    é justamente o caso de um no-reply em domínio próprio.
    """

    chave: str
    endereco: str
    enviar_http: Callable[[bytes, dict[str, str]], tuple[int, str]] | None = None

    @classmethod
    def do_ambiente(cls, ambiente: dict[str, str]) -> EnviadorResend:
        faltando = [
            nome for nome in ("RESEND_API_KEY", "EMAIL_REMETENTE") if not ambiente.get(nome)
        ]
        if faltando:
            raise ConfiguracaoInvalidaError(
                "Variáveis de ambiente ausentes: "
                + ", ".join(faltando)
                + ". A chave sai do painel da Resend e o remetente precisa estar num "
                "domínio verificado lá."
            )
        return cls(chave=ambiente["RESEND_API_KEY"], endereco=ambiente["EMAIL_REMETENTE"])

    @property
    def remetente(self) -> str:
        return self.endereco

    def enviar(self, mensagem: EmailMessage) -> None:
        corpo = json.dumps(_payload(mensagem)).encode("utf-8")
        cabecalhos = {
            "Authorization": f"Bearer {self.chave}",
            "Content-Type": "application/json",
        }

        codigo, resposta = (self.enviar_http or _postar)(corpo, cabecalhos)
        if codigo == 401:
            raise EnvioError("A Resend recusou a chave de API (401). Gere outra no painel.")
        if codigo in (403, 422):
            raise EnvioError(
                f"A Resend recusou a mensagem ({codigo}). O caso mais comum é o domínio do "
                f"remetente ainda não verificado no painel. Resposta: {resposta[:300]}"
            )
        if codigo >= 400:
            raise EnvioError(f"A Resend respondeu {codigo}: {resposta[:300]}")

    def fechar(self) -> None:
        return None


def _payload(mensagem: EmailMessage) -> dict[str, object]:
    """Traduz a mensagem MIME para o corpo que a API espera."""
    import base64

    texto = mensagem.get_body(("plain",))
    html = mensagem.get_body(("html",))

    conteudo: dict[str, object] = {
        "from": mensagem["From"],
        "to": [mensagem["To"]],
        "subject": mensagem["Subject"],
    }
    if texto is not None:
        conteudo["text"] = texto.get_content()
    if html is not None:
        conteudo["html"] = html.get_content()
    if mensagem["Reply-To"]:
        conteudo["reply_to"] = mensagem["Reply-To"]

    anexos = [
        {
            "filename": anexo.get_filename() or "anexo.pdf",
            "content": base64.b64encode(anexo.get_payload(decode=True)).decode("ascii"),
        }
        for anexo in mensagem.iter_attachments()
    ]
    if anexos:
        conteudo["attachments"] = anexos
    return conteudo


def _postar(corpo: bytes, cabecalhos: dict[str, str]) -> tuple[int, str]:
    requisicao = urllib.request.Request(URL_RESEND, data=corpo, headers=cabecalhos, method="POST")
    try:
        with urllib.request.urlopen(requisicao, timeout=TEMPO_LIMITE) as resposta:
            return resposta.status, resposta.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as erro:
        return erro.code, erro.read().decode("utf-8", "replace")
    except urllib.error.URLError as erro:
        raise EnvioError(f"Não foi possível falar com a API da Resend: {erro.reason}") from erro
