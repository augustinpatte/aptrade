import pandas as pd
import streamlit as st

from common import (MUTED, RED, chart_vs_spy, color, drawdown, footer, growth, kpi_row, kpis_vs_spy, lang,
                    monthly_heatmap, pct, research, results, style, t, tr)

style()
fr = lang() == "fr"
R = research()
res = results()
st.markdown(f"# {t('research')}")
st.caption(tr(R["data"]))

apps = R["approaches"]
names = [tr(a["name"]) for a in apps]
pick = st.radio("Approche" if fr else "Approach", range(len(apps)), format_func=lambda i: names[i], horizontal=True)
a = apps[pick]
st.markdown(f"## {tr(a['name'])}")
st.markdown(f"{tr(a['tagline'])}  \n<span class='pill'>{tr(a['horizon'])}</span>", unsafe_allow_html=True)
st.markdown(f"**{'Comment ça marche' if fr else 'How it works'}.** {tr(a['how'])}")

key = a.get("results_key")
if key and res:
    P = res["portfolios"]
    windows = {"3y": t("3y"), "full": t("full"), "holdout": t("holdout_w")}
    w = st.radio("Période" if fr else "Period", list(windows), format_func=windows.get, horizontal=True, key="w")
    stats = P[key]["stats"].get(w) or {}
    if stats:
        ps, ss = stats["portfolio"], stats["spy"]
        st.caption(f"{ps['start']} → {ps['end']}")
        kpis_vs_spy(ps, ss)
        g = {tr(a["name"]): growth(P[key]["monthly"], ps["start"], ps["end"]),
             "SPY": growth(P["spy"]["monthly"], ps["start"], ps["end"])}
        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown(f"**{t('growth_of')}**")
            chart_vs_spy(g, height=300)
        with c2:
            st.markdown(f"**{'Baisse depuis le plus haut (%)' if fr else 'Drop from the peak (%)'}**")
            st.area_chart(pd.DataFrame({k: drawdown(v) for k, v in g.items()}), height=300,
                          color=["#F6465D", "#5E6673"])
        with st.expander("Rendements mensuels" if fr else "Monthly returns"):
            monthly_heatmap(P[key]["monthly"], ps["start"], ps["end"])
elif a["key"] == "orb":
    n = a["static_numbers"]
    st.caption(f"{n['period']} · {n['trades']:,} trades")
    kpi_row([
        ("Compte simulé 5 000 $" if fr else "Simulated $5,000 account", pct(n["return_pct"], True), color(n["return_pct"]),
         f"SPY {pct(n['spy_return_pct'], True)}", MUTED),
        ("Pire baisse" if fr else "Worst drop", f"-{pct(n['max_drawdown_pct'])}", RED, "", MUTED),
        ("Trades", f"{n['trades']:,}", "#EAECEF", "", MUTED),
    ])
    st.info("Testé sur des bougies de 5 minutes, archivé dans `aptrade intraday`. Pas affiché dans les graphiques "
            "journaliers." if fr else "Tested on 5-minute bars, archived in `aptrade intraday`. Not shown on the "
            "daily charts.")

c1, c2 = st.columns(2)
with c1:
    st.markdown(f"#### {'Points forts' if fr else 'Strengths'}")
    for p in a["pros"][lang()]:
        st.markdown(f"<span class='pro'>▲</span> {p}", unsafe_allow_html=True)
with c2:
    st.markdown(f"#### {'Points faibles' if fr else 'Weaknesses'}")
    for p in a["cons"][lang()]:
        st.markdown(f"<span class='con'>▼</span> {p}", unsafe_allow_html=True)

st.markdown(f"#### {'Risque par position' if fr else 'Risk per position'}")
st.markdown(f'<div class="card">{tr(a["risk"])}</div>', unsafe_allow_html=True)
if key and res:
    act = res["portfolios"][key].get("activity", {})
    if act:
        kpi_row([
            ("Lignes en moyenne" if fr else "Lines on average", f"{act['avg_positions']:.0f}", "#EAECEF", "", MUTED),
            ("Plus grosse ligne" if fr else "Largest line", f"{act['max_position_pct']:.0f}%", "#EAECEF", "", MUTED),
            ("Investi en moyenne" if fr else "Invested on average", f"{act['avg_invested_pct']:.0f}%", "#EAECEF", "", MUTED),
            ("Rotation / an" if fr else "Turnover / year", f"{act['turnover_per_year']:.1f}x", "#EAECEF", "", MUTED),
            ("Frais / an" if fr else "Costs / year", f"{act['cost_pct_per_year']:.2f}%", "#EAECEF", "", MUTED),
        ])

with st.expander("Objectif fixé avant le test, et résultat" if fr else "Target set before the test, and outcome"):
    st.markdown(f"**{'Objectif' if fr else 'Target'}.** {tr(a['target'])}")
    st.markdown(f"**{'Résultat' if fr else 'Outcome'}.** {tr(a['outcome'])}")
    st.caption("Les objectifs sont volontairement exigeants : battre le S&P 500 en rendement ajusté du risque, de "
               "façon statistiquement solide. Voir Méthode et garde-fous." if fr else
               "Targets are deliberately demanding: beat the S&P 500 on a risk-adjusted basis, with statistical "
               "confidence. See Method & safeguards.")
footer()
