import streamlit as st

from utils.india_config import (
    INDIA_COUNTRY_BADGE,
    SUPPORTED_APP_LANGUAGES,
    normalize_app_language,
)
from utils.translations import get_ui


def render_language_back_topbar(key_prefix: str, back_key: str):
    """Render the shared page language selector and Home/Back control."""
    lang_key = f"{key_prefix}_page_language"
    current_language = normalize_app_language(
        st.session_state.get("user_language", "English")
    )
    if current_language not in SUPPORTED_APP_LANGUAGES:
        current_language = "English"

    st.markdown(
        f"""
<style>
[data-testid="stMainBlockContainer"] {{
    padding-top: .4rem !important;
}}
.st-key-{lang_key} [data-baseweb="select"] > div {{
    min-height: 38px !important;
    border: 1px solid #087647 !important;
    border-radius: 12px !important;
    background: #ffffff !important;
}}
.st-key-{back_key} button {{
    min-height: 38px !important;
    border-radius: 12px !important;
    white-space: nowrap !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )

    def _language_changed():
        selected = normalize_app_language(
            st.session_state.get(lang_key, current_language)
        )
        st.session_state["user_language"] = selected
        st.session_state["user_country"] = INDIA_COUNTRY_BADGE
        st.session_state["onboarding_done"] = True
        st.query_params["li"] = "1"
        st.query_params["l"] = selected
        st.query_params["c"] = INDIA_COUNTRY_BADGE
        if st.session_state.get("user_name"):
            st.query_params["n"] = st.session_state["user_name"]

    options = list(SUPPORTED_APP_LANGUAGES)
    index = options.index(current_language) if current_language in options else 0
    _, col_lang, col_back = st.columns([6.4, 1.5, 0.9])
    with col_lang:
        st.selectbox(
            "🌐 Language",
            options,
            index=index,
            key=lang_key,
            label_visibility="collapsed",
            on_change=_language_changed,
        )
    with col_back:
        t = get_ui(st.session_state.get("user_language", "English"))
        if st.button(t.get("back_btn", "🏠 Back"), key=back_key, use_container_width=True):
            st.session_state["onboarding_done"] = True
            st.switch_page("Home.py")

    return get_ui(st.session_state.get("user_language", "English"))
