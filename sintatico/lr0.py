"""Itens LR(0): CLOSURE (fig. 4.32), GOTO e coleção canônica (fig. 4.33)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Tuple

from .gramatica import Gramatica

Item = Tuple[int, int]  # (índice da produção, posição do ponto)


def closure(g: Gramatica, itens: List[Item]) -> List[Item]:
    """CLOSURE(I): adiciona B -> .γ para todo A -> α.Bβ em I.
    Mantém a ordem de descoberta (primeiro o núcleo) para exibição."""
    res = list(dict.fromkeys(itens))
    vistos = set(res)
    i = 0
    while i < len(res):
        p, d = res[i]
        corpo = g.producoes[p][1]
        if d < len(corpo) and g.eh_nao_terminal(corpo[d]):
            for q in g.producoes_de(corpo[d]):
                it = (q, 0)
                if it not in vistos:
                    vistos.add(it)
                    res.append(it)
        i += 1
    return res


def goto(g: Gramatica, itens: List[Item], X: str) -> List[Item]:
    nucleo = [(p, d + 1) for p, d in itens
              if d < len(g.producoes[p][1]) and g.producoes[p][1][d] == X]
    return closure(g, nucleo) if nucleo else []


@dataclass
class Colecao:
    estados: List[List[Item]] = field(default_factory=list)
    transicoes: Dict[int, Dict[str, int]] = field(default_factory=dict)


def colecao_canonica(g: Gramatica) -> Colecao:
    """g deve ser a gramática aumentada (produção 0 = S' -> S)."""
    col = Colecao()
    indice: Dict[FrozenSet[Item], int] = {}

    def registrar(itens: List[Item]) -> int:
        chave = frozenset(itens)
        if chave not in indice:
            indice[chave] = len(col.estados)
            col.estados.append(itens)
            col.transicoes[indice[chave]] = {}
        return indice[chave]

    registrar(closure(g, [(0, 0)]))
    i = 0
    while i < len(col.estados):
        itens = col.estados[i]
        # símbolos após o ponto, na ordem em que aparecem nos itens
        simbolos = list(dict.fromkeys(
            g.producoes[p][1][d] for p, d in itens if d < len(g.producoes[p][1])))
        for X in simbolos:
            col.transicoes[i][X] = registrar(goto(g, itens, X))
        i += 1
    return col


def item_texto(g: Gramatica, item: Item) -> str:
    p, d = item
    cab, corpo = g.producoes[p]
    simb = [g.simbolo_texto(s) for s in corpo]
    simb.insert(d, "•")
    return f"<{cab}> ::= " + " ".join(simb)
