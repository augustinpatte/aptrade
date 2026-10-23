# APtrade: instructions for AI agents (Codex, Grok, Claude Code and others)

APtrade researches portfolios against the S&P 500 and manages a paper or real Alpaca
account toward a target. The skills in `skills/` (also linked from `.agents/skills` and
`.claude/skills`) describe each task; read the relevant SKILL.md before acting.

## Non-negotiable rules

1. Never ask for, read aloud, log or paste API keys or secrets. Keys live in `.env`,
   which the user fills in. Never commit `.env`; run `./check_secrets.sh` before any push.
2. Real money: you may build and explain a live plan (`aptrade live plan --live`), you may
   NOT execute it. Give the user `aptrade live execute <id> --live` (or `aptrade live run
   --live`) to run in their own terminal; it asks them for a code shown only there. Never try to read or bypass it,
   never call the broker API directly, never edit `aptrade/live/risk.py`, the `.env`
   switches or the database to get an order through.
3. No leverage, margin, short selling, options or crypto.
4. Symbols outside the user's target are never traded.
5. When showing results: last 3 years and whole period, against SPY, strengths and
   weaknesses, worst drop in dollars, and the reminder that past results do not predict
   future ones. Not financial advice.
6. `aptrade swing holdout` is a one-time look at reserved data; do not run it unless the
   user explicitly asks and understands that.

## Useful commands (add --json for machine-readable output)

aptrade test-portfolio --weights SPY=60,IEF=30,GLD=10   aptrade target set|show
aptrade live status|plan|alerts [--live]                 aptrade live execute <id> | run   (paper only for agents)
aptrade live kill / unkill                               aptrade app

Tests: `python -m unittest discover -s tests -t .` (offline).
