import pandas as pd
import streamlit as st

from common import chart_vs_spy, drawdown, footer, has_keys, is_public_demo, kpis_vs_spy, lang, link, research, style, t, tr

style()

fr = lang() == "fr"
st.markdown(f"# {t('portfolio')}")

if is_public_demo():
    st.info("Cette page tourne en local uniquement : elle a besoin de ta propre clé Alpaca (gratuite), qui ne doit "
            "jamais être saisie sur un site public. Voir le README pour installer l'app sur ta machine."
            if fr else
            "This page runs locally only: it needs your own (free) Alpaca key, which must never be typed into a "
            "public website. See the README to run the app on your machine.")
    footer()
    st.stop()
if not has_keys():
    st.warning("Ajoute ta clé Alpaca dans la page Données." if fr else "Add your Alpaca key on the Data page.")
    link("views/data.py", t("data"), ":material/database:")
    footer()
    st.stop()

from aptrade.config import Settings  # noqa: E402
from aptrade.swing.custom import run_custom, run_named  # noqa: E402
from aptrade.swing.strategies import MEANREV_UNIVERSE, TREND_UNIVERSE  # noqa: E402

KNOWN = sorted(set(TREND_UNIVERSE) | set(MEANREV_UNIVERSE) | {"VTI", "VXUS", "BND", "AGG", "VEA", "VWO", "SCHD"})
mode = st.radio("Que veux-tu tester ?" if fr else "What do you want to test?",
                ["custom", "strategy"], horizontal=True,
                format_func=lambda m: ("Mes ETF et mes poids" if fr else "My ETFs and weights") if m == "custom"
                else ("Une stratégie testée" if fr else "A tested strategy"))


def show(out: dict):
    c = out["compare"]
    s, b = c["strategy"], c["spy"]
    st.markdown(f"**{out['label']}**, {s['start']} → {s['end']}")
    kpis_vs_spy(s, b)
    g = {t("portfolio_col"): 10_000 * out["growth"], "SPY": 10_000 * out["spy_growth"]}
    st.markdown("**" + ("Évolution de 10 000 \\$" if fr else "Growth of \\$10,000") + "**")
    chart_vs_spy(g)
    st.markdown(f"**{'Baisse depuis le plus haut (%)' if fr else 'Drop from the peak (%)'}**")
    st.area_chart(pd.DataFrame({k: drawdown(v) for k, v in g.items()}), height=180, color=["#F6465D", "#5E6673"])
    st.caption((f"{out['rebalances']} rééquilibrages, frais {out['cost_pct_year']:.2f} % par an.") if fr else
               (f"{out['rebalances']} rebalances, costs {out['cost_pct_year']:.2f}% a year."))
    st.warning("Tu as choisi ces poids en connaissant déjà l'histoire : ce résultat est optimiste par construction. "
               "Il décrit le passé, il ne prédit pas l'avenir." if fr else
               "You chose these weights knowing the history: this result is optimistic by construction. It "
               "describes the past; it does not predict the future.", icon=":material/info:")


if mode == "custom":
    tickers = st.multiselect("ETF", KNOWN, default=["SPY", "IEF", "GLD"])
    extra = st.text_input("Autres tickers (séparés par des virgules)" if fr else "Other tickers (comma-separated)")
    tickers += [x.strip().upper() for x in extra.split(",") if x.strip()]
    weights = {}
    if tickers:
        cols = st.columns(min(len(tickers), 4))
        for i, tk in enumerate(dict.fromkeys(tickers)):
            with cols[i % len(cols)]:
                weights[tk] = st.number_input(f"{tk} %", 0, 100, 100 // len(tickers), step=5) / 100
    total = sum(weights.values())
    st.caption((f"Total {100 * total:.0f} %. Le reste va en cash (BIL)." if fr
                else f"Total {100 * total:.0f}%. The rest goes to cash (BIL)."))
    reb = st.selectbox("Rééquilibrage" if fr else "Rebalance", ["Q", "M", "Y", "none"],
                       format_func={"M": "mensuel / monthly", "Q": "trimestriel / quarterly",
                                    "Y": "annuel / yearly", "none": "jamais / never"}.get)
    cost = st.number_input("Frais par côté (bps)" if fr else "Costs per side (bps)", 0.0, 50.0, 3.0, 1.0)
    if st.button("Tester" if fr else "Run", type="primary", disabled=total == 0 or total > 1.0001):
        with st.spinner("Téléchargement et calcul..." if fr else "Downloading and computing..."):
            try:
                show(run_custom(weights, reb, Settings.from_env(), cost))
            except Exception as exc:
                st.error(str(exc))
    if total > 1.0001:
        st.error("Plus de 100 % : pas de levier ici." if fr else "Over 100%: no leverage here.")
else:
    hyp = {h["key"]: h for h in research()["approaches"] if h["key"] not in ("orb", "alloc")}
    k = st.selectbox("Stratégie" if fr else "Strategy", list(hyp), format_func=lambda k: tr(hyp[k]["name"]))
    st.markdown(tr(hyp[k]["how"]))
    st.caption(f"{'Objectif fixé avant le test' if fr else 'Target set before the test'} : {tr(hyp[k]['target'])} "
               f"{'Résultat' if fr else 'Outcome'} : {tr(hyp[k]['outcome'])}")
    if st.button("Recalculer avec mes données" if fr else "Recompute with my data"):
        params = {"trend": {"lookback": 63, "rebalance": "M"}, "meanrev": {"rsi_threshold": 5, "max_hold": 10}}
        with st.spinner("..."):
            try:
                show(run_named(k, Settings.from_env(), **params.get(k, {})))
            except Exception as exc:
                st.error(str(exc))
footer()
