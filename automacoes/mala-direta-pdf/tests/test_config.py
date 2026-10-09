from pathlib import Path

import pytest

from mala_direta.config import carregar_arquivo_env, carregar_config, carregar_credenciais_smtp
from mala_direta.erros import ConfiguracaoInvalidaError


def test_caminhos_relativos_resolvem_a_partir_do_arquivo(projeto: Path):
    config = carregar_config(projeto / "config.toml")

    assert config.pdf.modelo == projeto / "modelo.pdf"
    assert config.envio.registro == projeto / "saida" / "registro.csv"
    assert config.moldes_do_pdf == ["{nome}", "{curso}"]


def test_config_inexistente_falha_claro(tmp_path: Path):
    with pytest.raises(ConfiguracaoInvalidaError, match="não encontrado"):
        carregar_config(tmp_path / "config.toml")


def test_campo_com_chave_desconhecida_e_recusado(projeto: Path):
    arquivo = projeto / "config.toml"
    arquivo.write_text(arquivo.read_text() + '\ncoluna_extra = "x"\n', encoding="utf-8")

    with pytest.raises(ConfiguracaoInvalidaError):
        carregar_config(arquivo)


def test_cor_invalida_e_recusada(projeto: Path):
    arquivo = projeto / "config.toml"
    arquivo.write_text(
        arquivo.read_text().replace('texto = "{curso}"', 'texto = "{curso}"\ncor = "azul"'),
        encoding="utf-8",
    )

    with pytest.raises(ConfiguracaoInvalidaError, match="cor"):
        carregar_config(arquivo)


def test_credenciais_ausentes_dizem_o_que_falta():
    with pytest.raises(ConfiguracaoInvalidaError, match="SMTP_SENHA"):
        carregar_credenciais_smtp({"SMTP_USUARIO": "envio@aya.tec.br"})


def test_credenciais_usam_o_usuario_como_remetente_padrao():
    credenciais = carregar_credenciais_smtp({"SMTP_USUARIO": "envio@aya.tec.br", "SMTP_SENHA": "x"})

    assert credenciais.remetente == "envio@aya.tec.br"
    assert credenciais.host == "smtp.gmail.com"
    assert credenciais.tls is True


def test_arquivo_env_nao_sobrescreve_o_ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SMTP_USUARIO", "ja-definido@aya.tec.br")
    arquivo = tmp_path / ".env"
    arquivo.write_text(
        'SMTP_USUARIO=do-arquivo@aya.tec.br\nSMTP_SENHA="segredo"\n', encoding="utf-8"
    )

    carregar_arquivo_env(arquivo)

    assert carregar_credenciais_smtp().usuario == "ja-definido@aya.tec.br"
    assert carregar_credenciais_smtp().senha == "segredo"
