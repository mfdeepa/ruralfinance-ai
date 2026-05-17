import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from urllib.parse import quote_plus

from utils.styles import inject_css, inject_nav_drawer
from utils.india_config import (
    INDIA_COUNTRY_BADGE,
    SUPPORTED_APP_LANGUAGES,
    normalize_app_language,
)

st.set_page_config(
    page_title="Sign In — RuralFinance AI",
    page_icon="🔐",
    layout="centered",
    initial_sidebar_state="collapsed",
)

inject_css()
inject_nav_drawer("Login")

st.markdown(
    """
    <style>
    header[data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"] { display:none !important; }
    header[data-testid="stHeader"] { height:0 !important; min-height:0 !important; }

    .stApp { background:#f0f5f1 !important; padding-top:0 !important; }
    .stApp > section,
    section[data-testid="stMain"],
    section[data-testid="stMain"] > div:first-child {
        padding-top:0 !important; margin-top:0 !important;
    }
    .main .block-container, [data-testid="stMainBlockContainer"] {
        max-width:460px !important;
        padding:40px 20px 20px !important;
        margin:0 auto !important;
    }

    /* Card wrapper */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background:#ffffff !important;
        border-radius:16px !important;
        border:1.5px solid #d8e2dc !important;
        box-shadow:0 12px 36px rgba(6,77,47,.11) !important;
        padding:0 !important;
    }

    /* Input sizing */
    .stTextInput input, [data-baseweb="select"] > div {
        min-height:44px !important;
        font-size:.95rem !important;
        border-radius:10px !important;
    }
    .stButton > button {
        min-height:46px !important;
        font-size:1rem !important;
        border-radius:10px !important;
    }
    div[data-testid="stMarkdownContainer"] p { margin-bottom:.2rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Logo + title ──────────────────────────────────────────────────────────────
import base64 as _b64

def _load_b64(rel_path, mime="image/png"):
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel_path)
    if os.path.exists(p):
        try:
            with open(p, "rb") as f:
                return f"data:{mime};base64," + _b64.b64encode(f.read()).decode()
        except Exception:
            pass
    return ""

_logo = _load_b64("static/ruralfinace-logo.png")
_logo_tag = f'<img src="{_logo}" style="width:72px;display:block;margin:0 auto 6px;">' if _logo else ""

st.markdown(
    f"""
    <div style="text-align:center;padding:0 0 8px;">
      {_logo_tag}
      <div style="font-size:1.5rem;font-weight:900;color:#064d2f;line-height:1.1;">RuralFinance AI</div>
      <div style="font-size:.84rem;color:#6b7280;margin-top:3px;">Understand before you sign</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Login card ────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown(
        """
        <div style="text-align:center;padding:4px 0 10px;">
          <div style="font-size:1.15rem;font-weight:800;color:#064d2f;">Welcome back 👋</div>
          <div style="font-size:.8rem;color:#6b7280;margin-top:2px;">Enter your name and language to continue</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Pre-fill if already in session
    _current_name = st.session_state.get("user_name", "")
    _current_lang = normalize_app_language(st.session_state.get("user_language", "English"))

    st.markdown("**Your name**")
    name_input = st.text_input(
        "Your name",
        value=_current_name,
        placeholder="Enter your name",
        label_visibility="collapsed",
        key="_login_name",
    )

    st.markdown("**Language**")
    lang_input = st.selectbox(
        "Language",
        SUPPORTED_APP_LANGUAGES,
        index=SUPPORTED_APP_LANGUAGES.index(_current_lang) if _current_lang in SUPPORTED_APP_LANGUAGES else 0,
        label_visibility="collapsed",
        key="_login_lang",
    )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    if st.button("Sign In →", type="primary", use_container_width=True):
        st.session_state["user_name"]       = name_input.strip() or "Guest"
        st.session_state["user_language"]   = lang_input
        st.session_state["user_country"]    = INDIA_COUNTRY_BADGE
        st.session_state["onboarding_done"] = True
        st.query_params["li"] = "1"
        st.query_params["l"]  = lang_input
        st.query_params["c"]  = INDIA_COUNTRY_BADGE
        if name_input.strip():
            st.query_params["n"] = name_input.strip()
        st.switch_page("Home.py")

# ── Back link ─────────────────────────────────────────────────────────────────
_lp = f"?li=1&l={quote_plus(_current_lang)}&c={quote_plus(INDIA_COUNTRY_BADGE)}"
if _current_name:
    _lp += f"&n={quote_plus(_current_name)}"

st.markdown(
    f"""
    <div style="text-align:center;margin-top:14px;">
      <a href="/{_lp}" target="_self"
         style="font-size:.83rem;color:#087a43;font-weight:600;text-decoration:none;">
        ← Back to Home
      </a>
    </div>
    """,
    unsafe_allow_html=True,
)
