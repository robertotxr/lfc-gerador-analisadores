"""Formatação de tabelas em texto (para visualização em tela/arquivo) e em CSV."""

from __future__ import annotations

import csv
import io
from typing import List, Sequence


def formatar_tabela(cabecalho: Sequence[str], linhas: Sequence[Sequence[str]],
                    titulo: str = "") -> str:
    """Monta uma tabela em texto com colunas alinhadas.

    >>> print(formatar_tabela(["a", "b"], [["1", "22"]]))
    | a | b  |
    |---+----|
    | 1 | 22 |
    """
    cab = [str(c) for c in cabecalho]
    lin = [[str(c) for c in l] for l in linhas]
    larguras = [len(c) for c in cab]
    for l in lin:
        for i, c in enumerate(l):
            if i >= len(larguras):
                larguras.append(len(c))
            else:
                larguras[i] = max(larguras[i], len(c))

    def fmt(l: List[str]) -> str:
        l = list(l) + [""] * (len(larguras) - len(l))
        return "| " + " | ".join(c.ljust(larguras[i]) for i, c in enumerate(l)) + " |"

    sep = "|" + "+".join("-" * (w + 2) for w in larguras) + "|"
    partes = []
    if titulo:
        partes.append(titulo)
    partes.append(fmt(cab))
    partes.append(sep)
    partes.extend(fmt(l) for l in lin)
    return "\n".join(partes)


def para_csv(cabecalho: Sequence[str], linhas: Sequence[Sequence[str]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(cabecalho)
    for l in linhas:
        w.writerow(l)
    return buf.getvalue()


def secao(titulo: str) -> str:
    barra = "=" * max(60, len(titulo) + 4)
    return f"\n{barra}\n  {titulo}\n{barra}\n"
