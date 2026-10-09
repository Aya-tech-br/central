"""Interface de linha de comando.

Camada fina: interpreta argumentos, chama o pipeline e imprime o resultado.
Nenhuma regra de negócio mora aqui.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mala_direta.config import (
    Config,
    carregar_arquivo_env,
    carregar_config,
    carregar_credenciais_smtp,
)
from mala_direta.envio import EnviadorEmail, EnviadorSimulado, EnviadorSmtp
from mala_direta.erros import ConfiguracaoInvalidaError, MalaDiretaError
from mala_direta.pdf import gerar_grade, inspecionar
from mala_direta.pipeline import Resultado, Resumo, Status, colunas_exigidas, executar
from mala_direta.planilha import emails_repetidos, ler_destinatarios

DESCRICAO = "Gera um PDF personalizado por linha da planilha e envia por e-mail com o anexo."


def main(argumentos: list[str] | None = None) -> int:
    analisador = _construir_analisador()
    opcoes = analisador.parse_args(argumentos)

    try:
        return opcoes.executar(opcoes)
    except MalaDiretaError as erro:
        print(f"\nErro: {erro}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompido. O registro guarda o que já foi enviado.", file=sys.stderr)
        return 130


def _construir_analisador() -> argparse.ArgumentParser:
    analisador = argparse.ArgumentParser(prog="mala-direta", description=DESCRICAO)
    analisador.add_argument(
        "--config", type=Path, default=Path("config.toml"), help="arquivo de configuração TOML"
    )
    analisador.add_argument(
        "--env", type=Path, default=Path(".env"), help="arquivo com as credenciais SMTP"
    )
    analisador.add_argument(
        "--valor",
        action="append",
        default=None,
        metavar="COLUNA=VALOR",
        help="define um valor igual para todas as linhas, ex.: --valor data=09/10/2026",
    )
    comandos = analisador.add_subparsers(dest="comando", required=True)

    inspecionar_cmd = comandos.add_parser(
        "inspecionar", help="mostra páginas e dimensões do PDF modelo"
    )
    inspecionar_cmd.set_defaults(executar=_comando_inspecionar)

    grade_cmd = comandos.add_parser(
        "grade", help="gera uma cópia do modelo com régua de coordenadas para posicionar os campos"
    )
    grade_cmd.add_argument(
        "--espacamento", type=int, default=50, help="distância entre linhas (pt)"
    )
    grade_cmd.add_argument("--saida", type=Path, default=None, help="onde salvar o PDF com a régua")
    grade_cmd.set_defaults(executar=_comando_grade)

    conferir_cmd = comandos.add_parser(
        "conferir", help="valida configuração, planilha e textos sem gerar nem enviar nada"
    )
    conferir_cmd.set_defaults(executar=_comando_conferir)

    gerar_cmd = comandos.add_parser("gerar", help="gera os PDFs personalizados, sem enviar e-mail")
    _adicionar_filtros(gerar_cmd)
    gerar_cmd.set_defaults(executar=_comando_gerar)

    enviar_cmd = comandos.add_parser(
        "enviar", help="gera os PDFs e envia os e-mails (simulação sem --confirmar)"
    )
    _adicionar_filtros(enviar_cmd)
    enviar_cmd.add_argument(
        "--confirmar", action="store_true", help="envia de verdade; sem esta opção é só simulação"
    )
    enviar_cmd.add_argument(
        "--reenviar", action="store_true", help="ignora o registro e reenvia para quem já recebeu"
    )
    enviar_cmd.set_defaults(executar=_comando_enviar)

    hash_cmd = comandos.add_parser(
        "hash-senha", help="gera o hash de uma senha para a interface web"
    )
    hash_cmd.set_defaults(executar=_comando_hash_senha)

    return analisador


def _adicionar_filtros(comando: argparse.ArgumentParser) -> None:
    comando.add_argument(
        "--limite", type=int, default=None, help="processa apenas as N primeiras linhas"
    )
    comando.add_argument(
        "--somente",
        action="append",
        default=None,
        metavar="EMAIL",
        help="restringe a esses e-mails",
    )


def _comando_inspecionar(opcoes: argparse.Namespace) -> int:
    config = _carregar(opcoes)
    info = inspecionar(config.pdf.modelo)

    print(f"Modelo: {config.pdf.modelo}")
    for pagina in info.paginas:
        print(
            f"  página {pagina.numero}: {pagina.largura_pt:.0f} x {pagina.altura_pt:.0f} pt "
            f"({pagina.largura_mm:.0f} x {pagina.altura_mm:.0f} mm)"
        )
    if info.campos_de_formulario:
        print("  campos de formulário encontrados: " + ", ".join(info.campos_de_formulario))
    print(f"\nCampos configurados: {len(config.pdf.campos)}")
    for campo in config.pdf.campos:
        pedaco = f", pedaço {campo.pedaco} de {campo.dividir_por!r}" if campo.dividir_por else ""
        print(
            f"  {campo.texto!r} -> página {campo.pagina}, x={campo.x:g}, y={campo.y:g}, "
            f"{campo.fonte} {campo.tamanho:g}pt, {campo.alinhamento}{pedaco}"
        )
    return 0


def _comando_grade(opcoes: argparse.Namespace) -> int:
    config = _carregar(opcoes)
    destino = opcoes.saida or config.pdf.diretorio_saida / "modelo-com-grade.pdf"
    gerar_grade(config.pdf.modelo, destino, espacamento=opcoes.espacamento)
    print(f"Régua gerada em {destino}")
    print("Vermelho = x (esquerda para a direita), azul = y (de baixo para cima), em pontos.")
    return 0


def _comando_conferir(opcoes: argparse.Namespace) -> int:
    config = _carregar(opcoes)
    destinatarios = ler_destinatarios(config.planilha, colunas_exigidas(config))

    print(f"Planilha: {config.planilha.arquivo.name} ({len(destinatarios)} linhas válidas)")
    print(f"Colunas: {', '.join(destinatarios[0].valores)}")

    repetidos = emails_repetidos(destinatarios)
    if repetidos:
        print(f"Atenção: e-mails repetidos ({len(repetidos)}): {', '.join(repetidos)}")

    resumo = executar(config, apenas_gerar=True, limite=1)
    amostra = resumo.resultados[0]
    if amostra.status is Status.ERRO:
        raise MalaDiretaError(amostra.detalhe)

    print("Configuração, modelo e textos validados.")
    print(f"Amostra da primeira linha ({amostra.destinatario.email}): {amostra.arquivo}")
    print("Abra a amostra e confira as posições antes de rodar o lote inteiro.")
    return 0


def _comando_gerar(opcoes: argparse.Namespace) -> int:
    config = _carregar(opcoes)
    resumo = executar(
        config,
        apenas_gerar=True,
        limite=opcoes.limite,
        somente=opcoes.somente,
        ao_progredir=_imprimir,
    )
    return _encerrar(resumo, config)


def _comando_enviar(opcoes: argparse.Namespace) -> int:
    config = _carregar(opcoes)
    simulacao = not opcoes.confirmar
    enviador = _construir_enviador(simulacao)

    if simulacao:
        print("SIMULAÇÃO: os PDFs são gerados e as mensagens montadas, mas nada é enviado.")
        print("Use --confirmar quando estiver tudo certo.\n")

    try:
        resumo = executar(
            config,
            enviador,
            simulacao=simulacao,
            reenviar=opcoes.reenviar,
            limite=opcoes.limite,
            somente=opcoes.somente,
            ao_progredir=_imprimir,
        )
    finally:
        enviador.fechar()

    return _encerrar(resumo, config)


def _comando_hash_senha(opcoes: argparse.Namespace) -> int:
    """A senha é digitada sem eco e nunca é gravada: só o hash sai na tela."""
    from getpass import getpass

    from mala_direta.web.seguranca import gerar_hash

    senha = getpass("Senha: ")
    if senha != getpass("Repita a senha: "):
        raise ConfiguracaoInvalidaError("As senhas não conferem.")
    if len(senha) < 10:
        raise ConfiguracaoInvalidaError("Use ao menos 10 caracteres.")

    print(f"\nusuario:{gerar_hash(senha)}")
    print("Troque 'usuario' pelo login e coloque a linha em MALA_DIRETA_USUARIOS.")
    return 0


def _construir_enviador(simulacao: bool) -> EnviadorEmail:
    if simulacao:
        try:
            return EnviadorSimulado(remetente=carregar_credenciais_smtp().remetente)
        except MalaDiretaError:
            return EnviadorSimulado()
    return EnviadorSmtp(carregar_credenciais_smtp())


def _carregar(opcoes: argparse.Namespace) -> Config:
    carregar_arquivo_env(opcoes.env)
    config = carregar_config(opcoes.config)
    config.valores.update(_valores_da_linha_de_comando(opcoes.valor))
    return config


def _valores_da_linha_de_comando(argumentos: list[str] | None) -> dict[str, str]:
    valores: dict[str, str] = {}
    for argumento in argumentos or []:
        coluna, separador, valor = argumento.partition("=")
        if not separador or not coluna.strip():
            raise ConfiguracaoInvalidaError(f"--valor espera COLUNA=VALOR, recebido: {argumento!r}")
        valores[coluna.strip()] = valor
    return valores


def _imprimir(resultado: Resultado) -> None:
    marcadores = {
        Status.ENVIADO: "enviado  ",
        Status.SIMULADO: "simulado ",
        Status.GERADO: "gerado   ",
        Status.PULADO: "pulado   ",
        Status.ERRO: "ERRO     ",
    }
    detalhe = f" ({resultado.detalhe})" if resultado.detalhe else ""
    print(f"{marcadores[resultado.status]} {resultado.destinatario.email}{detalhe}")


def _encerrar(resumo: Resumo, config: Config) -> int:
    print(
        "\nResumo: "
        + ", ".join(f"{quantidade} {status}" for status, quantidade in resumo.totais.items())
    )
    print(f"PDFs em {config.pdf.diretorio_saida}")
    print(f"Registro em {config.envio.registro}")
    if resumo.falhas:
        print(
            f"\n{len(resumo.falhas)} linha(s) com erro. Corrija e rode de novo: "
            "quem já foi enviado é pulado automaticamente.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
