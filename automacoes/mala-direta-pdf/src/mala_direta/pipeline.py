"""Orquestração: planilha -> PDF personalizado -> e-mail com anexo, com registro de envios."""

from __future__ import annotations

import csv
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from mala_direta.config import Config
from mala_direta.envio import Anexo, EnviadorEmail, montar_mensagem
from mala_direta.erros import ConfiguracaoInvalidaError, MalaDiretaError
from mala_direta.pdf import PreenchedorPdf
from mala_direta.planilha import Destinatario, chave_de_coluna, ler_destinatarios
from mala_direta.texto import nome_de_arquivo, placeholders, preencher, validar_textos

COLUNAS_DO_REGISTRO = ("momento", "email", "linha", "arquivo", "status", "detalhe")


class Status(StrEnum):
    GERADO = "gerado"
    ENVIADO = "enviado"
    SIMULADO = "simulado"
    PULADO = "pulado"
    ERRO = "erro"


@dataclass(frozen=True)
class Resultado:
    destinatario: Destinatario
    status: Status
    arquivo: Path | None = None
    detalhe: str = ""


@dataclass(frozen=True)
class Resumo:
    resultados: list[Resultado]

    @property
    def totais(self) -> dict[Status, int]:
        return dict(Counter(resultado.status for resultado in self.resultados))

    @property
    def falhas(self) -> list[Resultado]:
        return [resultado for resultado in self.resultados if resultado.status is Status.ERRO]


class RegistroDeEnvios:
    """Histórico em CSV que torna a reexecução segura: quem já recebeu não recebe de novo."""

    def __init__(self, caminho: Path) -> None:
        self._caminho = caminho

    def ja_enviados(self) -> set[str]:
        if not self._caminho.is_file():
            return set()
        with self._caminho.open(encoding="utf-8", newline="") as arquivo:
            return {
                linha["email"].strip().lower()
                for linha in csv.DictReader(arquivo)
                if linha.get("status") == Status.ENVIADO
            }

    def anotar(self, resultado: Resultado) -> None:
        novo = not self._caminho.is_file()
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._caminho.open("a", encoding="utf-8", newline="") as arquivo:
            escritor = csv.writer(arquivo)
            if novo:
                escritor.writerow(COLUNAS_DO_REGISTRO)
            escritor.writerow(
                [
                    datetime.now().isoformat(timespec="seconds"),
                    resultado.destinatario.email,
                    resultado.destinatario.linha,
                    resultado.arquivo.name if resultado.arquivo else "",
                    resultado.status,
                    resultado.detalhe,
                ]
            )


def executar(
    config: Config,
    enviador: EnviadorEmail | None = None,
    *,
    apenas_gerar: bool = False,
    simulacao: bool = False,
    reenviar: bool = False,
    limite: int | None = None,
    somente: Iterable[str] | None = None,
    ao_progredir: Callable[[Resultado], None] | None = None,
) -> Resumo:
    """Roda o lote inteiro. Uma falha de envio não interrompe as outras linhas."""
    if not apenas_gerar and enviador is None:
        raise MalaDiretaError("Envio pedido sem um enviador configurado.")

    _recusar_valores_pendentes(config.valores)

    destinatarios = [
        _com_valores_fixos(destinatario, config.valores)
        for destinatario in ler_destinatarios(config.planilha, colunas_exigidas(config))
    ]
    corpo_texto = _ler_texto(config.mensagem.corpo_texto)
    corpo_html = _ler_texto(config.mensagem.corpo_html) if config.mensagem.corpo_html else None

    validar_textos(
        {
            "assunto": config.mensagem.assunto,
            "corpo do e-mail": corpo_texto,
            **({"corpo HTML": corpo_html} if corpo_html else {}),
            "nome do arquivo": config.pdf.nome_arquivo,
            **({"nome do anexo": config.mensagem.nome_anexo} if config.mensagem.nome_anexo else {}),
            **{
                f"campo do PDF em x={campo.x:g}, y={campo.y:g}": campo.texto
                for campo in config.pdf.campos
            },
        },
        list(destinatarios[0].valores),
    )

    preenchedor = PreenchedorPdf(config.pdf.modelo, config.pdf.campos, config.pdf.fontes)
    registro = RegistroDeEnvios(config.envio.registro)
    # O registro só barra envio duplicado. Regerar PDFs de quem já recebeu é inofensivo.
    enviados = set() if (reenviar or apenas_gerar) else registro.ja_enviados()

    remetente = enviador.remetente if enviador else "simulacao@exemplo.com"
    selecionados = _selecionar(destinatarios, somente=somente, limite=limite)
    resultados: list[Resultado] = []
    ultimo_envio_real = False

    for destinatario in selecionados:
        if destinatario.email.lower() in enviados:
            resultado = Resultado(destinatario, Status.PULADO, detalhe="já consta no registro")
        else:
            if ultimo_envio_real and config.envio.pausa_segundos:
                time.sleep(config.envio.pausa_segundos)
            resultado = _processar(
                destinatario,
                config=config,
                remetente=remetente,
                preenchedor=preenchedor,
                enviador=enviador,
                corpo_texto=corpo_texto,
                corpo_html=corpo_html,
                apenas_gerar=apenas_gerar,
                simulacao=simulacao,
            )
            ultimo_envio_real = resultado.status is Status.ENVIADO

        registro.anotar(resultado)
        resultados.append(resultado)
        if ao_progredir:
            ao_progredir(resultado)

    return Resumo(resultados=resultados)


def _processar(
    destinatario: Destinatario,
    *,
    config: Config,
    remetente: str,
    preenchedor: PreenchedorPdf,
    enviador: EnviadorEmail | None,
    corpo_texto: str,
    corpo_html: str | None,
    apenas_gerar: bool,
    simulacao: bool,
) -> Resultado:
    arquivo = config.pdf.diretorio_saida / nome_de_arquivo(config.pdf.nome_arquivo, destinatario)
    try:
        preenchedor.gerar(destinatario, arquivo)
    except MalaDiretaError as erro:
        return Resultado(destinatario, Status.ERRO, detalhe=str(erro))

    if apenas_gerar:
        return Resultado(destinatario, Status.GERADO, arquivo=arquivo)

    nome_anexo = (
        nome_de_arquivo(config.mensagem.nome_anexo, destinatario)
        if config.mensagem.nome_anexo
        else arquivo.name
    )
    mensagem = montar_mensagem(
        remetente=remetente,
        remetente_nome=config.mensagem.remetente_nome,
        destinatario=destinatario.email,
        assunto=preencher(config.mensagem.assunto, destinatario),
        corpo_texto=preencher(corpo_texto, destinatario),
        corpo_html=preencher(corpo_html, destinatario) if corpo_html else None,
        responder_para=config.mensagem.responder_para,
        anexo=Anexo.de_arquivo(arquivo, nome_anexo),
    )

    if simulacao:
        return Resultado(destinatario, Status.SIMULADO, arquivo=arquivo, detalhe="nada foi enviado")

    assert enviador is not None
    try:
        enviador.enviar(mensagem)
    except MalaDiretaError as erro:
        return Resultado(destinatario, Status.ERRO, arquivo=arquivo, detalhe=str(erro))
    return Resultado(destinatario, Status.ENVIADO, arquivo=arquivo)


def _recusar_valores_pendentes(valores: dict[str, str]) -> None:
    """Impede que um texto de exemplo ainda por preencher saia para a lista inteira."""
    pendentes = sorted(
        nome for nome, valor in valores.items() if valor.strip().upper().startswith("PREENCHER")
    )
    if pendentes:
        raise ConfiguracaoInvalidaError("Preencha antes de continuar: " + ", ".join(pendentes))


def colunas_exigidas(config: Config) -> list[str]:
    """Colunas que a planilha precisa ter: as citadas nos campos, menos as fixas."""
    fixas = {chave_de_coluna(nome) for nome in config.valores}
    exigidas: dict[str, str] = {}
    for molde in config.moldes_do_pdf:
        for coluna in sorted(placeholders(molde)):
            chave = chave_de_coluna(coluna)
            if chave not in fixas:
                exigidas.setdefault(chave, coluna)
    return list(exigidas.values())


def _com_valores_fixos(destinatario: Destinatario, fixos: dict[str, str]) -> Destinatario:
    """Completa a linha com os valores da turma, sem sobrescrever o que veio da planilha."""
    if not fixos:
        return destinatario

    conhecidas = {chave_de_coluna(titulo) for titulo in destinatario.valores}
    extras = {
        nome: valor for nome, valor in fixos.items() if chave_de_coluna(nome) not in conhecidas
    }
    if not extras:
        return destinatario
    return replace(destinatario, valores={**destinatario.valores, **extras})


def _selecionar(
    destinatarios: list[Destinatario], *, somente: Iterable[str] | None, limite: int | None
) -> list[Destinatario]:
    selecionados = destinatarios
    if somente:
        alvos = {email.strip().lower() for email in somente}
        selecionados = [d for d in selecionados if d.email.lower() in alvos]
        if not selecionados:
            raise MalaDiretaError(f"Nenhuma linha com os e-mails informados: {', '.join(alvos)}")
    if limite is not None:
        selecionados = selecionados[:limite]
    return selecionados


def _ler_texto(caminho: Path) -> str:
    if not caminho.is_file():
        raise MalaDiretaError(f"Arquivo de texto não encontrado: {caminho}")
    return caminho.read_text(encoding="utf-8")
