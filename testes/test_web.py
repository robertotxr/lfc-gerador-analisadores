"""Testes da interface web: sobe o servidor numa porta livre e chama a API."""

import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.servidor import Manipulador  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ler(*p):
    with open(os.path.join(RAIZ, *p), encoding="utf-8") as f:
        return f.read()


class TestWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Manipulador)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def get(self, caminho):
        with urllib.request.urlopen(self.url + caminho) as r:
            return r.status, r.headers.get("Content-Type"), r.read()

    def post(self, rota, dados):
        req = urllib.request.Request(self.url + "/api/" + rota, data=json.dumps(dados).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_arquivos_estaticos(self):
        for caminho, tipo in (("/", "text/html"), ("/app.js", "javascript"), ("/estilo.css", "text/css")):
            status, ct, corpo = self.get(caminho)
            self.assertEqual(status, 200)
            self.assertIn(tipo, ct)
            self.assertTrue(corpo)
        with self.assertRaises(urllib.error.HTTPError):
            self.get("/../main.py")

    def test_exemplos(self):
        _, _, corpo = self.get("/api/exemplos")
        e = json.loads(corpo)
        self.assertEqual(e["lexico"][0]["id"], "manezes")
        self.assertEqual(e["sintatico"][0]["id"], "manezes")
        self.assertTrue(any(x["id"] == "manezes_correto.mane" for x in e["compilar"]))

    def test_lexico(self):
        defs = "id: [a-zA-Z]([a-zA-Z] | [0-9])*\nnum: [1-9]([0-9])* | 0\n"
        s, p = self.post("lexico/projetar", {"definicoes": defs})
        self.assertEqual(s, 200)
        self.assertEqual(p["tokens"], ["id", "num"])
        self.assertEqual(len(p["tabela"]["estados"]), 4)
        self.assertTrue(p["tabela"]["deterministico"])
        self.assertTrue(any(a["rotulo"] == "&" for a in p["uniao"]["arestas"]))
        s, x = self.post("lexico/executar", {"definicoes": defs, "fonte": "a1 0 @"})
        self.assertEqual([(t["lexema"], t["padrao"]) for t in x["tokens"]],
                         [("a1", "id"), ("0", "num"), ("@", "erro!")])
        s, x = self.post("lexico/projetar", {"definicoes": "x: (a"})
        self.assertEqual(s, 400)
        self.assertIn("linha 1", x["erro"])

    def test_sintatico(self):
        g = ler("exemplos", "sintatico", "01_expressoes_aho", "gramatica.glc")
        s, p = self.post("sintatico/projetar", {"gramatica": g})
        self.assertEqual(s, 200)
        self.assertTrue(p["eh_slr"])
        self.assertEqual(len(p["estados"]), 12)
        self.assertEqual(p["tabela"]["linhas"][0]["acao"]["id"], "s5")
        s, a = self.post("sintatico/executar", {"gramatica": g, "tokens": "<a, id>\n<+, soma>\n<b, id>\n"})
        self.assertTrue(a["aceito"])
        self.assertEqual(a["passos"][-1]["acao"], "aceita")

    def test_compilar_manezes(self):
        base = {"lexico": ler("linguagem", "lexico.er"), "gramatica": ler("linguagem", "sintatico.glc"),
                "palavras_reservadas": ler("linguagem", "palavras_reservadas.txt")}
        s, r = self.post("compilar", dict(base, fonte=ler("linguagem", "correto.mane")))
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["tokens"]), 206)
        self.assertEqual(r["ts"][0], {"linha": 1, "lexema": "ilha", "categoria": "PR"})
        s, r = self.post("compilar", dict(base, fonte=ler("linguagem", "com_erro.mane")))
        self.assertFalse(r["ok"])
        self.assertIn("linha 3, coluna 9", r["analise"]["mensagem"])
        s, r = self.post("compilar", dict(base, fonte=ler("linguagem", "com_erro_lexico.mane")))
        self.assertFalse(r["ok"])
        self.assertEqual(r["erros_lexicos"], 1)


if __name__ == "__main__":
    unittest.main()
