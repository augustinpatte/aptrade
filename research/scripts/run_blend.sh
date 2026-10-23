#!/usr/bin/env bash
# aptrade H3 : mélange 50 % SPY + 50 % suivi de tendance. Recherche, puis LE regard unique sur le holdout.
set -euo pipefail
cd "$HOME/code/aptrade"

step() { printf '\n==> %s\n' "$1"; }

[ -x .venv/bin/python ] || { echo "Lance d'abord : bash ~/code/aptrade/run_all.sh"; exit 1; }

step "1/4 Mise à jour du paquet"
.venv/bin/python -m pip install -q -e .
echo "OK"

step "2/4 Tests (doit finir par OK)"
.venv/bin/python -m unittest discover -s tests -t . 2>&1 | tail -3

step "3/4 Le mélange sur les données de recherche (contexte)"
.venv/bin/aptrade swing backtest --strategy blend 2>&1 | tee blend_research.txt

step "4/4 Le holdout : regard unique, décidé dans PREREGISTRATION.md"
.venv/bin/aptrade swing holdout --strategy blend 2>&1 | tee blend_holdout.txt

printf "\nTERMINÉ. Envoie blend_research.txt et blend_holdout.txt.\n"
open .
