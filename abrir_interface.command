#!/bin/bash
# Abre a interface grafica do gerador (dois cliques no Finder)
cd "$(dirname "$0")"
python3 main.py web
