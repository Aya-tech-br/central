"""Exceções de domínio.

Erros previsíveis (planilha sem coluna, modelo inexistente, SMTP recusando login)
sobem como exceções específicas e são traduzidos em mensagens claras na CLI.
"""


class MalaDiretaError(Exception):
    """Base de todos os erros previstos da automação."""


class ConfiguracaoInvalidaError(MalaDiretaError):
    """Arquivo de configuração ou variáveis de ambiente incompletos."""


class PlanilhaInvalidaError(MalaDiretaError):
    """Planilha sem as colunas exigidas ou com linhas inválidas."""


class ModeloPdfInvalidoError(MalaDiretaError):
    """PDF modelo ausente, corrompido ou sem a página referenciada."""


class TextoInvalidoError(MalaDiretaError):
    """Assunto ou corpo da mensagem com placeholder que não existe na planilha."""


class EnvioError(MalaDiretaError):
    """Falha ao entregar a mensagem ao servidor SMTP."""
