"""Servidor local da interface web (só biblioteca padrão).

    python3 main.py web            # abre http://127.0.0.1:8765 no navegador
"""

from __future__ import annotations

import json
import mimetypes
import os
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from lexico.er import ErroER
from sintatico.gramatica import ErroGramatica
from . import api

ESTATICOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

ROTAS = {
    "/api/lexico/projetar": lambda d: api.lexico_projetar(d.get("definicoes", ""), bool(d.get("minimizar"))),
    "/api/lexico/executar": lambda d: api.lexico_executar(d.get("definicoes", ""), d.get("fonte", ""),
                                                          d.get("modo", "fonte"), d.get("palavras_reservadas")),
    "/api/sintatico/projetar": lambda d: api.sintatico_projetar(d.get("gramatica", ""),
                                                                d.get("palavras_reservadas", "")),
    "/api/sintatico/executar": lambda d: api.sintatico_executar(d.get("gramatica", ""),
                                                                d.get("palavras_reservadas", ""),
                                                                d.get("tokens", "")),
    "/api/compilar": lambda d: api.compilar(d.get("lexico", ""), d.get("gramatica", ""),
                                            d.get("palavras_reservadas", ""), d.get("fonte", ""),
                                            d.get("modo", "fonte")),
}


class Manipulador(BaseHTTPRequestHandler):
    server_version = "LFC/1.0"

    def log_message(self, formato, *args):  # silencioso: a interface é o log
        pass

    def _responder(self, codigo: int, corpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, codigo: int, dados) -> None:
        self._responder(codigo, json.dumps(dados, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8")

    def do_GET(self):
        caminho = self.path.split("?", 1)[0]
        if caminho == "/api/exemplos":
            return self._json(200, api.exemplos())
        if caminho == "/":
            caminho = "/index.html"
        arquivo = os.path.normpath(os.path.join(ESTATICOS, caminho.lstrip("/")))
        if not arquivo.startswith(ESTATICOS) or not os.path.isfile(arquivo):
            return self._responder(404, b"nao encontrado", "text/plain")
        tipo = mimetypes.guess_type(arquivo)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript",):
            tipo += "; charset=utf-8"
        with open(arquivo, "rb") as f:
            self._responder(200, f.read(), tipo)

    def do_POST(self):
        rota = ROTAS.get(self.path.split("?", 1)[0])
        if rota is None:
            return self._json(404, {"erro": "rota inexistente"})
        try:
            tamanho = int(self.headers.get("Content-Length", 0))
            dados = json.loads(self.rfile.read(tamanho).decode("utf-8") or "{}")
            return self._json(200, rota(dados))
        except (ErroER, ErroGramatica, ValueError, KeyError) as e:
            return self._json(400, {"erro": str(e)})
        except Exception as e:  # erro inesperado: mostra na interface em vez de derrubar o servidor
            traceback.print_exc()
            return self._json(500, {"erro": f"erro interno: {e}"})


def iniciar(porta: int = 8765, abrir: bool = True) -> None:
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    servidor = None
    for p in range(porta, porta + 20):
        try:
            servidor = ThreadingHTTPServer(("127.0.0.1", p), Manipulador)
            break
        except OSError:
            continue
    if servidor is None:
        raise OSError(f"nenhuma porta livre entre {porta} e {porta + 19}")
    url = f"http://127.0.0.1:{servidor.server_address[1]}/"
    print(f"Interface em {url}  (Ctrl+C para encerrar)")
    if abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        servidor.server_close()
