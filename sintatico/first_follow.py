"""Cálculo de FIRST e FOLLOW (Aho et al., seção 4.4.2)."""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Set

from comum.tabela import formatar_tabela
from .gramatica import EPSILON, FIM, Gramatica


def calcular_first(g: Gramatica) -> Dict[str, Set[str]]:
    """FIRST de cada não terminal (EPSILON indica que deriva a palavra vazia)."""
    first: Dict[str, Set[str]] = {nt: set() for nt in g.nao_terminais}
    mudou = True
    while mudou:
        mudou = False
        for cab, corpo in g.producoes:
            novo = first_de_cadeia(g, first, corpo)
            if not novo <= first[cab]:
                first[cab] |= novo
                mudou = True
    return first


def first_de_cadeia(g: Gramatica, first: Dict[str, Set[str]], cadeia: Sequence[str]) -> Set[str]:
    """FIRST(X1 X2 ... Xn)."""
    res: Set[str] = set()
    for s in cadeia:
        if not g.eh_nao_terminal(s):
            res.add(s)
            return res
        res |= first[s] - {EPSILON}
        if EPSILON not in first[s]:
            return res
    res.add(EPSILON)
    return res


def calcular_follow(g: Gramatica, first: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    follow: Dict[str, Set[str]] = {nt: set() for nt in g.nao_terminais}
    follow[g.inicial].add(FIM)
    mudou = True
    while mudou:
        mudou = False
        for cab, corpo in g.producoes:
            for i, B in enumerate(corpo):
                if not g.eh_nao_terminal(B):
                    continue
                beta = first_de_cadeia(g, first, corpo[i + 1:])
                novo = beta - {EPSILON}
                if EPSILON in beta:
                    novo |= follow[cab]
                if not novo <= follow[B]:
                    follow[B] |= novo
                    mudou = True
    return follow


def _ordenar(g: Gramatica, conj: Iterable[str]) -> List[str]:
    ordem = {t: i for i, t in enumerate(g.terminais)}
    return sorted(conj, key=lambda t: (t == EPSILON, t == FIM, ordem.get(t, len(ordem)), t))


def texto_first_follow(g: Gramatica, first, follow) -> str:
    fmt = lambda c: "{ " + ", ".join(_ordenar(g, c)) + " }"
    linhas = [[f"<{nt}>", fmt(first[nt]), fmt(follow[nt])] for nt in g.nao_terminais]
    return formatar_tabela(["Não terminal", "FIRST", "FOLLOW"], linhas)
