"""Testes do canal por API. Nenhuma requisição sai: o transporte HTTP é injetado."""

from __future__ import annotations

import base64
import json

import pytest

from mala_direta.canais import EnviadorResend, criar_enviador
from mala_direta.envio import Anexo, EnviadorSmtp, montar_mensagem
from mala_direta.erros import ConfiguracaoInvalidaError, EnvioError

AMBIENTE_RESEND = {
    "EMAIL_CANAL": "resend",
    "RESEND_API_KEY": "re_chave_de_teste",
    "EMAIL_REMETENTE": "AYA Academy <no-reply@ayatech.co>",
}


def mensagem():
    return montar_mensagem(
        remetente="no-reply@ayatech.co",
        remetente_nome="AYA Academy",
        destinatario="ana@exemplo.com",
        assunto="Seu certificado",
        corpo_texto="Olá, Ana!",
        corpo_html="<p>Olá, Ana!</p>",
        anexo=Anexo(nome="certificado.pdf", conteudo=b"%PDF-1.4 conteudo"),
    )


class TransporteFalso:
    def __init__(self, codigo: int = 200, resposta: str = '{"id": "abc"}') -> None:
        self.codigo = codigo
        self.resposta = resposta
        self.chamadas: list[tuple[dict, dict[str, str]]] = []

    def __call__(self, corpo: bytes, cabecalhos: dict[str, str]) -> tuple[int, str]:
        self.chamadas.append((json.loads(corpo), cabecalhos))
        return self.codigo, self.resposta


def test_payload_leva_texto_html_e_anexo_em_base64():
    transporte = TransporteFalso()
    enviador = EnviadorResend(chave="re_chave", endereco="x", enviar_http=transporte)

    enviador.enviar(mensagem())

    corpo, cabecalhos = transporte.chamadas[0]
    assert cabecalhos["Authorization"] == "Bearer re_chave"
    assert corpo["from"] == "AYA Academy <no-reply@ayatech.co>"
    assert corpo["to"] == ["ana@exemplo.com"]
    assert corpo["subject"] == "Seu certificado"
    assert "Olá, Ana!" in corpo["text"]
    assert corpo["html"].strip().startswith("<p>")

    anexo = corpo["attachments"][0]
    assert anexo["filename"] == "certificado.pdf"
    assert base64.b64decode(anexo["content"]) == b"%PDF-1.4 conteudo"


def test_chave_recusada_vira_erro_explicito():
    enviador = EnviadorResend("re_x", "x", enviar_http=TransporteFalso(401, "unauthorized"))

    with pytest.raises(EnvioError, match="chave de API"):
        enviador.enviar(mensagem())


@pytest.mark.parametrize("codigo", [403, 422])
def test_dominio_nao_verificado_e_explicado(codigo: int):
    enviador = EnviadorResend("re_x", "x", enviar_http=TransporteFalso(codigo, "domain not found"))

    with pytest.raises(EnvioError, match="domínio do remetente"):
        enviador.enviar(mensagem())


def test_erro_generico_mostra_a_resposta():
    enviador = EnviadorResend("re_x", "x", enviar_http=TransporteFalso(500, "indisponível"))

    with pytest.raises(EnvioError, match="500"):
        enviador.enviar(mensagem())


def test_fabrica_escolhe_resend():
    enviador = criar_enviador(AMBIENTE_RESEND)

    assert isinstance(enviador, EnviadorResend)
    assert enviador.remetente == "AYA Academy <no-reply@ayatech.co>"


def test_fabrica_escolhe_smtp_por_padrao():
    enviador = criar_enviador({"SMTP_USUARIO": "envio@aya.tec.br", "SMTP_SENHA": "x"})

    assert isinstance(enviador, EnviadorSmtp)


def test_resend_sem_chave_diz_o_que_falta():
    with pytest.raises(ConfiguracaoInvalidaError, match="RESEND_API_KEY"):
        criar_enviador({"EMAIL_CANAL": "resend", "EMAIL_REMETENTE": "no-reply@ayatech.co"})


def test_canal_desconhecido_e_recusado():
    with pytest.raises(ConfiguracaoInvalidaError, match="EMAIL_CANAL"):
        criar_enviador({"EMAIL_CANAL": "pombo-correio"})
