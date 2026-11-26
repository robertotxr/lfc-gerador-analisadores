"""Interface de execução do analisador sintático: algoritmo de análise LR
(Aho et al., algoritmo 4.44 / fig. 4.36), registrando a pilha a cada passo."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from comum.tabela import formatar_tabela
from comum.tabela_simbolos import PR
from comum.tokens import ERRO, Token, ler_tokens
from .gramatica import simbolo_texto

FIM = "$"


@dataclass
class Entrada:
    """Um símbolo da entrada do sintático."""
    terminal: Optional[str]   # terminal da gramática (None = não reconhecido)
    texto: str                # como exibir (lexema ou <a, b>)
    local: str = ""           # onde está no fonte / arquivo de tokens
    erro_lexico: bool = False


@dataclass
class Passo:
    pilha: List[int]
    simbolos: List[str]
    pos: int        # índice do próximo símbolo da entrada
    acao: str


@dataclass
class Resultado:
    aceito: bool
    passos: List[Passo] = field(default_factory=list)
    mensagem: str = ""
    entrada: List[Entrada] = field(default_factory=list)

    def texto_pilha(self, max_entrada: int = 0, max_pilha: int = 0) -> str:
        """max_entrada / max_pilha > 0 limitam quantos símbolos da entrada (início) e
        da pilha (topo) aparecem por linha; 0 = tudo (usado nos arquivos)."""
        linhas = []
        for n, p in enumerate(self.passos, start=1):
            resto = [e.terminal or e.texto for e in self.entrada[p.pos:]] + [FIM]
            if max_entrada and len(resto) > max_entrada:
                resto = resto[:max_entrada] + ["..."]
            pilha, simb = [str(x) for x in p.pilha], list(p.simbolos)
            if max_pilha and len(pilha) > max_pilha:
                pilha = ["..."] + pilha[-max_pilha:]
                simb = ["..."] + simb[-(max_pilha - 1):]
            linhas.append([str(n), " ".join(pilha), " ".join(simb), " ".join(resto), p.acao])
        return formatar_tabela(["Passo", "Pilha", "Símbolos", "Entrada", "Ação"], linhas,
                               "PILHA DE EXECUÇÃO")


class AnalisadorSintatico:
    def __init__(self, dados: dict):
        if dados.get("tipo") != "analisador_sintatico":
            raise ValueError("arquivo não é uma tabela SLR gerada por este programa")
        self.producoes: List[Tuple[str, List[str]]] = [(c, list(b)) for c, b in dados["producoes"]]
        self.nao_terminais = set(dados["nao_terminais"])
        self.terminais = set(dados["terminais"])
        self.palavras_reservadas: List[str] = dados.get("palavras_reservadas", [])
        self.conflitos: List[str] = dados.get("conflitos", [])
        self._prs = set(self.palavras_reservadas)
        self.acao: Dict[int, Dict[str, list]] = {int(k): v for k, v in dados["acao"].items()}
        self.desvio: Dict[int, Dict[str, int]] = {int(k): v for k, v in dados["desvio"].items()}

    @classmethod
    def carregar(cls, caminho: str) -> "AnalisadorSintatico":
        with open(caminho, encoding="utf-8") as f:
            return cls(json.load(f))

    # ------------------------------------------------------------ entrada
    def terminal_de(self, a: str, b: str) -> Optional[str]:
        """Terminal da gramática correspondente a um token <a, b>.

        Aceita os dois formatos do léxico:
          com TS  (<id, 10>, <num, 11>, <for, PR>, <(, abre_par>)
          sem TS  (<x1, id>, <for, id>, <(, abre_par>)  - formato do Trabalho I
        Palavra reservada (está na lista de PRs ou veio marcada como PR) -> o lexema.
        Senão, se o 2º componente é terminal (padrão: id, num...) -> ele;
        senão, se o 1º é terminal (símbolo literal "(" ou categoria com TS) -> ele.
        Sem lista de PRs, o 1º componente tem precedência sobre o 2º."""
        if b == ERRO:
            return None
        if a in self._prs or b == PR:
            return a if a in self.terminais else None
        ordem = (b, a) if self._prs else (a, b)
        for x in ordem:
            if x in self.terminais:
                return x
        return None

    def entrada_de_arquivo(self, texto: str) -> List[Entrada]:
        res = []
        for a, b, n in ler_tokens(texto):
            res.append(Entrada(self.terminal_de(a, b), f"<{a}, {b}>",
                               f"linha {n} do arquivo de tokens", b == ERRO))
        return res

    def entrada_de_tokens(self, tokens: Sequence[Token]) -> List[Entrada]:
        res = []
        for t in tokens:
            if t.nome is not None:
                term = self.terminal_de(t.nome, t.atributo)
            else:
                term = self.terminal_de(t.lexema, t.padrao)
            res.append(Entrada(term, t.lexema, t.local(), t.erro))
        return res

    # ------------------------------------------------------------ análise
    def _desc_producao(self, p: int) -> str:
        cab, corpo = self.producoes[p]
        rhs = " ".join(simbolo_texto(s, s in self.nao_terminais) for s in corpo) or "&"
        return f"<{cab}> ::= {rhs}"

    def analisar(self, entrada: List[Entrada]) -> Resultado:
        res = Resultado(False, entrada=entrada)
        pilha: List[int] = [0]
        simbolos: List[str] = []
        pos = 0
        limite = 50 * (len(entrada) + 10) + 10000  # proteção contra laço infinito
        while len(res.passos) < limite:
            s = pilha[-1]
            atual = entrada[pos] if pos < len(entrada) else Entrada(FIM, FIM, "fim da entrada")
            a = atual.terminal
            acao = self.acao.get(s, {}).get(a) if a is not None else None
            if acao is None:
                res.passos.append(Passo(list(pilha), list(simbolos), pos, "ERRO"))
                res.mensagem = self._mensagem_erro(s, atual)
                return res
            if acao[0] == "s":
                res.passos.append(Passo(list(pilha), list(simbolos), pos, f"empilha {acao[1]}"))
                pilha.append(acao[1])
                simbolos.append(a)
                pos += 1
            elif acao[0] == "r":
                p = acao[1]
                cab, corpo = self.producoes[p]
                res.passos.append(Passo(list(pilha), list(simbolos), pos,
                                        f"reduz ({p}) {self._desc_producao(p)}"))
                if corpo:
                    del pilha[-len(corpo):]
                    del simbolos[-len(corpo):]
                t = pilha[-1]
                pilha.append(self.desvio[t][cab])
                simbolos.append(f"<{cab}>")
            else:  # acc
                res.passos.append(Passo(list(pilha), list(simbolos), pos, "aceita"))
                res.aceito = True
                res.mensagem = "Entrada aceita: o código está sintaticamente correto."
                return res
        res.mensagem = "análise interrompida: número de passos excedido"
        return res

    def _mensagem_erro(self, estado: int, atual: Entrada) -> str:
        esperados = sorted(self.acao.get(estado, {}), key=lambda t: (t == FIM, t))
        onde = f" ({atual.local})" if atual.local else ""
        if atual.erro_lexico:
            inicio = f"Erro léxico: '{atual.texto}' não é um token válido{onde}."
        elif atual.terminal is None:
            inicio = (f"Erro: o token {atual.texto}{onde} não corresponde a nenhum terminal "
                      f"da gramática.")
        elif atual.terminal == FIM:
            inicio = "Erro sintático: fim de entrada inesperado."
        else:
            inicio = f"Erro sintático em '{atual.texto}'{onde}: token inesperado."
        return inicio + " Esperado: " + "  ".join(f"'{t}'" for t in esperados)
