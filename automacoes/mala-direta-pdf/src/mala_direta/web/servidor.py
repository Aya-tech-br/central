"""Sobe a interface web.

Um processo só, de propósito: o andamento dos envios vive em memória, então
mais de um worker faria um envio sumir da tela de quem o iniciou.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mala_direta.config import carregar_arquivo_env
from mala_direta.erros import MalaDiretaError
from mala_direta.web.app import criar_app


def main(argumentos: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        prog="mala-direta-web", description="Interface web da mala direta."
    )
    analisador.add_argument("--host", default="127.0.0.1", help="endereço de escuta")
    analisador.add_argument("--porta", type=int, default=8000, help="porta de escuta")
    analisador.add_argument(
        "--modelos", type=Path, default=Path("."), help="pasta que contém os modelos"
    )
    analisador.add_argument("--env", type=Path, default=Path(".env"), help="arquivo de variáveis")
    opcoes = analisador.parse_args(argumentos)

    carregar_arquivo_env(opcoes.env)
    try:
        app = criar_app(raiz_modelos=opcoes.modelos)
    except MalaDiretaError as erro:
        print(f"\nErro: {erro}", file=sys.stderr)
        return 1

    import uvicorn

    # proxy_headers deixa o app enxergar o https de quem está na frente (Railway, Render,
    # nginx), que é o que decide se o cookie de sessão sai com a marca Secure.
    uvicorn.run(
        app,
        host=opcoes.host,
        port=opcoes.porta,
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
