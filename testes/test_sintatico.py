"""Testes do Trabalho II (gerador de analisadores sintáticos SLR).

O analisador SLR é comparado com um reconhecedor de Earley (oráculo
independente, aceita qualquer GLC) sobre todas as cadeias curtas de terminais
e sobre sentenças aleatórias geradas pela gramática e mutações delas.
"""

import itertools
import os
import random
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comum.tokens import ler_tokens  # noqa: E402
from sintatico.analisador import AnalisadorSintatico, Entrada  # noqa: E402
from sintatico.first_follow import calcular_first, calcular_follow  # noqa: E402
from sintatico.gerador import projetar  # noqa: E402
from sintatico.gramatica import EPSILON, ErroGramatica, ler_gramatica  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AHO = '''<E> ::= <E> "+" <T>
<E> ::= <T>
<T> ::= <T> "*" <F>
<T> ::= <F>
<F> ::= "(" <E> ")"
<F> ::= id
'''


def ler(caminho):
    with open(os.path.join(RAIZ, caminho), encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------- oráculo
def earley(g, tokens):
    """Reconhecedor de Earley (com o tratamento de anuláveis de Aycock & Horspool).
    g é a gramática aumentada (produção 0 = S' -> S)."""
    first = calcular_first(g)
    anulaveis = {nt for nt in g.nao_terminais if EPSILON in first[nt]}
    n = len(tokens)
    chart = [set() for _ in range(n + 1)]
    chart[0].add((0, 0, 0))
    for i in range(n + 1):
        agenda = list(chart[i])
        while agenda:
            p, d, o = agenda.pop()
            cab, corpo = g.producoes[p]
            novos = []
            if d < len(corpo):
                X = corpo[d]
                if g.eh_nao_terminal(X):
                    novos += [(q, 0, i) for q in g.producoes_de(X)]
                    if X in anulaveis:
                        novos.append((p, d + 1, o))
                elif i < n and tokens[i] == X:
                    chart[i + 1].add((p, d + 1, o))
            else:
                for p2, d2, o2 in list(chart[o]):
                    c2 = g.producoes[p2][1]
                    if d2 < len(c2) and c2[d2] == cab:
                        novos.append((p2, d2 + 1, o2))
            for it in novos:
                if it not in chart[i]:
                    chart[i].add(it)
                    agenda.append(it)
    return (0, 1, 0) in chart[n]


def gerar_sentenca(g, rng, max_prof=12):
    """Sentença aleatória por derivação mais à esquerda (prefere produções curtas
    quando a profundidade passa do limite)."""
    def tamanho_min():
        inf = float("inf")
        t = {nt: inf for nt in g.nao_terminais}
        mudou = True
        while mudou:
            mudou = False
            for cab, corpo in g.producoes:
                v = sum(t[s] if g.eh_nao_terminal(s) else 1 for s in corpo)
                if v < t[cab]:
                    t[cab] = v
                    mudou = True
        return t
    tmin = tamanho_min()

    def expandir(nt, prof):
        prods = g.producoes_de(nt)
        if prof > max_prof:
            prods = [min(prods, key=lambda p: sum(tmin[s] if g.eh_nao_terminal(s) else 1
                                                  for s in g.producoes[p][1]))]
        corpo = g.producoes[rng.choice(prods)][1]
        out = []
        for s in corpo:
            out += expandir(s, prof + 1) if g.eh_nao_terminal(s) else [s]
        return out
    return expandir(g.inicial, 0)


def slr_aceita(analisador, tokens):
    return analisador.analisar([Entrada(t, t) for t in tokens]).aceito


class TestGramatica(unittest.TestCase):
    def test_formato_basico(self):
        g = ler_gramatica(AHO)
        self.assertEqual(g.inicial, "E")
        self.assertEqual(g.nao_terminais, ["E", "T", "F"])
        self.assertEqual(g.terminais, ["+", "*", "(", ")", "id"])
        self.assertEqual(len(g.producoes), 6)

    def test_notacoes_alternativas(self):
        g = ler_gramatica('⟨Lista Itens⟩ ::= “[” ⟨X⟩ “]” | ε\n⟨X⟩ ::= a\n   | ⟨X⟩ "," a\n'
                          '# comentario\n// outro\n<X> -> &\n')
        self.assertEqual(g.producoes, [("Lista Itens", ("[", "X", "]")), ("Lista Itens", ()),
                                       ("X", ("a",)), ("X", ("X", ",", "a")), ("X", ())])

    def test_terminais_especiais(self):
        g = ler_gramatica('<A> ::= < <= "<" ">" <> "|" ":=" """ < id >\n')
        self.assertEqual(g.producoes[0][1], ("<", "<=", "<", ">", "<>", "|", ":=", '"', "<", "id", ">"))

    def test_so_palavra_vazia(self):
        p = projetar("<S> ::= &\n")
        an = AnalisadorSintatico(p.para_dict())
        self.assertTrue(an.analisar([]).aceito)
        self.assertFalse(an.analisar([Entrada("x", "x")]).aceito)

    def test_erros(self):
        casos = {
            "<A> ::= <B>": "sem produções",
            "A ::= b": "esperado",
            '<A> ::= "x': "aspas",
            "| a": "sem produção anterior",
            '<A> ::= ""': "terminal vazio",
            "<A> ::= $": "reservado",
            "": "nenhuma produção",
        }
        for texto, trecho in casos.items():
            with self.subTest(texto=texto):
                with self.assertRaises(ErroGramatica) as cm:
                    ler_gramatica(texto)
                self.assertIn(trecho, str(cm.exception))

    def test_avisos_inalcancavel_improdutivo(self):
        g = ler_gramatica("<S> ::= a\n<S> ::= <L>\n<L> ::= <L> b\n<Z> ::= z\n")
        self.assertTrue(any("<Z>" in a and "inalcançável" in a for a in g.avisos))
        self.assertTrue(any("<L>" in a and "improdutivo" in a for a in g.avisos))


class TestFirstFollow(unittest.TestCase):
    def test_gramatica_4_28_aho(self):
        g = ler_gramatica('<E> ::= <T> <E2>\n<E2> ::= "+" <T> <E2> | &\n<T> ::= <F> <T2>\n'
                          '<T2> ::= "*" <F> <T2> | &\n<F> ::= "(" <E> ")" | id\n')
        first = calcular_first(g)
        follow = calcular_follow(g, first)
        self.assertEqual(first["E"], {"(", "id"})
        self.assertEqual(first["E2"], {"+", EPSILON})
        self.assertEqual(first["T2"], {"*", EPSILON})
        self.assertEqual(follow["E"], {")", "$"})
        self.assertEqual(follow["E2"], {")", "$"})
        self.assertEqual(follow["T"], {"+", ")", "$"})
        self.assertEqual(follow["T2"], {"+", ")", "$"})
        self.assertEqual(follow["F"], {"+", "*", ")", "$"})


class TestSLR(unittest.TestCase):
    def test_tabela_fig_4_37_aho(self):
        p = projetar(AHO)
        self.assertTrue(p.eh_slr)
        self.assertEqual(len(p.colecao.estados), 12)
        a = p.tabela.acao
        esperado = {
            (0, "id"): ("s", 5), (0, "("): ("s", 4), (1, "+"): ("s", 6), (1, "$"): ("acc",),
            (2, "+"): ("r", 2), (2, "*"): ("s", 7), (2, ")"): ("r", 2), (2, "$"): ("r", 2),
            (3, "*"): ("r", 4), (5, "$"): ("r", 6), (8, ")"): ("s", 11), (9, "*"): ("s", 7),
            (9, "+"): ("r", 1), (10, "+"): ("r", 3), (11, "$"): ("r", 5),
        }
        for (i, t), acao in esperado.items():
            self.assertEqual(a[i][t], acao, (i, t))
        self.assertEqual(p.tabela.desvio[0], {"E": 1, "T": 2, "F": 3})
        self.assertEqual(p.tabela.desvio[4], {"E": 8, "T": 2, "F": 3})
        self.assertEqual(p.tabela.desvio[7], {"F": 10})

    def test_pilha_fig_4_38_aho(self):
        p = projetar(AHO)
        r = AnalisadorSintatico(p.para_dict()).analisar([Entrada(t, t) for t in "id * id + id".split()])
        self.assertTrue(r.aceito)
        self.assertEqual(len(r.passos), 14)
        self.assertEqual(r.passos[6].pilha, [0, 2, 7, 10])
        self.assertEqual(r.passos[6].acao, 'reduz (3) <T> ::= <T> "*" <F>')

    def test_conflito_gramatica_4_49_aho(self):
        p = projetar('<S> ::= <L> "=" <R> | <R>\n<L> ::= "*" <R> | id\n<R> ::= <L>\n')
        self.assertFalse(p.eh_slr)
        self.assertEqual(len(p.tabela.conflitos), 1)
        c = p.tabela.conflitos[0]
        self.assertEqual((c.estado, c.simbolo, c.tipo()), (2, "=", "empilha/reduz"))
        self.assertEqual(set(c.acoes), {("s", 6), ("r", 5)})

    def test_conflito_reduz_reduz(self):
        p = projetar("<S> ::= <A> | <B>\n<A> ::= x\n<B> ::= x\n")
        self.assertEqual([c.tipo() for c in p.tabela.conflitos], ["reduz/reduz"])

    def _comparar_com_earley(self, texto, max_len, n_aleat=0, semente=1, pr=()):
        p = projetar(texto, list(pr))
        self.assertTrue(p.eh_slr, p.tabela.conflitos and p.tabela.conflitos[0].texto(p.aumentada))
        g = p.aumentada
        an = AnalisadorSintatico(p.para_dict())
        for n in range(max_len + 1):
            for cadeia in itertools.product(g.terminais, repeat=n):
                self.assertEqual(slr_aceita(an, cadeia), earley(g, cadeia), cadeia)
        rng = random.Random(semente)
        for _ in range(n_aleat):
            s = gerar_sentenca(g, rng)
            self.assertTrue(slr_aceita(an, s), s)
            m = list(s)
            for _ in range(rng.randint(1, 3)):  # mutação: troca, remove ou insere
                op = rng.random()
                k = rng.randrange(len(m) + 1)
                if op < 0.33 and k < len(m):
                    m[k] = rng.choice(g.terminais)
                elif op < 0.66 and k < len(m):
                    del m[k]
                else:
                    m.insert(k, rng.choice(g.terminais))
            self.assertEqual(slr_aceita(an, m), earley(g, m), m)

    def test_aho_contra_earley(self):
        self._comparar_com_earley(AHO, 6, 300)

    def test_epsilon_contra_earley(self):
        self._comparar_com_earley(ler("exemplos/sintatico/03_epsilon/gramatica.glc"), 6, 200)

    def test_calculadora_contra_earley(self):
        self._comparar_com_earley(ler("exemplos/sintatico/05_calculadora_integrada/gramatica.glc"), 4, 400)

    def test_listas_aninhadas_contra_earley(self):
        self._comparar_com_earley(ler("exemplos/sintatico/06_formatos_alternativos/gramatica.glc"), 7, 200)

    def test_linguagem_manezes_contra_earley(self):
        self._comparar_com_earley(ler("linguagem/sintatico.glc"), 2, 400, semente=3)


class TestEntradaTokens(unittest.TestCase):
    def test_leitura_formato(self):
        self.assertEqual(ler_tokens("<a1, id>\n<,, virgula>\n<<=, op>\n< x , id >\n\n<>, op>\n"),
                         [("a1", "id", 1), (",", "virgula", 2), ("<=", "op", 3), ("x", "id", 4),
                          (">", "op", 6)])
        with self.assertRaises(ValueError):
            ler_tokens("a1, id\n")

    def test_mapeamento_dos_dois_formatos(self):
        p = projetar('<S> ::= se id "=" num fim\n', ["se", "fim"])
        an = AnalisadorSintatico(p.para_dict())
        com_ts = an.entrada_de_arquivo("<se, PR>\n<id, 3>\n<=, atrib>\n<num, 4>\n<fim, PR>\n")
        sem_ts = an.entrada_de_arquivo("<se, id>\n<x, id>\n<=, atrib>\n<10, num>\n<fim, id>\n")
        for ent in (com_ts, sem_ts):
            self.assertEqual([e.terminal for e in ent], ["se", "id", "=", "num", "fim"])
            self.assertTrue(an.analisar(ent).aceito)
        # variável chamada "num" no formato sem TS continua sendo um id
        p2 = projetar('<S> ::= id "=" num\n', ["se"])
        an2 = AnalisadorSintatico(p2.para_dict())
        self.assertTrue(an2.analisar(an2.entrada_de_arquivo("<num, id>\n<=, atrib>\n<5, num>\n")).aceito)
        r = an.analisar(an.entrada_de_arquivo("<se, PR>\n<@, erro!>\n"))
        self.assertFalse(r.aceito)
        self.assertIn("Erro léxico", r.mensagem)


class TestLinguagemEIntegracao(unittest.TestCase):
    def _compilar(self, fonte, *extra):
        cmd = [sys.executable, os.path.join(RAIZ, "main.py"), "compilar", fonte,
               "--lexico", "linguagem/lexico.er", "--gramatica", "linguagem/sintatico.glc",
               "--pr", "linguagem/palavras_reservadas.txt", "-o",
               os.path.join(RAIZ, "saida", "testes", os.path.basename(fonte)), "-q", *extra]
        return subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True)

    def test_correto(self):
        r = self._compilar("linguagem/correto.mane")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CÓDIGO CORRETO", r.stdout)
        self.assertNotIn("Aviso", r.stdout)

    def test_com_erro_sintatico(self):
        r = self._compilar("linguagem/com_erro.mane")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Erro sintático em 'peixes' (linha 3, coluna 9)", r.stdout)
        self.assertIn("Esperado: '('", r.stdout)

    def test_com_erro_lexico(self):
        r = self._compilar("linguagem/com_erro_lexico.mane")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Erro léxico: '@'", r.stdout)

    def test_cli_partes_separadas(self):
        """Cada parte funciona sozinha: projeta léxico, executa léxico com TS,
        projeta sintático e executa sintático lendo o arquivo de tokens."""
        out = os.path.join(RAIZ, "saida", "testes", "cli")
        py = [sys.executable, os.path.join(RAIZ, "main.py")]
        run = lambda *a: subprocess.run(py + list(a), cwd=RAIZ, capture_output=True, text=True)
        self.assertEqual(run("lexico", "projetar", "linguagem/lexico.er", "-o", out + "/lex", "-q").returncode, 0)
        self.assertEqual(run("sintatico", "projetar", "linguagem/sintatico.glc", "--pr",
                             "linguagem/palavras_reservadas.txt", "-o", out + "/sin", "-q").returncode, 0)
        for fonte, codigo in (("correto", 0), ("com_erro", 2)):
            r = run("lexico", "executar", out + "/lex/analisador_lexico.json", f"linguagem/{fonte}.mane",
                    "--sintatico", out + "/sin/analisador_sintatico.json", "-o", f"{out}/{fonte}.tokens.txt", "-q")
            self.assertEqual(r.returncode, 0, r.stderr)
            r = run("sintatico", "executar", out + "/sin/analisador_sintatico.json",
                    f"{out}/{fonte}.tokens.txt", "-o", f"{out}/{fonte}.pilha.txt", "-q")
            self.assertEqual(r.returncode, codigo, r.stdout + r.stderr)
            # o sintático também aceita a saída do léxico no formato do Trabalho I
            r = run("lexico", "executar", out + "/lex/analisador_lexico.json", f"linguagem/{fonte}.mane",
                    "-o", f"{out}/{fonte}.t1.txt", "-q")
            r = run("sintatico", "executar", out + "/sin/analisador_sintatico.json",
                    f"{out}/{fonte}.t1.txt", "-o", f"{out}/{fonte}.t1.pilha.txt", "-q")
            self.assertEqual(r.returncode, codigo, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
