"""Transforma o SVG da arte em um PDF modelo, sem os textos de exemplo.

Quando o design entrega só o mockup preenchido ("Nome do Participante",
"XX / XX / XXXX"), escrever por cima deixaria os dois textos sobrepostos. Como
no SVG cada texto é um traçado isolado, dá para remover só os placeholders e
converter o resto em PDF, preservando o layout exatamente.

    # 1. veja os traçados e suas posições, em coordenadas do PDF
    python ferramentas/modelo_a_partir_do_svg.py listar arte.svg

    # 2. remova os que são placeholders e gere o modelo
    python ferramentas/modelo_a_partir_do_svg.py limpar arte.svg modelo.pdf 15 24 25 26

Requer as dependências opcionais: pip install -e ".[ferramentas]"
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)


def tracados(raiz: ET.Element) -> list[ET.Element]:
    """Os <path> em ordem de documento: a mesma ordem usada pelos dois comandos."""
    return list(raiz.iter(f"{{{SVG}}}path"))


def listar(arquivo: Path) -> int:
    from svgelements import Path as Tracado

    raiz = ET.parse(arquivo).getroot()
    altura = float(raiz.get("height", 0)) or _altura_da_viewbox(raiz)

    for indice, elemento in enumerate(tracados(raiz)):
        try:
            caixa = Tracado(elemento.get("d", "")).bbox()
        except Exception as erro:  # noqa: BLE001
            print(f"{indice:>3}: não foi possível medir ({erro})")
            continue
        if caixa is None:
            continue
        x0, y0, x1, y1 = caixa
        print(
            f"{indice:>3}: x {x0:>7.0f}..{x1:<7.0f}  y {altura - y1:>7.0f}..{altura - y0:<7.0f}"
            f"  largura={x1 - x0:>6.0f}  altura={y1 - y0:>5.0f}  cor={elemento.get('fill', '-')}"
        )
    return 0


def limpar(arquivo: Path, destino: Path, indices: list[int]) -> int:
    import cairosvg

    arvore = ET.parse(arquivo)
    raiz = arvore.getroot()
    pais = {filho: pai for pai in raiz.iter() for filho in pai}
    caminhos = tracados(raiz)

    fora_do_intervalo = [i for i in indices if i >= len(caminhos)]
    if fora_do_intervalo:
        print(
            f"Índices inexistentes: {fora_do_intervalo}. O arquivo tem {len(caminhos)} traçados.",
            file=sys.stderr,
        )
        return 1

    for indice in sorted(set(indices), reverse=True):
        elemento = caminhos[indice]
        pais[elemento].remove(elemento)

    limpo = destino.with_suffix(".svg")
    arvore.write(limpo, encoding="utf-8", xml_declaration=False)
    # dpi=72 faz 1 unidade do SVG valer 1 ponto no PDF, preservando as coordenadas.
    cairosvg.svg2pdf(url=str(limpo), write_to=str(destino), dpi=72)
    limpo.unlink()

    print(f"{destino} gerado, sem os traçados {sorted(set(indices))}")
    print("Confira o resultado antes de usar: os placeholders devem sumir, o resto ficar.")
    return 0


def _altura_da_viewbox(raiz: ET.Element) -> float:
    partes = (raiz.get("viewBox") or "0 0 0 0").split()
    return float(partes[3]) if len(partes) == 4 else 0.0


def main(argumentos: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    comandos = analisador.add_subparsers(dest="comando", required=True)

    listar_cmd = comandos.add_parser("listar", help="mostra os traçados e suas posições")
    listar_cmd.add_argument("svg", type=Path)

    limpar_cmd = comandos.add_parser("limpar", help="remove traçados e gera o PDF modelo")
    limpar_cmd.add_argument("svg", type=Path)
    limpar_cmd.add_argument("pdf", type=Path)
    limpar_cmd.add_argument("indices", type=int, nargs="+")

    opcoes = analisador.parse_args(argumentos)
    if opcoes.comando == "listar":
        return listar(opcoes.svg)
    return limpar(opcoes.svg, opcoes.pdf, opcoes.indices)


if __name__ == "__main__":
    raise SystemExit(main())
