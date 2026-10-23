import streamlit as st

from common import GREEN, MUTED, RED, color, footer, kpi_html, lang, link, pct, research, results, style, t, tr

style()
fr = lang() == "fr"
R = research()
res = results()

st.markdown("# APtrade")
st.markdown(
    "**Une expérience** : prendre des stratégies de trading et des portefeuilles, les tester honnêtement sur "
    "10 ans de données de marché réelles, frais compris, et comparer chacun au S&P 500. Choisis une allocation, "
    "explore les stratégies, ou teste ton propre portefeuille."
    if fr else
    "**An experiment**: take trading strategies and portfolios, test them honestly on 10 years of real market "
    "data, costs included, and compare each one with the S&P 500. Pick an allocation, explore the strategies, "
    "or test your own portfolio.")

if res is None:
    st.warning(t("no_results"))
    footer()
    st.stop()

P = res["portfolios"]
show = [("alloc_100", "S&P 500"), ("alloc_50", "Diversifié 50 %" if fr else "Diversified 50%"),
        ("blend", "50 % SPY + tendance" if fr else "50% SPY + trend"), ("trend", "Tendance" if fr else "Trend"),
        ("rotation", "Rotation")]
st.markdown(f"#### {'Performance sur les 3 dernières années' if fr else 'Performance over the last 3 years'}")
cols = st.columns(len(show))
for c, (k, name) in zip(cols, show):
    s = P.get(k, {}).get("stats", {}).get("3y", {}).get("portfolio", {})
    c.markdown(kpi_html(name, pct(s.get("total_return_pct"), True), color(s.get("total_return_pct")),
                        f"{'baisse max' if fr else 'max drop'} -{pct(s.get('max_drawdown_pct'))}", RED),
               unsafe_allow_html=True)
s3 = P["alloc_100"]["stats"]["3y"]["portfolio"]
st.caption(f"{s3['start']} → {s3['end']} · {'frais inclus' if fr else 'costs included'}")

st.markdown(f"#### {'Les approches' if fr else 'The approaches'}")
apps = [a for a in R["approaches"] if a.get("results_key")]
for row in range(0, len(apps), 3):
    cols = st.columns(3)
    for c, a in zip(cols, apps[row:row + 3]):
        s = P.get(a["results_key"], {}).get("stats", {}).get("3y", {}).get("portfolio", {})
        f = P.get(a["results_key"], {}).get("stats", {}).get("full", {}).get("portfolio", {})
        c.markdown(
            f'<div class="card"><h4>{tr(a["name"])}</h4><div class="tag">{tr(a["tagline"])}</div>'
            f'<span class="pill">{tr(a["horizon"])}</span><br><br>'
            f'<b style="color:{color(s.get("total_return_pct"))}">{pct(s.get("total_return_pct"), True)}</b> '
            f'<span style="color:{MUTED}">{"sur 3 ans" if fr else "over 3 years"}</span> · '
            f'<b style="color:{color(f.get("cagr_pct"))}">{pct(f.get("cagr_pct"), True)}</b> '
            f'<span style="color:{MUTED}">{"par an depuis 2017" if fr else "a year since 2017"}</span><br>'
            f'<span style="color:{RED}">-{pct(s.get("max_drawdown_pct"))}</span> '
            f'<span style="color:{MUTED}">{"pire baisse (3 ans)" if fr else "worst drop (3 y)"}</span></div>',
            unsafe_allow_html=True)
link("views/research.py", "Voir chaque stratégie en détail" if fr else "See each strategy in detail",
     ":material/query_stats:")

st.markdown(f"#### {'Ce que l’expérience a montré' if fr else 'What the experiment showed'}")
for f_ in R["findings"][lang()]:
    st.markdown(f"- {f_}")

c1, c2, c3 = st.columns(3)
with c1:
    link("views/profiles.py", t("profiles"), ":material/tune:")
    st.caption("Choisis ta part d'actions, vois rendement et baisses." if fr else
               "Choose your share of stocks, see returns and drops.")
with c2:
    link("views/portfolio.py", t("portfolio"), ":material/work:")
    st.caption("Tes ETF, tes poids, le même moteur." if fr else "Your ETFs, your weights, the same engine.")
with c3:
    link("views/method.py", t("method"), ":material/verified_user:")
    st.caption("Comment les tests évitent de se mentir." if fr else "How the tests avoid fooling themselves.")
footer()
