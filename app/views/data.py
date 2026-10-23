import os

import streamlit as st

from common import ROOT, footer, has_keys, is_public_demo, lang, results, results_file, style, t

style()

fr = lang() == "fr"
st.markdown(f"# {t('data')}")
res = results()
if res:
    m = res["meta"]
    st.markdown((f"Résultats : données du **{m['data_start']}** au **{m['data_end']}**, générés le "
                 f"{m['generated'][:10]}, holdout à partir du {m['holdout_start']}.") if fr else
                (f"Results: data from **{m['data_start']}** to **{m['data_end']}**, generated "
                 f"{m['generated'][:10]}, holdout from {m['holdout_start']}."))
else:
    st.warning(t("no_results"))

if is_public_demo():
    st.info("Démo publique : lecture seule. Pour tes propres tests, installe l'app en local (voir le README)."
            if fr else "Public demo: read-only. For your own tests, run the app locally (see the README).")
    footer()
    st.stop()

st.markdown("### " + ("Clé Alpaca" if fr else "Alpaca key"))
if has_keys():
    k = os.environ["ALPACA_API_KEY"]
    st.success((f"Clé trouvée : {k[:4]}… (dans .env)" if fr else f"Key found: {k[:4]}… (in .env)"))
else:
    st.markdown("Crée un compte gratuit sur alpaca.markets, génère des clés **paper trading**, et colle-les ici. "
                "Elles sont écrites dans le fichier `.env` de ta machine, jamais ailleurs." if fr else
                "Create a free account on alpaca.markets, generate **paper trading** keys and paste them here. They "
                "are written to the `.env` file on your machine, nowhere else.")
    with st.form("keys"):
        key = st.text_input("ALPACA_API_KEY")
        sec = st.text_input("ALPACA_SECRET_KEY", type="password")
        if st.form_submit_button("Enregistrer" if fr else "Save") and key and sec:
            from aptrade.config import set_env_values
            set_env_values(ROOT / ".env", {"ALPACA_API_KEY": key.strip(), "ALPACA_SECRET_KEY": sec.strip()})
            os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"] = key.strip(), sec.strip()
            st.rerun()

st.markdown("### " + ("Mettre à jour les résultats" if fr else "Update the results"))
st.markdown("Télécharge les données journalières des 26 ETF et recalcule tout ce que montre l'app (1 à 3 minutes)."
            if fr else "Downloads daily data for the 26 ETFs and recomputes everything the app shows (1 to 3 minutes).")
if not has_keys():
    st.caption("Sans clé Alpaca, les prix viennent de Yahoo (gratuit, non officiel) ou de Tiingo si TIINGO_API_KEY "
               "est dans .env." if fr else "Without an Alpaca key, prices come from Yahoo (free, unofficial) or from "
               "Tiingo if TIINGO_API_KEY is in .env.")
if st.button("Mettre à jour" if fr else "Update", type="primary"):
    import argparse

    from aptrade.config import Settings
    from aptrade.export import cmd_export
    with st.spinner("..."):
        try:
            cmd_export(argparse.Namespace(out=str(results_file().parent), start="2016-01-01", end=None,
                                          cost_bps=3.0), Settings.from_env())
            st.cache_data.clear()
            st.success("Résultats à jour." if fr else "Results updated.")
        except SystemExit as exc:
            st.error(str(exc))
footer()
