"""Managing a real portfolio: a target, a rebalancing plan, risk checks, execution.

Design rules (see SAFETY in the README and skills/aptrade-broker/SKILL.md):
  - APtrade only manages the symbols in your target; anything else in the account is left alone.
  - Paper and live use different keys; live also needs APTRADE_ALLOW_LIVE=1.
  - A live plan is executed only after a human types its confirmation code in a real
    terminal. An AI agent can build and explain the plan, it cannot approve it.
  - Hard limits live in risk.py and cannot be raised from the command line.
"""
