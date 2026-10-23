"""APtrade app entry point: `streamlit run app/Home.py` (or `aptrade app`)."""
import streamlit as st

from common import style, t

st.set_page_config(page_title="APtrade", page_icon=":material/candlestick_chart:", layout="wide")
style()

with st.sidebar:
    st.markdown("### APtrade")
    choice = st.selectbox("Language / Langue", ["English", "Français"],
                          index=0 if st.session_state.get("lang", "en") == "en" else 1)
    st.session_state["lang"] = "en" if choice == "English" else "fr"

pages = [
    st.Page("views/home.py", title=t("home"), icon=":material/space_dashboard:", default=True),
    st.Page("views/profiles.py", title=t("profiles"), icon=":material/tune:"),
    st.Page("views/research.py", title=t("research"), icon=":material/query_stats:"),
    st.Page("views/portfolio.py", title=t("portfolio"), icon=":material/work:"),
    st.Page("views/method.py", title=t("method"), icon=":material/verified_user:"),
    st.Page("views/data.py", title=t("data"), icon=":material/settings:"),
]
st.navigation(pages).run()
