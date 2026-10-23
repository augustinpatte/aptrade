"""Fill the results tables of README.md and README.fr.md from results/results.json.

The README numbers are never typed by hand: `aptrade export` rewrites the block
between <!-- results:start --> and <!-- results:end --> in both files."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START, END = "<!-- results:start -->", "<!-- results:end -->"

ROWS = [  # (results key, research key or None, English name, French name)
    ("alloc_100", None, "S&P 500 (SPY), the benchmark", "S&P 500 (SPY), la référence"),
    ("alloc_70", "alloc", "Diversified 70% SPY", "Diversifié 70 % SPY"),
    ("alloc_50", "alloc", "Diversified 50% SPY", "Diversifié 50 % SPY"),
    ("alloc_30", "alloc", "Diversified 30% SPY", "Diversifié 30 % SPY"),
    ("blend", "blend", "Half SPY, half trend following", "Moitié SPY, moitié tendance"),
    ("trend", "trend", "Trend following", "Suivi de tendance"),
    ("rotation", "rotation", "Momentum rotation", "Rotation par momentum"),
    ("meanrev", "meanrev", "Buy the dip (3 to 10 days)", "Acheter le repli (3 à 10 jours)"),
]


def _ret(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{'🟢' if x >= 0 else '🔴'} {x:+.1f}%"


def _pct(x: float | None, fr: bool) -> str:
    if x is None:
        return "n/a"
    s = f"{x:.1f}%"
    return s.replace(".", ",").replace("%", " %") if fr else s


def table(doc: dict, research: dict, lang: str) -> str:
    fr = lang == "fr"
    P = doc["portfolios"]
    meta = doc["meta"]
    head = ("| Approche | 3 ans | Par an (3 ans) | Pire baisse (3 ans) | Volatilité | Par an depuis 2017 | Risque par position |\n"
            "|---|---|---|---|---|---|---|") if fr else \
           ("| Approach | 3 years | Per year (3 y) | Worst drop (3 y) | Volatility | Per year since 2017 | Risk per position |\n"
            "|---|---|---|---|---|---|---|")
    lines = [head]
    for key, rkey, en, frn in ROWS:
        if key not in P:
            continue
        s3 = P[key]["stats"].get("3y", {}).get("portfolio", {})
        sf = P[key]["stats"].get("full", {}).get("portfolio", {})
        a = P[key].get("activity", {})
        if key == "alloc_100":
            risk = "1 ligne, 100 %" if fr else "1 line, 100%"
        else:
            risk = (f"{a.get('avg_positions', 0):.0f} lignes en moyenne, max {a.get('max_position_pct', 0):.0f} %"
                    if fr else f"{a.get('avg_positions', 0):.0f} lines on average, max {a.get('max_position_pct', 0):.0f}%")
        lines.append(f"| {frn if fr else en} | {_ret(s3.get('total_return_pct'))} | {_ret(s3.get('cagr_pct'))} | "
                     f"{_pct(s3.get('max_drawdown_pct'), fr)} | {_pct(s3.get('vol_pct'), fr)} | "
                     f"{_ret(sf.get('cagr_pct'))} | {risk} |")
    orb = next((h for h in research.get("approaches", []) if h["key"] == "orb"), None)
    if orb and orb.get("static_numbers"):
        n = orb["static_numbers"]
        lines.append(f"| {'Day trading (cassure d’ouverture)' if fr else 'Day trading (opening-range breakout)'} | "
                     f"{_ret(n['return_pct'])} {'(18 mois)' if fr else '(18 months)'} | n/a | "
                     f"{_pct(n['max_drawdown_pct'], fr)} | n/a | n/a | "
                     f"{'0,25 % du compte par trade' if fr else '0.25% of the account per trade'} |")
    s3spy = P.get("alloc_100", {}).get("stats", {}).get("3y", {}).get("portfolio", {})
    note = (f"Données du {meta['data_start']} au {meta['data_end']} ; « 3 ans » = du {s3spy.get('start', '?')} au "
            f"{s3spy.get('end', '?')}. Frais de {meta['cost_bps']} points de base par côté inclus. Les performances "
            "passées ne préjugent pas des performances futures.") if fr else \
           (f"Data from {meta['data_start']} to {meta['data_end']}; \"3 years\" = {s3spy.get('start', '?')} to "
            f"{s3spy.get('end', '?')}. Costs of {meta['cost_bps']} bps per side included. Past performance does not "
            "predict future results.")
    return "\n".join(lines) + "\n\n" + f"<sub>{note}</sub>"


def fill(path: Path, doc: dict, research: dict, lang: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text()
    if START not in text or END not in text:
        return False
    block = f"{START}\n{table(doc, research, lang)}\n{END}"
    path.write_text(re.sub(re.escape(START) + r".*?" + re.escape(END), lambda m: block, text, flags=re.S))
    return True


def fill_readmes(doc: dict, root: Path = ROOT) -> list:
    research = json.loads((root / "results" / "research.json").read_text())
    done = []
    for name, lang in (("README.md", "en"), ("README.fr.md", "fr")):
        if fill(root / name, doc, research, lang):
            done.append(root / name)
    return done
