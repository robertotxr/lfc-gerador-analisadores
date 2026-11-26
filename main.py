#!/usr/bin/env python3
"""Gerador de Analisadores Léxicos e Sintáticos (SLR) - LFC/UFSC.

Uso rápido (veja o README.md para tudo):
    python3 main.py                                  # menu interativo
    python3 main.py web                              # interface gráfica no navegador
    python3 main.py lexico projetar  DEF.er   [-o PASTA]
    python3 main.py lexico executar  PASTA/analisador_lexico.json FONTE [-o tokens.txt]
    python3 main.py sintatico projetar GRAM.glc [--pr PR.txt] [-o PASTA]
    python3 main.py sintatico executar PASTA/analisador_sintatico.json TOKENS.txt
    python3 main.py compilar --lexico DEF.er --gramatica GRAM.glc --pr PR.txt FONTE
"""

from __future__ import annotations

import argparse
import os
import sys

sys.setrecursionlimit(20000)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum.tabela import secao  # noqa: E402
from comum.tabela_simbolos import TabelaSimbolos, ler_palavras_reservadas  # noqa: E402
from comum.tokens import escrever_tokens  # noqa: E402
from lexico.analisador import AnalisadorLexico, aplicar_tabela_simbolos  # noqa: E402
from lexico.er import ErroER  # noqa: E402
from lexico import gerador as gerador_lexico  # noqa: E402
from sintatico.analisador import AnalisadorSintatico  # noqa: E402
from sintatico.gramatica import ErroGramatica  # noqa: E402
from sintatico import gerador as gerador_sintatico  # noqa: E402

LIMITE_ENTRADA_TELA = 8
LIMITE_PILHA_TELA = 10


def ler(caminho: str) -> str:
    """Lê texto em UTF-8 (com ou sem BOM); se falhar, tenta Latin-1 (Windows)."""
    with open(caminho, "rb") as f:
        dados = f.read()
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dados.decode("latin-1")


def escrever(caminho: str, texto: str) -> None:
    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)


def nome_base(caminho: str) -> str:
    return os.path.splitext(os.path.basename(caminho))[0]


def mostrar(texto: str, silencioso: bool = False) -> None:
    if not silencioso:
        print(texto)


# ============================================================== léxico
def cmd_lexico_projetar(definicoes: str, saida: str, minimizar_tabela: bool = False,
                        silencioso: bool = False):
    projeto = gerador_lexico.projetar(ler(definicoes), minimizar_tabela)
    arquivos = projeto.salvar(saida)
    mostrar(projeto.relatorio(), silencioso)
    if silencioso:
        mostrar(projeto.texto_tabela())
        for a in projeto.avisos:
            print("Aviso:", a)
    print(f"Analisador léxico gerado: {arquivos['json']}")
    print(f"Relatório completo: {arquivos['relatorio']}  |  tabela: {arquivos['tabela']} "
          f"(e .csv)  |  grafos: {os.path.join(saida, 'dot')}/")
    return projeto


def cmd_lexico_executar(tabela: str, fonte: str, saida: str, modo: str = "fonte",
                        pr: str = None, sintatico: str = None, silencioso: bool = False):
    lex = AnalisadorLexico.carregar(tabela)
    tokens = lex.analisar(ler(fonte), modo)
    prs = None
    if pr:
        prs = ler_palavras_reservadas(ler(pr))
    elif sintatico:
        prs = AnalisadorSintatico.carregar(sintatico).palavras_reservadas
    if prs is None:
        texto = escrever_tokens(tokens)
        escrever(saida, texto)
        mostrar(texto.rstrip("\n"), silencioso)
    else:
        ts = TabelaSimbolos(prs)
        aplicar_tabela_simbolos(tokens, ts)
        texto = escrever_tokens(tokens, com_ts=True)
        escrever(saida, texto)
        caminho_ts = os.path.splitext(saida)[0] + "_tabela_simbolos.txt"
        escrever(caminho_ts, ts.texto() + "\n")
        mostrar(texto.rstrip("\n"), silencioso)
        mostrar("\n" + ts.texto(), silencioso)
        print(f"\nTabela de símbolos: {caminho_ts}")
    erros = [t for t in tokens if t.erro]
    print(f"\n{len(tokens)} token(s), {len(erros)} erro(s) léxico(s). Lista de tokens: {saida}")
    for t in erros:
        print(f"  erro léxico: '{t.lexema}' ({t.local()})")
    return tokens


# ============================================================== sintático
def cmd_sintatico_projetar(gramatica: str, saida: str, pr: str = None, silencioso: bool = False):
    prs = ler_palavras_reservadas(ler(pr)) if pr else []
    projeto = gerador_sintatico.projetar(ler(gramatica), prs)
    arquivos = projeto.salvar(saida)
    mostrar(projeto.relatorio(), silencioso)
    if silencioso:
        print("Gramática SLR(1)." if projeto.eh_slr else
              f"ATENÇÃO: gramática não é SLR(1) ({len(projeto.tabela.conflitos)} conflito(s)); "
              f"tabela gerada resolvendo conflitos com empilhar > reduzir.")
    print(f"Analisador sintático gerado: {arquivos['json']}")
    print(f"Relatório completo: {arquivos['relatorio']}  |  tabela: {arquivos['tabela']} (e .csv)")
    return projeto


def cmd_sintatico_executar(tabela: str, tokens: str, saida: str, silencioso: bool = False):
    sin = AnalisadorSintatico.carregar(tabela)
    if sin.conflitos:
        print(f"Aviso: a gramática não é SLR(1); a tabela tem {len(sin.conflitos)} conflito(s) "
              f"resolvido(s) por empilhar > reduzir:")
        for c in sin.conflitos:
            print("  -", c)
    entrada = sin.entrada_de_arquivo(ler(tokens))
    res = sin.analisar(entrada)
    escrever(saida, res.texto_pilha() + "\n\n" + res.mensagem + "\n")
    mostrar(res.texto_pilha(LIMITE_ENTRADA_TELA, LIMITE_PILHA_TELA), silencioso)
    print("\n" + res.mensagem)
    print(f"Pilha de execução completa: {saida}")
    return res


# ============================================================== pipeline
def verificar_integracao(lex_proj, sin_proj, prs) -> list:
    """Confere se cada terminal da gramática pode ser produzido pelo léxico."""
    avisos = []
    lex = AnalisadorLexico(lex_proj.para_dict())
    for t in sin_proj.gramatica.terminais:
        if t in prs or t in lex_proj.tokens:
            continue
        padrao = lex.reconhece(t)
        if padrao is None:
            avisos.append(f"o terminal '{t}' não é nome de padrão, nem palavra reservada, "
                          f"nem é reconhecido pelo analisador léxico")
        elif any(c.isalnum() for c in t):
            avisos.append(f"o terminal '{t}' é reconhecido como '{padrao}' pelo léxico; "
                          f"inclua-o nas palavras reservadas")
    return avisos


def cmd_compilar(lexico: str, gramatica: str, pr: str, fonte: str, saida: str,
                 modo: str = "fonte", silencioso: bool = False) -> bool:
    prs = ler_palavras_reservadas(ler(pr)) if pr else []
    print(secao("1. PROJETO DO ANALISADOR LÉXICO"))
    lex_proj = gerador_lexico.projetar(ler(lexico))
    lex_proj.salvar(os.path.join(saida, "lexico"))
    print(f"{len(lex_proj.tokens)} padrões de token; tabela léxica com {lex_proj.tabela.n} estados "
          f"-> {os.path.join(saida, 'lexico')}/")
    for a in lex_proj.avisos:
        print("  Aviso:", a)

    print(secao("2. PROJETO DO ANALISADOR SINTÁTICO"))
    sin_proj = gerador_sintatico.projetar(ler(gramatica), prs)
    sin_proj.salvar(os.path.join(saida, "sintatico"))
    print(f"{len(sin_proj.aumentada.producoes)} produções; {len(sin_proj.colecao.estados)} estados LR(0); "
          + ("gramática SLR(1)" if sin_proj.eh_slr else
             f"ATENÇÃO: {len(sin_proj.tabela.conflitos)} conflito(s) - não é SLR(1)")
          + f" -> {os.path.join(saida, 'sintatico')}/")
    for c in sin_proj.tabela.conflitos:
        print("  Conflito:", c.texto(sin_proj.aumentada))
    for a in sin_proj.avisos + verificar_integracao(lex_proj, sin_proj, prs):
        print("  Aviso:", a)

    print(secao("3. ANÁLISE LÉXICA DO FONTE"))
    lex = AnalisadorLexico(lex_proj.para_dict())
    tokens = lex.analisar(ler(fonte), modo)
    ts = TabelaSimbolos(prs)
    aplicar_tabela_simbolos(tokens, ts)
    escrever(os.path.join(saida, "tokens_lexemas.txt"), escrever_tokens(tokens))
    escrever(os.path.join(saida, "tokens.txt"), escrever_tokens(tokens, com_ts=True))
    escrever(os.path.join(saida, "tabela_simbolos.txt"), ts.texto() + "\n")
    if not silencioso:
        largura = max((len(t.formato_lexema()) for t in tokens), default=0)
        for t in tokens:
            print(f"{t.formato_lexema().ljust(largura)}   {t.formato_ts()}")
        print("\n" + ts.texto())
    erros = [t for t in tokens if t.erro]
    print(f"\n{len(tokens)} token(s), {len(erros)} erro(s) léxico(s).")
    for t in erros:
        print(f"  Erro léxico: '{t.lexema}' ({t.local()})")

    print(secao("4. ANÁLISE SINTÁTICA (PILHA DE EXECUÇÃO)"))
    sin = AnalisadorSintatico(sin_proj.para_dict())
    res = sin.analisar(sin.entrada_de_tokens(tokens))
    escrever(os.path.join(saida, "pilha.txt"), res.texto_pilha() + "\n\n" + res.mensagem + "\n")
    mostrar(res.texto_pilha(LIMITE_ENTRADA_TELA, LIMITE_PILHA_TELA), silencioso)
    ok = res.aceito and not erros
    print(secao("RESULTADO"))
    print(res.mensagem)
    if res.aceito and erros:
        print("Mas há erros léxicos (acima).")
    print("\nCÓDIGO CORRETO" if ok else "\nCÓDIGO COM ERRO")
    print(f"Arquivos gerados em: {saida}/ (tokens.txt, tokens_lexemas.txt, tabela_simbolos.txt, "
          f"pilha.txt, lexico/, sintatico/)")
    return ok


# ============================================================== menu interativo
def _perguntar(msg: str, padrao: str = "") -> str:
    r = input(f"{msg}" + (f" [{padrao}]" if padrao else "") + ": ").strip()
    return r or padrao


def _digitar_arquivo(descricao: str, caminho_padrao: str) -> str:
    print(f"Digite {descricao}. Termine com uma linha contendo apenas FIM.")
    linhas = []
    while True:
        l = input()
        if l.strip() == "FIM":
            break
        linhas.append(l)
    caminho = _perguntar("Salvar em", caminho_padrao)
    escrever(caminho, "\n".join(linhas) + "\n")
    print(f"Salvo em {caminho}")
    return caminho


def _arquivo_ou_digitar(descricao: str, caminho_padrao: str) -> str:
    r = _perguntar(f"Arquivo com {descricao} (ou D para digitar agora)")
    if r.upper() == "D":
        return _digitar_arquivo(descricao, caminho_padrao)
    return r


def menu() -> None:
    opcoes = {
        "1": "Projetar analisador léxico (definições regulares -> tabela léxica)",
        "2": "Executar analisador léxico (texto fonte -> lista de tokens)",
        "3": "Projetar analisador sintático (GLC + palavras reservadas -> tabela SLR)",
        "4": "Executar analisador sintático (lista de tokens -> pilha de execução)",
        "5": "Compilar: léxico + sintático integrados sobre um fonte",
        "6": "Abrir a interface gráfica no navegador",
        "0": "Sair",
    }
    while True:
        print(secao("GERADOR DE ANALISADORES LÉXICOS E SINTÁTICOS - LFC/UFSC"))
        for k, v in opcoes.items():
            print(f"  {k}) {v}")
        try:
            op = input("\nOpção: ").strip()
            if op == "0":
                return
            if op == "6":
                from web.servidor import iniciar
                iniciar()
                continue
            if op == "1":
                d = _arquivo_ou_digitar("as definições regulares (nome: ER)", "saida/definicoes.er")
                cmd_lexico_projetar(d, _perguntar("Pasta de saída", f"saida/lexico_{nome_base(d)}"))
            elif op == "2":
                t = _perguntar("Tabela léxica (analisador_lexico.json)")
                f = _arquivo_ou_digitar("o texto fonte", "saida/fonte.txt")
                modo = "palavras" if _perguntar("Modo: F = fonte, P = cada palavra é um token",
                                                "F").upper() == "P" else "fonte"
                pr = _perguntar("Arquivo de palavras reservadas para usar a tabela de símbolos "
                                "(Enter = sem TS)")
                cmd_lexico_executar(t, f, _perguntar("Arquivo de saída",
                                                     f"saida/{nome_base(f)}.tokens.txt"),
                                    modo, pr or None)
            elif op == "3":
                g = _arquivo_ou_digitar("a gramática (<A> ::= corpo)", "saida/gramatica.glc")
                pr = _perguntar("Arquivo de palavras reservadas (Enter = nenhum)")
                cmd_sintatico_projetar(g, _perguntar("Pasta de saída",
                                                     f"saida/sintatico_{nome_base(g)}"), pr or None)
            elif op == "4":
                t = _perguntar("Tabela SLR (analisador_sintatico.json)")
                k = _perguntar("Arquivo com a lista de tokens")
                cmd_sintatico_executar(t, k, _perguntar("Arquivo de saída",
                                                        f"saida/{nome_base(k)}.pilha.txt"))
            elif op == "5":
                l = _perguntar("Definições léxicas (.er)", "linguagem/lexico.er")
                g = _perguntar("Gramática (.glc)", "linguagem/sintatico.glc")
                pr = _perguntar("Palavras reservadas", "linguagem/palavras_reservadas.txt")
                f = _arquivo_ou_digitar("o código fonte", "saida/programa.mane")
                cmd_compilar(l, g, pr, f, _perguntar("Pasta de saída", f"saida/{nome_base(f)}"))
            else:
                print("Opção inválida.")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        except FileNotFoundError as e:
            print(f"\nErro: arquivo não encontrado: {e.filename}")
        except (ErroER, ErroGramatica, ValueError, OSError, KeyError) as e:
            print(f"\nErro: {e}")
        try:
            input("\n[Enter para voltar ao menu]")
        except (EOFError, KeyboardInterrupt):
            print()
            return


# ============================================================== CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="main.py", description="Gerador de analisadores léxicos e sintáticos SLR (LFC/UFSC). "
        "Sem argumentos abre o menu interativo.")
    sub = ap.add_subparsers(dest="parte")

    lx = sub.add_parser("lexico", help="Trabalho I: gerador de analisadores léxicos")
    lxs = lx.add_subparsers(dest="acao", required=True)
    p = lxs.add_parser("projetar", help="definições regulares -> tabela de análise léxica")
    p.add_argument("definicoes")
    p.add_argument("-o", "--saida", help="pasta de saída (padrão: saida/lexico_<nome>)")
    p.add_argument("--minimizar-tabela", action="store_true",
                   help="também minimiza o AFD final (respeitando os padrões dos estados finais)")
    p.add_argument("-q", "--silencioso", action="store_true", help="mostra só a tabela final")
    p = lxs.add_parser("executar", help="texto fonte -> lista de tokens <lexema, padrão>")
    p.add_argument("tabela", help="analisador_lexico.json gerado pelo projeto")
    p.add_argument("fonte")
    p.add_argument("-o", "--saida", help="arquivo de tokens (padrão: saida/<fonte>.tokens.txt)")
    p.add_argument("--palavras", action="store_true",
                   help="cada palavra separada por espaço deve ser um token inteiro")
    p.add_argument("--pr", help="palavras reservadas: usa a tabela de símbolos (<id, n>, <for, PR>)")
    p.add_argument("--sintatico", help="usa as palavras reservadas de um analisador_sintatico.json")
    p.add_argument("-q", "--silencioso", action="store_true")

    sx = sub.add_parser("sintatico", help="Trabalho II: gerador de analisadores sintáticos SLR")
    sxs = sx.add_subparsers(dest="acao", required=True)
    p = sxs.add_parser("projetar", help="GLC -> First/Follow, coleção canônica, tabela SLR")
    p.add_argument("gramatica")
    p.add_argument("--pr", help="arquivo com as palavras reservadas")
    p.add_argument("-o", "--saida", help="pasta de saída (padrão: saida/sintatico_<nome>)")
    p.add_argument("-q", "--silencioso", action="store_true", help="não mostra o relatório")
    p = sxs.add_parser("executar", help="lista de tokens -> pilha de execução")
    p.add_argument("tabela", help="analisador_sintatico.json gerado pelo projeto")
    p.add_argument("tokens", help="arquivo de tokens gerado pelo analisador léxico")
    p.add_argument("-o", "--saida", help="arquivo da pilha (padrão: saida/<tokens>.pilha.txt)")
    p.add_argument("-q", "--silencioso", action="store_true")

    p = sub.add_parser("web", help="abre a interface gráfica no navegador")
    p.add_argument("--porta", type=int, default=8765)
    p.add_argument("--sem-navegador", action="store_true", help="não abre o navegador sozinho")

    p = sub.add_parser("compilar", help="léxico + tabela de símbolos + sintático sobre um fonte")
    p.add_argument("fonte")
    p.add_argument("--lexico", required=True, help="definições regulares (.er)")
    p.add_argument("--gramatica", required=True, help="gramática (.glc)")
    p.add_argument("--pr", help="palavras reservadas")
    p.add_argument("-o", "--saida", help="pasta de saída (padrão: saida/<fonte>)")
    p.add_argument("--palavras", action="store_true")
    p.add_argument("-q", "--silencioso", action="store_true", help="não mostra tokens e pilha")

    a = ap.parse_args(argv)
    if a.parte is None:
        menu()
        return 0
    if a.parte == "web":
        from web.servidor import iniciar
        iniciar(a.porta, not a.sem_navegador)
        return 0
    try:
        if a.parte == "lexico" and a.acao == "projetar":
            cmd_lexico_projetar(a.definicoes, a.saida or f"saida/lexico_{nome_base(a.definicoes)}",
                                a.minimizar_tabela, a.silencioso)
        elif a.parte == "lexico":
            cmd_lexico_executar(a.tabela, a.fonte, a.saida or f"saida/{nome_base(a.fonte)}.tokens.txt",
                                "palavras" if a.palavras else "fonte", a.pr, a.sintatico, a.silencioso)
        elif a.parte == "sintatico" and a.acao == "projetar":
            cmd_sintatico_projetar(a.gramatica, a.saida or f"saida/sintatico_{nome_base(a.gramatica)}",
                                   a.pr, a.silencioso)
        elif a.parte == "sintatico":
            res = cmd_sintatico_executar(a.tabela, a.tokens,
                                         a.saida or f"saida/{nome_base(a.tokens)}.pilha.txt",
                                         a.silencioso)
            return 0 if res.aceito else 2
        elif a.parte == "compilar":
            ok = cmd_compilar(a.lexico, a.gramatica, a.pr, a.fonte,
                              a.saida or f"saida/{nome_base(a.fonte)}",
                              "palavras" if a.palavras else "fonte", a.silencioso)
            return 0 if ok else 2
    except FileNotFoundError as e:
        print(f"Erro: arquivo não encontrado: {e.filename}", file=sys.stderr)
        return 1
    except (ErroER, ErroGramatica, ValueError, OSError, KeyError) as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
