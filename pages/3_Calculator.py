import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from services.calculator_service import (
    calculate_emi, amortization_schedule,
    simple_interest, compound_interest, savings_growth,
)
from services.ai_service import generate, detect_mode
from utils.styles import inject_css, sidebar_header, inject_nav_drawer
from utils.translations import get_ui
from utils.india_config import INDIA_COUNTRY_BADGE, normalize_app_language
from utils.page_controls import render_language_back_topbar

load_dotenv()

_CALC_TR_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "calc_translations.json"
)


def _load_calc_tr_cache():
    try:
        with open(_CALC_TR_CACHE, "r", encoding="utf-8") as _f:
            for k, v in json.load(_f).items():
                if k not in st.session_state:
                    st.session_state[k] = v
    except Exception:
        pass


def _save_calc_tr_cache():
    existing = {}
    try:
        with open(_CALC_TR_CACHE, "r", encoding="utf-8") as _f:
            existing = json.load(_f)
    except Exception:
        pass
    for k, v in st.session_state.items():
        if k.startswith("calct_") and _is_good_translation(v):
            existing[k] = v
        elif k.startswith("calct_") and k in existing:
            del existing[k]  # remove garbage from disk
    os.makedirs(os.path.dirname(_CALC_TR_CACHE), exist_ok=True)
    with open(_CALC_TR_CACHE, "w", encoding="utf-8") as _f:
        json.dump(existing, _f, ensure_ascii=False)


_load_calc_tr_cache()

st.set_page_config(
    page_title="Calculator — RuralFinance AI",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()
mode = detect_mode()

_qp = st.query_params
if "user_language" not in st.session_state and _qp.get("l"):
    st.session_state["user_language"] = normalize_app_language(_qp.get("l", "English"))
    st.session_state["user_country"] = INDIA_COUNTRY_BADGE
    st.session_state["user_name"] = _qp.get("n", "")
    st.session_state["onboarding_done"] = True
st.session_state["user_country"] = INDIA_COUNTRY_BADGE

sidebar_header(mode)
inject_nav_drawer("EMI Calculator")
_t = get_ui(st.session_state.get("user_language", "English"))
_lang = st.session_state.get("user_language", "English")

# Maps every _calc_t() key → English text to send to the translator
_CALC_TRANS_KEYS = [
    ("Fill in the loan details on the left, then click **Calculate EMI**.",
     "Fill in the loan details on the left, then click Calculate EMI."),
    ("Fill in the details on the left, then click **Calculate Interest**.",
     "Fill in the details on the left, then click Calculate Interest."),
    ("Fill in the details on the left, then click **Calculate Savings**.",
     "Fill in the details on the left, then click Calculate Savings."),
    ("Tenure", "Tenure"),
    ("years_short", "years"),
    ("months_short", "months"),
    ("months", "months"),
    ("Month", "Month"),
    ("Type", "Type"),
    ("Simple Interest", "Simple Interest"),
    ("Compound Interest", "Compound Interest"),
    ("Interest", "Interest"),
    ("Principal", "Principal"),
    ("Balance", "Balance"),
    ("Total", "Total"),
    ("Compound earns", "Compound earns"),
    ("more over", "more over"),
    ("Compound = better when saving. Always choose reducing-balance loans when borrowing.",
     "Compound interest is better for savings. Always choose reducing-balance loans when borrowing."),
    ("Growth Over Time", "Growth Over Time"),
    ("Simple", "Simple"),
    ("Compound", "Compound"),
    ("Years", "Years"),
    ("Invested", "Invested"),
    ("Value", "Value"),
    ("Rate", "Rate"),
    ("month at different rates", "month at different rates"),
    ("Getting AI advice...", "Getting AI advice..."),
    ("AI advice source", "AI advice available from online or local model."),
    ("Download CSV", "Download CSV"),
    ("12 = 1 year, 60 = 5 years", "12 equals 1 year, 60 equals 5 years"),
    # ── Affordability ──
    ("Affordability Check", "Affordability Check"),
    ("Monthly Income (₹)", "Monthly Income (₹)"),
    ("EMI as % of Income", "EMI as % of Income"),
    ("Enter your monthly income to check if this loan is affordable", "Enter your monthly income to check if this loan is affordable"),
    ("Affordable — EMI is under 30% of income.", "Affordable — EMI is under 30% of income."),
    ("Borderline — EMI is 30–40% of income. Budget carefully.", "Borderline — EMI is 30–40% of income. Budget carefully."),
    ("Stressful — EMI exceeds 40% of income. Very high risk.", "Stressful — EMI exceeds 40% of income. Very high risk."),
    ("left after EMI for food, savings, and emergencies.", "left after EMI for food, savings, and emergencies."),
    # ── Floating Rate ──
    ("What If Rate Changes?", "What If Rate Changes?"),
    ("Current", "Current"),
    ("Extra Interest Cost", "Extra Interest Cost"),
    ("If this loan has a floating rate, your EMI will increase as shown above. Always ask your bank: Is this rate fixed or floating?",
     "If this loan has a floating rate, your EMI will increase as shown above. Always ask your bank: Is this rate fixed or floating?"),
    # ── Loan Comparison ──
    ("Loan Compare", "Loan Compare"),
    ("Compare Two Loans Side by Side", "Compare Two Loans Side by Side"),
    ("Enter details for two loans to find out which costs less.", "Enter details for two loans to find out which costs less."),
    ("Loan A", "Loan A"),
    ("Loan B", "Loan B"),
    ("🔍 Compare Loans", "Compare Loans"),
    ("Total Payment", "Total Payment"),
    ("saves you", "saves you"),
    ("vs Loan B.", "vs Loan B."),
    ("vs Loan A.", "vs Loan A."),
    ("Both loans have equal total cost.", "Both loans have equal total cost."),
    ("Lower Monthly EMI:", "Lower Monthly EMI:"),
    ("Lower Total Cost:", "Lower Total Cost:"),
    ("Outstanding Balance Over Time", "Outstanding Balance Over Time"),
    ("Before choosing, ask: Which loan has a fixed rate? Are there prepayment penalties? What are the foreclosure charges?",
     "Before choosing, ask: Which loan has a fixed rate? Are there prepayment penalties? What are the foreclosure charges?"),
]

CALC_TEXT = {
    "Hindi": {
        "Fill in the loan details on the left, then click **Calculate EMI**.": "बाईं तरफ़ लोन की जानकारी भरें, फिर **ईएमआई गणना करें** पर क्लिक करें।",
        "Fill in the details on the left, then click **Calculate Interest**.": "बाईं तरफ़ जानकारी भरें, फिर **ब्याज गणना करें** पर क्लिक करें।",
        "Fill in the details on the left, then click **Calculate Savings**.": "बाईं तरफ़ जानकारी भरें, फिर **बचत गणना करें** पर क्लिक करें।",
        "Tenure": "अवधि",
        "years_short": "वर्ष",
        "months_short": "महीने",
        "months": "महीने",
        "Type": "प्रकार",
        "Simple Interest": "साधारण ब्याज",
        "Compound Interest": "चक्रवृद्धि ब्याज",
        "Interest": "ब्याज",
        "Total": "कुल",
        "Compound earns": "चक्रवृद्धि से",
        "more over": "अधिक मिलते हैं",
        "Compound = better when saving. Always choose reducing-balance loans when borrowing.": "बचत में चक्रवृद्धि बेहतर है। कर्ज लेते समय हमेशा घटते-बैलेंस वाला लोन चुनें।",
        "Growth Over Time": "समय के साथ वृद्धि",
        "Simple": "साधारण",
        "Compound": "चक्रवृद्धि",
        "Years": "वर्ष",
        "Invested": "निवेश",
        "Value": "मूल्य",
        "Rate": "दर",
        "month at different rates": "प्रति माह अलग-अलग दरों पर",
        "Getting AI advice...": "AI सलाह तैयार हो रही है...",
        "AI advice source": "AI सलाह उपलब्ध मोड से आती है: ऑनलाइन Gemma हो तो ऑनलाइन, नहीं तो स्थानीय/ऑफ़लाइन fallback।",
        "Download CSV": "CSV डाउनलोड करें",
        "12 = 1 year, 60 = 5 years": "12 = 1 वर्ष, 60 = 5 वर्ष",
        "Loan Compare": "लोन तुलना",
    },
    "Bengali": {
        "Fill in the loan details on the left, then click **Calculate EMI**.": "বাঁদিকে ঋণের তথ্য দিন, তারপর **EMI হিসাব করুন** ক্লিক করুন।",
        "Fill in the details on the left, then click **Calculate Interest**.": "বাঁদিকে তথ্য দিন, তারপর **সুদ হিসাব করুন** ক্লিক করুন।",
        "Fill in the details on the left, then click **Calculate Savings**.": "বাঁদিকে তথ্য দিন, তারপর **সঞ্চয় হিসাব করুন** ক্লিক করুন।",
        "Tenure": "মেয়াদ",
        "years_short": "বছর",
        "months_short": "মাস",
        "months": "মাস",
        "Type": "ধরন",
        "Simple Interest": "সরল সুদ",
        "Compound Interest": "চক্রবৃদ্ধি সুদ",
        "Interest": "সুদ",
        "Total": "মোট",
        "Compound earns": "চক্রবৃদ্ধিতে",
        "more over": "বেশি পাওয়া যায়",
        "Compound = better when saving. Always choose reducing-balance loans when borrowing.": "সঞ্চয়ের ক্ষেত্রে চক্রবৃদ্ধি ভালো। ঋণ নেওয়ার সময় কমতে থাকা ব্যালেন্স পদ্ধতি বেছে নিন।",
        "Growth Over Time": "সময়ের সাথে বৃদ্ধি",
        "Simple": "সরল",
        "Compound": "চক্রবৃদ্ধি",
        "Years": "বছর",
        "Invested": "বিনিয়োগ",
        "Value": "মূল্য",
        "Rate": "হার",
        "month at different rates": "প্রতি মাসে ভিন্ন হারে",
        "Getting AI advice...": "AI পরামর্শ তৈরি হচ্ছে...",
        "AI advice source": "AI পরামর্শ উপলব্ধ মোড থেকে আসে: অনলাইন Gemma থাকলে অনলাইন, না হলে স্থানীয়/অফলাইন fallback।",
        "Download CSV": "CSV ডাউনলোড করুন",
        "12 = 1 year, 60 = 5 years": "12 = 1 বছর, 60 = 5 বছর",
        "Loan Compare": "লোন তুলনা",
    },
}


def _is_good_translation(val: str) -> bool:
    """Reject garbage: multi-line text or implausibly long strings."""
    return bool(val) and "\n" not in val and len(val) < 400


def _calc_t(text: str) -> str:
    # 1. Hardcoded translations (Hindi / Bengali)
    translated = CALC_TEXT.get(_lang, {}).get(text)
    if translated:
        return translated
    if _lang == "English":
        return text
    # 2. Session-state cache — validate to avoid crashing on garbage AI output
    cached = st.session_state.get(f"calct_{_lang}_{text}")
    if _is_good_translation(cached):
        return cached
    # 3. Fallback to English key until a valid translation is cached
    return text

# ── Compact styles ────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stMainBlockContainer"] { padding-top: 0.3rem !important; padding-bottom: 0.3rem !important; }
[data-testid="stVerticalBlock"] > div { gap: 0.3rem !important; }
.stTabs [data-baseweb="tab-list"] { gap: 1rem; margin-top: 0; margin-bottom: 0; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 0.4rem !important; }
.stMetric { background:#fff; border:1px solid #d7e5dc; border-radius:8px; padding:.3rem .5rem; }
.stMetric label { font-size:.75rem !important; }
.stMetric [data-testid="stMetricValue"] { font-size:1.1rem !important; color:#064d2f; }
.block-container { padding-top:0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Header: title LEFT, back button RIGHT ─────────────────────────────────────
_t = render_language_back_topbar("calc", "btn_calc_home")
_lang = st.session_state.get("user_language", "English")
st.markdown(f"### 🧮 {_t.get('calc_page_title', 'Know Your True Loan Cost')}")

tab_emi, tab_interest, tab_savings, tab_compare = st.tabs([
    _t.get("tab_emi", "🏦 EMI & Loan Planner"),
    _t.get("tab_interest", "💹 Interest Calculator"),
    _t.get("tab_savings", "💰 Savings Growth"),
    f"📊 {_calc_t('Loan Compare')}"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — EMI Calculator
# ══════════════════════════════════════════════════════════════════════════════
with tab_emi:
    col_in, col_out = st.columns([1, 1])

    with col_in:
        with st.form("emi_form"):
            principal = st.number_input(
                _t.get("loan_amount_label", "Loan Amount (₹)"), min_value=1000, max_value=10_000_000,
                value=300_000, step=5000, format="%d",
            )
            c1, c2 = st.columns(2)
            with c1:
                rate = st.number_input(
                    _t.get("interest_rate_label", "Interest Rate (%/yr)"), min_value=1.0, max_value=36.0,
                    value=12.0, step=0.5, format="%.1f",
                )
            with c2:
                months = st.number_input(
                    _t.get("tenure_months_label", "Tenure (months)"), min_value=6, max_value=360,
                    value=36, step=6, help=_calc_t("12 = 1 year, 60 = 5 years"),
                )
            st.caption(f"{_calc_t('Tenure')} = **{months//12} {_calc_t('years_short')} {months%12} {_calc_t('months_short')}**")
            clicked = st.form_submit_button(_t.get("calc_emi_btn", "🧮 Calculate EMI"), type="primary", use_container_width=True)

        if clicked:
            st.session_state["emi_result"] = {
                "principal": principal, "rate": rate, "months": months,
                "result": calculate_emi(principal, rate, months),
            }

    with col_out:
        calc = st.session_state.get("emi_result")
        if not calc:
            st.info(_calc_t("Fill in the loan details on the left, then click **Calculate EMI**."))
        else:
            r = calc["result"]
            m1, m2 = st.columns(2)
            m1.metric(_t.get("monthly_emi_label", "Monthly EMI"),    f"₹{r['emi']:,.0f}")
            m2.metric(_t.get("total_interest_label", "Total Interest"), f"₹{r['total_interest']:,.0f}")
            m3, m4 = st.columns(2)
            m3.metric(_t.get("total_payment_label", "Total Payment"),  f"₹{r['total_payment']:,.0f}")
            m4.metric(_t.get("interest_share_label", "Interest Share"), f"{r['interest_pct']}%")
            st.caption(f"₹{calc['principal']:,.0f} @ {calc['rate']}% · {calc['months']} {_calc_t('months')}")

            with st.expander(_t.get("repayment_schedule_label", "📅 Repayment schedule"), expanded=False):
                df = pd.DataFrame(amortization_schedule(calc["principal"], calc["rate"], calc["months"]))
                _mcol = _calc_t("Month")
                _bcol = f"{_calc_t('Balance')} (₹)"
                df = df.rename(columns={
                    "Month": _mcol,
                    "Principal (₹)": f"{_calc_t('Principal')} (₹)",
                    "Interest (₹)": f"{_calc_t('Interest')} (₹)",
                    "Balance (₹)": _bcol,
                })
                st.line_chart(df.set_index(_mcol)[[_bcol]], height=160, color="#2D6A4F")
                st.dataframe(df, use_container_width=True, height=180)
                st.download_button("⬇️ " + _calc_t("Download CSV"), df.to_csv(index=False),
                                   file_name="loan_schedule.csv", mime="text/csv")

            if st.button(_t.get("ai_advice_btn", "🤖 AI Advice"), type="secondary", use_container_width=True, key="emi_ai"):
                st.caption(_calc_t("AI advice source"))
                with st.spinner(_calc_t("Getting AI advice...")):
                    advice = generate(
                        f"Loan ₹{calc['principal']:,} at {calc['rate']}% for {calc['months']} months. "
                        f"EMI ₹{r['emi']:,}, interest ₹{r['total_interest']:,} ({r['interest_pct']}%). "
                        "Advise: affordability, warnings, questions to ask before signing. Simple language.",
                        language=st.session_state.get("user_language", "English"),
                    )
                st.markdown(advice)

            # ── Affordability Check ──────────────────────────────────────────
            with st.expander("💼 " + _calc_t("Affordability Check"), expanded=False):
                income = st.number_input(
                    _calc_t("Monthly Income (₹)"),
                    min_value=0, value=0, step=500,
                    help=_calc_t("Enter your monthly income to check if this loan is affordable"),
                    key="emi_income",
                )
                if income > 0:
                    pct = r["emi"] / income * 100
                    remaining = income - r["emi"]
                    st.metric(_calc_t("EMI as % of Income"), f"{pct:.1f}%")
                    if pct <= 30:
                        st.success("✅ " + _calc_t("Affordable — EMI is under 30% of income."))
                    elif pct <= 40:
                        st.warning("⚠️ " + _calc_t("Borderline — EMI is 30–40% of income. Budget carefully."))
                    else:
                        st.error("🚨 " + _calc_t("Stressful — EMI exceeds 40% of income. Very high risk."))
                    st.caption(f"₹{remaining:,.0f} " + _calc_t("left after EMI for food, savings, and emergencies."))
                else:
                    st.caption(_calc_t("Enter your monthly income to check if this loan is affordable"))

            # ── Floating Rate Simulation ─────────────────────────────────────
            with st.expander("📈 " + _calc_t("What If Rate Changes?"), expanded=False):
                scenarios = []
                for delta in [0, 1, 2, 3, 5]:
                    rr = calc["rate"] + delta
                    rr_res = calculate_emi(calc["principal"], rr, calc["months"])
                    extra = rr_res["total_interest"] - r["total_interest"]
                    scenarios.append({
                        _calc_t("Rate"): f"{rr:.1f}%  ({'📍 ' + _calc_t('Current') if delta == 0 else f'+{delta}%'})",
                        "EMI (₹)": f"₹{rr_res['emi']:,.0f}",
                        f"{_calc_t('Interest')} (₹)": f"₹{rr_res['total_interest']:,.0f}",
                        _calc_t("Extra Interest Cost"): "" if delta == 0 else f"+₹{extra:,.0f}",
                    })
                st.dataframe(
                    pd.DataFrame(scenarios),
                    use_container_width=True, hide_index=True,
                )
                st.caption("⚠️ " + _calc_t("If this loan has a floating rate, your EMI will increase as shown above. Always ask your bank: Is this rate fixed or floating?"))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Interest Calculator
# ══════════════════════════════════════════════════════════════════════════════
with tab_interest:
    col_in2, col_out2 = st.columns([1, 1])

    with col_in2:
        with st.form("interest_form"):
            int_principal = st.number_input(_t.get("principal_amount_label", "Principal Amount (₹)"), min_value=1000, value=50_000, step=1000, key="int_p")
            ci1, ci2 = st.columns(2)
            with ci1:
                int_rate  = st.number_input(_t.get("rate_yr_label", "Rate (%/yr)"), min_value=0.1, value=7.5, step=0.1, key="int_r")
            with ci2:
                int_years = st.number_input(_t.get("period_years_label", "Period (Years)"), min_value=0.5, value=5.0, step=0.5, key="int_y")
            int_clicked = st.form_submit_button(_t.get("calc_interest_btn", "💹 Calculate Interest"), type="primary", use_container_width=True)

        if int_clicked:
            st.session_state["int_result"] = {
                "principal": int_principal, "rate": int_rate, "years": int_years,
                "si": simple_interest(int_principal, int_rate, int_years),
                "ci": compound_interest(int_principal, int_rate, int_years),
            }

    with col_out2:
        ir = st.session_state.get("int_result")
        if not ir:
            st.info(_calc_t("Fill in the details on the left, then click **Calculate Interest**."))
        else:
            si, ci_res = ir["si"], ir["ci"]
            extra = ci_res["total"] - si["total"]

            comp_df = pd.DataFrame({
                _calc_t("Type"):          [_calc_t("Simple Interest"), _calc_t("Compound Interest")],
                f"{_calc_t('Interest')} (₹)":  [si["interest"],   ci_res["interest"]],
                f"{_calc_t('Total')} (₹)":     [si["total"],       ci_res["total"]],
            })
            st.dataframe(comp_df, use_container_width=True, hide_index=True)
            st.success(f"✨ {_calc_t('Compound earns')} **₹{extra:,.0f}** {_calc_t('more over')} {ir['years']} {_calc_t('years_short')}!")
            st.caption("💡 " + _calc_t("Compound = better when saving. Always choose reducing-balance loans when borrowing."))

            years_range = list(range(1, int(ir["years"]) + 1))
            chart_df = pd.DataFrame({
                _calc_t("Simple"):   [simple_interest(ir["principal"], ir["rate"], y)["total"]   for y in years_range],
                _calc_t("Compound"): [compound_interest(ir["principal"], ir["rate"], y)["total"] for y in years_range],
            }, index=years_range)
            chart_df.index.name = _calc_t("Years")
            st.markdown("**📈 " + _calc_t("Growth Over Time") + "**")
            st.line_chart(chart_df, height=240)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Savings Growth
# ══════════════════════════════════════════════════════════════════════════════
with tab_savings:
    col_in3, col_out3 = st.columns([1, 1])

    with col_in3:
        with st.form("savings_form"):
            monthly  = st.number_input(_t.get("monthly_savings_label", "Monthly Savings (₹)"), min_value=100, value=2000, step=100, key="sv_m")
            sv1, sv2 = st.columns(2)
            with sv1:
                sv_rate  = st.number_input(_t.get("return_yr_label", "Return (%/yr)"), min_value=1.0, max_value=20.0, value=7.0, step=0.5, key="sv_r")
            with sv2:
                sv_years = st.number_input(_t.get("years_label", "Years"), min_value=1, max_value=30, value=10, step=1, key="sv_y")
            sv_clicked = st.form_submit_button(_t.get("calc_savings_btn", "💰 Calculate Savings"), type="primary", use_container_width=True)

        if sv_clicked:
            st.session_state["sv_result"] = {
                "monthly": monthly, "rate": sv_rate, "years": sv_years,
                "sg": savings_growth(monthly, sv_rate, sv_years),
            }

    with col_out3:
        svr = st.session_state.get("sv_result")
        if not svr:
            st.info(_calc_t("Fill in the details on the left, then click **Calculate Savings**."))
        else:
            sg = svr["sg"]
            m1, m2, m3 = st.columns(3)
            m1.metric(_t.get("future_value_label", "Future Value"),   f"₹{sg['future_value']:,.0f}")
            m2.metric(_t.get("total_invested_label", "Total Invested"), f"₹{sg['total_invested']:,.0f}")
            m3.metric(_t.get("gain_label", "Gain"),           f"₹{sg['total_interest']:,.0f}",
                      delta=f"+{sg['total_interest']/sg['total_invested']*100:.0f}%")

            years_list = list(range(1, svr["years"] + 1))
            sv_chart = pd.DataFrame({
                _calc_t("Invested"): [svr["monthly"] * 12 * y for y in years_list],
                _calc_t("Value"):    [savings_growth(svr["monthly"], svr["rate"], y)["future_value"] for y in years_list],
            }, index=years_list)
            sv_chart.index.name = _calc_t("Years")
            st.area_chart(sv_chart, height=200)

            rates = [4.0, 6.0, 7.0, 8.0, 10.0, 12.0]
            cmp = [{_calc_t("Rate"): f"{r}%", _calc_t("Value"): f"₹{savings_growth(svr['monthly'],r,svr['years'])['future_value']:,.0f}"}
                   for r in rates]
            st.caption(f"**₹{svr['monthly']:,}/{_calc_t('month at different rates')} ({svr['years']} {_calc_t('years_short')}):**")
            st.dataframe(pd.DataFrame(cmp), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Loan Comparison
# ══════════════════════════════════════════════════════════════════════════════
with tab_compare:
    st.caption("📊 " + _calc_t("Enter details for two loans to find out which costs less."))

    with st.form("loan_compare_form"):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"#### 🏦 {_t.get('loan_a_label', 'Loan A')}")
            la_p = st.number_input(_t.get("loan_amount_label", "Loan Amount (₹)"),
                                   min_value=1000, max_value=10_000_000, value=300_000, step=5000, key="la_p")
            la_r = st.number_input(_t.get("interest_rate_label", "Interest Rate (%/yr)"),
                                   min_value=1.0, max_value=36.0, value=12.0, step=0.5, key="la_r")
            la_m = st.number_input(_t.get("tenure_months_label", "Tenure (months)"),
                                   min_value=6, max_value=360, value=36, step=6, key="la_m")
        with col_b:
            st.markdown(f"#### 🏦 {_t.get('loan_b_label', 'Loan B')}")
            lb_p = st.number_input(_t.get("loan_amount_label", "Loan Amount (₹)"),
                                   min_value=1000, max_value=10_000_000, value=300_000, step=5000, key="lb_p")
            lb_r = st.number_input(_t.get("interest_rate_label", "Interest Rate (%/yr)"),
                                   min_value=1.0, max_value=36.0, value=14.0, step=0.5, key="lb_r")
            lb_m = st.number_input(_t.get("tenure_months_label", "Tenure (months)"),
                                   min_value=6, max_value=360, value=48, step=6, key="lb_m")
        compare_btn = st.form_submit_button(
            "🔍 " + _calc_t("Compare Two Loans Side by Side"), type="primary", use_container_width=True
        )

    if compare_btn:
        st.session_state["cmp_result"] = {
            "a": {"p": la_p, "r": la_r, "m": la_m, "res": calculate_emi(la_p, la_r, la_m)},
            "b": {"p": lb_p, "r": lb_r, "m": lb_m, "res": calculate_emi(lb_p, lb_r, lb_m)},
        }

    cmp_data = st.session_state.get("cmp_result")
    if cmp_data:
        ad, bd = cmp_data["a"], cmp_data["b"]
        ar2, br2 = ad["res"], bd["res"]

        # Side-by-side comparison table
        _la = _calc_t("Loan A")
        _lb = _calc_t("Loan B")
        comp_rows = [
            (_t.get("loan_amount_label", "Loan Amount"),  f"₹{ad['p']:,}",           f"₹{bd['p']:,}"),
            (_t.get("interest_rate_label", "Rate"),        f"{ad['r']}%",              f"{bd['r']}%"),
            (_calc_t("Tenure"),                            f"{ad['m']} {_calc_t('months_short')}", f"{bd['m']} {_calc_t('months_short')}"),
            (_t.get("monthly_emi_label", "Monthly EMI"),   f"₹{ar2['emi']:,.0f}",      f"₹{br2['emi']:,.0f}"),
            (_t.get("total_interest_label", "Total Interest"), f"₹{ar2['total_interest']:,.0f}", f"₹{br2['total_interest']:,.0f}"),
            (_calc_t("Total Payment"),                     f"₹{ar2['total_payment']:,.0f}", f"₹{br2['total_payment']:,.0f}"),
            (_t.get("interest_share_label", "Interest Share"), f"{ar2['interest_pct']}%", f"{br2['interest_pct']}%"),
        ]
        comp_df = pd.DataFrame(comp_rows, columns=["", _la, _lb])
        st.dataframe(comp_df.set_index(""), use_container_width=True)

        # Winner verdict
        diff = abs(ar2["total_payment"] - br2["total_payment"])
        if ar2["total_payment"] < br2["total_payment"]:
            st.success(f"✅ **{_la}** {_calc_t('saves you')} ₹{diff:,.0f} {_calc_t('vs Loan B.')}")
        elif br2["total_payment"] < ar2["total_payment"]:
            st.success(f"✅ **{_lb}** {_calc_t('saves you')} ₹{diff:,.0f} {_calc_t('vs Loan A.')}")
        else:
            st.info(_calc_t("Both loans have equal total cost."))

        # Lower EMI / Lower cost breakdown
        lower_emi  = _la if ar2["emi"] <= br2["emi"] else _lb
        lower_cost = _la if ar2["total_payment"] <= br2["total_payment"] else _lb
        c1c, c2c = st.columns(2)
        c1c.info(f"**{_calc_t('Lower Monthly EMI:')}** {lower_emi}")
        c2c.info(f"**{_calc_t('Lower Total Cost:')}** {lower_cost}")

        # Balance-over-time chart
        max_m2 = max(ad["m"], bd["m"])
        a_sched = {row["Month"]: row["Balance (₹)"] for row in amortization_schedule(ad["p"], ad["r"], ad["m"])}
        b_sched = {row["Month"]: row["Balance (₹)"] for row in amortization_schedule(bd["p"], bd["r"], bd["m"])}
        bal_df = pd.DataFrame({
            _la: [a_sched.get(i + 1, 0) for i in range(max_m2)],
            _lb: [b_sched.get(i + 1, 0) for i in range(max_m2)],
        }, index=range(1, max_m2 + 1))
        bal_df.index.name = _calc_t("Month")
        st.markdown(f"**📉 {_calc_t('Outstanding Balance Over Time')}**")
        st.line_chart(bal_df, height=200)

        st.caption("💡 " + _calc_t("Before choosing, ask: Which loan has a fixed rate? Are there prepayment penalties? What are the foreclosure charges?"))

# ── Silent one-shot calculator translation ─────────────────────────────────────
if _lang not in ("English",) and _lang not in CALC_TEXT and mode != "limited":
    _missing_calc = [
        (k, en) for k, en in _CALC_TRANS_KEYS
        if not _is_good_translation(st.session_state.get(f"calct_{_lang}_{k}"))
    ]
    if _missing_calc:
        _saved_calc = False
        _batch_payload = json.dumps({k: en for k, en in _missing_calc}, ensure_ascii=False)
        _batch_prompt = (
            f"Translate these UI phrases to {_lang}. "
            "Return ONLY a valid JSON object with the same keys and translated values. "
            "Keep numbers, currency symbols, and brand names unchanged. No extra text.\n\n"
            + _batch_payload
        )
        _resp = generate(_batch_prompt, language=_lang, allow_online=(mode == "online")).strip()
        _translations: dict = {}
        try:
            _s = _resp.find("{")
            _e = _resp.rfind("}") + 1
            if _s >= 0 and _e > _s:
                _translations = json.loads(_resp[_s:_e])
        except Exception:
            pass
        for _key, _en_text in _missing_calc:
            _tr = str(_translations.get(_key, "")).strip()
            if _is_good_translation(_tr) and not _tr.startswith("⚠️") and _tr != _en_text:
                st.session_state[f"calct_{_lang}_{_key}"] = _tr
                _saved_calc = True
        if not _translations:
            for _key, _en_text in _missing_calc[:8]:
                _r = generate(
                    f"Translate to {_lang}. Return ONLY the translation, nothing else:\n\n{_en_text}",
                    language=_lang, allow_online=(mode == "online"),
                ).strip()
                if _is_good_translation(_r) and not _r.startswith("⚠️"):
                    st.session_state[f"calct_{_lang}_{_key}"] = _r
                    _saved_calc = True
        if _saved_calc:
            _save_calc_tr_cache()
            st.rerun()
