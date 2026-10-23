#!/usr/bin/env bash
# aptrade H4 (témoin sans signal) et H5 (rotation par momentum relatif) : recherche, puis un regard unique sur le holdout.
set -euo pipefail
cd "$HOME/code/aptrade"

step() { printf '\n==> %s\n' "$1"; }

[ -x .venv/bin/python ] || { echo "Lance d'abord : bash ~/code/aptrade/run_all.sh"; exit 1; }

step "1/4 Mise à jour du paquet"
.venv/bin/python -m pip install -q -e .
echo "OK"

step "2/4 Tests (doit finir par OK)"
.venv/bin/python -m unittest discover -s tests -t . 2>&1 | tail -3

step "3/4 H4 témoin : recherche puis holdout"
{ .venv/bin/aptrade swing backtest --strategy static && echo && \
  .venv/bin/aptrade swing holdout --strategy static; } 2>&1 | tee h4_static.txt

step "4/4 H5 rotation : recherche puis holdout"
{ .venv/bin/aptrade swing backtest --strategy rotation && echo && \
  .venv/bin/aptrade swing holdout --strategy rotation; } 2>&1 | tee h5_rotation.txt

printf "\nTERMINÉ. Envoie h4_static.txt et h5_rotation.txt.\n"
open .
