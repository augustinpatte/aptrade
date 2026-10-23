import streamlit as st

from common import REPO_URL, footer, lang, research, style, t

style()
fr = lang() == "fr"
R = research()
st.markdown(f"# {t('method')}")
st.markdown(
    "Un backtest peut facilement se mentir à lui-même : on règle les paramètres sur les mêmes données qui servent "
    "à juger. APtrade est construit pour l'éviter. Voici chaque garde-fou."
    if fr else
    "A backtest can easily fool itself: parameters get tuned on the same data used to judge them. APtrade is built "
    "to avoid that. Here is every safeguard.")
for title, text in R["guardrails"][lang()]:
    st.markdown(f'<div class="card"><h4>{title}</h4>{text}</div>', unsafe_allow_html=True)
st.markdown(f"[PREREGISTRATION.md]({REPO_URL}/blob/main/PREREGISTRATION.md) · "
            f"[{'Code source' if fr else 'Source code'}]({REPO_URL})")
st.markdown(f"#### {'Ce que les chiffres ne disent pas' if fr else 'What the numbers do not say'}")
for line in ([
    "Dix ans, c'est une seule histoire de marché ; l'avenir peut être différent.",
    "Les simulations utilisent des fractions d'actions et un coût fixe ; un vrai compte a des actions entières, des "
    "spreads plus larges en crise, et des impôts.",
    "Rien ici n'est un conseil financier. Aucun ordre n'est jamais passé par l'application.",
] if fr else [
    "Ten years is a single market history; the future can be different.",
    "Simulations use fractional shares and a fixed cost; a real account has whole shares, wider spreads in a crisis, "
    "and taxes.",
    "Nothing here is financial advice. The app never places an order.",
]):
    st.markdown(f"- {line}")
footer()
