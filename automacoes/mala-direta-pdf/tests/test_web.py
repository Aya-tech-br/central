"""Testes da interface web. Nenhum e-mail sai: o enviador é um dublê."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mala_direta.envio import EnviadorSimulado
from mala_direta.erros import ConfiguracaoInvalidaError
from mala_direta.web.app import criar_app
from mala_direta.web.seguranca import Autenticacao, carregar_autenticacao, gerar_hash

SENHA = "senha-de-teste-123"
CHAVE = "chave-secreta-com-mais-de-trinta-e-dois-caracteres"


@pytest.fixture
def autenticacao() -> Autenticacao:
    return Autenticacao(usuarios={"veronica": gerar_hash(SENHA)}, chave_secreta=CHAVE)


@pytest.fixture
def raiz(projeto: Path, tmp_path: Path) -> Path:
    """Uma raiz com um modelo chamado 'certificado', nos moldes da pasta real."""
    raiz = tmp_path / "raiz"
    destino = raiz / "certificado"
    destino.mkdir(parents=True)
    for arquivo in ("config.toml", "modelo.pdf", "corpo.txt", "planilha.csv"):
        shutil.copy(projeto / arquivo, destino / arquivo)

    config = destino / "config.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "[planilha]",
            'nome = "Certificado de teste"\n\n[valores]\ndata = "09/10/2026"\n\n[planilha]',
        ),
        encoding="utf-8",
    )
    return raiz


@pytest.fixture
def enviador() -> EnviadorSimulado:
    return EnviadorSimulado(remetente="envio@aya.tec.br")


@pytest.fixture
def cliente(raiz: Path, autenticacao: Autenticacao, enviador: EnviadorSimulado) -> TestClient:
    app = criar_app(raiz_modelos=raiz, autenticacao=autenticacao, criar_enviador=lambda: enviador)
    return TestClient(app, follow_redirects=False)


def entrar(cliente: TestClient) -> None:
    resposta = cliente.post("/entrar", data={"usuario": "veronica", "senha": SENHA})
    assert resposta.status_code == 303


def planilha(raiz: Path) -> dict:
    caminho = raiz / "certificado" / "planilha.csv"
    return {"planilha": ("participantes.csv", caminho.read_bytes(), "text/csv")}


def test_painel_exige_sessao(cliente: TestClient):
    resposta = cliente.get("/")

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_senha_errada_nao_abre_sessao(cliente: TestClient):
    resposta = cliente.post("/entrar", data={"usuario": "veronica", "senha": "errada"})

    assert resposta.status_code == 401
    assert "incorretos" in resposta.text


def test_usuario_inexistente_recebe_a_mesma_resposta(cliente: TestClient):
    resposta = cliente.post("/entrar", data={"usuario": "ninguem", "senha": SENHA})

    assert resposta.status_code == 401
    assert "incorretos" in resposta.text


def test_tentativas_repetidas_sao_bloqueadas(cliente: TestClient):
    for _ in range(5):
        cliente.post("/entrar", data={"usuario": "veronica", "senha": "errada"})

    resposta = cliente.post("/entrar", data={"usuario": "veronica", "senha": SENHA})

    assert resposta.status_code == 429


def test_cookie_de_sessao_e_httponly(cliente: TestClient):
    resposta = cliente.post("/entrar", data={"usuario": "veronica", "senha": SENHA})

    cabecalho = resposta.headers["set-cookie"]
    assert "HttpOnly" in cabecalho
    assert "samesite=lax" in cabecalho.lower()


def test_painel_lista_os_modelos_e_os_campos_da_turma(cliente: TestClient):
    entrar(cliente)

    resposta = cliente.get("/")

    assert resposta.status_code == 200
    assert "Certificado de teste" in resposta.text
    assert 'name="valor:data"' in resposta.text


def test_amostra_devolve_um_pdf(cliente: TestClient, raiz: Path):
    entrar(cliente)

    resposta = cliente.post(
        "/amostra",
        data={"modelo": "certificado", "valor:data": "09/10/2026"},
        files=planilha(raiz),
    )

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.content.startswith(b"%PDF")


def test_envio_sem_confirmacao_e_recusado(cliente: TestClient, raiz: Path, enviador):
    entrar(cliente)

    resposta = cliente.post("/enviar", data={"modelo": "certificado"}, files=planilha(raiz))

    assert resposta.status_code == 400
    assert "confirma" in resposta.text.lower()
    assert enviador.enviadas == []


def test_envio_confirmado_dispara_um_email_por_linha(
    cliente: TestClient, raiz: Path, enviador: EnviadorSimulado
):
    entrar(cliente)

    resposta = cliente.post(
        "/enviar",
        data={"modelo": "certificado", "confirmar": "sim", "valor:data": "09/10/2026"},
        files=planilha(raiz),
    )
    assert resposta.status_code == 303

    identificador = resposta.headers["location"].rsplit("/", 1)[-1]
    estado = cliente.get(f"/envio/{identificador}/estado").json()

    assert estado["total"] == 2
    assert estado["concluida"] is True
    assert [linha["status"] for linha in estado["linhas"]] == ["enviado", "enviado"]
    assert [m["To"] for m in enviador.enviadas] == ["ana@exemplo.com", "carlos@exemplo.com"]


def test_planilha_de_formato_errado_e_recusada(cliente: TestClient):
    entrar(cliente)

    resposta = cliente.post(
        "/enviar",
        data={"modelo": "certificado", "confirmar": "sim"},
        files={"planilha": ("lista.txt", b"nome,email", "text/plain")},
    )

    assert resposta.status_code == 400
    assert "Formato não suportado" in resposta.text


def test_modelo_desconhecido_e_recusado(cliente: TestClient, raiz: Path):
    entrar(cliente)

    resposta = cliente.post("/amostra", data={"modelo": "inexistente"}, files=planilha(raiz))

    assert resposta.status_code == 400


def test_registro_so_sai_com_sessao(cliente: TestClient):
    assert cliente.get("/registro/certificado").status_code == 303


def test_ambiente_sem_credenciais_falha_claro():
    with pytest.raises(ConfiguracaoInvalidaError, match="MALA_DIRETA_USUARIOS"):
        carregar_autenticacao({})


def test_chave_secreta_curta_e_recusada():
    with pytest.raises(ConfiguracaoInvalidaError, match="32 caracteres"):
        carregar_autenticacao({"MALA_DIRETA_USUARIOS": "a:b", "MALA_DIRETA_CHAVE_SECRETA": "curta"})


def test_sessao_assinada_nao_aceita_token_adulterado(autenticacao: Autenticacao):
    token = autenticacao.criar_sessao("veronica")

    assert autenticacao.ler_sessao(token) == "veronica"
    assert autenticacao.ler_sessao(token + "x") is None
    assert autenticacao.ler_sessao(None) is None
