#!/usr/bin/env bash
# aptrade : installation, données, résultats, puis l'app. Relançable sans risque.
set -euo pipefail

DIR="$HOME/code/aptrade"
ZIP="$HOME/Downloads/aptrade.zip"
PKG_URL="https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg"

step() { printf '\n==> %s\n' "$1"; }

step "1/6 Dossier du projet"
if [ ! -f "$DIR/pyproject.toml" ]; then
  [ -f "$ZIP" ] || { echo "Introuvable : $ZIP"; exit 1; }
  mkdir -p "$HOME/code"
  unzip -oq "$ZIP" -d "$HOME/code"
fi
cd "$DIR"
echo "OK : $DIR"

step "2/6 Python 3.10 ou plus"
# /usr/bin/python3 est volontairement ignoré : c'est celui d'Xcode (3.9, et bloqué par la licence).
PY=""
for c in python3.13 python3.12 python3.11 python3.10 \
         /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if command -v "$c" >/dev/null 2>&1 && [ "$(command -v "$c")" != "/usr/bin/python3" ] &&
     "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' </dev/null >/dev/null 2>&1; then
    PY="$(command -v "$c")"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Aucun Python récent trouvé : installation de Python 3.12 depuis python.org."
  echo "Le Mac va demander ton mot de passe de session (rien ne s'affiche quand tu tapes, c'est normal)."
  curl -fL --progress-bar -o /tmp/python312.pkg "$PKG_URL"
  sudo installer -pkg /tmp/python312.pkg -target /
  PY="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
fi
echo "OK : $("$PY" --version) ($PY)"

step "3/6 Environnement et dépendances (1 à 2 min la première fois)"
if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  rm -rf .venv
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -e .
echo "OK"

step "4/6 Clés Alpaca"
[ -f .env ] || cp .env.example .env
key="$(grep -E '^ALPACA_API_KEY=' .env | cut -d= -f2- | tr -d '[:space:]"' || true)"
sec="$(grep -E '^ALPACA_SECRET_KEY=' .env | cut -d= -f2- | tr -d '[:space:]"' || true)"
if [ -z "$key" ] || [ -z "$sec" ]; then
  echo "Clés absentes de .env. Colle-les ici (paper trading). Le secret ne s'affiche pas."
  read -r -p "ALPACA_API_KEY : " key </dev/tty
  read -r -s -p "ALPACA_SECRET_KEY : " sec </dev/tty; echo
  printf 'ALPACA_API_KEY=%s\nALPACA_SECRET_KEY=%s\n' "$key" "$sec" > .env
  chmod 600 .env
fi
echo "OK : clé ${key:0:4}... enregistrée dans .env"

step "5/6 Tests (doit finir par OK)"
.venv/bin/python -m unittest discover -s tests -t . 2>&1 | tail -3

step "6/6 Données journalières, résultats, puis l'app"
.venv/bin/aptrade swing fetch
.venv/bin/aptrade export
printf "\nL'app s'ouvre dans ton navigateur. Ctrl+C dans ce terminal pour l'arrêter.\n"
.venv/bin/aptrade app
