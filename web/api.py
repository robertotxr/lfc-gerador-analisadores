"""Funções da interface web: recebem textos (definições, gramática, fonte...)
e devolvem dicionários prontos para virar JSON. Usam os mesmos módulos da
linha de comando; nada de lógica duplicada aqui, só serialização."""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from comum.tabela_simbolos import TabelaSimbolos, ler_palavras_reservadas
from comum.tokens import Token
from lexico import gerador as gerador_lexico
from lexico.analisador import AnalisadorLexico, aplicar_tabela_simbolos
from lexico.automato import AF
from lexico.simbolos import EPSILON, rotulo
from sintatico import gerador as gerador_sintatico
from sintatico.analisador import AnalisadorSintatico, Resultado
from sintatico.first_follow import _ordenar
from sintatico.lr0 import item_texto
from sintatico.slr import acao_texto

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ autômatos
def af_json(af: AF) -> dict:
    cols = list(af.alfabeto) + ([EPSILON] if af.tem_epsilon() else [])
    arestas: Dict[tuple, List[str]] = {}
    for q in af.estados:
        for s, dests in af.trans[q].items():
            for p in dests:
                arestas.setdefault((q, p), []).append(rotulo(s))
    return {
        "deterministico": af.deterministico(),
        "transicoes": af.num_transicoes(),
        "colunas": [rotulo(c) for c in cols],
        "estados": [{
            "id": q,
            "inicial": q == af.inicial,
            "token": af.finais.get(q),
            "descricao": af.descricao.get(q, ""),
            "destinos": [sorted(af.trans[q].get(c, ())) for c in cols],
        } for q in af.estados],
        "arestas": [{"de": o, "para": d, "rotulo": ", ".join(sorted(r))}
                    for (o, d), r in sorted(arestas.items())],
    }


def _resumo_min(mn) -> dict:
    return {"inalcancaveis": mn.inalcancaveis, "mortos": mn.mortos,
            "classes": mn.classes, "afd": af_json(mn.afd)}


# ------------------------------------------------------------------ léxico
def lexico_projetar(definicoes: str, minimizar_tabela: bool = False) -> dict:
    p = gerador_lexico.projetar(definicoes, minimizar_tabela)
    padroes = []
    for nome in p.tokens:
        conv = p.conversoes[nome]
        padroes.append({
            "nome": nome,
            "er_expandida": conv.er_expandida,
            "firstpos": sorted(conv.firstpos_raiz),
            "pos_fim": conv.pos_fim,
            "followpos": [{"pos": pos,
                           "simbolo": "#" if s is None else rotulo(s),
                           "follow": sorted(conv.followpos.get(pos, ()))}
                          for pos, s in sorted(conv.simbolo_pos.items())],
            "afd": af_json(conv.afd),
            "minimizacao": _resumo_min(p.minimizacoes[nome]),
        })
    return {
        "definicoes": [{"nome": d.nome, "er": d.er, "auxiliar": d.auxiliar,
                        "prioridade": p.tokens.index(d.nome) + 1 if not d.auxiliar else None}
                       for d in p.definicoes],
        "tokens": p.tokens,
        "padroes": padroes,
        "uniao": af_json(p.uniao),
        "determinizado": af_json(p.determinizacao.afd),
        "tabela": af_json(p.tabela),
        "minimizacao_final": _resumo_min(p.minimizacao_final) if p.minimizacao_final else None,
        "conflitos": [{"estado": q, "padroes": ps, "escolhido": e}
                      for q, ps, e in p.determinizacao.conflitos],
        "avisos": p.avisos,
    }


def _token_json(t: Token) -> dict:
    return {"lexema": t.lexema, "padrao": t.padrao, "linha": t.linha, "coluna": t.coluna,
            "erro": t.erro, "nome": t.nome, "atributo": t.atributo}


def _ts_json(ts: TabelaSimbolos) -> List[dict]:
    return [{"linha": i, "lexema": lex, "categoria": cat}
            for i, (lex, cat) in enumerate(ts.entradas, start=1)]


def lexico_executar(definicoes: str, fonte: str, modo: str = "fonte",
                    palavras_reservadas: Optional[str] = None) -> dict:
    p = gerador_lexico.projetar(definicoes)
    tokens = AnalisadorLexico(p.para_dict()).analisar(fonte, modo)
    ts = None
    if palavras_reservadas is not None and palavras_reservadas.strip():
        ts = TabelaSimbolos(ler_palavras_reservadas(palavras_reservadas))
        aplicar_tabela_simbolos(tokens, ts)
    return {"tokens": [_token_json(t) for t in tokens],
            "ts": _ts_json(ts) if ts else None,
            "erros": sum(t.erro for t in tokens)}


# ------------------------------------------------------------------ sintático
def _projeto_sintatico_json(p) -> dict:
    g = p.aumentada
    terms = list(g.terminais) + ["$"]
    nts = [nt for nt in g.nao_terminais if nt != g.inicial]
    conf = {}
    for c in p.tabela.conflitos:
        conf.setdefault(c.estado, []).append(c.simbolo)
    linhas = []
    for i in sorted(p.tabela.acao):
        linhas.append({
            "estado": i,
            "acao": {t: acao_texto(a) for t, a in p.tabela.acao[i].items()},
            "desvio": p.tabela.desvio[i],
            "conflitos": conf.get(i, []),
        })
    return {
        "producoes": [{"n": i, "texto": g.producao_texto(i), "cabeca": c, "corpo": list(b)}
                      for i, (c, b) in enumerate(g.producoes)],
        "terminais": g.terminais,
        "nao_terminais": g.nao_terminais,
        "inicial": g.inicial,
        "first": {nt: _ordenar(g, p.first[nt]) for nt in g.nao_terminais},
        "follow": {nt: _ordenar(g, p.follow[nt]) for nt in g.nao_terminais},
        "estados": [{"n": i,
                     "itens": [item_texto(g, it) for it in itens],
                     "goto": [{"simbolo": g.simbolo_texto(X), "destino": j}
                              for X, j in p.colecao.transicoes[i].items()]}
                    for i, itens in enumerate(p.colecao.estados)],
        "tabela": {"terminais": terms, "nao_terminais": nts, "linhas": linhas},
        "conflitos": [c.texto(g) for c in p.tabela.conflitos],
        "eh_slr": p.eh_slr,
        "palavras_reservadas": p.palavras_reservadas,
        "avisos": p.avisos,
    }


def sintatico_projetar(gramatica: str, palavras_reservadas: str = "") -> dict:
    p = gerador_sintatico.projetar(gramatica, ler_palavras_reservadas(palavras_reservadas or ""))
    return _projeto_sintatico_json(p)


def _resultado_json(r: Resultado) -> dict:
    return {
        "aceito": r.aceito,
        "mensagem": r.mensagem,
        "entrada": [{"terminal": e.terminal, "texto": e.texto, "local": e.local,
                     "erro_lexico": e.erro_lexico} for e in r.entrada],
        "passos": [{"pilha": s.pilha, "simbolos": s.simbolos, "pos": s.pos, "acao": s.acao}
                   for s in r.passos],
    }


def sintatico_executar(gramatica: str, palavras_reservadas: str, tokens: str) -> dict:
    p = gerador_sintatico.projetar(gramatica, ler_palavras_reservadas(palavras_reservadas or ""))
    an = AnalisadorSintatico(p.para_dict())
    return _resultado_json(an.analisar(an.entrada_de_arquivo(tokens)))


# ------------------------------------------------------------------ integrado
def compilar(lexico: str, gramatica: str, palavras_reservadas: str, fonte: str,
             modo: str = "fonte") -> dict:
    from main import verificar_integracao  # import tardio: main importa este pacote sob demanda

    prs = ler_palavras_reservadas(palavras_reservadas or "")
    lex_proj = gerador_lexico.projetar(lexico)
    sin_proj = gerador_sintatico.projetar(gramatica, prs)
    tokens = AnalisadorLexico(lex_proj.para_dict()).analisar(fonte, modo)
    ts = TabelaSimbolos(prs)
    aplicar_tabela_simbolos(tokens, ts)
    sin = AnalisadorSintatico(sin_proj.para_dict())
    res = sin.analisar(sin.entrada_de_tokens(tokens))
    erros = [t for t in tokens if t.erro]
    return {
        "ok": res.aceito and not erros,
        "lexico": {"tokens": len(lex_proj.tokens), "estados": lex_proj.tabela.n,
                   "avisos": lex_proj.avisos},
        "sintatico": {"producoes": len(sin_proj.aumentada.producoes),
                      "estados": len(sin_proj.colecao.estados), "eh_slr": sin_proj.eh_slr,
                      "conflitos": [c.texto(sin_proj.aumentada) for c in sin_proj.tabela.conflitos],
                      "avisos": sin_proj.avisos},
        "avisos": verificar_integracao(lex_proj, sin_proj, prs),
        "tokens": [_token_json(t) for t in tokens],
        "ts": _ts_json(ts),
        "erros_lexicos": len(erros),
        "analise": _resultado_json(res),
    }


# ------------------------------------------------------------------ exemplos
def _ler(*partes: str) -> str:
    with open(os.path.join(RAIZ, *partes), encoding="utf-8") as f:
        return f.read()


_TITULOS_LEX = {
    "01_enunciado_id_num": "Enunciado, exemplo 1: id e num",
    "02_enunciado_ab": "Enunciado, exemplo 2: er1 e er2",
    "03_definicoes_regulares": "Definições auxiliares e números reais",
    "04_operadores": "Operadores e casamento mais longo",
    "05_aho_abb": "(a|b)*abb do livro",
    "06_cadeias_negacao": "Cadeias, classes negadas e comentários",
    "07_erros_lexicos": "Erros léxicos",
    "08_prioridade_reservadas": "Palavras-chave e prioridade",
}
_TITULOS_SIN = {
    "01_expressoes_aho": "Expressões (gramática 4.1 do livro)",
    "02_nao_slr_aho": "Gramática que não é SLR(1)",
    "03_epsilon": "Produções vazias",
    "04_if_else_ambigua": "Else pendente",
    "05_calculadora_integrada": "Calculadora",
    "06_formatos_alternativos": "Listas aninhadas (notações alternativas)",
}


def exemplos() -> dict:
    lex, sin, comp = [], [], []
    # a linguagem do grupo aparece primeiro nas três abas
    lexico_mane = _ler("linguagem", "lexico.er")
    correto = _ler("linguagem", "correto.mane")
    prs_mane = _ler("linguagem", "palavras_reservadas.txt")
    tokens_mane = lexico_executar(lexico_mane, correto, "fonte", prs_mane)["tokens"]
    lex.append({"id": "manezes", "titulo": "Manezês: definição léxica do grupo",
                "definicoes": lexico_mane, "entrada": correto, "modo": "fonte"})
    sin.append({"id": "manezes", "titulo": "Manezês: gramática do grupo",
                "gramatica": _ler("linguagem", "sintatico.glc"), "palavras_reservadas": prs_mane,
                "tokens": "".join(f"<{t['nome']}, {t['atributo']}>\n" for t in tokens_mane)})
    base = os.path.join(RAIZ, "exemplos", "lexico")
    for d in sorted(os.listdir(base)):
        lex.append({"id": d, "titulo": _TITULOS_LEX.get(d, d),
                    "definicoes": _ler("exemplos", "lexico", d, "definicoes.er"),
                    "entrada": _ler("exemplos", "lexico", d, "entrada.txt"),
                    "modo": "palavras" if "abb" in d else "fonte"})
        if os.path.exists(os.path.join(base, d, "definicoes_intencao.er")):
            lex.append({"id": d + "_intencao", "titulo": "Enunciado, exemplo 2: versão que separa a e b",
                        "definicoes": _ler("exemplos", "lexico", d, "definicoes_intencao.er"),
                        "entrada": _ler("exemplos", "lexico", d, "entrada.txt"), "modo": "fonte"})
    base = os.path.join(RAIZ, "exemplos", "sintatico")
    for d in sorted(os.listdir(base)):
        arqs = sorted(os.listdir(os.path.join(base, d)))
        toks = [a for a in arqs if a.startswith("tokens")]
        pr = _ler("exemplos", "sintatico", d, "palavras_reservadas.txt") if "palavras_reservadas.txt" in arqs else ""
        sin.append({"id": d, "titulo": _TITULOS_SIN.get(d, d),
                    "gramatica": _ler("exemplos", "sintatico", d, "gramatica.glc"),
                    "palavras_reservadas": pr,
                    "tokens": _ler("exemplos", "sintatico", d, toks[0]) if toks else ""})
        if "lexico.er" in arqs:
            for prog in [a for a in arqs if a.startswith("programa")]:
                comp.append({"id": f"{d}_{prog}", "titulo": f"Calculadora: {prog}",
                             "lexico": _ler("exemplos", "sintatico", d, "lexico.er"),
                             "gramatica": _ler("exemplos", "sintatico", d, "gramatica.glc"),
                             "palavras_reservadas": pr,
                             "fonte": _ler("exemplos", "sintatico", d, prog)})
    titulos = {"correto.mane": "Manezês: código correto",
               "com_erro.mane": "Manezês: erro sintático",
               "com_erro_lexico.mane": "Manezês: erro léxico"}
    for prog, titulo in titulos.items():
        comp.insert(len([c for c in comp if c["id"].startswith("manezes")]), {
            "id": "manezes_" + prog, "titulo": titulo,
            "lexico": _ler("linguagem", "lexico.er"),
            "gramatica": _ler("linguagem", "sintatico.glc"),
            "palavras_reservadas": _ler("linguagem", "palavras_reservadas.txt"),
            "fonte": _ler("linguagem", prog)})
    return {"lexico": lex, "sintatico": sin, "compilar": comp}
