"""Leitura de definições regulares e conversão de cada ER em árvore sintática.

Formato do arquivo (Anexo I do enunciado):

    def-reg1: ER1
    def-reg2: ER2

Sintaxe aceita nas ERs:
    a b c         símbolos literais (espaços fora de [ ] são ignorados)
    [a-zA-Z_]     classe de caracteres (espaço dentro de [ ] é literal)
    [^"\n]        classe negada (complemento em relação ao universo)
    r1 | r2       união
    r1 r2         concatenação (implícita)
    r*  r+  r?    fecho, fecho positivo, opcional
    ( r )         agrupamento
    &             palavra vazia (épsilon)
    {nome}        referência a outra definição regular
    \\x           escape: \\n \\t \\r, \\s (espaço) e qualquer outro caractere
                  literal, ex.: \\+ \\* \\( \\| \\& \\{ \\[ \\\\

Uma definição referenciada por outra (via {nome}) é auxiliar: ela não gera
token próprio. As demais são padrões de token, com prioridade dada pela ordem
em que aparecem no arquivo (a primeira tem maior prioridade).
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .simbolos import UNIVERSO, Classe, rotulo

NOME_VALIDO = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]*$")
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "s": " "}
OPERADORES = set("|*+?()")


class ErroER(Exception):
    """Erro de sintaxe numa ER ou no arquivo de definições."""


# ---------------------------------------------------------------- árvore
class No:
    __slots__ = ()


class Folha(No):
    __slots__ = ("conjunto",)

    def __init__(self, conjunto: Classe):
        self.conjunto = conjunto


class Vazio(No):  # épsilon
    __slots__ = ()


class Concat(No):
    __slots__ = ("esq", "dir")

    def __init__(self, esq: No, dir: No):
        self.esq, self.dir = esq, dir


class Uniao(No):
    __slots__ = ("esq", "dir")

    def __init__(self, esq: No, dir: No):
        self.esq, self.dir = esq, dir


class Unario(No):
    __slots__ = ("filho", "op")

    def __init__(self, filho: No, op: str):  # op em '*', '+', '?'
        self.filho, self.op = filho, op


def para_texto(no: No) -> str:
    """Reconstrói a ER (já com as referências expandidas) para exibição."""
    if isinstance(no, Folha):
        return rotulo(no.conjunto)
    if isinstance(no, Vazio):
        return "&"
    if isinstance(no, Uniao):
        return para_texto(no.esq) + "|" + para_texto(no.dir)
    if isinstance(no, Concat):
        partes = []
        for f in (no.esq, no.dir):
            t = para_texto(f)
            partes.append("(" + t + ")" if isinstance(f, Uniao) else t)
        return "".join(partes)
    if isinstance(no, Unario):
        t = para_texto(no.filho)
        if not isinstance(no.filho, (Folha, Vazio)):
            t = "(" + t + ")"
        return t + no.op
    raise TypeError(no)


# ---------------------------------------------------------------- tokens da ER
@dataclass
class _Tok:
    tipo: str  # 'LIT', 'EPS', 'OP', 'REF'
    valor: object = None
    pos: int = 0


def _ler_char_escapado(s: str, i: int) -> Tuple[str, int]:
    """s[i] == '\\'; devolve (caractere, próximo índice)."""
    if i + 1 >= len(s):
        raise ErroER(f"'\\' sem caractere depois (coluna {i + 1})")
    c = s[i + 1]
    return ESCAPES.get(c, c), i + 2


def _ler_classe(s: str, i: int) -> Tuple[Classe, int]:
    """s[i] == '['; devolve (conjunto, índice após ']')."""
    inicio = i
    i += 1
    negada = False
    if i < len(s) and s[i] == "^":
        negada = True
        i += 1
    chars: Set[str] = set()

    def ler_um(j: int) -> Tuple[str, int]:
        if s[j] == "\\":
            return _ler_char_escapado(s, j)
        return s[j], j + 1

    while True:
        if i >= len(s):
            raise ErroER(f"classe '[' aberta na coluna {inicio + 1} sem ']'")
        if s[i] == "]":
            i += 1
            break
        lo, i = ler_um(i)
        if i + 1 < len(s) and s[i] == "-" and s[i + 1] != "]":
            hi, i = ler_um(i + 1)
            if ord(lo) > ord(hi):
                raise ErroER(f"faixa inválida '{lo}-{hi}' na classe da coluna {inicio + 1}")
            chars.update(chr(c) for c in range(ord(lo), ord(hi) + 1))
        else:
            chars.add(lo)
    if negada:
        chars = set(UNIVERSO - chars)
    if not chars:
        raise ErroER(f"classe vazia na coluna {inicio + 1}")
    return frozenset(chars), i


def _tokenizar(er: str, nomes: Set[str]) -> List[_Tok]:
    toks: List[_Tok] = []
    i = 0
    while i < len(er):
        c = er[i]
        if c.isspace():
            i += 1
        elif c == "\\":
            ch, j = _ler_char_escapado(er, i)
            toks.append(_Tok("LIT", frozenset(ch), i))
            i = j
        elif c == "[":
            conj, j = _ler_classe(er, i)
            toks.append(_Tok("LIT", conj, i))
            i = j
        elif c == "{":
            m = re.match(r"\{\s*([A-Za-z_][A-Za-z0-9_\-]*)\s*\}", er[i:])
            if m and m.group(1) in nomes:
                toks.append(_Tok("REF", m.group(1), i))
                i += m.end()
            elif m:
                raise ErroER(
                    f"referência a definição inexistente '{{{m.group(1)}}}' "
                    f"(para a chave literal use \\{{)")
            else:
                toks.append(_Tok("LIT", frozenset("{"), i))
                i += 1
        elif c == "&":
            toks.append(_Tok("EPS", None, i))
            i += 1
        elif c in OPERADORES:
            toks.append(_Tok("OP", c, i))
            i += 1
        else:
            toks.append(_Tok("LIT", frozenset(c), i))
            i += 1
    return toks


# ---------------------------------------------------------------- parser
class _Parser:
    """Descida recursiva:
        uniao   -> concat ('|' concat)*
        concat  -> posfixo posfixo*
        posfixo -> atomo ('*' | '+' | '?')*
        atomo   -> LIT | EPS | REF | '(' uniao ')'
    """

    def __init__(self, toks: List[_Tok], resolver):
        self.toks = toks
        self.i = 0
        self.resolver = resolver

    def _atual(self) -> Optional[_Tok]:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def _eh_op(self, c: str) -> bool:
        t = self._atual()
        return t is not None and t.tipo == "OP" and t.valor == c

    def analisar(self) -> No:
        if not self.toks:
            raise ErroER("expressão regular vazia (use & para a palavra vazia)")
        no = self._uniao()
        if self._atual() is not None:
            t = self._atual()
            if t.tipo == "OP" and t.valor == ")":
                raise ErroER(f"')' sem '(' correspondente na coluna {t.pos + 1}")
            raise ErroER(f"símbolo inesperado '{t.valor}' na coluna {t.pos + 1}")
        return no

    def _uniao(self) -> No:
        no = self._concat()
        while self._eh_op("|"):
            self.i += 1
            no = Uniao(no, self._concat())
        return no

    def _concat(self) -> No:
        t = self._atual()
        if t is None or (t.tipo == "OP" and t.valor in "|)"):
            pos = t.pos + 1 if t else "final"
            raise ErroER(f"alternativa vazia antes da coluna {pos} (use & para a palavra vazia)")
        no = self._posfixo()
        while True:
            t = self._atual()
            if t is None or (t.tipo == "OP" and t.valor in "|)"):
                return no
            no = Concat(no, self._posfixo())

    def _posfixo(self) -> No:
        no = self._atomo()
        while True:
            t = self._atual()
            if t is not None and t.tipo == "OP" and t.valor in "*+?":
                self.i += 1
                no = Unario(no, t.valor)
            else:
                return no

    def _atomo(self) -> No:
        t = self._atual()
        if t is None:
            raise ErroER("expressão terminou antes do esperado")
        self.i += 1
        if t.tipo == "LIT":
            return Folha(t.valor)
        if t.tipo == "EPS":
            return Vazio()
        if t.tipo == "REF":
            return self.resolver(t.valor)
        if t.valor == "(":
            no = self._uniao()
            if not self._eh_op(")"):
                raise ErroER(f"'(' da coluna {t.pos + 1} sem ')' correspondente")
            self.i += 1
            return no
        if t.valor == ")":
            raise ErroER(f"')' sem '(' correspondente na coluna {t.pos + 1}")
        raise ErroER(f"operador '{t.valor}' sem operando na coluna {t.pos + 1} "
                     f"(para o caractere literal use \\{t.valor})")


# ---------------------------------------------------------------- definições
@dataclass
class Definicao:
    nome: str
    er: str
    linha: int
    arvore: Optional[No] = None
    auxiliar: bool = False
    referencias: List[str] = field(default_factory=list)


def ler_definicoes(texto: str) -> List[Definicao]:
    """Lê o arquivo de definições regulares e devolve as definições com a
    árvore de cada ER já construída (referências expandidas)."""
    defs: List[Definicao] = []
    por_nome: Dict[str, Definicao] = {}
    for n, linha in enumerate(texto.splitlines(), start=1):
        s = linha.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in s:
            raise ErroER(f"linha {n}: esperado 'nome: ER', encontrado '{s}'")
        nome, er = s.split(":", 1)
        nome, er = nome.strip(), er.strip()
        if not NOME_VALIDO.match(nome):
            raise ErroER(f"linha {n}: nome de definição inválido '{nome}'")
        if nome in por_nome:
            raise ErroER(f"linha {n}: definição '{nome}' repetida "
                         f"(já definida na linha {por_nome[nome].linha})")
        if not er:
            raise ErroER(f"linha {n}: definição '{nome}' sem expressão regular")
        d = Definicao(nome, er, n)
        defs.append(d)
        por_nome[nome] = d
    if not defs:
        raise ErroER("nenhuma definição regular encontrada")

    nomes = set(por_nome)
    em_construcao: List[str] = []

    def construir(nome: str) -> No:
        d = por_nome[nome]
        if d.arvore is None:
            if nome in em_construcao:
                ciclo = " -> ".join(em_construcao[em_construcao.index(nome):] + [nome])
                raise ErroER(f"definições regulares circulares: {ciclo}")
            em_construcao.append(nome)
            try:
                toks = _tokenizar(d.er, nomes)
                d.referencias = [t.valor for t in toks if t.tipo == "REF"]
                for r in d.referencias:
                    por_nome[r].auxiliar = True
                d.arvore = _Parser(toks, lambda r: copy.deepcopy(construir(r))).analisar()
            except ErroER as e:
                if str(e).startswith("linha "):
                    raise
                raise ErroER(f"linha {d.linha} ({d.nome}): {e}") from None
            finally:
                em_construcao.pop()
        return d.arvore

    for d in defs:
        construir(d.nome)
    return defs


def er_unica(er: str, nome: str = "er") -> No:
    """Constrói a árvore de uma ER isolada (sem definições). Útil em testes."""
    return ler_definicoes(f"{nome}: {er}")[0].arvore
