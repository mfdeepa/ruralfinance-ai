import os
import sys
from html import escape
from urllib.parse import quote_plus

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from dotenv import load_dotenv

from utils.styles import inject_css, inject_nav_drawer
from utils.translations import get_ui
from utils.india_config import (
    INDIA_COUNTRY_BADGE,
    SUPPORTED_APP_LANGUAGES,
    SUPPORTED_LANGUAGE_COPY,
    normalize_app_language,
)

load_dotenv()

st.set_page_config(
    page_title="RuralFinance AI",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()

ALL_LANGUAGES = SUPPORTED_APP_LANGUAGES


def restore_session_from_url():
    qp = st.query_params
    if "onboarding_done" not in st.session_state and qp.get("li") == "1":
        st.session_state["onboarding_done"] = True
        st.session_state["user_name"] = qp.get("n", "")
        st.session_state["user_language"] = normalize_app_language(qp.get("l", "English"))
        st.session_state["user_country"] = INDIA_COUNTRY_BADGE


def render_onboarding():
    st.markdown("""
        <style>
        [data-testid="stSidebar"] { display:block !important; }
        [data-testid="stAppViewContainer"],
        [data-testid="stApp"] {
            background: linear-gradient(180deg, #f8fbf8 0%, #eef7ef 100%) !important;
            min-height: 100vh;
        }
        .main .block-container,
        [data-testid="stMainBlockContainer"],
        [data-testid="block-container"] {
            max-width: 620px !important;
            padding-top: 0rem !important;
            padding-bottom: .7rem !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }
        header[data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {
            display:none !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background:#ffffff !important;
            max-width: 480px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            border-radius:14px !important;
            border:1px solid #d8e2dc !important;
            box-shadow:0 12px 34px rgba(0,0,0,.09) !important;
            padding: 0 !important;
        }
        div[data-testid="stTextInput"],
        div[data-testid="stSelectbox"] {
            margin-bottom: .1rem !important;
        }
        .stCaptionContainer {
            margin-top: -1.5rem !important;
            margin-bottom: .45rem !important;
        }
        .stButton > button {
            min-height: 42px !important;
            font-size: .95rem !important;
        }
        .stTextInput input,
        [data-baseweb="select"] > div {
            min-height: 40px !important;
            font-size: .95rem !important;
        }
        div[data-testid="stMarkdownContainer"] p {
            margin-bottom: .25rem !important;
        }
        .main .block-container {
            padding-top: 0rem !important;
            margin-top: -4rem !important;
        }
        header[data-testid="stHeader"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div style='text-align:center; padding:0; margin-top:-20px;'>
          <div style='font-size:1.6rem;font-weight:800;color:#064d2f;line-height:1.1;'>RuralFinance AI</div>
          <div style='font-size:.86rem;color:#1f2937;margin-top:2px;'>Check loan documents before you sign</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True, width=480):
        st.markdown(
            """
            <div style='text-align:center;padding:2px 0 4px;'>
              <div style='font-size:1.12rem;font-weight:800;color:#064d2f;'>Welcome!</div>
              <div style='font-size:.8rem;color:#6b7280;margin-top:1px;'>
                Set up in 2 simple steps.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("**1. Your name**")
        name_val = st.text_input(
            "Your name",
            placeholder="Type your name",
            label_visibility="collapsed",
            key="_setup_name",
        )
        st.caption("No password needed.")

        st.markdown("**2. Choose language**")
        chosen_language = st.selectbox(
            "Choose language",
            ALL_LANGUAGES,
            index=0,
            label_visibility="collapsed",
            help=f"Choose the language used for explanations and reports, {SUPPORTED_LANGUAGE_COPY}.",
        )
        st.caption(SUPPORTED_LANGUAGE_COPY + ".")

        st.markdown("**Deployment country**")
        st.markdown(
            """
            <div style='border:1px solid #d8e2dc;border-radius:8px;padding:10px 14px;
                        background:#f8fbf8;font-size:.95rem;font-weight:600;color:#064d2f;
                        margin-bottom:4px;'>
              India only
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Built for Indian borrowers, banks, NBFCs, MFIs, and cooperative banks.")

        if st.button("Start →", type="primary", use_container_width=True):
            st.session_state["user_name"] = name_val.strip()
            st.session_state["user_language"] = chosen_language
            st.session_state["user_country"] = INDIA_COUNTRY_BADGE
            st.session_state["onboarding_done"] = True
            st.query_params["li"] = "1"
            st.query_params["l"] = chosen_language
            st.query_params["c"] = INDIA_COUNTRY_BADGE
            if name_val.strip():
                st.query_params["n"] = name_val.strip()
            st.rerun()


def render_home():
    user_name = st.session_state.get("user_name", "").strip() or "Guest"
    safe_name = escape(user_name)
    user_lang = normalize_app_language(st.session_state.get("user_language", "English"))
    _t = get_ui(user_lang)
    _lang = user_lang
    st.session_state["user_language"] = user_lang
    st.session_state["user_country"] = INDIA_COUNTRY_BADGE

    def _hm_t(key: str, en_text: str) -> str:
        if _lang == "English":
            return en_text
        dict_val = _t.get(key, en_text)
        if dict_val != en_text:
            return dict_val
        return en_text

    def _home_copy(key: str, en_text: str, fallback_key: str | None = None) -> str:
        val = _hm_t(key, en_text)
        if _lang != "English" and val == en_text:
            if fallback_key:
                fallback = _hm_t(fallback_key, "")
                if fallback:
                    return fallback
            return ""
        return val

    import base64 as _b64
    def _load_b64(rel_path: str, mime: str = "image/png") -> str:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    return f"data:{mime};base64," + _b64.b64encode(f.read()).decode()
            except Exception:
                pass
        return ""

    _logo_src   = _load_b64("static/ruralfinace-logo.png")
    _farmer_src = _load_b64("static/farmer_family.svg", "image/svg+xml")

    inject_nav_drawer("Home")

    def _apply_lang():
        st.session_state["user_language"] = st.session_state["_home_lang_select"]
        st.query_params["li"] = "1"
        st.query_params["l"] = st.session_state["_home_lang_select"]
        st.query_params["c"] = INDIA_COUNTRY_BADGE
        if user_name and user_name != "Guest":
            st.query_params["n"] = user_name

    login_params = f"?li=1&l={quote_plus(user_lang)}&c={quote_plus(INDIA_COUNTRY_BADGE)}"
    if user_name and user_name != "Guest":
        login_params += f"&n={quote_plus(user_name)}"

    _icon_map = {
        "scan":   "📄",
        "search": "🔍",
        "calc":   "🧮",
        "book":   "📖",
        "sos":    "🆘",
    }

    def feature_card(title, desc, button, href, icon_class, color):
        icon_emoji = _icon_map.get(icon_class, "📋")
        return f"""
        <article class="rf-feature-card {color}">
          <div class="rf-feature-icon">{icon_emoji}</div>
          <h3>{title}</h3>
          <p>{desc}</p>
          <a href="{href}{login_params}" target="_self">{button}</a>
        </article>
        """

    feature_cards = [
        (_home_copy("card1_title", "Scan Loan Document", "scan_document"),      _home_copy("card1_desc", "Upload loan papers, PDFs, or photos to detect hidden charges, risky clauses, and incomplete documents."), _home_copy("card1_btn", "Scan Now",    "scan_document"),      "/Document_Scanner",   "scan",   "green"),
        (_home_copy("card2_title", "Understand Document", "understand_doc"),    _home_copy("card2_desc", "Get simple AI-powered explanations of loan terms, penalties, repayment risks, and important financial conditions."), _home_copy("card2_btn", "Understand",  "understand_doc"),    "/Understand_Document","search",  "blue"),
        (_home_copy("card3_title", "Calculate EMI", "emi_calculator"),          _home_copy("card3_desc", "Calculate EMI, total repayment, interest burden, and compare loan affordability before borrowing."),                _home_copy("card3_btn", "Calculate",   "emi_calculator"),     "/Calculator",         "calc",   "purple"),
        (_home_copy("card4_title", "Understand Banking Words", "understand_banking"), _home_copy("card4_desc", "Learn difficult banking and financial terms in simple language with easy examples."),                          _home_copy("card4_btn", "Open Guide",  "understand_banking"), "/Banking_Knowledge",  "book",   "orange"),
        (_home_copy("card5_title", "Emergency Help", "emergency_help"),         _home_copy("card5_desc", "Get borrower guidance for loan harassment, repayment stress, recovery pressure, or financial emergencies."),         _home_copy("card5_btn", "Get Help",    "emergency_help"),     "/Emergency_Help",     "sos",    "red"),
    ]

    hero_subtitle = _home_copy("hero_h2", "AI Financial Safety Assistant for Indian Borrowers", "tagline")
    hero_body = _home_copy(
        "hero_p",
        "Understand loan documents, hidden charges, risky clauses and repayment conditions in simple language before signing.",
        "before_signing",
    )

    _initials = (safe_name[0].upper() if safe_name and safe_name != "Guest" else "G")

    st.markdown(
        f"""
        <style>
        /* ── lock page to one screen — no scroll on home ── */
        html, body {{ overflow:hidden !important; height:100dvh !important; }}

        /* ── hide streamlit chrome + kill reserved header space ── */
        header[data-testid="stHeader"], [data-testid="stToolbar"],
        [data-testid="stDecoration"], a[data-testid="stMarkdownAnchor"],
        [data-testid="stHeadingWithActionElements"] a {{ display:none !important; }}
        header[data-testid="stHeader"] {{ height:0 !important; min-height:0 !important;
            padding:0 !important; overflow:hidden !important; }}

        /* ── zero ALL top padding Streamlit adds for the header ── */
        .stApp {{ background:#f0f5f1 !important; padding-top:0 !important; margin-top:0 !important; }}
        .stApp > section, .stApp > .stMain,
        section[data-testid="stMain"],
        section[data-testid="stMain"] > div:first-child {{
            padding-top:0 !important; margin-top:0 !important;
        }}

        /* ── main container ── */
        .main .block-container, [data-testid="stMainBlockContainer"] {{
            max-width:none !important;
            padding:4px 14px 4px 66px !important;
            margin-top:0 !important; box-sizing:border-box !important;
            height:100dvh !important; overflow:hidden !important;
        }}

        /* ── kill ALL inter-element gaps Streamlit injects ── */
        div[data-testid="stVerticalBlock"] {{ gap:0 !important; row-gap:0 !important; }}
        div[data-testid="stVerticalBlock"] > div {{ gap:0 !important; margin-bottom:0 !important; }}
        div[data-testid="element-container"] {{ margin:0 !important; padding-bottom:0 !important; }}
        [data-testid="stHorizontalBlock"] {{ gap:6px !important; align-items:center !important; }}
        [data-testid="column"] > div {{ padding:0 !important; }}

        /* ── selectbox compact ── */
        div[data-testid="stSelectbox"] label {{ display:none !important; }}
        div[data-testid="stSelectbox"] [data-baseweb="select"] > div {{
            min-height:32px !important; border-radius:8px !important;
            border:1.5px solid #c7ddd0 !important; background:#fff !important;
            font-size:.80rem !important; font-weight:600 !important;
        }}

        /* ═══════ TOP BAR ═══════ */
        .rf-top-left {{ display:flex; align-items:center; gap:8px; }}
        .rf-top-avatar {{
            width:28px; height:28px; border-radius:50%;
            background:linear-gradient(135deg,#087a43,#a3d9a5);
            display:inline-flex; align-items:center; justify-content:center;
            color:#fff; font-weight:900; font-size:.80rem; flex-shrink:0;
            box-shadow:0 2px 6px rgba(8,122,67,.3);
        }}
        .rf-top-name {{
            color:#064d2f; font-weight:700; font-size:.90rem;
            display:flex; flex-direction:column; line-height:1.1;
        }}
        .rf-top-name span {{ font-size:.74rem; color:#6b7280; font-weight:500; }}
        .rf-top-right {{ display:flex; align-items:center; gap:6px; justify-content:flex-end; }}
        .rf-btn-signin {{
            padding:5px 14px; border-radius:8px; font-weight:700; font-size:.82rem;
            color:#064d2f !important; text-decoration:none !important;
            border:1.5px solid #087a43; background:#fff;
            display:inline-flex; align-items:center; gap:4px;
            box-shadow:0 1px 3px rgba(6,77,47,.08); white-space:nowrap;
        }}
        .rf-btn-signup {{
            padding:5px 14px; border-radius:8px; font-weight:700; font-size:.82rem;
            color:#fff !important; text-decoration:none !important;
            background:linear-gradient(135deg,#087a43,#055c33);
            display:inline-flex; align-items:center; gap:4px;
            box-shadow:0 2px 8px rgba(8,122,67,.25); white-space:nowrap;
        }}
        .rf-user-chip {{
            padding:5px 12px; border-radius:8px; font-weight:700; font-size:.82rem;
            color:#064d2f; border:1.5px solid #c7ddd0; background:#fff;
            display:inline-flex; align-items:center; gap:5px;
            box-shadow:0 1px 3px rgba(0,0,0,.05); white-space:nowrap;
        }}

        /* ═══════ PAGE BODY — fills remaining viewport after top bar ═══════ */
        .rf-page-body {{
            display:flex; flex-direction:column; gap:5px;
            height:calc(100dvh - 48px);
            overflow:hidden;
        }}

        /* ═══════ HERO — takes ~40% of page body ═══════ */
        .rf-hero {{
            flex:2 1 0; min-height:0;
            border-radius:14px; overflow:hidden;
            display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr);
            gap:0; border:1.5px solid rgba(6,77,47,.10);
            background:linear-gradient(110deg,#ffffff 0%,#f4fbf5 45%,#dff0e3 100%);
            box-shadow:0 4px 18px rgba(6,77,47,.12);
            align-items:stretch;
        }}
        .rf-hero-text {{
            padding:16px 20px 16px 24px;
            display:flex; flex-direction:column; justify-content:center;
            box-sizing:border-box; overflow:hidden;
        }}
        .rf-hero h1 {{ margin:0 0 6px; line-height:1.05; font-weight:900; }}
        .rf-hero h1 .green  {{ color:#064d2f !important; font-size:2.3rem; display:block; }}
        .rf-hero h1 .orange {{ color:#f97316 !important; font-size:2.3rem; display:block; }}
        .rf-hero h2 {{ margin:0 0 6px; color:#1f2937; font-size:1.0rem; font-weight:700; }}
        .rf-hero p  {{ margin:0; color:#4b5563; font-size:.92rem; line-height:1.5; }}
        .rf-pills   {{ display:flex; flex-wrap:wrap; gap:5px; margin-top:10px; }}
        .rf-pill {{
            display:inline-flex; align-items:center; gap:3px;
            padding:4px 12px; border-radius:20px;
            background:#fff; border:1.5px solid #b6d9c3;
            color:#064d2f; font-weight:700; font-size:.78rem;
            box-shadow:0 1px 3px rgba(6,77,47,.08);
        }}
        .rf-hero-art {{
            position:relative; overflow:hidden;
            background:linear-gradient(160deg,#4caf50 0%,#2e7d32 60%,#1b5e20 100%);
            min-height:0;
        }}
        .rf-farmer-img {{
            position:absolute; inset:0; width:100%; height:100%;
            object-fit:cover; object-position:center center; display:block;
        }}
        .rf-logo-overlay {{
            position:absolute; top:8px; right:8px; z-index:3;
            background:#fff; border-radius:8px;
            padding:5px 9px; box-shadow:0 3px 12px rgba(6,77,47,.28);
            text-align:center; min-width:72px;
        }}
        .rf-logo-small {{ width:58px; max-width:88%; display:block; margin:0 auto; }}
        .rf-logo-tag {{
            font-size:.50rem; font-weight:900; color:#0b6b3e;
            letter-spacing:.05em; text-transform:uppercase; margin-top:2px;
        }}
        .rf-logo-sub {{ font-size:.44rem; color:#6b7280; margin-top:1px; font-style:italic; }}

        /* ═══════ SECTION TITLE ═══════ */
        .rf-section-title {{
            flex-shrink:0;
            color:#064d2f; font-size:1.05rem; font-weight:900;
            margin:0; text-align:center; padding:2px 0;
        }}

        /* ═══════ FEATURE GRID — takes ~35% of page body ═══════ */
        .rf-feature-grid {{
            flex:1.5 1 0; min-height:0;
            display:grid; grid-template-columns:repeat(5,1fr);
            gap:7px;
        }}
        .rf-feature-card {{
            padding:10px 10px 9px; border-radius:12px;
            background:#ffffff; border:1.5px solid rgba(6,77,47,.08);
            box-shadow:0 2px 8px rgba(6,77,47,.07);
            display:flex; flex-direction:column; align-items:center;
            text-align:center; transition:transform .15s,box-shadow .15s;
            overflow:hidden; min-height:0;
        }}
        .rf-feature-card:hover {{
            transform:translateY(-2px); box-shadow:0 4px 14px rgba(6,77,47,.12);
        }}
        .rf-feature-icon {{
            width:44px; height:44px; border-radius:50%; margin-bottom:7px;
            display:flex; align-items:center; justify-content:center;
            font-size:1.35rem; flex-shrink:0;
        }}
        .rf-feature-card h3 {{
            margin:0 0 5px; font-size:.92rem; font-weight:800; line-height:1.2;
        }}
        .rf-feature-card p {{
            margin:0 0 8px; font-size:.78rem; color:#4b5563;
            line-height:1.38; flex:1; overflow:hidden;
        }}
        .rf-feature-card a {{
            width:100%; padding:7px 4px; border-radius:7px; color:#fff !important;
            text-decoration:none !important; font-weight:800; font-size:.82rem;
            display:block; box-shadow:0 2px 5px rgba(0,0,0,.15); flex-shrink:0;
        }}
        .rf-feature-card a:hover {{ filter:brightness(1.08); }}
        .rf-feature-card.green  h3 {{ color:#087a43; }}
        .rf-feature-card.blue   h3 {{ color:#1f67d2; }}
        .rf-feature-card.purple h3 {{ color:#7c3aed; }}
        .rf-feature-card.orange h3 {{ color:#d97706; }}
        .rf-feature-card.red    h3 {{ color:#dc2626; }}
        .rf-feature-card.green  a  {{ background:linear-gradient(135deg,#087a43,#055c33); }}
        .rf-feature-card.blue   a  {{ background:linear-gradient(135deg,#1f67d2,#1549a3); }}
        .rf-feature-card.purple a  {{ background:linear-gradient(135deg,#7c3aed,#5b21b6); }}
        .rf-feature-card.orange a  {{ background:linear-gradient(135deg,#f97316,#d97706); }}
        .rf-feature-card.red    a  {{ background:linear-gradient(135deg,#dc2626,#b91c1c); }}
        .rf-feature-card.green  .rf-feature-icon {{ background:#dcf5e4; }}
        .rf-feature-card.blue   .rf-feature-icon {{ background:#dbeafe; }}
        .rf-feature-card.purple .rf-feature-icon {{ background:#ede9fe; }}
        .rf-feature-card.orange .rf-feature-icon {{ background:#ffedd5; }}
        .rf-feature-card.red    .rf-feature-icon {{ background:#fee2e2; }}

        /* ═══════ SAFETY BAR ═══════ */
        .rf-safety-bar {{
            flex-shrink:0;
            display:flex; align-items:center; gap:7px; flex-wrap:nowrap;
            padding:7px 16px; border-radius:10px;
            background:linear-gradient(135deg,#064d2f,#0a7a45);
            color:#fff; box-shadow:0 2px 10px rgba(6,77,47,.20);
        }}
        .rf-safety-title {{
            color:#fff; font-weight:900; font-size:.92rem; white-space:nowrap;
        }}
        .rf-safety-item {{
            display:inline-flex; align-items:center; gap:3px;
            background:rgba(255,255,255,.15); border-radius:20px;
            padding:3px 10px; font-size:.80rem; font-weight:600; white-space:nowrap;
        }}
        .rf-check {{ color:#86efac; font-weight:900; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── TOP BAR ───────────────────────────────────────────────────────────────
    _c_user, _c_auth, _c_lang = st.columns([2.8, 2.2, 1.5], vertical_alignment="center")
    with _c_user:
        st.markdown(
            f'<div class="rf-top-left">'
            f'<div class="rf-top-avatar">{_initials}</div>'
            f'<div class="rf-top-name">'
            f'<b>{escape(_hm_t("greeting","Namaste"))}, {safe_name}</b>'
            f'<span>Dashboard &amp; overview</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    with _c_auth:
        st.markdown(
            '<div class="rf-top-right">'
            f'<a class="rf-btn-signin" href="/Login{login_params}" target="_self">👤 Sign In</a>'
            f'<a class="rf-btn-signup" href="/Login{login_params}" target="_self">👤+ Sign Up</a>'
            f'<div class="rf-user-chip">👤 {safe_name} ▾</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with _c_lang:
        st.selectbox(
            "Language",
            ALL_LANGUAGES,
            index=ALL_LANGUAGES.index(user_lang) if user_lang in ALL_LANGUAGES else 0,
            key="_home_lang_select",
            label_visibility="collapsed",
            on_change=_apply_lang,
        )

    # ── HERO + CARDS + SAFETY BAR ─────────────────────────────────────────────
    st.markdown(
        f"""
        <div class="rf-page-body">

          <section class="rf-hero">
            <div class="rf-hero-text">
              <h1>
                <span class="green">{escape(_hm_t("hero_title_1","Understanding"))}</span>
                <span class="orange">{escape(_hm_t("hero_title_2","Before You Sign"))}</span>
              </h1>
              <h2>{escape(hero_subtitle)}</h2>
              <p>{escape(hero_body)}</p>
              <div class="rf-pills">
                <span class="rf-pill">🛡️ {escape(_home_copy("pill_private","100% Private"))}</span>
                <span class="rf-pill">📶 {escape(_home_copy("pill_offline","Works Offline"))}</span>
                <span class="rf-pill">🤖 {escape(_home_copy("pill_ai","AI Powered"))}</span>
                <span class="rf-pill">🌐 {escape(_home_copy("pill_langs","22+ Languages"))}</span>
              </div>
            </div>
            <div class="rf-hero-art">
              <img src="{_farmer_src}" class="rf-farmer-img" alt="Rural family">
              <div class="rf-logo-overlay">
                <img src="{_logo_src}" alt="RuralFinance AI" class="rf-logo-small">
                <div class="rf-logo-tag">RuralFinance</div>
                <div class="rf-logo-sub">Understanding Before You Sign</div>
              </div>
            </div>
          </section>

          <div class="rf-section-title">🌿 {escape(_home_copy("what_today","How can we help you today?"))} 🌿</div>

          <section class="rf-feature-grid">{''.join(feature_card(*c) for c in feature_cards)}</section>

          <div class="rf-safety-bar">
            <span class="rf-safety-title">🛡️ {escape(_home_copy("safety_title","Before signing, always check:"))}</span>
            <span class="rf-safety-item"><b class="rf-check">✔</b> {escape(_home_copy("safety_c1","Total Repayment"))}</span>
            <span class="rf-safety-item"><b class="rf-check">✔</b> {escape(_home_copy("safety_c2","All Fees"))}</span>
            <span class="rf-safety-item"><b class="rf-check">✔</b> {escape(_home_copy("safety_c3","Penalty"))}</span>
            <span class="rf-safety-item"><b class="rf-check">✔</b> {escape(_home_copy("safety_c4","Insurance"))}</span>
            <span class="rf-safety-item"><b class="rf-check">✔</b> {escape(_home_copy("safety_c5","Copy of Agreement"))}</span>
          </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


restore_session_from_url()

if "onboarding_done" not in st.session_state:
    render_onboarding()
    st.stop()

render_home()
