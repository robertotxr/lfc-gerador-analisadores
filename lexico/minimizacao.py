"""Minimização de AFD.

1. elimina estados inalcançáveis;
2. elimina estados mortos (dos quais nenhum estado final é alcançável);
3. agrupa estados equivalentes por refinamento de partições (classes de
   equivalência). A partição inicial separa os estados finais pelo padrão que
   reconhecem e os não finais; uma classe é dividida enquanto houver estados
   que, para algum símbolo, vão para classes diferentes (ou um vai e o outro
   fica indefinido).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .automato import AF


@dataclass
class Minimizacao:
    afd: AF
    inalcancaveis: List[int] = field(default_factory=list)
    mortos: List[int] = field(default_factory=list)
    classes: List[List[int]] = field(default_factory=list)  # estados originais por novo estado

    def resumo(self) -> str:
        fmt = lambda l: "{" + ",".join(f"q{x}" for x in l) + "}" if l else "nenhum"
        linhas = [f"Inalcançáveis eliminados: {fmt(self.inalcancaveis)}",
                  f"Mortos eliminados: {fmt(self.mortos)}",
                  "Classes de equivalência: " + (", ".join(
                      f"q{i}={fmt(c)}" for i, c in enumerate(self.classes)) or "nenhuma")]
        return "\n".join(linhas)


def minimizar(afd: AF) -> Minimizacao:
    if not afd.deterministico():
        raise ValueError("minimizar() exige um AFD")
    if afd.inicial is None:
        return Minimizacao(AF(afd.alfabeto))

    alcancaveis = afd.alcancaveis()
    inalcancaveis = [q for q in afd.estados if q not in alcancaveis]

    # estados vivos: alcançam algum final (busca no grafo reverso)
    reverso: Dict[int, Set[int]] = {q: set() for q in afd.estados}
    for q in alcancaveis:
        for dests in afd.trans[q].values():
            for p in dests:
                reverso[p].add(q)
    vivos = {q for q in alcancaveis if q in afd.finais}
    fila = deque(vivos)
    while fila:
        p = fila.popleft()
        for q in reverso[p]:
            if q in alcancaveis and q not in vivos:
                vivos.add(q)
                fila.append(q)
    mortos = sorted(q for q in alcancaveis if q not in vivos)

    if afd.inicial not in vivos:
        # linguagem vazia: um único estado inicial, não final, sem transições
        vazio = AF(afd.alfabeto)
        vazio.novo_estado()
        vazio.inicial = 0
        return Minimizacao(vazio, inalcancaveis, mortos, [[afd.inicial]])

    uteis = sorted(vivos)

    def destino(q: int, a) -> Optional[int]:
        p = afd.destino(q, a)
        return p if p in vivos else None

    # partição inicial: não finais + um grupo por padrão reconhecido
    grupos: Dict[Optional[str], List[int]] = {}
    for q in uteis:
        grupos.setdefault(afd.finais.get(q), []).append(q)
    particao: List[List[int]] = [g for _, g in sorted(grupos.items(), key=lambda kv: kv[1][0])]

    while True:
        classe_de = {q: i for i, g in enumerate(particao) for q in g}
        nova: List[List[int]] = []
        for g in particao:
            sub: Dict[Tuple, List[int]] = {}
            for q in g:
                assinatura = tuple(
                    classe_de[d] if (d := destino(q, a)) is not None else -1
                    for a in afd.alfabeto)
                sub.setdefault(assinatura, []).append(q)
            nova.extend(sub.values())
        if len(nova) == len(particao):
            break
        particao = nova

    # monta o AFD mínimo numerando as classes em ordem de busca a partir do inicial
    classe_de = {q: i for i, g in enumerate(particao) for q in g}
    ordem: List[int] = []
    vistos = {classe_de[afd.inicial]}
    fila = deque([classe_de[afd.inicial]])
    while fila:
        c = fila.popleft()
        ordem.append(c)
        rep = particao[c][0]
        for a in afd.alfabeto:
            d = destino(rep, a)
            if d is not None and classe_de[d] not in vistos:
                vistos.add(classe_de[d])
                fila.append(classe_de[d])
    novo_id = {c: i for i, c in enumerate(ordem)}

    minimo = AF(afd.alfabeto)
    classes = []
    for c in ordem:
        membros = sorted(particao[c])
        classes.append(membros)
        minimo.novo_estado("{" + ",".join(f"q{x}" for x in membros) + "}")
    minimo.inicial = 0
    for c in ordem:
        rep = particao[c][0]
        q = novo_id[c]
        if rep in afd.finais:
            minimo.finais[q] = afd.finais[rep]
        for a in afd.alfabeto:
            d = destino(rep, a)
            if d is not None:
                minimo.adicionar(q, a, novo_id[classe_de[d]])
    return Minimizacao(minimo, inalcancaveis, mortos, classes)
