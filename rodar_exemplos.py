#!/usr/bin/env python3
"""Roda todos os exemplos do projeto e grava as saídas em saida/exemplos/.

    python3 rodar_exemplos.py
"""

import contextlib
import io
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import main  # noqa: E402

SAIDA = os.path.join("saida", "exemplos")


def quieto(f, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = f(*a, **kw)
    return r, buf.getvalue()


def lexicos():
    base = os.path.join("exemplos", "lexico")
    for nome in sorted(os.listdir(base)):
        d = os.path.join(base, nome)
        defs = sorted(f for f in os.listdir(d) if f.endswith(".er"))
        for arq in defs:
            sufixo = "" if arq == "definicoes.er" else "_" + os.path.splitext(arq)[0]
            out = os.path.join(SAIDA, "lexico", nome + sufixo)
            proj, _ = quieto(main.cmd_lexico_projetar, os.path.join(d, arq), out, silencioso=True)
            modo = "palavras" if "abb" in nome else "fonte"
            toks, _ = quieto(main.cmd_lexico_executar, os.path.join(out, "analisador_lexico.json"),
                             os.path.join(d, "entrada.txt"), os.path.join(out, "tokens.txt"), modo,
                             silencioso=True)
            erros = sum(t.erro for t in toks)
            print(f"  {nome + sufixo:<40} tabela: {proj.tabela.n:>3} estados   tokens: {len(toks):>3}"
                  f"   erros léxicos: {erros}" + ("   (avisos no relatório)" if proj.avisos else ""))


def sintaticos():
    base = os.path.join("exemplos", "sintatico")
    for nome in sorted(os.listdir(base)):
        d = os.path.join(base, nome)
        out = os.path.join(SAIDA, "sintatico", nome)
        pr = os.path.join(d, "palavras_reservadas.txt")
        proj, _ = quieto(main.cmd_sintatico_projetar, os.path.join(d, "gramatica.glc"), out,
                         pr if os.path.exists(pr) else None, silencioso=True)
        status = "SLR(1)" if proj.eh_slr else f"{len(proj.tabela.conflitos)} conflito(s)"
        print(f"  {nome:<40} {len(proj.colecao.estados):>3} estados LR(0)   {status}")
        for arq in sorted(f for f in os.listdir(d) if f.startswith("tokens")):
            res, _ = quieto(main.cmd_sintatico_executar, os.path.join(out, "analisador_sintatico.json"),
                            os.path.join(d, arq), os.path.join(out, arq.replace(".txt", ".pilha.txt")),
                            silencioso=True)
            print(f"      {arq:<36} {'ACEITA' if res.aceito else 'REJEITA'}")
        if os.path.exists(os.path.join(d, "lexico.er")):
            for arq in sorted(f for f in os.listdir(d) if f.startswith("programa")):
                ok, _ = quieto(main.cmd_compilar, os.path.join(d, "lexico.er"),
                               os.path.join(d, "gramatica.glc"), pr, os.path.join(d, arq),
                               os.path.join(out, os.path.splitext(arq)[0]), silencioso=True)
                print(f"      {arq + ' (compilar)':<36} {'CORRETO' if ok else 'COM ERRO'}")


def linguagem():
    for arq in ("correto.mane", "com_erro.mane", "com_erro_lexico.mane"):
        ok, _ = quieto(main.cmd_compilar, "linguagem/lexico.er", "linguagem/sintatico.glc",
                       "linguagem/palavras_reservadas.txt", os.path.join("linguagem", arq),
                       os.path.join(SAIDA, "linguagem", os.path.splitext(arq)[0]), silencioso=True)
        print(f"  {arq:<40} {'CORRETO' if ok else 'COM ERRO'}")


if __name__ == "__main__":
    print("Exemplos léxicos:")
    lexicos()
    print("\nExemplos sintáticos:")
    sintaticos()
    print("\nLinguagem Manezês:")
    linguagem()
    print(f"\nSaídas (relatórios, tabelas, tokens, pilhas) em {SAIDA}/")
