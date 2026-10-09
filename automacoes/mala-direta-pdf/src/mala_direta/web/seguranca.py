"""Login sem banco de dados: senhas em hash no ambiente e sessão em cookie assinado."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from mala_direta.erros import ConfiguracaoInvalidaError

COOKIE = "mala_direta_sessao"
HASH_FALSO = bcrypt.hashpw(b"nao-existe", bcrypt.gensalt(rounds=12))


def gerar_hash(senha: str) -> str:
    """Hash bcrypt para colar na variável de ambiente. Senha em texto puro nunca é guardada."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


@dataclass(frozen=True)
class Autenticacao:
    """Verifica credenciais e assina sessões, sem guardar estado no servidor."""

    usuarios: dict[str, str]
    chave_secreta: str
    duracao_horas: int = 12

    @property
    def _assinador(self) -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(self.chave_secreta, salt="sessao-mala-direta")

    def verificar(self, usuario: str, senha: str) -> bool:
        """Compara sempre um hash, mesmo com usuário inexistente, para não vazar quem existe."""
        esperado = self.usuarios.get(usuario.strip().lower(), HASH_FALSO.decode("ascii"))
        return bcrypt.checkpw(senha.encode("utf-8"), esperado.encode("utf-8"))

    def criar_sessao(self, usuario: str) -> str:
        return self._assinador.dumps(usuario.strip().lower())

    def ler_sessao(self, token: str | None) -> str | None:
        if not token:
            return None
        try:
            return self._assinador.loads(token, max_age=self.duracao_horas * 3600)
        except (BadSignature, SignatureExpired):
            return None


@dataclass
class LimitadorDeTentativas:
    """Rate limit de login em memória: suficiente para um serviço de um processo só."""

    maximo: int = 5
    janela_segundos: int = 900
    _tentativas: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def bloqueado(self, chave: str) -> bool:
        tentativas = self._tentativas[chave]
        limite = time.monotonic() - self.janela_segundos
        while tentativas and tentativas[0] < limite:
            tentativas.popleft()
        return len(tentativas) >= self.maximo

    def registrar_falha(self, chave: str) -> None:
        self._tentativas[chave].append(time.monotonic())

    def limpar(self, chave: str) -> None:
        self._tentativas.pop(chave, None)


def carregar_autenticacao(ambiente: dict[str, str] | None = None) -> Autenticacao:
    """Lê MALA_DIRETA_USUARIOS e MALA_DIRETA_CHAVE_SECRETA do ambiente."""
    ambiente = dict(os.environ if ambiente is None else ambiente)

    bruto = ambiente.get("MALA_DIRETA_USUARIOS", "").strip()
    chave = ambiente.get("MALA_DIRETA_CHAVE_SECRETA", "").strip()
    if not bruto or not chave:
        raise ConfiguracaoInvalidaError(
            "Defina MALA_DIRETA_USUARIOS e MALA_DIRETA_CHAVE_SECRETA antes de subir a interface. "
            "Gere o hash de cada senha com: mala-direta hash-senha"
        )
    if len(chave) < 32:
        raise ConfiguracaoInvalidaError(
            "MALA_DIRETA_CHAVE_SECRETA precisa de pelo menos 32 caracteres aleatórios. "
            'Gere uma com: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )

    usuarios: dict[str, str] = {}
    for entrada in bruto.split(","):
        usuario, separador, hash_senha = entrada.strip().partition(":")
        if not separador or not usuario or not hash_senha:
            raise ConfiguracaoInvalidaError(
                "MALA_DIRETA_USUARIOS espera usuario:hash separados por vírgula, "
                f"recebido: {entrada.strip()!r}"
            )
        usuarios[usuario.strip().lower()] = hash_senha.strip()

    return Autenticacao(usuarios=usuarios, chave_secreta=chave)
