"""Leitura de Gramáticas Livres de Contexto.

Formato (uma produção por linha):

    <NaoTerminal> ::= corpo da produção

  - não terminais entre < > (ou ⟨ ⟩), ex.: <Expr>, <Lista Comandos>
  - terminais escritos diretamente (id, num, if) ou entre aspas
    ("(", "+", “[” ...) quando forem caracteres especiais
  - & (ou ε) é a palavra vazia
  - opcionalmente, alternativas com | na mesma linha, ou em linhas seguintes
    começando com |
  - linhas em branco e iniciadas por # ou // são ignoradas

O símbolo inicial é o lado esquerdo da primeira produção.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

EPSILON = "&"
FIM = "$"

_ABRE_NT = "<⟨"
_FECHA_NT = {"<": ">", "⟨": "⟩"}
_ASPAS = {'"': '"', "“": "”", "”": "”", "'": "'"}
_SETA = re.compile(r"::=|→|->")


class ErroGramatica(Exception):
    pass


def simbolo_texto(s: str, nao_terminal: bool) -> str:
    """<X> para não terminais; terminais especiais entre aspas: "(" "+"."""
    if nao_terminal:
        return f"<{s}>"
    if re.fullmatch(r"[A-Za-z0-9_]+", s) or '"' in s:
        return s
    return f'"{s}"'


@dataclass
class Gramatica:
    producoes: List[Tuple[str, Tuple[str, ...]]]  # (cabeça, corpo); corpo vazio = &
    inicial: str
    nao_terminais: List[str]  # em ordem de aparição
    terminais: List[str]      # em ordem de aparição
    avisos: List[str] = field(default_factory=list)

    def eh_nao_terminal(self, s: str) -> bool:
        return s in self._nts

    def __post_init__(self):
        self._nts: Set[str] = set(self.nao_terminais)
        self._por_cabeca: Dict[str, List[int]] = {}
        for i, (c, _) in enumerate(self.producoes):
            self._por_cabeca.setdefault(c, []).append(i)

    def producoes_de(self, nt: str) -> List[int]:
        return self._por_cabeca.get(nt, [])

    def simbolo_texto(self, s: str) -> str:
        return simbolo_texto(s, s in self._nts)

    def producao_texto(self, i: int) -> str:
        cab, corpo = self.producoes[i]
        rhs = " ".join(self.simbolo_texto(s) for s in corpo) if corpo else EPSILON
        return f"<{cab}> ::= {rhs}"

    def aumentada(self) -> "Gramatica":
        """Gramática aumentada com S' ::= S como produção 0."""
        novo = self.inicial + "'"
        while novo in self._nts:
            novo += "'"
        prods = [(novo, (self.inicial,))] + list(self.producoes)
        return Gramatica(prods, novo, [novo] + list(self.nao_terminais),
                         list(self.terminais), list(self.avisos))

    def texto(self) -> str:
        return "\n".join(f"  ({i}) {self.producao_texto(i)}" for i in range(len(self.producoes)))


def _ler_corpo(s: str, nlinha: int) -> List[List[str]]:
    """Divide o corpo em alternativas; cada símbolo vira ('NT', nome) ou ('T', t)."""
    alternativas: List[List[str]] = [[]]
    i = 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c in _ASPAS:
            fecha = _ASPAS[c]
            if s[i + 1:i + 2] == fecha and s[i + 2:i + 3] == fecha:  # """ = aspas literal
                alternativas[-1].append(("T", c))
                i += 3
                continue
            j = s.find(fecha, i + 1)
            if j == -1 and fecha == "”":
                j = s.find('"', i + 1)
            if j == -1:
                raise ErroGramatica(f"linha {nlinha}: aspas abertas sem fechamento")
            conteudo = s[i + 1:j]
            if not conteudo:
                raise ErroGramatica(f"linha {nlinha}: terminal vazio \"\" (use & para a palavra vazia)")
            alternativas[-1].append(("T", conteudo))
            i = j + 1
            continue
        if c in _ABRE_NT:
            # <Nome> sem espaço logo após '<' nem antes de '>' (assim "< id >" são 3 terminais)
            m = re.match(r"[<⟨]([^<>⟨⟩\"“”\s](?:[^<>⟨⟩\"“”]*[^<>⟨⟩\"“”\s])?)[>⟩]", s[i:])
            if m:
                alternativas[-1].append(("NT", re.sub(r"\s+", " ", m.group(1))))
                i += m.end()
                continue
        j = i
        while j < len(s) and not s[j].isspace():
            j += 1
        palavra = s[i:j]
        i = j
        if palavra == "|":
            alternativas.append([])
        elif palavra in (EPSILON, "ε"):
            alternativas[-1].append(("EPS", None))
        else:
            alternativas[-1].append(("T", palavra))
    return alternativas


def ler_gramatica(texto: str) -> Gramatica:
    brutas: List[Tuple[str, List[Tuple[str, Optional[str]]], int]] = []
    ultima_cabeca: Optional[str] = None
    for n, linha in enumerate(texto.splitlines(), start=1):
        s = linha.strip()
        if not s or s.startswith("#") or s.startswith("//"):
            continue
        if s.startswith("|"):
            if ultima_cabeca is None:
                raise ErroGramatica(f"linha {n}: alternativa '|' sem produção anterior")
            cabeca, corpo = ultima_cabeca, s[1:]
        else:
            m = re.match(r"[<⟨]\s*([^<>⟨⟩]+?)\s*[>⟩]\s*(::=|→|->)(.*)$", s)
            if not m:
                raise ErroGramatica(f"linha {n}: esperado '<NaoTerminal> ::= corpo', encontrado: {s}")
            cabeca, corpo = re.sub(r"\s+", " ", m.group(1)), m.group(3)
            ultima_cabeca = cabeca
        for alt in _ler_corpo(corpo, n):
            brutas.append((cabeca, alt, n))
    if not brutas:
        raise ErroGramatica("nenhuma produção encontrada")

    nts: List[str] = []
    for cab, _, _ in brutas:
        if cab not in nts:
            nts.append(cab)
    conj_nts = set(nts)

    producoes: List[Tuple[str, Tuple[str, ...]]] = []
    terminais: List[str] = []
    for cab, alt, n in brutas:
        corpo: List[str] = []
        for tipo, valor in alt:
            if tipo == "EPS":
                continue
            if tipo == "NT":
                if valor not in conj_nts:
                    raise ErroGramatica(f"linha {n}: não terminal <{valor}> usado mas sem produções")
                corpo.append(valor)
            else:
                if valor == FIM:
                    raise ErroGramatica(f"linha {n}: '$' é reservado como marcador de fim de entrada")
                if valor in conj_nts:
                    raise ErroGramatica(
                        f"linha {n}: '{valor}' é nome de não terminal; escreva <{valor}> ou use outro terminal")
                corpo.append(valor)
                if valor not in terminais:
                    terminais.append(valor)
        p = (cab, tuple(corpo))
        if p in producoes:
            continue  # produção repetida
        producoes.append(p)

    g = Gramatica(producoes, nts[0], nts, terminais)
    g.avisos.extend(_diagnosticar(g))
    return g


def _diagnosticar(g: Gramatica) -> List[str]:
    avisos = []
    # inalcançáveis a partir do símbolo inicial
    alc = {g.inicial}
    mudou = True
    while mudou:
        mudou = False
        for cab, corpo in g.producoes:
            if cab in alc:
                for s in corpo:
                    if g.eh_nao_terminal(s) and s not in alc:
                        alc.add(s)
                        mudou = True
    for nt in g.nao_terminais:
        if nt not in alc:
            avisos.append(f"<{nt}> é inalcançável a partir de <{g.inicial}>")
    # improdutivos (não geram nenhuma sentença)
    prod: Set[str] = set()
    mudou = True
    while mudou:
        mudou = False
        for cab, corpo in g.producoes:
            if cab not in prod and all(not g.eh_nao_terminal(s) or s in prod for s in corpo):
                prod.add(cab)
                mudou = True
    for nt in g.nao_terminais:
        if nt not in prod:
            avisos.append(f"<{nt}> é improdutivo (não deriva nenhuma sentença)")
    return avisos
