#!/usr/bin/env bash
# Run before every push: fails if a key, a .env file or market data would be published.
set -uo pipefail
cd "$(dirname "$0")" || exit 1
fail=0

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "STOP: not a git repository yet (run git init and git add first): nothing was checked."; exit 1
fi

if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "STOP: .env is tracked by git. Run: git rm --cached .env"; fail=1
fi
if git ls-files | grep -qE '^data/|\.db$|\.csv\.gz$'; then
  echo "STOP: market data or the database is tracked (data/, *.db, *.csv.gz)."; fail=1
fi
# Alpaca keys look like PK/AK + 16 to 30 capitals and digits; secrets are 40 characters
if git grep -nIE '(PK|AK)[A-Z0-9]{16,30}|ALPACA_SECRET_KEY=[A-Za-z0-9]{20,}' -- . ':!check_secrets.sh' 2>/dev/null; then
  echo "STOP: something that looks like an Alpaca key is in a tracked file (lines above)."; fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "OK: no key, no .env, no market data in what git will publish."
fi
exit "$fail"
