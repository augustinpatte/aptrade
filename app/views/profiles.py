import pandas as pd
import streamlit as st

from common import (MUTED, chart_vs_spy, drawdown, footer, growth, kpi_row, kpis_vs_spy, lang, monthly_heatmap,
                    research, results, style, t, tr)

style()
fr = lang() == "fr"
st.markdown(f"# {t('profiles')}")
res = results()
if res is None:
    st.warning(t("no_results"))
    st.stop()

meta, P = res["meta"], res["portfolios"]
st.markdown(
    "Une part en **actions américaines (SPY)**, le reste dans **15 ETF diversifiés** (obligations, or, matières "
    "premières, international, immobilier), pondérés par l'inverse de leur volatilité et remis à la cible chaque "
    "fin de mois. Aucun timing : c'est l'allocation qui a le mieux tenu dans l'expérience."
    if fr else
    "A share in **US stocks (SPY)**, the rest in **15 diversified ETFs** (bonds, gold, commodities, international, "
    "real estate), weighted by inverse volatility and reset every month-end. No timing: the allocation that held "
    "up best in the experiment.")

c1, c2 = st.columns([3, 2])
with c1:
    spy_pct = st.select_slider("Part en SPY" if fr else "Share in SPY", options=list(range(0, 101, 10)),
                               value=50, format_func=lambda v: f"{v}%")
with c2:
    windows = {"3y": t("3y"), "full": t("full")}
    if meta.get("holdout_start"):
        windows.update({"research": t("research_w"), "holdout": t("holdout_w")})
    w = st.radio("Période" if fr else "Period", list(windows), format_func=windows.get, horizontal=True)

port = P[f"alloc_{spy_pct}"]
stats = port["stats"].get(w) or {}
if not stats:
    st.warning("Pas assez de données pour cette période." if fr else "Not enough data for this period.")
    st.stop()
ps, ss = stats["portfolio"], stats["spy"]
start, end = ps["start"], ps["end"]
st.caption(f"{start} → {end}")
kpis_vs_spy(ps, ss)

hyp = {a["results_key"]: a for a in research()["approaches"] if a.get("results_key") and a["key"] != "alloc"}
compare = st.multiselect("Superposer une stratégie" if fr else "Overlay a strategy", list(hyp),
                         format_func=lambda k: tr(hyp[k]["name"]))
label = f"{spy_pct}% SPY"
g = {label: growth(port["monthly"], start, end), "SPY": growth(P["spy"]["monthly"], start, end)}
for k in compare:
    g[tr(hyp[k]["name"])] = growth(P[k]["monthly"], start, end)
st.markdown(f"**{t('growth_of')}**")
chart_vs_spy(g)

st.markdown(f"**{'Baisse depuis le plus haut (%)' if fr else 'Drop from the peak (%)'}**")
st.area_chart(pd.DataFrame({label: drawdown(g[label]), "SPY": drawdown(g["SPY"])}), height=180,
              color=["#F6465D", "#5E6673"])
loss = 10_000 * ps["max_drawdown_pct"] / 100
st.markdown(
    f"Au pire moment, ce portefeuille a perdu **{ps['max_drawdown_pct']:.1f} %** depuis son sommet, soit "
    f"**{loss:,.0f} \\$** sur 10 000 \\$. Le SPY : {ss['max_drawdown_pct']:.1f} %." if fr else
    f"At its worst, this portfolio was **{ps['max_drawdown_pct']:.1f}%** below its peak, **\\${loss:,.0f}** on "
    f"\\$10,000. SPY: {ss['max_drawdown_pct']:.1f}%.")

st.markdown(f"**{'Rendements mensuels (%)' if fr else 'Monthly returns (%)'}**")
monthly_heatmap(port["monthly"], start, end)

a = port.get("activity", {})
if a:
    st.markdown(f"**{'Risque et positions' if fr else 'Risk and positions'}**")
    kpi_row([
        ("Lignes en moyenne" if fr else "Lines on average", f"{a['avg_positions']:.0f}", "#EAECEF", "", MUTED),
        ("Plus grosse ligne" if fr else "Largest line", f"{a['max_position_pct']:.0f}%", "#EAECEF",
         "SPY" if spy_pct >= 20 else "", MUTED),
        ("Investi" if fr else "Invested", f"{a['avg_invested_pct']:.0f}%", "#EAECEF",
         "le reste en bons du Trésor" if fr else "rest in T-bills", MUTED),
        ("Rééquilibrages / an" if fr else "Rebalances / year", f"{a['rebalances_per_year']:.0f}", "#EAECEF", "", MUTED),
        ("Frais / an" if fr else "Costs / year", f"{a['cost_pct_per_year']:.2f}%", "#EAECEF", "", MUTED),
    ])
d = stats["excess_sharpe_diff"]
st.caption(
    (f"Écart de Sharpe hors cash avec le SPY : {d['diff']:+.2f} (intervalle à 90 % : {d['ci90_low']:+.2f} à "
     f"{d['ci90_high']:+.2f}). Frais {meta['cost_bps']} pb par côté. Résultats du {meta['generated'][:10]}.")
    if fr else
    (f"Excess Sharpe gap with SPY: {d['diff']:+.2f} (90% interval {d['ci90_low']:+.2f} to {d['ci90_high']:+.2f}). "
     f"Costs {meta['cost_bps']} bps per side. Results from {meta['generated'][:10]}."))
footer()
