import os as _os
import base64 as _base64
from html import escape as _html_escape

import streamlit as st
import textwrap
from urllib.parse import quote_plus
from utils.translations import _T, _LANG_CODE
from utils.india_config import (
    INDIA_COUNTRY_BADGE, normalize_app_language, SUPPORTED_APP_LANGUAGES
)

# India-only deployment. Country switching was removed to keep the UX and
# regulatory context focused on Indian borrowers.
COUNTRIES = [INDIA_COUNTRY_BADGE]


def inject_css():
    st.markdown(
        """
        <style>
        /* ─── Google Font ─────────────────────────────────────── */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        /* ─── Mobile-first base ───────────────────────────────── */
        html, body, [class*="css"] {
            font-family: 'Inter', system-ui, sans-serif;
            font-size: 16px;
            -webkit-text-size-adjust: 100%;
        }

        /* Prevent horizontal overflow on small screens */
        html, body { overflow-x: hidden; }

        .stApp {
            background: linear-gradient(135deg, #f0fdf4 0%, #f8fafc 100%);
        }

        /* ─── Main content padding (mobile-first) ─────────────── */
        .main .block-container {
            max-width: 1100px !important;
            padding: 2rem !important;
            margin: 0 auto !important; /* This centers the content */
        }

        /* ─── Columns: stack on mobile, side-by-side on tablet+ ── */
        /* This is the key mobile-first rule for Streamlit columns */
        @media (max-width: 640px) {
            [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
                gap: 0.5rem !important;
            }
            [data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
                min-width: 100% !important;
            }
        }

        /* ─── Sidebar — white design ──────────────────────────── */
        [data-testid="stSidebar"] {
            background: #ffffff !important;
            border-right: 1.5px solid #d8e2dc !important;
            box-shadow: 2px 0 12px rgba(0,0,0,.04) !important;
            min-width: 280px !important;
        }
        [data-testid="stSidebar"] * {
            color: #374151 !important;
        }
        [data-testid="stSidebar"] hr {
            border-color: #f3f4f6 !important;
        }
        /* Sidebar buttons */
        [data-testid="stSidebar"] .stButton > button {
            background: #f0fdf4 !important;
            border: 1px solid #d1fae5 !important;
            color: #065f46 !important;
            border-radius: 8px !important;
            width: 100%;
            text-align: left;
            min-height: 44px !important;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background: #d1fae5 !important;
            border-color: #a7f3d0 !important;
        }
        /* Page link nav items */
        [data-testid="stPageLink-NavLink"] {
            border-radius: 12px !important;
            margin: 3px 8px !important;
            padding: 10px 14px !important;
            color: #111827 !important;
            font-weight: 600 !important;
            font-size: .92rem !important;
            transition: background .15s ease !important;
        }
        [data-testid="stPageLink-NavLink"]:hover {
            background: #f0fdf4 !important;
            color: #1a4731 !important;
        }
        [data-testid="stPageLink-NavLink"][aria-current="page"] {
            background: #eef7ef !important;
            color: #065f46 !important;
            font-weight: 800 !important;
        }

        /* ─── Sidebar selectbox ───────────────────────────────── */
        [data-testid="stSidebar"] .stSelectbox label {
            color: #6b7280 !important;
            font-size: 0.88rem !important;
            font-weight: 600 !important;
        }
        [data-testid="stSidebar"] [data-baseweb="select"] {
            background-color: #f9fafb !important;
            border: 1px solid #e5e7eb !important;
            border-radius: 8px !important;
        }
        [data-testid="stSidebar"] [data-baseweb="select"] > div {
            background-color: transparent !important;
            border: none !important;
        }
        [data-testid="stSidebar"] [data-baseweb="select"] * {
            color: #374151 !important;
            background-color: transparent !important;
        }
        [data-testid="stSidebar"] [data-baseweb="select"] svg {
            fill: #6b7280 !important;
            color: #6b7280 !important;
        }

        /* ─── Metric cards ────────────────────────────────────── */
        [data-testid="stMetric"] {
            background: white;
            border-radius: 12px;
            padding: 14px 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border: 1px solid #e2e8f0;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.82rem !important;
        }
        [data-testid="stMetricValue"] {
            color: #1a4731 !important;
            font-weight: 700 !important;
            font-size: 1.4rem !important;
            word-break: break-word;
        }

        /* ─── Containers / Cards ──────────────────────────────── */
        [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
            border-radius: 14px;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: #d8e2dc !important;
            border-radius: 16px !important;
            box-shadow: 0 8px 24px rgba(0,0,0,.035) !important;
        }

        /* ─── Buttons — touch-friendly by default ─────────────── */
        .stButton > button {
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 1rem !important;
            min-height: 42px !important;
            transition: all 0.2s ease !important;
            border: none !important;
            width: 100%;
        }
        .stButton > button[kind="primary"] {
            background: #006837 !important;
            color: white !important;
        }
        .stButton > button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(45,106,79,0.4) !important;
        }

        /* ─── Input elements — prevent iOS auto-zoom (needs 16px) */
        .stTextInput > div > div > input,
        .stTextArea textarea,
        .stSelectbox select,
        [data-baseweb="input"] input,
        [data-baseweb="textarea"] textarea {
            border-radius: 10px !important;
            border: 1.5px solid #d1fae5 !important;
            font-size: 16px !important;
            min-height: 48px !important;
        }
        .stTextInput > div > div > input:focus,
        .stTextArea textarea:focus {
            border-color: #2D6A4F !important;
            box-shadow: 0 0 0 3px rgba(45,106,79,0.1) !important;
        }

        /* ─── Number inputs ───────────────────────────────────── */
        [data-testid="stNumberInput"] input {
            font-size: 16px !important;
            min-height: 48px !important;
        }

        /* ─── Select boxes ────────────────────────────────────── */
        [data-baseweb="select"] {
            min-height: 48px !important;
        }

        /* ─── Labels ──────────────────────────────────────────── */
        .stTextInput label, .stTextArea label,
        .stSelectbox label, .stNumberInput label,
        .stSlider label, .stRadio label {
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            color: #374151 !important;
        }

        /* ─── Progress bar ────────────────────────────────────── */
        .stProgress > div > div > div {
            background: linear-gradient(90deg, #2D6A4F, #52B788) !important;
        }

        /* ─── Alert / Info boxes ──────────────────────────────── */
        .stAlert, .stInfo, .stWarning, .stError, .stSuccess {
            border-radius: 12px !important;
            font-size: 0.95rem !important;
        }

        /* ─── Tabs ────────────────────────────────────────────── */
        [data-testid="stTabs"] [data-baseweb="tab"] {
            font-size: 0.9rem !important;
            font-weight: 600 !important;
            min-height: 44px !important;
            padding: 8px 12px !important;
        }

        /* ─── Expander ────────────────────────────────────────── */
        [data-testid="stExpander"] summary {
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            min-height: 48px !important;
            display: flex !important;
            align-items: center !important;
        }

        /* ─── Hero text helpers ───────────────────────────────── */
        .hero-badge {
            display: inline-block;
            background: #d1fae5;
            color: #065f46;
            padding: 5px 14px;
            border-radius: 20px;
            font-size: 0.88rem;
            font-weight: 600;
            margin-bottom: 12px;
        }

        /* ─── Status pills ────────────────────────────────────── */
        .pill-online  { background:#dcfce7; color:#15803d; padding:4px 12px; border-radius:20px; font-size:.85rem; font-weight:600; }
        .pill-offline { background:#fef9c3; color:#854d0e; padding:4px 12px; border-radius:20px; font-size:.85rem; font-weight:600; }
        .pill-limited { background:#fee2e2; color:#991b1b; padding:4px 12px; border-radius:20px; font-size:.85rem; font-weight:600; }

        /* ─── Risk colours ────────────────────────────────────── */
        .risk-high   { color:#dc2626; font-weight:700; font-size:1.2rem; }
        .risk-medium { color:#d97706; font-weight:700; font-size:1.2rem; }
        .risk-low    { color:#16a34a; font-weight:700; font-size:1.2rem; }

        /* ─── Chat bubbles ────────────────────────────────────── */
        .chat-ai {
            background: white;
            border-left: 4px solid #52B788;
            border-radius: 0 12px 12px 12px;
            padding: 14px 16px;
            margin: 6px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            line-height: 1.65;
            font-size: 0.95rem;
        }

        /* ─── Divider ─────────────────────────────────────────── */
        hr { border-color: #d1fae5 !important; }

        /* ─── Hide Streamlit chrome ───────────────────────────── */
        #MainMenu { visibility: hidden; }
        footer    { visibility: hidden; }
        header    { visibility: hidden; }
        /* Remove the space reserved for the hidden header */
        header[data-testid="stHeader"] { height: 0 !important; min-height: 0 !important;
            padding: 0 !important; overflow: hidden !important; }
        /* Kill ALL top padding Streamlit reserves for the header bar */
        .stApp { padding-top: 0 !important; margin-top: 0 !important; }
        .stApp > section, section[data-testid="stMain"],
        section[data-testid="stMain"] > div:first-child {
            padding-top: 0 !important; margin-top: 0 !important;
        }
        /* Minimal top clearance — header is hidden on all pages */
        .main .block-container { padding-top: 8px !important; }

        /* ─── Hide native sidebar toggle (we use custom hamburger) */
        [data-testid="collapsedControl"] { display: none !important; }
        [data-testid="stSidebarCollapsedControl"] { display: none !important; }

        /* ─── Dataframe / Table ───────────────────────────────── */
        [data-testid="stDataFrame"] {
            overflow-x: auto !important;
        }

        /* ─── Tablet (641px – 1024px) ─────────────────────────── */
        @media (min-width: 641px) and (max-width: 1024px) {
            .main .block-container {
                padding: 1.25rem 1.25rem 2rem !important;
            }
        }

        /* ─── Desktop (1025px+) ───────────────────────────────── */
        @media (min-width: 1025px) {
            .main .block-container {
                padding: 1.25rem 2rem 1rem !important;
            }
            .stButton > button {
                min-height: 44px !important;
            }
        }

        /* ─── Extra-small phones (< 400px) ───────────────────── */
        @media (max-width: 400px) {
            [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
            .stButton > button { font-size: 0.95rem !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    # PWA — manifest, meta tags, service worker registration
    st.markdown(
        # Viewport and PWA meta
        '<meta name="mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
        '<meta name="apple-mobile-web-app-title" content="RuralFinance AI">'
        '<meta name="theme-color" content="#1a4731">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=5">'
        '<meta name="description" content="Offline-first web app for understanding loan documents before signing">'
        # Apple touch icon
        '<link rel="apple-touch-icon" href="/app/static/icon-192.png">'
        # Service worker for offline caching
        '<script>'
        'if("serviceWorker" in navigator){'
        'navigator.serviceWorker.register("/app/static/sw.js",{scope:"/"}).catch(()=>{});'
        '}'
        '</script>',
        unsafe_allow_html=True,
    )


MODE_ICON = {
    "online":  ("🟢", "Online  · Gemma 4 + Vision + Tools"),
    "offline": ("🟡", "Offline · Gemma via Ollama / Local"),
    "limited": ("🔴", "Limited · Rule-based mode"),
}


NAV_PAGES = [
    ("🏠", "Home",                   "/"),
    ("📤", "Scan Document",          "/Document_Scanner"),
    ("🔍", "Understand Document",    "/Understand_Document"),
    ("🧮", "EMI Calculator",         "/Calculator"),
    ("🆘", "Emergency Help",         "/Emergency_Help"),
    ("📖", "Understand Banking",     "/Banking_Knowledge"),
]

NAV_SECONDARY = [
]


def inject_nav_drawer(active_page: str = ""):
    """Sliding nav drawer — rich panel matching the green sidebar design."""
    user_name = st.session_state.get("user_name", "")
    user_lang = normalize_app_language(st.session_state.get("user_language", "English"))
    st.session_state["user_language"] = user_lang
    st.session_state["user_country"] = INDIA_COUNTRY_BADGE
    user_country = INDIA_COUNTRY_BADGE

    _lp = f"?li=1&l={quote_plus(user_lang)}"
    if user_country:
        _lp += f"&c={quote_plus(user_country)}"
    if user_name:
        _lp += f"&n={quote_plus(user_name)}"

    lang_code = _LANG_CODE.get(user_lang, "en")
    t = {**_T["en"], **_T.get(lang_code, _T["en"])}
    en = _T["en"]

    # ── Base64 logo ──────────────────────────────────────────────────────────
    _logo_path = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
        "static", "ruralfinace-logo.png",
    )
    logo_b64 = ""
    if _os.path.exists(_logo_path):
        try:
            with open(_logo_path, "rb") as _f:
                logo_b64 = _base64.b64encode(_f.read()).decode()
        except Exception:
            pass
    logo_src = f"data:image/png;base64,{logo_b64}" if logo_b64 else ""
    logo_img = (
        f'<img src="{logo_src}" alt="RuralFinance AI" '
        'style="width:100px;max-width:100%;display:block;margin:0 auto 3px;">'
        if logo_src else
        '<div style="font-size:1.2rem;font-weight:900;color:#064d2f;text-align:center;">RuralFinance AI</div>'
    )

    # ── Nav items: (label, sublabel, path, en_label, icon_char, icon_color, icon_bg) ─
    NAV_ITEMS = [
        (t["home"],               "Dashboard & overview", "/",                   en["home"],               "⌂",   "#087a43", "#e8f7ec"),
        (t["scan_document"],      "Scan papers",          "/Document_Scanner",   en["scan_document"],      "▤",   "#087a43", "#eef7ef"),
        (t["understand_doc"],     "AI Report",            "/Understand_Document",en["understand_doc"],     "⌕",   "#1f67d2", "#edf4ff"),
        (t["emi_calculator"],     "Plan payments",        "/Calculator",         en["emi_calculator"],     "▦",   "#7c3edb", "#f2ebff"),
        (t["understand_banking"], "Learn terms",          "/Banking_Knowledge",  en["understand_banking"], "▱",   "#f97316", "#fff3df"),
        (t["emergency_help"],     "Get help",             "/Emergency_Help",     en["emergency_help"],     "SOS", "#ef3434", "#fff0f0"),
    ]

    _ap = active_page.lower()
    links_html = ""
    for label, sub, path, en_label, icon_char, icon_color, icon_bg in NAV_ITEMS:
        _el = en_label.lower()
        is_active = (_ap in _el or _el in _ap) or \
                    (active_page in ("Home", "Dashboard", "") and path == "/")
        active_style = "background:rgba(255,255,255,.92);color:#172033 !important;" if is_active else ""
        icon_fs = ".6rem" if icon_char == "SOS" else "1.05rem"
        links_html += (
            f'<a class="rf-sp-item" href="{path}{_lp}" target="_self" style="{active_style}">'
            f'<span class="rf-sp-icon" style="background:{icon_bg};">'
            f'<span style="color:{icon_color};font-size:{icon_fs};font-weight:900;">{icon_char}</span>'
            f'</span>'
            f'<span class="rf-sp-text">'
            f'<b style="{"color:#064d2f;" if is_active else ""}">{_html_escape(label)}</b>'
            f''
            f'</span></a>\n'
        )

    greeting = _html_escape(t.get("greeting", "Hello"))
    safe_name = _html_escape(user_name) if user_name else ""
    user_chip = (
        f'<div class="rf-sp-user">{greeting}, {safe_name}</div>'
        if user_name else ""
    )

    nav_html = f"""
    <style>
    [data-testid="stSidebar"] {{ display:none !important; }}
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"] {{ display:none !important; }}
    /* ── Floating trigger button ──────────────────────────── */
    .rf-float-logo {{
        position:fixed; left:12px; top:8px; z-index:2147483647;
        width:42px; height:42px; border-radius:12px;
        background:#d4eedb;
        display:flex; align-items:center; justify-content:center;
        cursor:pointer; user-select:none; text-decoration:none !important;
        border:1.5px solid #a8d5b5; box-shadow:0 2px 10px rgba(6,77,47,.15);
    }}
    .rf-float-logo:hover {{
        background:#c2e6cb; box-shadow:0 4px 14px rgba(6,77,47,.22);
    }}
    /* ── Slide root ───────────────────────────────────────── */
    .rf-slide-root {{
        display:none; position:fixed; top:0; left:0; bottom:0; width:290px;
        z-index:2147483646; pointer-events:none; font-family:Inter,system-ui,sans-serif;
    }}
    .rf-slide-root:target {{ display:block; }}
    html:has(.rf-slide-root:target) .rf-float-logo {{ display:none !important; }}
    html:has(.rf-slide-root:target) [data-testid="stMainBlockContainer"],
    html:has(.rf-slide-root:target) .main .block-container {{
        padding-left: calc(290px + 1rem) !important;
        transition: padding-left .22s ease;
    }}
    .rf-slide-overlay {{ display:none; }}
    /* ── Panel ────────────────────────────────────────────── */
    .rf-slide-panel {{
        position:absolute; top:0; left:0; bottom:0; width:290px;
        background:linear-gradient(180deg,#075f3a 0%,#064d2f 52%,#033820 100%);
        border-right:1px solid rgba(6,77,47,.22);
        box-shadow:10px 0 28px rgba(6,77,47,.22);
        overflow-y:auto; pointer-events:auto;
        display:flex; flex-direction:column; gap:0;
        padding:10px 10px 10px;
    }}
    .rf-slide-close {{
        position:absolute; right:8px; top:8px; width:26px; height:26px;
        border-radius:8px; background:rgba(255,255,255,.18); color:#fff;
        display:flex; align-items:center; justify-content:center;
        cursor:pointer; font-weight:900; font-size:1rem; text-decoration:none;
    }}
    .rf-slide-close:hover {{ background:rgba(255,255,255,.30); }}
    /* ── Brand card ───────────────────────────────────────── */
    .rf-sp-brand {{
        text-align:center; padding:4px 4px 5px; border-radius:12px;
        background:rgba(255,255,255,.97); box-shadow:0 3px 10px rgba(0,0,0,.10);
        margin-bottom:5px; flex-shrink:0;
    }}
    .rf-sp-brand img {{ width:72px !important; margin-bottom:1px !important; }}
    .rf-sp-tagline {{
        color:#0b6b3e; font-size:.58rem; font-weight:900;
        letter-spacing:.07em; text-transform:uppercase;
    }}
    /* ── User chip ────────────────────────────────────────── */
    .rf-sp-user {{
        padding:4px 10px; border-radius:8px; margin-bottom:4px;
        background:rgba(255,255,255,.15); color:#fff; font-weight:700; font-size:.76rem;
        border:1px solid rgba(255,255,255,.22); flex-shrink:0;
    }}
    /* ── Nav items — fill remaining height evenly ─────────── */
    .rf-sp-nav {{
        display:flex; flex-direction:column; gap:0; flex:1;
        justify-content:space-evenly;
    }}
    .rf-sp-item {{
        display:flex; align-items:center; gap:8px;
        padding:0 8px; min-height:38px;
        border-radius:10px; color:#fff !important; text-decoration:none !important;
        transition:background .15s ease; flex:1; max-height:56px;
    }}
    .rf-sp-item:hover {{ background:rgba(255,255,255,.18) !important; }}
    .rf-sp-icon {{
        width:28px; height:28px; border-radius:8px; flex:0 0 28px;
        display:grid; place-items:center;
    }}
    .rf-sp-text {{ display:flex; flex-direction:column; }}
    .rf-sp-text b {{ font-size:.76rem; line-height:1.1; color:#fff; }}
    .rf-sp-text small {{ font-size:.60rem; color:rgba(255,255,255,.65); margin-top:0; }}
    .rf-sp-item:hover .rf-sp-text b {{ color:#fff; }}
    /* ── Bottom section ───────────────────────────────────── */
    .rf-sp-bottom {{ padding-top:5px; flex-shrink:0; }}
    .rf-sp-offline {{
        padding:7px 10px; border-radius:10px;
        background:linear-gradient(135deg,#eef9ef,#fffdf7);
        border:1px solid rgba(6,77,47,.14); margin-bottom:5px;
    }}
    .rf-sp-offline b {{ color:#064d2f; font-size:.75rem; display:block; margin-bottom:2px; }}
    .rf-sp-offline p {{ margin:0; color:#253044; font-size:.66rem; line-height:1.35; }}
    .rf-sp-chips {{ display:grid; grid-template-columns:1fr 1fr; gap:4px; }}
    .rf-sp-chip {{
        border:1px solid rgba(255,255,255,.22); border-radius:8px;
        background:rgba(255,255,255,.12);
        padding:4px 6px; color:#e8fff2; font-size:.66rem; font-weight:700;
        text-align:center;
    }}
    @media (max-width: 640px) {{
        .rf-float-logo {{ left:12px; top:12px; width:44px; height:44px; border-radius:14px; }}
        .rf-slide-panel, .rf-slide-root {{ width:min(88vw, 290px); }}
        html:has(.rf-slide-root:target) [data-testid="stMainBlockContainer"],
        html:has(.rf-slide-root:target) .main .block-container {{
            padding-left: 1rem !important;
        }}
    }}
    </style>
    <a href="#rfSlideRoot" class="rf-float-logo" title="Open menu">
      <span style="display:flex;flex-direction:column;gap:4px;align-items:center;justify-content:center;">
        <span style="width:18px;height:3px;border-radius:2px;background:#064d2f;display:block;"></span>
        <span style="width:18px;height:3px;border-radius:2px;background:#064d2f;display:block;"></span>
        <span style="width:18px;height:3px;border-radius:2px;background:#064d2f;display:block;"></span>
      </span>
    </a>
    <div id="rfSlideRoot" class="rf-slide-root">
      <a href="#" class="rf-slide-overlay" aria-label="Close menu"></a>
      <div class="rf-slide-panel">
        <a href="#" class="rf-slide-close" aria-label="Close">×</a>
        <div class="rf-sp-brand">
          {logo_img}
          <div class="rf-sp-tagline">{_html_escape(t.get("tagline", "Understand Before You Sign"))}</div>
        </div>
        {user_chip}
        <nav class="rf-sp-nav">
          {links_html}
        </nav>
        <div class="rf-sp-bottom">
          <div class="rf-sp-offline">
            <b>{_html_escape(t.get("works_offline", "Works offline"))}</b>
            <p>{_html_escape(t.get("offline_text", "All tools work on this device."))}</p>
          </div>
          <div class="rf-sp-chips">
            <div class="rf-sp-chip">🌐 {_html_escape(user_lang)}</div>
            <div class="rf-sp-chip">📍 India</div>
          </div>
        </div>
      </div>
    </div>
    """
    nav_html = "\n".join(line.lstrip() for line in nav_html.splitlines()).strip()
    st.markdown(nav_html, unsafe_allow_html=True)


def sidebar_header(mode: str):
    user_name = st.session_state.get("user_name", "")
    user_lang = normalize_app_language(st.session_state.get("user_language", "English"))
    st.session_state["user_language"] = user_lang
    st.session_state["user_country"] = INDIA_COUNTRY_BADGE
    user_country = INDIA_COUNTRY_BADGE

    st.sidebar.markdown(
        """
        <div style='background:#064d2f;margin:-1rem -1rem .8rem -1rem;
                    padding:22px 24px 24px;color:white;'>
          <div style='font-size:1.42rem;font-weight:800;line-height:1.12;
                      margin-bottom:6px;color:white;'>RuralFinance AI</div>
          <div style='font-size:.9rem;color:#e8fff2;line-height:1.3;'>
            Understand before you sign
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for icon, label, page in [
        ("🏠", "Home", "Home.py"),
        ("📄", "Scan Document", "pages/2_Document_Scanner.py"),
        ("🔍", "Understand Document", "pages/6_Understand_Document.py"),
        ("🧮", "EMI Calculator", "pages/3_Calculator.py"),
        ("🆘", "Emergency Help", "pages/8_Emergency_Help.py"),
        ("📖", "Understand Banking", "pages/5_Banking_Knowledge.py"),
    ]:
        st.sidebar.page_link(page, label=f"{icon}  {label}")

    st.sidebar.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Dynamic mode status pill
    _mode_meta = {
        "online":  ("🟢", "Online — Gemma 4 Active",    "#dcfce7", "#166534", "All AI features available. Deep document analysis enabled."),
        "offline": ("🟡", "Local AI — Ollama Active",   "#fefce8", "#854d0e", "Offline AI running. Explanations work without internet."),
        "limited": ("🔵", "Offline — Core Tools Only",  "#dbeafe", "#1e40af", "Core tools work offline. Start Ollama or add API key for AI."),
    }.get(mode, ("🔵", "Offline Mode", "#dbeafe", "#1e40af", "Core features available offline."))
    st.sidebar.markdown(
        f"""
        <div style='border:1px solid {_mode_meta[3]}44;border-radius:10px;padding:8px 12px;
                    background:{_mode_meta[2]};margin:0 8px 4px;'>
          <div style='font-weight:800;color:{_mode_meta[3]};font-size:.83rem;margin-bottom:3px;'>
            {_mode_meta[0]} {_mode_meta[1]}
          </div>
          <div style='font-size:.69rem;color:#374151;line-height:1.35;'>{_mode_meta[4]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if user_name or user_lang or user_country:
        st.sidebar.markdown(
            f"""
            <div style='font-size:.76rem;color:#6b7280;line-height:1.6;
                        padding:10px 16px;margin:0 8px;'>
              {('👤 ' + user_name + '<br>') if user_name else ''}
              🌐 {user_lang}<br>
              {('📍 ' + user_country) if user_country else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )


def page_lang_selector(page_key: str = "") -> None:
    """Compact right-aligned language selector for inner pages.

    Call once after inject_nav_drawer(). Selecting a new language updates
    session_state and query params, re-running the page in the chosen language.
    """
    _cur = st.session_state.get("user_language", "English")
    _key = f"_plang_{page_key}"

    def _on_change() -> None:
        _new = st.session_state[_key]
        st.session_state["user_language"] = _new
        st.query_params["l"] = _new
        st.query_params["li"] = "1"
        st.query_params["c"] = INDIA_COUNTRY_BADGE

    st.markdown(
        """<style>
        .rf-lang-row [data-baseweb="select"]>div{
            min-height:30px !important;border-radius:8px !important;
            border:1px solid #d8e2dc !important;background:#fff !important;font-size:.78rem !important;
        }
        .rf-lang-row label{display:none !important;}
        </style><div class="rf-lang-row"></div>""",
        unsafe_allow_html=True,
    )
    _, _lc = st.columns([7, 2])
    with _lc:
        st.selectbox(
            "🌐 Language",
            SUPPORTED_APP_LANGUAGES,
            index=SUPPORTED_APP_LANGUAGES.index(_cur) if _cur in SUPPORTED_APP_LANGUAGES else 0,
            key=_key,
            on_change=_on_change,
        )
