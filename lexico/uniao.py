"""União de autômatos via &-transições.

Cria um novo estado inicial q0 com &-transição para o estado inicial de cada
autômato. Como cada AFD tem o seu próprio alfabeto de classes, antes calcula-se
uma partição comum que refina todas elas, e cada transição sobre uma classe C é
reescrita como transições sobre os blocos da partição comum contidos em C.
"""

from __future__ import annotations

from typing import List, Tuple

from .automato import AF
from .simbolos import EPSILON, particionar


def unir(automatos: List[Tuple[str, AF]]) -> AF:
    alfabeto = particionar(a for _, af in automatos for a in af.alfabeto)
    uniao = AF(alfabeto)
    uniao.inicial = uniao.novo_estado("novo inicial")
    for nome, af in automatos:
        if af.inicial is None:
            continue
        mapa = {q: uniao.novo_estado(f"{nome}.q{q}") for q in af.estados}
        uniao.adicionar(uniao.inicial, EPSILON, mapa[af.inicial])
        for q in af.estados:
            if q in af.finais:
                uniao.finais[mapa[q]] = af.finais[q]
            for s, dests in af.trans[q].items():
                if s == EPSILON:
                    for p in dests:
                        uniao.adicionar(mapa[q], EPSILON, mapa[p])
                    continue
                for bloco in alfabeto:
                    if bloco <= s:
                        for p in dests:
                            uniao.adicionar(mapa[q], bloco, mapa[p])
    return uniao
