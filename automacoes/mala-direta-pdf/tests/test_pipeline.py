import csv
from email.message import EmailMessage
from pathlib import Path

import pytest

from mala_direta.config import Config
from mala_direta.envio import EnviadorSimulado
from mala_direta.erros import (
    EnvioError,
    MalaDiretaError,
    PlanilhaInvalidaError,
    TextoInvalidoError,
)
from mala_direta.pipeline import Status, executar


class EnviadorQueFalha(EnviadorSimulado):
    """Enviador que recusa um endereço específico, como um servidor faria."""

    def __init__(self, endereco_ruim: str) -> None:
        super().__init__()
        self._ruim = endereco_ruim

    def enviar(self, mensagem: EmailMessage) -> None:
        if mensagem["To"] == self._ruim:
            raise EnvioError("caixa postal cheia")
        super().enviar(mensagem)


def test_envia_um_email_por_linha_com_o_pdf_da_pessoa(config: Config):
    enviador = EnviadorSimulado()

    resumo = executar(config, enviador)

    assert resumo.totais == {Status.ENVIADO: 2}
    assert [m["To"] for m in enviador.enviadas] == ["ana@exemplo.com", "carlos@exemplo.com"]
    assert enviador.enviadas[0]["Subject"] == "Certificado de Claude for Business"

    anexo = next(enviador.enviadas[0].iter_attachments())
    assert anexo.get_filename() == "certificado-Ana-Ribeiro.pdf"
    assert anexo.get_payload(decode=True).startswith(b"%PDF")
    assert (config.pdf.diretorio_saida / "certificado-Ana-Ribeiro.pdf").is_file()


def test_reexecucao_pula_quem_ja_recebeu(config: Config):
    executar(config, EnviadorSimulado())

    enviador = EnviadorSimulado()
    resumo = executar(config, enviador)

    assert resumo.totais == {Status.PULADO: 2}
    assert enviador.enviadas == []


def test_reenviar_ignora_o_registro(config: Config):
    executar(config, EnviadorSimulado())

    enviador = EnviadorSimulado()
    resumo = executar(config, enviador, reenviar=True)

    assert resumo.totais == {Status.ENVIADO: 2}
    assert len(enviador.enviadas) == 2


def test_falha_em_uma_linha_nao_interrompe_o_lote(config: Config):
    enviador = EnviadorQueFalha("ana@exemplo.com")

    resumo = executar(config, enviador)

    assert resumo.totais == {Status.ERRO: 1, Status.ENVIADO: 1}
    assert [m["To"] for m in enviador.enviadas] == ["carlos@exemplo.com"]
    assert resumo.falhas[0].detalhe == "caixa postal cheia"


def test_linha_com_erro_pode_ser_reprocessada_sem_duplicar_envio(config: Config):
    executar(config, EnviadorQueFalha("ana@exemplo.com"))

    enviador = EnviadorSimulado()
    resumo = executar(config, enviador)

    assert resumo.totais == {Status.ENVIADO: 1, Status.PULADO: 1}
    assert [m["To"] for m in enviador.enviadas] == ["ana@exemplo.com"]


def test_simulacao_monta_tudo_mas_nao_entrega(config: Config):
    enviador = EnviadorSimulado()

    resumo = executar(config, enviador, simulacao=True)

    assert resumo.totais == {Status.SIMULADO: 2}
    assert enviador.enviadas == []
    assert list(config.pdf.diretorio_saida.glob("*.pdf"))


def test_simulacao_nao_bloqueia_o_envio_real_depois(config: Config):
    executar(config, EnviadorSimulado(), simulacao=True)

    resumo = executar(config, EnviadorSimulado())

    assert resumo.totais == {Status.ENVIADO: 2}


def test_apenas_gerar_nao_pede_enviador(config: Config):
    resumo = executar(config, apenas_gerar=True)

    assert resumo.totais == {Status.GERADO: 2}


def test_gerar_nao_e_bloqueado_pelo_registro_de_envios(config: Config):
    executar(config, EnviadorSimulado())

    resumo = executar(config, apenas_gerar=True)

    assert resumo.totais == {Status.GERADO: 2}


def test_somente_restringe_aos_enderecos_informados(config: Config):
    enviador = EnviadorSimulado()

    executar(config, enviador, somente=["CARLOS@exemplo.com"])

    assert [m["To"] for m in enviador.enviadas] == ["carlos@exemplo.com"]


def test_somente_sem_correspondencia_falha(config: Config):
    with pytest.raises(MalaDiretaError, match="Nenhuma linha"):
        executar(config, EnviadorSimulado(), somente=["ninguem@exemplo.com"])


def test_limite_processa_o_comeco_da_planilha(config: Config):
    enviador = EnviadorSimulado()

    executar(config, enviador, limite=1)

    assert [m["To"] for m in enviador.enviadas] == ["ana@exemplo.com"]


def test_registro_guarda_uma_linha_por_destinatario(config: Config):
    executar(config, EnviadorSimulado())

    with config.envio.registro.open(encoding="utf-8") as arquivo:
        linhas = list(csv.DictReader(arquivo))

    assert [linha["email"] for linha in linhas] == ["ana@exemplo.com", "carlos@exemplo.com"]
    assert {linha["status"] for linha in linhas} == {Status.ENVIADO}
    assert linhas[0]["arquivo"] == "certificado-Ana-Ribeiro.pdf"


def test_texto_com_coluna_inexistente_falha_antes_de_gerar_pdf(config: Config, projeto: Path):
    config.mensagem.assunto = "Certificado de {turma}"

    with pytest.raises(TextoInvalidoError, match="turma"):
        executar(config, EnviadorSimulado())

    assert not list(config.pdf.diretorio_saida.glob("*.pdf"))


def test_valores_fixos_completam_as_colunas_que_faltam(config: Config, projeto: Path):
    """Data e carga horária são iguais para a turma, então não precisam estar na planilha."""
    arquivo = projeto / "config.toml"
    arquivo.write_text(
        arquivo.read_text().replace(
            '[[pdf.campos]]\ntexto = "{curso}"\nx = 100\ny = 360',
            '[[pdf.campos]]\ntexto = "{data} | {carga horaria} horas"\nx = 100\ny = 360',
        )
        + '\n[valores]\ndata = "09/10/2026"\n"carga horaria" = "16"\n',
        encoding="utf-8",
    )
    from mala_direta.config import carregar_config

    atualizado = carregar_config(arquivo)
    enviador = EnviadorSimulado()

    resumo = executar(atualizado, enviador, apenas_gerar=False)

    assert resumo.totais == {Status.ENVIADO: 2}
    from pypdf import PdfReader

    texto = PdfReader(atualizado.pdf.diretorio_saida / "certificado-Ana-Ribeiro.pdf").pages[0]
    assert "09/10/2026 | 16 horas" in texto.extract_text()


def test_planilha_tem_precedencia_sobre_valor_fixo(config: Config):
    config.valores["curso"] = "Valor que não deve aparecer"
    enviador = EnviadorSimulado()

    executar(config, enviador)

    assert enviador.enviadas[0]["Subject"] == "Certificado de Claude for Business"


def test_coluna_que_nao_existe_nem_como_valor_fixo_falha(config: Config):
    config.pdf.campos[0].texto = "{turma}"

    with pytest.raises(PlanilhaInvalidaError, match="turma"):
        executar(config, EnviadorSimulado())
