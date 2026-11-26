"""Símbolos do alfabeto dos autômatos.

Cada símbolo de transição é uma *classe de caracteres* (frozenset de caracteres).
As classes de um autômato são sempre disjuntas entre si (uma partição), então
um caractere de entrada pertence a no máximo uma classe. Isso mantém as tabelas
pequenas e legíveis: [a-zA-Z] vira uma coluna só, em vez de 52.

A transição vazia é representada pela string EPSILON ('&'), como em sala.
"""

from __future__ import annotations

from typing import FrozenSet, Iterable, List, Union

EPSILON = "&"

Classe = FrozenSet[str]
Simbolo = Union[Classe, str]  # classe de caracteres ou EPSILON

# Universo usado para complementar classes negadas ([^...]):
# tab, quebra de linha, retorno de carro, ASCII imprimível e Latin-1 (acentos).
UNIVERSO: FrozenSet[str] = frozenset(
    ["\t", "\n", "\r"]
    + [chr(c) for c in range(32, 127)]
    + [chr(c) for c in range(160, 256)]
)

_ESCAPES_EXIBICAO = {"\n": "\\n", "\t": "\\t", "\r": "\\r", " ": "\\s"}


def particionar(conjuntos: Iterable[Iterable[str]]) -> List[Classe]:
    """Partição mais grossa da união dos conjuntos em que cada conjunto de
    entrada é uma união exata de blocos."""
    blocos: List[Classe] = []
    for s in conjuntos:
        s = frozenset(s)
        if not s:
            continue
        novos: List[Classe] = []
        resto = set(s)
        for b in blocos:
            inter = b & s
            if inter:
                novos.append(frozenset(inter))
                resto -= inter
                dif = b - s
                if dif:
                    novos.append(frozenset(dif))
            else:
                novos.append(b)
        if resto:
            novos.append(frozenset(resto))
        blocos = novos
    return sorted(blocos, key=chave_simbolo)


def chave_simbolo(s: Simbolo):
    """Ordenação estável: classes pelo menor caractere, EPSILON por último."""
    if isinstance(s, str):
        return (1, "")
    return (0, min(s))


def _esc_char(c: str, dentro_classe: bool) -> str:
    if c in _ESCAPES_EXIBICAO:
        return _ESCAPES_EXIBICAO[c]
    if dentro_classe and c in "]\\^-":
        return "\\" + c
    if not dentro_classe and c in "&\\":
        return "\\" + c
    return c


def _tipo(c: str) -> str:
    if "0" <= c <= "9":
        return "d"
    if "A" <= c <= "Z":
        return "M"
    if "a" <= c <= "z":
        return "m"
    return "o"


def _faixas(chars: Iterable[str]) -> str:
    """Compacta em faixas só dentro de dígitos, maiúsculas ou minúsculas
    (ex.: [0-9A-Za-z_]); outros caracteres só viram faixa em sequências longas."""
    cs = sorted(chars)
    out = []
    i = 0
    while i < len(cs):
        j = i
        while (j + 1 < len(cs) and ord(cs[j + 1]) == ord(cs[j]) + 1
               and _tipo(cs[j + 1]) == _tipo(cs[i])):
            j += 1
        minimo = 3 if _tipo(cs[i]) != "o" else 5
        if j - i + 1 >= minimo:
            out.append(_esc_char(cs[i], True) + "-" + _esc_char(cs[j], True))
        else:
            out.extend(_esc_char(cs[k], True) for k in range(i, j + 1))
        i = j + 1
    return "".join(out)


def rotulo(s: Simbolo) -> str:
    """Texto curto para exibir um símbolo em tabelas: a, [0-9], [^"], &."""
    if isinstance(s, str):
        return s
    if len(s) == 1:
        return _esc_char(next(iter(s)), False)
    complemento = UNIVERSO - s
    if s <= UNIVERSO and len(complemento) < len(s) and len(complemento) <= 12:
        return "[^" + _faixas(complemento) + "]"
    return "[" + _faixas(s) + "]"


def descrever_char(c: str) -> str:
    """Caractere legível para mensagens de erro."""
    return _ESCAPES_EXIBICAO.get(c, c)
