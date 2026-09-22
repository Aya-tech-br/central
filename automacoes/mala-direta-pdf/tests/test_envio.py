import smtplib
from unittest.mock import MagicMock

import pytest

from mala_direta.config import CredenciaisSmtp
from mala_direta.envio import Anexo, EnviadorSmtp, montar_mensagem
from mala_direta.erros import EnvioError

CREDENCIAIS = CredenciaisSmtp(
    usuario="envio@aya.tec.br", senha="senha-de-app", remetente="envio@aya.tec.br"
)


def mensagem_exemplo():
    return montar_mensagem(
        remetente="envio@aya.tec.br",
        remetente_nome="AYA Academy",
        destinatario="ana@exemplo.com",
        assunto="Seu certificado",
        corpo_texto="Olá, Ana!",
        corpo_html="<p>Olá, Ana!</p>",
        responder_para="contato@aya.tec.br",
        anexo=Anexo(nome="certificado.pdf", conteudo=b"%PDF-1.4 conteudo"),
    )


def test_mensagem_leva_texto_html_e_anexo():
    mensagem = mensagem_exemplo()

    assert mensagem["From"] == "AYA Academy <envio@aya.tec.br>"
    assert mensagem["To"] == "ana@exemplo.com"
    assert mensagem["Reply-To"] == "contato@aya.tec.br"

    anexos = list(mensagem.iter_attachments())
    assert [anexo.get_filename() for anexo in anexos] == ["certificado.pdf"]
    assert anexos[0].get_content_type() == "application/pdf"
    assert mensagem.get_body(("html",)) is not None
    assert "Olá, Ana!" in mensagem.get_body(("plain",)).get_content()


def test_credenciais_recusadas_viram_erro_com_dica(monkeypatch: pytest.MonkeyPatch):
    conexao = MagicMock()
    conexao.login.side_effect = smtplib.SMTPAuthenticationError(535, b"invalid")
    monkeypatch.setattr(smtplib, "SMTP", lambda *_, **__: conexao)

    with pytest.raises(EnvioError, match="senha de app"):
        EnviadorSmtp(CREDENCIAIS).enviar(mensagem_exemplo())


def test_reconecta_uma_vez_quando_o_servidor_derruba(monkeypatch: pytest.MonkeyPatch):
    conexao = MagicMock()
    conexao.send_message.side_effect = [smtplib.SMTPServerDisconnected(), None]
    monkeypatch.setattr(smtplib, "SMTP", lambda *_, **__: conexao)

    EnviadorSmtp(CREDENCIAIS).enviar(mensagem_exemplo())

    assert conexao.send_message.call_count == 2
    assert conexao.login.call_count == 2


def test_destinatario_recusado_nomeia_o_endereco(monkeypatch: pytest.MonkeyPatch):
    conexao = MagicMock()
    conexao.send_message.side_effect = smtplib.SMTPRecipientsRefused(
        {"ana@exemplo.com": (550, b"no such user")}
    )
    monkeypatch.setattr(smtplib, "SMTP", lambda *_, **__: conexao)

    with pytest.raises(EnvioError, match="ana@exemplo.com"):
        EnviadorSmtp(CREDENCIAIS).enviar(mensagem_exemplo())


def test_conexao_reaproveitada_entre_envios(monkeypatch: pytest.MonkeyPatch):
    conexao = MagicMock()
    monkeypatch.setattr(smtplib, "SMTP", lambda *_, **__: conexao)

    with EnviadorSmtp(CREDENCIAIS) as enviador:
        enviador.enviar(mensagem_exemplo())
        enviador.enviar(mensagem_exemplo())

    assert conexao.login.call_count == 1
    assert conexao.starttls.call_count == 1
    assert conexao.quit.call_count == 1
