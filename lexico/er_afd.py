"""Conversão direta de ER para AFD (Aho, Lam, Sethi & Ullman, seção 3.9.5).

A ER r é aumentada para (r)#, cada folha não-& recebe uma posição e são
calculadas as funções nullable, firstpos, lastpos e followpos. Os estados do
AFD são conjuntos de posições; o inicial é firstpos(raiz) e são finais os
estados que contêm a posição do marcador #.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set

from comum.tabela import formatar_tabela
from .automato import AF
from .er import Concat, Folha, No, Uniao, Unario, Vazio, para_texto
from .simbolos import Classe, particionar, rotulo


@dataclass
class ConversaoER:
    nome: str
    er_expandida: str
    afd: AF
    simbolo_pos: Dict[int, Optional[Classe]] = field(default_factory=dict)  # None = '#'
    followpos: Dict[int, Set[int]] = field(default_factory=dict)
    firstpos_raiz: Set[int] = field(default_factory=set)
    pos_fim: int = 0

    def texto_followpos(self) -> str:
        linhas = []
        for p in sorted(self.simbolo_pos):
            s = self.simbolo_pos[p]
            fp = "{" + ",".join(map(str, sorted(self.followpos.get(p, ())))) + "}"
            linhas.append([str(p), "#" if s is None else rotulo(s), "-" if s is None else fp])
        return formatar_tabela(["Posição", "Símbolo", "followpos"], linhas)


class _Calculo:
    def __init__(self):
        self.prox_pos = 1
        self.simbolo: Dict[int, Optional[Classe]] = {}
        self.follow: Dict[int, Set[int]] = {}

    def visitar(self, no: No):
        """Devolve (nullable, firstpos, lastpos) e acumula followpos."""
        if isinstance(no, Folha):
            p = self._nova_pos(no.conjunto)
            return False, {p}, {p}
        if isinstance(no, Vazio):
            return True, set(), set()
        if isinstance(no, Uniao):
            n1, f1, l1 = self.visitar(no.esq)
            n2, f2, l2 = self.visitar(no.dir)
            return n1 or n2, f1 | f2, l1 | l2
        if isinstance(no, Concat):
            n1, f1, l1 = self.visitar(no.esq)
            n2, f2, l2 = self.visitar(no.dir)
            for i in l1:
                self.follow[i] |= f2
            return n1 and n2, (f1 | f2) if n1 else f1, (l1 | l2) if n2 else l2
        if isinstance(no, Unario):
            n, f, l = self.visitar(no.filho)
            if no.op in "*+":
                for i in l:
                    self.follow[i] |= f
            return (True if no.op in "*?" else n), f, l
        raise TypeError(no)

    def _nova_pos(self, simbolo: Optional[Classe]) -> int:
        p = self.prox_pos
        self.prox_pos += 1
        self.simbolo[p] = simbolo
        self.follow[p] = set()
        return p


def er_para_afd(arvore: No, nome: str) -> ConversaoER:
    calc = _Calculo()
    anulavel, first, last = calc.visitar(arvore)
    fim = calc._nova_pos(None)  # marcador '#': (r)#
    for i in last:
        calc.follow[i].add(fim)
    # firstpos((r)#) = firstpos(r), mais a posição de '#' se r é anulável
    raiz_first = set(first) | ({fim} if anulavel else set())

    alfabeto = particionar(s for s in calc.simbolo.values() if s is not None)
    afd = AF(alfabeto)

    def desc(S: FrozenSet[int]) -> str:
        return "{" + ",".join(map(str, sorted(S))) + "}"

    inicio = frozenset(raiz_first)
    indice = {inicio: afd.novo_estado(desc(inicio))}
    afd.inicial = 0
    fila = deque([inicio])
    while fila:
        S = fila.popleft()
        q = indice[S]
        if fim in S:
            afd.finais[q] = nome
        for a in alfabeto:
            U: Set[int] = set()
            for p in S:
                s = calc.simbolo[p]
                if s is not None and a <= s:
                    U |= calc.follow[p]
            if not U:
                continue
            U = frozenset(U)
            if U not in indice:
                indice[U] = afd.novo_estado(desc(U))
                fila.append(U)
            afd.adicionar(q, a, indice[U])

    return ConversaoER(nome, para_texto(arvore), afd, calc.simbolo, calc.follow,
                       raiz_first, fim)

