"""Interface de projeto do analisador sintático SLR:
GLC + palavras reservadas -> FIRST/FOLLOW -> coleção canônica LR(0) -> tabela SLR."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Set

from comum.tabela import formatar_tabela, secao
from comum.tabela_simbolos import TabelaSimbolos
from .first_follow import calcular_first, calcular_follow, texto_first_follow
from .gramatica import Gramatica, ler_gramatica
from .lr0 import Colecao, colecao_canonica, item_texto
from .slr import TabelaSLR, acao_texto, construir_slr


@dataclass
class ProjetoSintatico:
    texto_gramatica: str
    gramatica: Gramatica          # original
    aumentada: Gramatica
    first: Dict[str, Set[str]]
    follow: Dict[str, Set[str]]
    colecao: Colecao
    tabela: TabelaSLR
    palavras_reservadas: List[str]
    avisos: List[str] = field(default_factory=list)

    @property
    def eh_slr(self) -> bool:
        return not self.tabela.conflitos

    def texto_colecao(self) -> str:
        g, col = self.aumentada, self.colecao
        partes = []
        for i, itens in enumerate(col.estados):
            partes.append(f"I{i}:")
            for it in itens:
                partes.append("    " + item_texto(g, it))
            trans = col.transicoes[i]
            if trans:
                partes.append("    " + "   ".join(
                    f"GOTO(I{i}, {g.simbolo_texto(X)}) = I{j}" for X, j in trans.items()))
            partes.append("")
        return "\n".join(partes)

    def relatorio(self) -> str:
        g = self.aumentada
        out = [secao("GRAMÁTICA AUMENTADA (produções numeradas)"), g.texto()]
        out.append(f"\nTerminais: {', '.join(g.terminais)}")
        out.append(f"Não terminais: {', '.join('<' + n + '>' for n in g.nao_terminais)}")
        if self.palavras_reservadas:
            out.append(secao("PALAVRAS RESERVADAS (pré-carregadas na tabela de símbolos)"))
            out.append(TabelaSimbolos(self.palavras_reservadas).texto())
        out.append(secao("FIRST E FOLLOW"))
        out.append(texto_first_follow(g, self.first, self.follow))
        out.append(secao(f"COLEÇÃO CANÔNICA DE ITENS LR(0)  ({len(self.colecao.estados)} estados)"))
        out.append(self.texto_colecao())
        out.append(secao("TABELA DE ANÁLISE SLR"))
        out.append(self.tabela.texto(g))
        out.append(secao("RESULTADO"))
        if self.eh_slr:
            out.append("A gramática é SLR(1): nenhuma célula da tabela tem conflito.")
        else:
            out.append(f"A gramática NÃO é SLR(1): {len(self.tabela.conflitos)} conflito(s).")
            for c in self.tabela.conflitos:
                out.append("  - " + c.texto(g))
        if self.avisos:
            out.append(secao("AVISOS"))
            out.extend("  - " + a for a in self.avisos)
        return "\n".join(out) + "\n"

    def para_dict(self) -> dict:
        g = self.aumentada
        return {
            "tipo": "analisador_sintatico",
            "versao": 1,
            "inicial": g.inicial,
            "producoes": [[c, list(b)] for c, b in g.producoes],
            "nao_terminais": g.nao_terminais,
            "terminais": g.terminais,
            "palavras_reservadas": self.palavras_reservadas,
            "acao": {str(i): {t: list(a) for t, a in linha.items()}
                     for i, linha in self.tabela.acao.items()},
            "desvio": {str(i): linha for i, linha in self.tabela.desvio.items()},
            "conflitos": [c.texto(g) for c in self.tabela.conflitos],
            "gramatica": self.texto_gramatica,
        }

    def salvar(self, pasta: str) -> Dict[str, str]:
        os.makedirs(pasta, exist_ok=True)
        arquivos = {
            "json": os.path.join(pasta, "analisador_sintatico.json"),
            "relatorio": os.path.join(pasta, "relatorio_sintatico.txt"),
            "tabela": os.path.join(pasta, "tabela_slr.txt"),
            "csv": os.path.join(pasta, "tabela_slr.csv"),
        }
        with open(arquivos["json"], "w", encoding="utf-8") as f:
            json.dump(self.para_dict(), f, ensure_ascii=False, indent=1)
        with open(arquivos["relatorio"], "w", encoding="utf-8") as f:
            f.write(self.relatorio())
        with open(arquivos["tabela"], "w", encoding="utf-8") as f:
            f.write(self.tabela.texto(self.aumentada) + "\n")
        with open(arquivos["csv"], "w", encoding="utf-8") as f:
            f.write(self.tabela.csv(self.aumentada))
        return arquivos


def projetar(texto_gramatica: str, palavras_reservadas: List[str] = ()) -> ProjetoSintatico:
    g = ler_gramatica(texto_gramatica)
    ga = g.aumentada()
    first = calcular_first(ga)
    follow = calcular_follow(ga, first)
    col = colecao_canonica(ga)
    tab = construir_slr(ga, col, follow)
    avisos = list(g.avisos)
    prs = list(palavras_reservadas)
    nao_usadas = [p for p in prs if p not in g.terminais]
    if nao_usadas:
        avisos.append("palavras reservadas que não aparecem na gramática: " + ", ".join(nao_usadas))
    return ProjetoSintatico(texto_gramatica, g, ga, first, follow, col, tab, prs, avisos)
