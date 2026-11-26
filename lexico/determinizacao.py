"""Determinização de AFND com &-transições (construção de subconjuntos).

Cada estado do AFD é o &-fecho de um conjunto de estados do AFND. Um estado do
AFD é final se contém algum final do AFND; se contém finais de padrões
diferentes, vence o de maior prioridade (o definido primeiro no arquivo) e o
conflito é registrado para ser exibido.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from .automato import AF


@dataclass
class Determinizacao:
    afd: AF
    conflitos: List[Tuple[int, List[str], str]] = field(default_factory=list)  # (estado, padrões, escolhido)


def determinizar(afnd: AF, prioridade: Optional[Dict[str, int]] = None) -> Determinizacao:
    prioridade = prioridade or {}
    afd = AF(afnd.alfabeto)
    res = Determinizacao(afd)
    if afnd.inicial is None:
        return res

    def desc(T: FrozenSet[int]) -> str:
        return "{" + ",".join(f"q{x}" for x in sorted(T)) + "}"

    inicio = frozenset(afnd.fecho_epsilon({afnd.inicial}))
    indice = {inicio: afd.novo_estado(desc(inicio))}
    afd.inicial = 0
    fila = deque([inicio])
    while fila:
        T = fila.popleft()
        q = indice[T]
        padroes = sorted({afnd.finais[x] for x in T if x in afnd.finais},
                         key=lambda p: (prioridade.get(p, len(prioridade)), p))
        if padroes:
            afd.finais[q] = padroes[0]
            if len(padroes) > 1:
                res.conflitos.append((q, padroes, padroes[0]))
        for a in afnd.alfabeto:
            mov = set()
            for x in T:
                mov |= afnd.trans[x].get(a, set())
            if not mov:
                continue
            U = frozenset(afnd.fecho_epsilon(mov))
            if U not in indice:
                indice[U] = afd.novo_estado(desc(U))
                fila.append(U)
            afd.adicionar(q, a, indice[U])
    return res
