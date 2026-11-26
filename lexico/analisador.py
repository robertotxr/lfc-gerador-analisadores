"""Interface de execução do analisador léxico: usa a tabela de análise léxica
gerada na fase de projeto para quebrar um texto fonte em tokens.

Modo 'fonte' (padrão): casamento mais longo (maximal munch). Espaços, tabs e
quebras de linha separam tokens; dois tokens podem estar colados (x=a+1;).
Se nenhum padrão casa na posição atual, o lexema de erro é o caractere atual
mais os seguintes que também não podem iniciar token (recuperação em modo
pânico), e a análise continua.

Modo 'palavras': cada palavra separada por espaço deve ser, inteira, um único
token; senão é erro (útil para listas de palavras como as do enunciado).
"""

from __future__ import annotations

import bisect
import json
import re
from typing import Dict, List, Optional

from comum.tabela_simbolos import PR, TabelaSimbolos
from comum.tokens import ERRO, Token

ESPACOS = frozenset(" \t\n\r\f\v")


class AnalisadorLexico:
    def __init__(self, dados: dict):
        if dados.get("tipo") != "analisador_lexico":
            raise ValueError("arquivo não é uma tabela de análise léxica gerada por este programa")
        self.tokens: List[str] = dados["tokens"]
        self.classe_de: Dict[str, int] = {c: i for i, cl in enumerate(dados["classes"]) for c in cl}
        self.trans: List[Dict[int, int]] = [{int(k): v for k, v in t.items()}
                                            for t in dados["transicoes"]]
        self.finais: Dict[int, str] = {int(k): v for k, v in dados["finais"].items()}
        self.inicial: int = dados["inicial"]
        self.classes_iniciais = set(self.trans[self.inicial]) if self.trans else set()

    @classmethod
    def carregar(cls, caminho: str) -> "AnalisadorLexico":
        with open(caminho, encoding="utf-8") as f:
            return cls(json.load(f))

    # ------------------------------------------------------------------
    def _passo(self, q: Optional[int], c: str) -> Optional[int]:
        if q is None:
            return None
        k = self.classe_de.get(c)
        return None if k is None else self.trans[q].get(k)

    def reconhece(self, palavra: str) -> Optional[str]:
        """Padrão da palavra inteira (ou None se não for um token)."""
        q: Optional[int] = self.inicial
        for c in palavra:
            q = self._passo(q, c)
        return self.finais.get(q) if q is not None and palavra else None

    def analisar(self, texto: str, modo: str = "fonte") -> List[Token]:
        inicios = [0] + [m.end() for m in re.finditer("\n", texto)]

        def pos(i: int):
            l = bisect.bisect_right(inicios, i)
            return l, i - inicios[l - 1] + 1

        tokens: List[Token] = []
        if modo == "palavras":
            for m in re.finditer(r"\S+", texto):
                w = m.group()
                padrao = self.reconhece(w)
                tokens.append(Token(w, padrao or ERRO, *pos(m.start())))
            return tokens
        if modo != "fonte":
            raise ValueError(f"modo desconhecido: {modo}")

        i, n = 0, len(texto)
        while i < n:
            if texto[i] in ESPACOS:
                i += 1
                continue
            q: Optional[int] = self.inicial
            j = i
            ultimo = None  # (fim, padrão) do maior prefixo aceito
            while j < n:
                q = self._passo(q, texto[j])
                if q is None:
                    break
                j += 1
                if q in self.finais:
                    ultimo = (j, self.finais[q])
            if ultimo is not None:
                fim, padrao = ultimo
                tokens.append(Token(texto[i:fim], padrao, *pos(i)))
                i = fim
            else:
                j = i + 1
                while (j < n and texto[j] not in ESPACOS
                       and self.classe_de.get(texto[j]) not in self.classes_iniciais):
                    j += 1
                tokens.append(Token(texto[i:j], ERRO, *pos(i)))
                i = j
        return tokens


def aplicar_tabela_simbolos(tokens: List[Token], ts: TabelaSimbolos) -> List[Token]:
    """Preenche nome/atributo de cada token consultando e atualizando a TS:
      - lexema já na TS como palavra reservada  -> <lexema, PR>
      - caractere(s) especial(is) (sem letras/dígitos/_) -> <lexema, padrão>
      - demais (ids, constantes...)            -> <categoria, linha na TS>
      - erro léxico                            -> <lexema, erro!>
    """
    for t in tokens:
        if t.erro:
            t.nome, t.atributo = t.lexema, ERRO
            continue
        linha = ts.buscar(t.lexema)
        if linha is not None and ts.categoria(linha) == PR:
            t.nome, t.atributo = t.lexema, PR
        elif not any(ch.isalnum() or ch == "_" for ch in t.lexema):
            t.nome, t.atributo = t.lexema, t.padrao
        else:
            if linha is None:
                linha = ts.inserir(t.lexema, t.padrao)
            t.nome, t.atributo = ts.categoria(linha), str(linha)
    return tokens
