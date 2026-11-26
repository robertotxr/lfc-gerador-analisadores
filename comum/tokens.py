"""Tokens e o formato do arquivo de tokens trocado entre léxico e sintático.

Formato (uma linha por token):
    <lexema, padrão>      saída do Trabalho I, ex.: <a1, id>  ou  <@, erro!>
    <nome, atributo>      saída com tabela de símbolos, ex.: <id, 10>, <for, PR>, <(, abre_par>
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

ERRO = "erro!"


@dataclass
class Token:
    lexema: str
    padrao: str          # padrão reconhecido, ou ERRO
    linha: int = 0
    coluna: int = 0
    nome: Optional[str] = None      # 1º componente com TS (id, for, ( ...)
    atributo: Optional[str] = None  # 2º componente com TS (linha da TS, PR, ...)

    @property
    def erro(self) -> bool:
        return self.padrao == ERRO

    def formato_lexema(self) -> str:
        return f"<{_esc(self.lexema)}, {self.padrao}>"

    def formato_ts(self) -> str:
        return f"<{_esc(self.nome)}, {self.atributo}>"

    def local(self) -> str:
        return f"linha {self.linha}, coluna {self.coluna}" if self.linha else ""


def _esc(s: Optional[str]) -> str:
    return (s or "").replace("\n", "\\n").replace("\r", "\\r")


def escrever_tokens(tokens: List[Token], com_ts: bool = False) -> str:
    f = Token.formato_ts if com_ts else Token.formato_lexema
    return "".join(f(t) + "\n" for t in tokens)


def ler_tokens(texto: str) -> List[Tuple[str, str, int]]:
    """Lê um arquivo de tokens e devolve (componente1, componente2, linha_no_arquivo).

    O separador é a última vírgula da linha, então lexemas como ',' ou '<='
    funcionam: <,, virgula>  <<=, op_rel>.
    """
    res = []
    for n, linha in enumerate(texto.splitlines(), start=1):
        s = linha.strip()
        if not s or s.startswith("#"):
            continue
        if not (s.startswith("<") and s.endswith(">")) or "," not in s:
            raise ValueError(f"linha {n} do arquivo de tokens fora do formato <a, b>: {s}")
        a, b = s[1:-1].rsplit(",", 1)
        res.append((a.strip(), b.strip(), n))
    return res
