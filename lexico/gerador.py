"""Interface de projeto do analisador léxico.

definições regulares -> (para cada padrão) AFD pela conversão direta
                     -> AFD mínimo
                     -> união de todos via &-transições (AFND)
                     -> determinização = tabela de análise léxica
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from comum.tabela import secao
from .automato import AF
from .determinizacao import Determinizacao, determinizar
from .er import Definicao, ler_definicoes
from .er_afd import ConversaoER, er_para_afd
from .minimizacao import Minimizacao, minimizar
from .uniao import unir


@dataclass
class ProjetoLexico:
    texto_definicoes: str
    definicoes: List[Definicao]
    tokens: List[str]
    conversoes: Dict[str, ConversaoER]
    minimizacoes: Dict[str, Minimizacao]
    uniao: AF
    determinizacao: Determinizacao
    tabela: AF
    minimizacao_final: Optional[Minimizacao] = None
    avisos: List[str] = field(default_factory=list)

    # -------------------------------------------------------- relatório
    def relatorio(self) -> str:
        out = [secao("DEFINIÇÕES REGULARES")]
        for d in self.definicoes:
            tipo = "auxiliar" if d.auxiliar else f"token (prioridade {self.tokens.index(d.nome) + 1})"
            out.append(f"  {d.nome}: {d.er}    [{tipo}]")
        for nome in self.tokens:
            conv = self.conversoes[nome]
            out.append(secao(f"ER -> AFD (conversão direta): {nome}"))
            out.append(f"ER expandida: ({conv.er_expandida})#")
            out.append(f"firstpos(raiz) = {{{','.join(map(str, sorted(conv.firstpos_raiz)))}}}"
                       f"   posição de #: {conv.pos_fim}\n")
            out.append(conv.texto_followpos() + "\n")
            out.append(conv.afd.texto(f"AFD de '{nome}' (composição = conjunto de posições):"))
            mn = self.minimizacoes[nome]
            out.append(f"\nMinimização de '{nome}':")
            out.append("  " + mn.resumo().replace("\n", "\n  "))
            out.append(mn.afd.texto(f"AFD mínimo de '{nome}' (composição = estados do AFD acima):"))
        out.append(secao("UNIÃO DOS AFDs MÍNIMOS VIA &-TRANSIÇÕES (AFND)"))
        out.append(self.uniao.texto())
        out.append(secao("DETERMINIZAÇÃO -> TABELA DE ANÁLISE LÉXICA"))
        out.append(self.determinizacao.afd.texto(
            "AFD obtido (composição = estados do AFND):"))
        if self.determinizacao.conflitos:
            out.append("\nEstados finais de mais de um padrão (vence a maior prioridade):")
            for q, padroes, esc in self.determinizacao.conflitos:
                out.append(f"  q{q}: {', '.join(padroes)} -> {esc}")
        if self.minimizacao_final is not None:
            out.append(secao("TABELA DE ANÁLISE LÉXICA MINIMIZADA"))
            out.append(self.minimizacao_final.resumo())
            out.append(self.tabela.texto())
        if self.avisos:
            out.append(secao("AVISOS"))
            out.extend("  - " + a for a in self.avisos)
        return "\n".join(out) + "\n"

    def texto_tabela(self) -> str:
        return self.tabela.texto("TABELA DE ANÁLISE LÉXICA") + "\n"

    # -------------------------------------------------------- persistência
    def para_dict(self) -> dict:
        af = self.tabela
        classes = ["".join(sorted(a)) for a in af.alfabeto]
        idx = {a: i for i, a in enumerate(af.alfabeto)}
        trans = []
        for q in af.estados:
            trans.append({str(idx[a]): af.destino(q, a)
                          for a in af.alfabeto if af.destino(q, a) is not None})
        return {
            "tipo": "analisador_lexico",
            "versao": 1,
            "tokens": self.tokens,
            "classes": classes,
            "inicial": af.inicial,
            "transicoes": trans,
            "finais": {str(q): t for q, t in af.finais.items()},
            "definicoes": self.texto_definicoes,
        }

    def salvar(self, pasta: str) -> Dict[str, str]:
        os.makedirs(pasta, exist_ok=True)
        os.makedirs(os.path.join(pasta, "dot"), exist_ok=True)
        arquivos = {
            "json": os.path.join(pasta, "analisador_lexico.json"),
            "relatorio": os.path.join(pasta, "relatorio_lexico.txt"),
            "tabela": os.path.join(pasta, "tabela_lexica.txt"),
            "csv": os.path.join(pasta, "tabela_lexica.csv"),
        }
        with open(arquivos["json"], "w", encoding="utf-8") as f:
            json.dump(self.para_dict(), f, ensure_ascii=False, indent=1)
        with open(arquivos["relatorio"], "w", encoding="utf-8") as f:
            f.write(self.relatorio())
        with open(arquivos["tabela"], "w", encoding="utf-8") as f:
            f.write(self.texto_tabela())
        with open(arquivos["csv"], "w", encoding="utf-8") as f:
            f.write(self.tabela.csv())
        grafos = [(f"afd_{n}", self.conversoes[n].afd) for n in self.tokens]
        grafos += [(f"afd_{n}_min", self.minimizacoes[n].afd) for n in self.tokens]
        grafos += [("afnd_uniao", self.uniao), ("tabela_lexica", self.tabela)]
        for nome, af in grafos:
            with open(os.path.join(pasta, "dot", nome + ".dot"), "w", encoding="utf-8") as f:
                f.write(af.dot(nome))
        return arquivos


def projetar(texto_definicoes: str, minimizar_tabela: bool = False) -> ProjetoLexico:
    definicoes = ler_definicoes(texto_definicoes)
    tokens = [d.nome for d in definicoes if not d.auxiliar]
    avisos: List[str] = []
    # nome de outra definição escrito sem chaves vira texto literal: provável engano
    for d in definicoes:
        for outra in definicoes:
            if outra is d or len(outra.nome) < 2:
                continue
            if re.search(r"(?<![A-Za-z0-9_{\[\\])" + re.escape(outra.nome) + r"(?![A-Za-z0-9_}])", d.er):
                avisos.append(f"a ER de '{d.nome}' contém '{outra.nome}' como texto literal; "
                              f"para usar a definição regular escreva {{{outra.nome}}}")
    if not tokens:
        raise ValueError("todas as definições são auxiliares: nenhum padrão de token")

    conversoes, minimizacoes = {}, {}
    for d in definicoes:
        if d.auxiliar:
            continue
        conv = er_para_afd(d.arvore, d.nome)
        conversoes[d.nome] = conv
        mn = minimizar(conv.afd)
        minimizacoes[d.nome] = mn
        if mn.afd.inicial in mn.afd.finais:
            avisos.append(f"o padrão '{d.nome}' aceita a palavra vazia; ela é ignorada "
                          f"na análise (todo token tem pelo menos 1 caractere)")
        if not mn.afd.finais:
            avisos.append(f"o padrão '{d.nome}' denota a linguagem vazia")

    uniao = unir([(n, minimizacoes[n].afd) for n in tokens])
    prioridade = {n: i for i, n in enumerate(tokens)}
    det = determinizar(uniao, prioridade)
    tabela = det.afd
    min_final = None
    if minimizar_tabela:
        min_final = minimizar(tabela)
        tabela = min_final.afd

    reconhecidos = set(tabela.finais.values())
    for n in tokens:
        if n not in reconhecidos and minimizacoes[n].afd.finais:
            outros = sorted({p for _, ps, _ in det.conflitos if n in ps for p in ps} - {n})
            avisos.append(f"o padrão '{n}' nunca será reconhecido: todas as suas palavras "
                          f"também são de padrões de maior prioridade"
                          + (f" ({', '.join(outros)})" if outros else ""))
    return ProjetoLexico(texto_definicoes, definicoes, tokens, conversoes, minimizacoes,
                         uniao, det, tabela, min_final, avisos)
