"""Construção da tabela SLR (Aho et al., algoritmo 4.46).

Para cada estado Ii da coleção canônica LR(0):
  - A -> α.aβ em Ii e GOTO(Ii, a) = Ij        => ACTION[i, a] = shift j
  - A -> α. em Ii (A != S')                   => ACTION[i, a] = reduce A -> α, p/ todo a em FOLLOW(A)
  - S' -> S. em Ii                            => ACTION[i, $] = accept
  - GOTO(Ii, A) = Ij                          => GOTO[i, A] = j
Duas ações na mesma célula = conflito: a gramática não é SLR(1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from comum.tabela import formatar_tabela, para_csv
from .gramatica import FIM, Gramatica
from .lr0 import Colecao

Acao = Tuple  # ('s', estado) | ('r', produção) | ('acc',)


def acao_texto(a: Acao) -> str:
    if a[0] == "acc":
        return "acc"
    return f"{a[0]}{a[1]}"


@dataclass
class Conflito:
    estado: int
    simbolo: str
    acoes: List[Acao]
    escolhida: Acao

    def tipo(self) -> str:
        tem_s = any(a[0] == "s" for a in self.acoes)
        return "empilha/reduz" if tem_s else "reduz/reduz"

    def texto(self, g: Gramatica) -> str:
        desc = []
        for a in self.acoes:
            if a[0] == "s":
                desc.append(f"empilhar e ir para {a[1]}")
            elif a[0] == "r":
                desc.append(f"reduzir por ({a[1]}) {g.producao_texto(a[1])}")
            else:
                desc.append("aceitar")
        return (f"estado {self.estado}, símbolo '{self.simbolo}' ({self.tipo()}): "
                + " | ".join(desc) + f"  -> resolvido como {acao_texto(self.escolhida)}")


@dataclass
class TabelaSLR:
    acao: Dict[int, Dict[str, Acao]] = field(default_factory=dict)
    desvio: Dict[int, Dict[str, int]] = field(default_factory=dict)
    conflitos: List[Conflito] = field(default_factory=list)

    def tabela(self, g: Gramatica) -> Tuple[List[str], List[List[str]]]:
        terms = list(g.terminais) + [FIM]
        nts = [nt for nt in g.nao_terminais if nt != g.inicial]
        cab = ["Estado"] + terms + [f"<{nt}>" for nt in nts]
        conf = {(c.estado, c.simbolo) for c in self.conflitos}
        linhas = []
        for i in sorted(self.acao):
            l = [str(i)]
            for t in terms:
                a = self.acao[i].get(t)
                txt = acao_texto(a) if a else ""
                l.append(txt + ("!" if (i, t) in conf else ""))
            for nt in nts:
                d = self.desvio[i].get(nt)
                l.append("" if d is None else str(d))
            linhas.append(l)
        return cab, linhas

    def texto(self, g: Gramatica) -> str:
        cab, linhas = self.tabela(g)
        nota = "s = empilha (shift), r = reduz pela produção, acc = aceita"
        if self.conflitos:
            nota += ", ! = célula com conflito"
        return formatar_tabela(cab, linhas, "TABELA SLR (ACTION | GOTO)  -  " + nota)

    def csv(self, g: Gramatica) -> str:
        cab, linhas = self.tabela(g)
        return para_csv(cab, linhas)


def construir_slr(g: Gramatica, col: Colecao, follow: Dict[str, Set[str]]) -> TabelaSLR:
    """g é a gramática aumentada; follow foi calculado sobre ela."""
    tab = TabelaSLR()
    candidatas: Dict[Tuple[int, str], List[Acao]] = {}

    def propor(i: int, a: str, acao: Acao):
        lst = candidatas.setdefault((i, a), [])
        if acao not in lst:
            lst.append(acao)

    for i, itens in enumerate(col.estados):
        tab.acao[i], tab.desvio[i] = {}, {}
        for p, d in itens:
            cab, corpo = g.producoes[p]
            if d < len(corpo):
                X = corpo[d]
                if not g.eh_nao_terminal(X):
                    propor(i, X, ("s", col.transicoes[i][X]))
            elif p == 0:
                propor(i, FIM, ("acc",))
            else:
                for a in follow[cab]:
                    propor(i, a, ("r", p))
        for X, j in col.transicoes[i].items():
            if g.eh_nao_terminal(X):
                tab.desvio[i][X] = j

    for (i, a), acoes in sorted(candidatas.items()):
        if len(acoes) == 1:
            escolhida = acoes[0]
        else:
            # resolução padrão (como no yacc): empilhar vence reduzir;
            # entre reduções, vence a produção que aparece primeiro
            acoes = sorted(acoes, key=lambda x: (x[0] != "acc", x[0] != "s", x[1] if len(x) > 1 else 0))
            escolhida = acoes[0]
            tab.conflitos.append(Conflito(i, a, acoes, escolhida))
        tab.acao[i][a] = escolhida
    return tab
