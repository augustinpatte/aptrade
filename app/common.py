"""Shared pieces of the app: language, results, formatting, charts."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:                       # the app runs without `pip install`
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)                                      # data/ and .env are relative to the repo

from aptrade.config import load_dotenv  # noqa: E402

RESEARCH_FILE = ROOT / "results" / "research.json"
REPO_URL = "https://github.com/augustinpatte/aptrade"

S = {
    "lang": {"en": "Language", "fr": "Langue"},
    "home": {"en": "Dashboard", "fr": "Tableau de bord"},
    "profiles": {"en": "Allocation", "fr": "Allocation"},
    "portfolio": {"en": "My portfolio", "fr": "Mon portefeuille"},
    "research": {"en": "Strategies", "fr": "Stratégies"},
    "method": {"en": "Method & safeguards", "fr": "Méthode et garde-fous"},
    "data": {"en": "Settings", "fr": "Réglages"},
    "disclaimer": {
        "en": "Educational software, not financial advice. Past results do not predict future ones. "
              "Every number here can be reproduced from the code.",
        "fr": "Logiciel éducatif, pas un conseil financier. Les résultats passés ne prédisent pas les "
              "résultats futurs. Chaque chiffre ici est reproductible à partir du code."},
    "no_results": {
        "en": "No precomputed results yet. On a machine with an Alpaca key, run `aptrade swing fetch` then "
              "`aptrade export`, and reload.",
        "fr": "Pas encore de résultats précalculés. Sur une machine avec une clé Alpaca, lance "
              "`aptrade swing fetch` puis `aptrade export`, et recharge."},
    "portfolio_col": {"en": "Portfolio", "fr": "Portefeuille"},
    "cagr": {"en": "Return per year", "fr": "Rendement par an"},
    "total": {"en": "Total return", "fr": "Rendement total"},
    "vol": {"en": "Volatility", "fr": "Volatilité"},
    "sharpe": {"en": "Sharpe (over cash)", "fr": "Sharpe (hors cash)"},
    "mdd": {"en": "Max drawdown", "fr": "Baisse max"},
    "worst": {"en": "Worst month", "fr": "Pire mois"},
    "up": {"en": "Months up", "fr": "Mois positifs"},
    "full": {"en": "Since 2017", "fr": "Depuis 2017"},
    "3y": {"en": "Last 3 years", "fr": "3 dernières années"},
    "research_w": {"en": "Research period", "fr": "Période de recherche"},
    "holdout_w": {"en": "Reserved test period", "fr": "Période de test réservée"},
    "growth_of": {"en": "Growth of \\$10,000 (monthly)", "fr": "Évolution de 10 000 \\$ (mensuel)"},
}

VERDICT_COLOR = {"PASS": "green", "WEAK": "orange", "FAIL": "red"}


def lang() -> str:
    return st.session_state.get("lang", "en")


def t(key: str) -> str:
    return S[key][lang()] if key in S else key


def tr(d: dict) -> str:
    """Pick the current language from a {'en': ..., 'fr': ...} dict."""
    return d.get(lang(), d.get("en", ""))


def is_public_demo() -> bool:
    """The public deployment sets APTRADE_PUBLIC_DEMO=1: no keys accepted, no downloads."""
    if os.environ.get("APTRADE_PUBLIC_DEMO") == "1":
        return True
    try:
        return str(st.secrets.get("APTRADE_PUBLIC_DEMO", "")) == "1"
    except Exception:
        return False


def has_keys() -> bool:
    load_dotenv(ROOT / ".env")
    return bool(os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"))


def results_file() -> Path:
    return Path(os.environ.get("APTRADE_RESULTS", ROOT / "results" / "results.json"))


@st.cache_data
def load_results(path: str, mtime: float | None) -> dict | None:
    return json.loads(Path(path).read_text()) if mtime is not None else None


def results() -> dict | None:
    f = results_file()
    return load_results(str(f), f.stat().st_mtime if f.is_file() else None)


def link(page: str, label: str, icon: str | None = None):
    """st.page_link, or plain text when the page runs outside the app's navigation (tests)."""
    try:
        st.page_link(page, label=label, icon=icon)
    except Exception:
        st.markdown(f"**{label}**")


@st.cache_data
def research() -> dict:
    return json.loads(RESEARCH_FILE.read_text())


def verdict_badge(v: str) -> str:
    return f":{VERDICT_COLOR.get(v, 'gray')}[**{v}**]"


def growth(monthly: list, start: str | None = None, end: str | None = None, base: float = 10_000) -> pd.Series:
    s = pd.Series({m: r for m, r in monthly})
    if start:
        s = s[s.index >= start[:7]]
    if end:
        s = s[s.index <= end[:7]]
    g = base * (1 + s).cumprod()
    g.index = pd.PeriodIndex(g.index, freq="M").to_timestamp()
    return g


def pct(x, signed=False) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "n/a"
    return f"{x:+.1f}%" if signed else f"{x:.1f}%"


def stats_table(port: dict, spy: dict, name: str) -> pd.DataFrame:
    rows = [("cagr", "cagr_pct", True), ("total", "total_return_pct", True), ("vol", "vol_pct", False),
            ("sharpe", "excess_sharpe", None), ("mdd", "max_drawdown_pct", False),
            ("worst", "worst_month_pct", True), ("up", "pct_months_up", False)]
    out = []
    for label, key, signed in rows:
        f = (lambda v: f"{v:.2f}") if signed is None else (lambda v, s=signed: pct(v, s))
        out.append({"": t(label), name: f(port.get(key)), "SPY": f(spy.get(key))})
    return pd.DataFrame(out).set_index("")


def footer():
    st.divider()
    st.caption(t("disclaimer"))


# ------------------------------------------------------------------ trader look

GREEN, RED, MUTED = "#0ECB81", "#F6465D", "#848E9C"

CSS = """
<style>
.kpi {background:#161A1E;border:1px solid #2B3139;border-radius:10px;padding:14px 16px;height:100%}
.kpi .l {color:#848E9C;font-size:0.78rem;text-transform:uppercase;letter-spacing:.04em}
.kpi .v {font-size:1.55rem;font-weight:700;margin-top:2px;font-variant-numeric:tabular-nums}
.kpi .d {font-size:0.8rem;margin-top:2px;font-variant-numeric:tabular-nums}
.card {background:#161A1E;border:1px solid #2B3139;border-radius:12px;padding:16px 18px;margin-bottom:12px}
.card h4 {margin:0 0 4px 0}
.card .tag {color:#848E9C;font-size:0.85rem;margin-bottom:10px}
.pill {display:inline-block;background:#2B3139;color:#EAECEF;border-radius:999px;padding:1px 9px;font-size:0.75rem;margin-right:6px}
.pro {color:#0ECB81} .con {color:#F6465D}
</style>
"""


def style():
    st.markdown(CSS, unsafe_allow_html=True)


def color(x, good_if_positive=True) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return MUTED
    good = x >= 0 if good_if_positive else x <= 0
    return GREEN if good else RED


def kpi_html(label: str, value: str, col: str = "#EAECEF", delta: str = "", delta_col: str = MUTED) -> str:
    d = f'<div class="d" style="color:{delta_col}">{delta}</div>' if delta else ""
    return f'<div class="kpi"><div class="l">{label}</div><div class="v" style="color:{col}">{value}</div>{d}</div>'


def kpi_row(items: list):
    """items: (label, value, value_color, delta_text, delta_color)."""
    cols = st.columns(len(items))
    for c, it in zip(cols, items):
        c.markdown(kpi_html(*it), unsafe_allow_html=True)


def kpis_vs_spy(p: dict, s: dict):
    """The standard KPI strip: a portfolio's stats, each compared with SPY's."""
    fr = lang() == "fr"
    def dpts(a, b, inverse=False):
        if a is None or b is None:
            return "", MUTED
        d = a - b
        better = d <= 0 if inverse else d >= 0
        return (f"{d:+.1f} pts {'vs' if not fr else 'vs'} SPY", GREEN if better else RED)
    tr_, ac = dpts(p.get("total_return_pct"), s.get("total_return_pct"))
    cg, cc = dpts(p.get("cagr_pct"), s.get("cagr_pct"))
    dd, dc = dpts(p.get("max_drawdown_pct"), s.get("max_drawdown_pct"), inverse=True)
    vo, vc = dpts(p.get("vol_pct"), s.get("vol_pct"), inverse=True)
    sh = p.get("excess_sharpe")
    shd = (sh - s["excess_sharpe"]) if sh is not None and s.get("excess_sharpe") is not None else None
    kpi_row([
        (t("total"), pct(p.get("total_return_pct"), True), color(p.get("total_return_pct")), tr_, ac),
        (t("cagr"), pct(p.get("cagr_pct"), True), color(p.get("cagr_pct")), cg, cc),
        (t("mdd"), f"-{pct(p.get('max_drawdown_pct'))}", RED, dd, dc),
        (t("vol"), pct(p.get("vol_pct")), "#EAECEF", vo, vc),
        (t("sharpe"), f"{sh:.2f}" if sh is not None else "n/a", "#EAECEF",
         f"{shd:+.2f} vs SPY" if shd is not None else "", GREEN if (shd or 0) >= 0 else RED),
        (t("worst"), pct(p.get("worst_month_pct"), True), RED if (p.get("worst_month_pct") or 0) < 0 else GREEN,
         f"SPY {pct(s.get('worst_month_pct'), True)}", MUTED),
    ])


def drawdown(g: pd.Series) -> pd.Series:
    return 100 * (g / g.cummax() - 1)


def monthly_heatmap(monthly: list, start: str | None = None, end: str | None = None):
    s = pd.Series({m: r for m, r in monthly})
    if start:
        s = s[s.index >= start[:7]]
    if end:
        s = s[s.index <= end[:7]]
    if s.empty:
        return
    df = pd.DataFrame({"y": [m[:4] for m in s.index], "m": [int(m[5:]) for m in s.index], "r": 100 * s.values})
    tab = df.pivot(index="y", columns="m", values="r").reindex(columns=range(1, 13)).astype(float)
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] if lang() == "en" \
        else ["Janv", "Févr", "Mars", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc"]
    tab.columns = names
    tab["Year" if lang() == "en" else "Année"] = ((1 + df.groupby("y")["r"].apply(lambda x: (1 + x / 100).prod() - 1)) - 1) * 100
    tab.index.name = None

    def bg(v):
        if pd.isna(v):
            return "color:#3a3f45"
        a = min(abs(v) / 8, 1) * 0.75 + 0.1
        return f"background-color:rgba({'14,203,129' if v >= 0 else '246,70,93'},{a:.2f});color:#EAECEF"
    shown = tab.map(lambda v: "" if pd.isna(v) else f"{v:+.1f}")      # text cells: no "None" for future months
    st.dataframe(shown.style.apply(lambda _: tab.map(bg), axis=None), width="stretch")


def chart_vs_spy(series: dict, height: int = 340):
    """Growth lines with a y-axis fitted to the data (not starting at 0), SPY in grey."""
    import altair as alt
    df = pd.DataFrame(series)
    df.index.name = "date"
    long = df.reset_index().melt("date", var_name="series", value_name="value").dropna()
    palette = [GREEN, "#F0B90B", "#3B82F6", "#A855F7", "#EC4899"]
    names = list(df.columns)
    colors = [MUTED if c == "SPY" else palette[i % len(palette)] for i, c in enumerate(names)]
    chart = alt.Chart(long).mark_line(strokeWidth=2).encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("value:Q", title=None, scale=alt.Scale(zero=False), axis=alt.Axis(format=",.0f")),
        color=alt.Color("series:N", scale=alt.Scale(domain=names, range=colors),
                        legend=alt.Legend(orient="bottom", title=None)),
        tooltip=[alt.Tooltip("date:T"), "series:N", alt.Tooltip("value:Q", format=",.0f")],
    ).properties(height=height)
    st.altair_chart(chart, width="stretch")
