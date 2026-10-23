#!/usr/bin/env bash
# aptrade swing : tests + données journalières + walk-forward des deux hypothèses pré-enregistrées.
# Prérequis : run_all.sh a déjà tourné une fois (Python, .venv, clés Alpaca).
set -euo pipefail
cd "$HOME/code/aptrade"

step() { printf '\n==> %s\n' "$1"; }

[ -x .venv/bin/python ] || { echo "Lance d'abord : bash ~/code/aptrade/run_all.sh"; exit 1; }

step "1/4 Mise à jour du paquet"
.venv/bin/python -m pip install -q -e .
echo "OK"

step "2/4 Tests (doit finir par OK)"
.venv/bin/python -m unittest discover -s tests -t . 2>&1 | tail -3

step "3/4 Données journalières des 26 ETF depuis 2016"
.venv/bin/aptrade swing fetch 2>&1 | tee swing_fetch.txt

step "4/4 Walk-forward des deux hypothèses (1 à 2 min chacune)"
.venv/bin/aptrade swing sweep --strategy trend 2>&1 | tee swing_trend.txt
.venv/bin/aptrade swing sweep --strategy meanrev 2>&1 | tee swing_meanrev.txt

printf "\nTERMINÉ. Envoie swing_trend.txt et swing_meanrev.txt. Ne lance PAS swing holdout.\n"
open .
