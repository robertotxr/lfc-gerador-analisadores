"""Testes do Trabalho I (gerador de analisadores léxicos).

Os autômatos são comparados com o módulo `re` do Python (oráculo independente)
sobre TODAS as palavras de um alfabeto pequeno até um certo tamanho.
"""

import itertools
import os
import random
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lexico.analisador import AnalisadorLexico, aplicar_tabela_simbolos  # noqa: E402
from lexico.automato import AF  # noqa: E402
from lexico.determinizacao import determinizar  # noqa: E402
from lexico.er import ErroER, er_unica, ler_definicoes  # noqa: E402
from lexico.er_afd import er_para_afd  # noqa: E402
from lexico.gerador import projetar  # noqa: E402
from lexico.minimizacao import minimizar  # noqa: E402
from lexico.simbolos import EPSILON, particionar, rotulo  # noqa: E402
from lexico.uniao import unir  # noqa: E402
from comum.tabela_simbolos import TabelaSimbolos  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALFABETO_TESTE = "ab+c"


def palavras(alfabeto, max_len):
    for n in range(max_len + 1):
        for t in itertools.product(alfabeto, repeat=n):
            yield "".join(t)


# --------------------------------------------------------------- gerador de ER
# Cada nó gera o par (ER na nossa sintaxe, ER equivalente para o `re` do Python)
PREC_UNIAO, PREC_CONCAT, PREC_POSFIXO = 0, 1, 2


def gerar_er(rng, prof):
    """Devolve (texto_nosso, texto_python, precedencia)."""
    if prof == 0 or rng.random() < 0.25:
        r = rng.random()
        if r < 0.45:
            c = rng.choice("abc")
            return c, c, PREC_POSFIXO
        if r < 0.55:
            return "\\+", "\\+", PREC_POSFIXO
        if r < 0.75:
            cs = "".join(sorted(rng.sample("abc", rng.randint(1, 3))))
            return f"[{cs}]", f"[{cs}]", PREC_POSFIXO
        if r < 0.85:
            c = rng.choice("ab")
            return f"[^{c}]", f"[^{c}]", PREC_POSFIXO
        return "&", "(?:)", PREC_POSFIXO
    op = rng.choice(["|", ".", ".", "*", "+", "?"])
    if op in "*+?":
        n, p, prec = gerar_er(rng, prof - 1)
        if prec < PREC_POSFIXO or (rng.random() < 0.3):
            n = f"({n})"
        return n + op, f"(?:{p}){op}", PREC_POSFIXO
    a = gerar_er(rng, prof - 1)
    b = gerar_er(rng, prof - 1)
    if op == "|":
        esp = " " if rng.random() < 0.3 else ""
        return f"{a[0]}{esp}|{esp}{b[0]}", f"(?:{a[1]}|{b[1]})", PREC_UNIAO
    na = a[0] if a[2] >= PREC_CONCAT else f"({a[0]})"
    nb = b[0] if b[2] >= PREC_CONCAT else f"({b[0]})"
    return na + nb, f"(?:{a[1]})(?:{b[1]})", PREC_CONCAT


class TestSimbolos(unittest.TestCase):
    def test_particao(self):
        p = particionar([set("abc"), set("bcd"), set("x")])
        self.assertEqual(p, [frozenset("a"), frozenset("bc"), frozenset("d"), frozenset("x")])

    def test_rotulos(self):
        self.assertEqual(rotulo(frozenset("0123456789")), "[0-9]")
        self.assertEqual(rotulo(frozenset("ab")), "[ab]")
        self.assertEqual(rotulo(frozenset(" ")), "\\s")
        self.assertEqual(rotulo(EPSILON), "&")


class TestLeituraER(unittest.TestCase):
    def test_exemplo_enunciado(self):
        defs = ler_definicoes("id: [a-zA-Z]([a-zA-Z] | [0-9])*\nnum: [1-9]([0-9])* | 0\n")
        self.assertEqual([d.nome for d in defs], ["id", "num"])
        self.assertFalse(any(d.auxiliar for d in defs))

    def test_definicoes_auxiliares_e_ordem_livre(self):
        defs = ler_definicoes("id: {letra}({letra}|{digito})*\nletra: [a-z]\ndigito: [0-9]\n")
        aux = {d.nome: d.auxiliar for d in defs}
        self.assertEqual(aux, {"id": False, "letra": True, "digito": True})
        afd = er_para_afd(defs[0].arvore, "id").afd
        self.assertTrue(afd.aceita("x12y"))
        self.assertFalse(afd.aceita("1x"))

    def test_escapes_e_literais(self):
        afd = er_para_afd(er_unica(r"\(\*\)\+\&\{x\}\\"), "e").afd
        self.assertTrue(afd.aceita("(*)+&{x}\\"))
        afd = er_para_afd(er_unica(r"a\sb\tc"), "e").afd
        self.assertTrue(afd.aceita("a b\tc"))
        afd = er_para_afd(er_unica("{ }"), "e").afd  # chave sem nome = literal
        self.assertTrue(afd.aceita("{}"))

    def test_classes(self):
        afd = er_para_afd(er_unica("[-a-c_ ]+"), "e").afd
        self.assertTrue(afd.aceita("a-b c_"))
        self.assertFalse(afd.aceita("d"))
        afd = er_para_afd(er_unica('"[^"]*"'), "e").afd
        self.assertTrue(afd.aceita('"olá, mundo"'))
        self.assertFalse(afd.aceita('"a"b"'))

    def test_erros(self):
        casos = {
            "x: (ab": "sem ')'",
            "x: ab)": "')' sem '('",
            "x: *a": "sem operando",
            "x: a||b": "alternativa vazia",
            "x: [z-a]": "faixa inválida",
            "x: [abc": "sem ']'",
            "x: {nada}": "inexistente",
            "x: {y}\ny: {x}": "circulares",
            "x: a\nx: b": "repetida",
            "x:": "sem expressão",
            "1x: a": "inválido",
            "sem dois pontos": "esperado",
        }
        for texto, trecho in casos.items():
            with self.subTest(texto=texto):
                with self.assertRaises(ErroER) as cm:
                    ler_definicoes(texto)
                self.assertIn(trecho, str(cm.exception))


class TestConversaoDireta(unittest.TestCase):
    def test_aho_abb(self):
        """Exemplo 3.36 do Aho: (a|b)*abb tem AFD de 4 estados com followpos conhecido."""
        conv = er_para_afd(er_unica("(a|b)*abb"), "abb")
        self.assertEqual(conv.followpos, {1: {1, 2, 3}, 2: {1, 2, 3}, 3: {4}, 4: {5}, 5: {6}, 6: set()})
        self.assertEqual(conv.firstpos_raiz, {1, 2, 3})
        self.assertEqual(conv.afd.n, 4)
        self.assertEqual(minimizar(conv.afd).afd.n, 4)

    def test_aleatorio_contra_re(self):
        rng = random.Random(2026)
        for k in range(400):
            nosso, py, _ = gerar_er(rng, rng.randint(1, 5))
            with self.subTest(er=nosso, py=py):
                arvore = er_unica(nosso)
                afd = er_para_afd(arvore, "t").afd
                self.assertTrue(afd.deterministico())
                mn = minimizar(afd).afd
                self.assertLessEqual(mn.n, afd.n)
                regex = re.compile(py)
                for w in palavras(ALFABETO_TESTE, 5):
                    esperado = regex.fullmatch(w) is not None
                    self.assertEqual(afd.aceita(w), esperado, f"AFD direto, palavra {w!r}")
                    self.assertEqual(mn.aceita(w), esperado, f"AFD mínimo, palavra {w!r}")


def _classes_table_filling(afd: AF) -> int:
    """Número de classes de estados equivalentes (algoritmo de preenchimento de
    tabela), usado como verificação independente da minimização."""
    est = list(afd.estados)
    dist = set()
    for p, q in itertools.combinations(est, 2):
        if afd.finais.get(p) != afd.finais.get(q):
            dist.add((p, q))
    mudou = True
    while mudou:
        mudou = False
        for p, q in itertools.combinations(est, 2):
            if (p, q) in dist:
                continue
            for a in afd.alfabeto:
                dp, dq = afd.destino(p, a), afd.destino(q, a)
                if (dp is None) != (dq is None):
                    dist.add((p, q)); mudou = True; break
                if dp is not None and dp != dq and (min(dp, dq), max(dp, dq)) in dist:
                    dist.add((p, q)); mudou = True; break
    classes = []
    for q in est:
        for c in classes:
            r = c[0]
            if (min(r, q), max(r, q)) not in dist:
                c.append(q); break
        else:
            classes.append([q])
    return len(classes)


class TestMinimizacao(unittest.TestCase):
    def _afd(self, n, trans, finais, inicial=0):
        a, b = frozenset("a"), frozenset("b")
        af = AF([a, b])
        for _ in range(n):
            af.novo_estado()
        af.inicial = inicial
        for (o, s), d in trans.items():
            af.adicionar(o, {"a": a, "b": b}[s], d)
        for q in finais:
            af.finais[q] = "x"
        return af

    def test_inalcancavel_morto_equivalentes(self):
        # q1 e q2 equivalentes; q3 inalcançável; q4 morto
        af = self._afd(5, {(0, "a"): 1, (0, "b"): 2, (1, "a"): 1, (2, "a"): 2,
                           (1, "b"): 4, (2, "b"): 4, (4, "a"): 4, (3, "a"): 0}, [1, 2])
        mn = minimizar(af)
        self.assertEqual(mn.inalcancaveis, [3])
        self.assertEqual(mn.mortos, [4])
        self.assertEqual(mn.afd.n, 2)
        for w in palavras("ab", 6):
            self.assertEqual(af.aceita(w), mn.afd.aceita(w))

    def test_linguagem_vazia(self):
        af = self._afd(2, {(0, "a"): 1}, [])
        mn = minimizar(af)
        self.assertEqual(mn.afd.n, 1)
        self.assertFalse(mn.afd.finais)

    def test_aleatorio_minimo_e_equivalente(self):
        rng = random.Random(7)
        for k in range(300):
            n = rng.randint(1, 8)
            trans = {(o, s): rng.randrange(n) for o in range(n) for s in "ab" if rng.random() < 0.8}
            finais = [q for q in range(n) if rng.random() < 0.4]
            af = self._afd(n, trans, finais)
            mn = minimizar(af).afd
            for w in palavras("ab", 7):
                self.assertEqual(af.aceita(w), mn.aceita(w))
            if mn.finais:
                self.assertEqual(_classes_table_filling(mn), mn.n, "sobrou estado equivalente")


class TestUniaoDeterminizacao(unittest.TestCase):
    def test_uniao_e_determinizacao_contra_re(self):
        rng = random.Random(99)
        for k in range(150):
            ers = [gerar_er(rng, rng.randint(1, 4)) for _ in range(rng.randint(2, 4))]
            nomes = [f"t{i}" for i in range(len(ers))]
            afds = [(n, minimizar(er_para_afd(er_unica(e[0]), n).afd).afd) for n, e in zip(nomes, ers)]
            uniao = unir(afds)
            self.assertTrue(uniao.tem_epsilon())
            det = determinizar(uniao, {n: i for i, n in enumerate(nomes)}).afd
            self.assertTrue(det.deterministico())
            regexes = [re.compile(e[1]) for e in ers]
            for w in palavras(ALFABETO_TESTE, 4):
                casam = [n for n, r in zip(nomes, regexes) if r.fullmatch(w)]
                self.assertEqual(uniao.reconhece(w), set(casam), w)
                self.assertEqual(det.reconhece(w), set(casam[:1]), w)


class TestAnalisadorLexico(unittest.TestCase):
    def _lex(self, defs, **kw):
        return AnalisadorLexico(projetar(defs, **kw).para_dict())

    def test_exemplo_1_enunciado(self):
        lex = self._lex("id: [a-zA-Z]([a-zA-Z] | [0-9])*\nnum: [1-9]([0-9])* | 0\n")
        toks = lex.analisar("a1\n0\nteste2\n21\nalpha123\n3444\na43teste\n")
        self.assertEqual([t.formato_lexema() for t in toks],
                         ["<a1, id>", "<0, num>", "<teste2, id>", "<21, num>", "<alpha123, id>",
                          "<3444, num>", "<a43teste, id>"])

    def test_exemplo_2_enunciado_ambiguo(self):
        """As duas ERs do exemplo 2 denotam a mesma linguagem ((a|b)+), então
        vence sempre a de maior prioridade e o gerador avisa."""
        p = projetar("er1: a?(a | b)+\ner2: b?(a | b)+\n")
        self.assertTrue(any("er2" in a and "nunca" in a for a in p.avisos))
        lex = AnalisadorLexico(p.para_dict())
        self.assertEqual({t.padrao for t in lex.analisar("aa bbbba ababab bbbbb")}, {"er1"})
        lex = self._lex("er1: a(a | b)*\ner2: b(a | b)*\n")
        self.assertEqual([t.padrao for t in lex.analisar("aa bbbba ababab bbbbb")],
                         ["er1", "er2", "er1", "er2"])

    def test_maximal_munch_e_erros(self):
        lex = self._lex("id: [a-z]+\nnum: [0-9]+\nop: <|<=|<>|=|:=\n")
        toks = lex.analisar("x:=y<=10<>z @@ w : 5")
        self.assertEqual([(t.lexema, t.padrao) for t in toks],
                         [("x", "id"), (":=", "op"), ("y", "id"), ("<=", "op"), ("10", "num"),
                          ("<>", "op"), ("z", "id"), ("@@", "erro!"), ("w", "id"),
                          (":", "erro!"), ("5", "num")])
        self.assertEqual((toks[7].linha, toks[7].coluna), (1, 13))

    def test_recuo_ao_ultimo_aceito(self):
        lex = self._lex("num: [0-9]+(\\.[0-9]+)?(E[+\\-]?[0-9]+)?\nid: [A-Z]+\n")
        self.assertEqual([(t.lexema, t.padrao) for t in lex.analisar("7.5E 3.E2 1E+")],
                         [("7.5", "num"), ("E", "id"), ("3", "num"), (".", "erro!"), ("E", "id"),
                          ("2", "num"), ("1", "num"), ("E", "id"), ("+", "erro!")])

    def test_modo_palavras(self):
        lex = self._lex("abb: (a|b)*abb\n")
        toks = lex.analisar("abb ab babb abba", modo="palavras")
        self.assertEqual([t.padrao for t in toks], ["abb", "erro!", "abb", "erro!"])

    def test_aleatorio_contra_referencia(self):
        """Compara com uma implementação de referência por força bruta usando `re`."""
        defs = [("kw", "se|senao"), ("id", "[a-z][a-z0-9]*"), ("num", "[0-9]+"),
                ("op", "<|<=|<>|=|\\+"), ("str", '"[^"]*"')]
        py = [("kw", "se|senao"), ("id", "[a-z][a-z0-9]*"), ("num", "[0-9]+"),
              ("op", "<|<=|<>|=|\\+"), ("str", '"[^"]*"')]
        lex = self._lex("\n".join(f"{n}: {e}" for n, e in defs))
        reg = [(n, re.compile(e)) for n, e in py]
        rng = random.Random(5)
        alfabeto = list("aesnoz019<>=+\" @")
        for _ in range(500):
            txt = "".join(rng.choice(alfabeto) for _ in range(rng.randint(0, 25)))
            obtido = [(t.lexema, t.padrao) for t in lex.analisar(txt) if t.padrao != "erro!"]
            esperado = []
            i = 0
            while i < len(txt):
                if txt[i] == " ":
                    i += 1
                    continue
                melhor = None
                for j in range(len(txt), i, -1):
                    for n, r in reg:
                        if r.fullmatch(txt[i:j]):
                            melhor = (j, n)
                            break
                    if melhor:
                        break
                if melhor:
                    esperado.append((txt[i:melhor[0]], melhor[1]))
                    i = melhor[0]
                else:
                    i += 1  # erro (o lexema de erro é checado em outros testes)
            self.assertEqual(obtido, esperado, txt)

    def test_tabela_de_simbolos(self):
        lex = self._lex("id: [a-z]+\nnum: [0-9]+\nsimb: [(){};=]\n")
        ts = TabelaSimbolos(["se", "faca"])
        toks = aplicar_tabela_simbolos(lex.analisar("se (x) { x = 10; y = x; } faca"), ts)
        self.assertEqual([t.formato_ts() for t in toks],
                         ["<se, PR>", "<(, simb>", "<id, 3>", "<), simb>", "<{, simb>", "<id, 3>",
                          "<=, simb>", "<num, 4>", "<;, simb>", "<id, 5>", "<=, simb>", "<id, 3>",
                          "<;, simb>", "<}, simb>", "<faca, PR>"])
        self.assertEqual(ts.entradas[2:], [("x", "id"), ("10", "num"), ("y", "id")])

    def test_avisos(self):
        p = projetar("dig: [0-9]\nnum: dig+\n")
        self.assertTrue(any("'dig' como texto literal" in a for a in p.avisos))
        p = projetar("se: se\nsenao: senao\nid: [a-z]+\n")
        self.assertFalse(any("texto literal" in a for a in p.avisos))
        p = projetar("vazio: a*\nid: [a-z]+\nletra: [a-z]\n")
        self.assertTrue(any("palavra vazia" in a for a in p.avisos))
        self.assertTrue(any("letra" in a and "nunca" in a for a in p.avisos))

    def test_minimizar_tabela_final_equivalente(self):
        defs = open(os.path.join(RAIZ, "linguagem", "lexico.er"), encoding="utf-8").read()
        a = AnalisadorLexico(projetar(defs).para_dict())
        b = AnalisadorLexico(projetar(defs, minimizar_tabela=True).para_dict())
        fonte = open(os.path.join(RAIZ, "linguagem", "correto.mane"), encoding="utf-8").read()
        self.assertEqual([(t.lexema, t.padrao) for t in a.analisar(fonte)],
                         [(t.lexema, t.padrao) for t in b.analisar(fonte)])

    def test_exemplos_do_projeto_rodam(self):
        base = os.path.join(RAIZ, "exemplos", "lexico")
        for d in sorted(os.listdir(base)):
            with self.subTest(exemplo=d):
                defs = open(os.path.join(base, d, "definicoes.er"), encoding="utf-8").read()
                p = projetar(defs)
                p.relatorio()  # não pode falhar
                lex = AnalisadorLexico(p.para_dict())
                lex.analisar(open(os.path.join(base, d, "entrada.txt"), encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main()
