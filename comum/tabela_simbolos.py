"""Tabela de símbolos compartilhada entre os analisadores léxico e sintático.

As palavras reservadas são inseridas a priori com a categoria PR. Quando o
léxico encontra um lexema já presente, devolve o token lá indicado (ex.:
<for, PR>); senão insere o lexema e devolve <categoria, linha da TS> (ex.: <id, 10>).
As linhas são numeradas a partir de 1.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from .tabela import formatar_tabela

PR = "PR"


class TabelaSimbolos:
    def __init__(self, palavras_reservadas: Iterable[str] = ()):
        self.entradas: List[Tuple[str, str]] = []
        self._indice: Dict[str, int] = {}
        for p in palavras_reservadas:
            if p not in self._indice:
                self.inserir(p, PR)

    def buscar(self, lexema: str) -> Optional[int]:
        return self._indice.get(lexema)

    def inserir(self, lexema: str, categoria: str) -> int:
        if lexema in self._indice:
            return self._indice[lexema]
        self.entradas.append((lexema, categoria))
        self._indice[lexema] = len(self.entradas)
        return len(self.entradas)

    def categoria(self, linha: int) -> str:
        return self.entradas[linha - 1][1]

    def lexema(self, linha: int) -> str:
        return self.entradas[linha - 1][0]

    def eh_reservada(self, lexema: str) -> bool:
        i = self.buscar(lexema)
        return i is not None and self.categoria(i) == PR

    def __len__(self) -> int:
        return len(self.entradas)

    def texto(self) -> str:
        linhas = [[str(i), lex, cat] for i, (lex, cat) in enumerate(self.entradas, start=1)]
        return formatar_tabela(["Linha", "Lexema", "Categoria"], linhas, "TABELA DE SÍMBOLOS")


def ler_palavras_reservadas(texto: str) -> List[str]:
    """Uma ou mais palavras por linha (separadas por espaço ou vírgula);
    linhas iniciadas por # são comentários."""
    palavras: List[str] = []
    for linha in texto.splitlines():
        s = linha.strip()
        if not s or s.startswith("#"):
            continue
        for p in s.replace(",", " ").split():
            if p not in palavras:
                palavras.append(p)
    return palavras
