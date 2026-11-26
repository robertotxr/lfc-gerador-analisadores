"""Representação de autômatos finitos (AFD e AFND com &-transições)."""

from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from comum.tabela import formatar_tabela, para_csv
from .simbolos import EPSILON, Classe, Simbolo, chave_simbolo, rotulo


class AF:
    """Autômato finito. Estados são inteiros 0..n-1 (exibidos como q0..qn-1).

    finais: estado final -> nome do padrão (token) que ele reconhece.
    trans:  estado -> {símbolo -> conjunto de destinos}; símbolo é uma classe
            de caracteres (frozenset) ou EPSILON.
    """

    def __init__(self, alfabeto: Iterable[Classe] = ()):
        self.n = 0
        self.inicial: Optional[int] = None
        self.finais: Dict[int, str] = {}
        self.trans: Dict[int, Dict[Simbolo, Set[int]]] = {}
        self.descricao: Dict[int, str] = {}
        self.alfabeto: List[Classe] = sorted(set(alfabeto), key=chave_simbolo)

    # ------------------------------------------------------------ construção
    def novo_estado(self, descricao: Optional[str] = None) -> int:
        q = self.n
        self.n += 1
        self.trans[q] = {}
        if descricao is not None:
            self.descricao[q] = descricao
        return q

    @property
    def estados(self) -> range:
        return range(self.n)

    def adicionar(self, origem: int, simbolo: Simbolo, destino: int) -> None:
        self.trans[origem].setdefault(simbolo, set()).add(destino)

    # ------------------------------------------------------------ consulta
    def destinos(self, origem: int, simbolo: Simbolo) -> Set[int]:
        return self.trans[origem].get(simbolo, set())

    def destino(self, origem: int, simbolo: Simbolo) -> Optional[int]:
        d = self.trans[origem].get(simbolo)
        if not d:
            return None
        if len(d) != 1:
            raise ValueError("destino() chamado em autômato não determinístico")
        return next(iter(d))

    def tem_epsilon(self) -> bool:
        return any(EPSILON in t for t in self.trans.values())

    def deterministico(self) -> bool:
        return not self.tem_epsilon() and all(
            len(d) <= 1 for t in self.trans.values() for d in t.values())

    def num_transicoes(self) -> int:
        return sum(len(d) for t in self.trans.values() for d in t.values())

    def fecho_epsilon(self, estados: Iterable[int]) -> Set[int]:
        fecho = set(estados)
        pilha = list(fecho)
        while pilha:
            q = pilha.pop()
            for p in self.trans[q].get(EPSILON, ()):
                if p not in fecho:
                    fecho.add(p)
                    pilha.append(p)
        return fecho

    def classe_de(self, c: str) -> Optional[Classe]:
        for a in self.alfabeto:
            if c in a:
                return a
        return None

    def reconhece(self, palavra: str) -> Set[str]:
        """Simula o autômato (determinístico ou não) sobre a palavra inteira e
        devolve os nomes dos padrões dos estados finais atingidos."""
        if self.inicial is None:
            return set()
        atuais = self.fecho_epsilon({self.inicial})
        for c in palavra:
            a = self.classe_de(c)
            if a is None:
                return set()
            prox: Set[int] = set()
            for q in atuais:
                prox |= self.trans[q].get(a, set())
            atuais = self.fecho_epsilon(prox)
            if not atuais:
                return set()
        return {self.finais[q] for q in atuais if q in self.finais}

    def aceita(self, palavra: str) -> bool:
        return bool(self.reconhece(palavra))

    def alcancaveis(self) -> Set[int]:
        if self.inicial is None:
            return set()
        vistos = {self.inicial}
        fila = deque([self.inicial])
        while fila:
            q = fila.popleft()
            for dests in self.trans[q].values():
                for p in dests:
                    if p not in vistos:
                        vistos.add(p)
                        fila.append(p)
        return vistos

    # ------------------------------------------------------------ exibição
    def _colunas(self) -> List[Simbolo]:
        cols: List[Simbolo] = list(self.alfabeto)
        if self.tem_epsilon():
            cols.append(EPSILON)
        return cols

    def tabela(self, mostrar_descricao: bool = True) -> Tuple[List[str], List[List[str]]]:
        cols = self._colunas()
        cab = ["", "δ"] + [rotulo(c) for c in cols] + ["Token"]
        usa_desc = mostrar_descricao and bool(self.descricao)
        if usa_desc:
            cab.append("Composição")
        det = self.deterministico()
        linhas = []
        for q in self.estados:
            marca = ("->" if q == self.inicial else "") + ("*" if q in self.finais else "")
            linha = [marca, f"q{q}"]
            for c in cols:
                d = sorted(self.trans[q].get(c, ()))
                if not d:
                    linha.append("-")
                elif len(d) == 1 and c != EPSILON and det:
                    linha.append(f"q{d[0]}")
                else:
                    linha.append("{" + ",".join(f"q{x}" for x in d) + "}")
            linha.append(self.finais.get(q, ""))
            if usa_desc:
                linha.append(self.descricao.get(q, ""))
            linhas.append(linha)
        return cab, linhas

    def texto(self, titulo: str = "", mostrar_descricao: bool = True) -> str:
        cab, linhas = self.tabela(mostrar_descricao)
        tipo = "AFD" if self.deterministico() else "AFND"
        info = (f"{tipo} | estados: {self.n} | finais: {len(self.finais)} | "
                f"transições: {self.num_transicoes()}   (-> inicial, * final, - indefinido)")
        return (titulo + "\n" if titulo else "") + info + "\n" + formatar_tabela(cab, linhas)

    def csv(self) -> str:
        cab, linhas = self.tabela()
        return para_csv(cab, linhas)

    def dot(self, nome: str = "AF") -> str:
        """Representação Graphviz (dot -Tpng arquivo.dot -o arquivo.png)."""
        def esc(s: str) -> str:
            return s.replace("\\", "\\\\").replace('"', '\\"')

        out = [f'digraph "{esc(nome)}" {{', "  rankdir=LR;", '  inicio [shape=point];']
        for q in self.estados:
            forma = "doublecircle" if q in self.finais else "circle"
            rot = f"q{q}" + (f"\\n{esc(self.finais[q])}" if q in self.finais else "")
            out.append(f'  q{q} [shape={forma}, label="{rot}"];')
        if self.inicial is not None:
            out.append(f"  inicio -> q{self.inicial};")
        for q in self.estados:
            agrup: Dict[int, List[str]] = {}
            for s, dests in self.trans[q].items():
                for p in dests:
                    agrup.setdefault(p, []).append(rotulo(s))
            for p, rots in sorted(agrup.items()):
                out.append(f'  q{q} -> q{p} [label="{esc(", ".join(sorted(rots)))}"];')
        out.append("}")
        return "\n".join(out) + "\n"

    # ------------------------------------------------------------ cópia
    def renumerado(self, ordem: Sequence[int]) -> "AF":
        """Novo autômato só com os estados de `ordem`, renumerados na ordem dada."""
        mapa = {q: i for i, q in enumerate(ordem)}
        novo = AF(self.alfabeto)
        for q in ordem:
            novo.novo_estado(self.descricao.get(q))
        novo.inicial = mapa.get(self.inicial)
        for q in ordem:
            if q in self.finais:
                novo.finais[mapa[q]] = self.finais[q]
            for s, dests in self.trans[q].items():
                for p in dests:
                    if p in mapa:
                        novo.adicionar(mapa[q], s, mapa[p])
        return novo
