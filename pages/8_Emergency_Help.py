import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from dotenv import load_dotenv
from services.ai_service import generate, detect_mode
from utils.styles import inject_css, sidebar_header, inject_nav_drawer
from utils.translations import get_ui
from utils.india_config import INDIA_COUNTRY_BADGE, normalize_app_language
from utils.page_controls import render_language_back_topbar

load_dotenv()

_EH_TR_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "eh_translations.json"
)


def _load_eh_tr_cache():
    try:
        with open(_EH_TR_CACHE, "r", encoding="utf-8") as _f:
            for k, v in json.load(_f).items():
                if k not in st.session_state:
                    st.session_state[k] = v
    except Exception:
        pass


def _save_eh_tr_cache():
    existing = {}
    try:
        with open(_EH_TR_CACHE, "r", encoding="utf-8") as _f:
            existing = json.load(_f)
    except Exception:
        pass
    for k, v in st.session_state.items():
        if k.startswith("eh_t_") and _is_good_eh_translation(v):
            existing[k] = v
        elif k.startswith("eh_t_") and k in existing:
            del existing[k]
    os.makedirs(os.path.dirname(_EH_TR_CACHE), exist_ok=True)
    with open(_EH_TR_CACHE, "w", encoding="utf-8") as _f:
        json.dump(existing, _f, ensure_ascii=False)


_load_eh_tr_cache()

st.set_page_config(
    page_title="Already Signed? Get Help — RuralFinance AI",
    page_icon="🆘",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()

# ── Country-based emergency contacts ─────────────────────────────────────────
INDIA_CONTACTS = {
    "Financial Fraud": [
        ("National Cyber Crime Helpline", "1930", "Call immediately for UPI fraud, online loan app scams, and cyber financial fraud"),
        ("Cyber Crime Portal", "cybercrime.gov.in", "File an online financial fraud complaint"),
        ("NPCI / UPI Help", "1800-120-1740", "UPI payment disputes and RuPay-related issues"),
    ],
    "Banking Complaints": [
        ("RBI Ombudsman", "14440", "Free complaint resolution against banks and NBFCs"),
        ("RBI Complaint Portal", "cms.rbi.org.in", "File complaints against banks, NBFCs, digital lenders, and payment issues"),
        ("National Consumer Helpline", "1915", "Consumer complaints about financial services"),
        ("IRDAI Insurance Helpline", "155255", "Insurance claim and policy complaints"),
    ],
    "Legal Aid (Free)": [
        ("NALSA Legal Aid", "15100", "Free legal help for eligible borrowers, women, senior citizens, SC/ST, and low-income families"),
        ("Consumer Commission Portal", "edaakhil.nic.in", "Online consumer complaint filing"),
    ],
    "Police": [
        ("Emergency Response", "112", "Immediate danger or harassment"),
        ("Police", "100", "Local police emergency"),
        ("Women Helpline", "1091", "Violence, coercion, or financial exploitation of women"),
        ("Senior Citizen Helpline", "14567", "Fraud or exploitation of elderly borrowers"),
    ],
}

# ── Borrower Rights data (offline, static) ───────────────────────────────────
BORROWER_RIGHTS = [
    {
        "title": "Right to Receive Loan Agreement Copy",
        "icon": "📄",
        "law": "RBI Fair Practices Code",
        "points": [
            "You must receive a copy of the loan agreement BEFORE you sign it.",
            "The lender must give you time to read it — you can refuse to sign on the spot.",
            "All fees, charges, and interest rates must be written clearly in the agreement.",
            "If the lender refuses to give you a copy, do not sign.",
        ],
        "action": "Ask: 'Can I take this home to read?' — Any legitimate lender will say yes.",
    },
    {
        "title": "Right to Know All Charges (Key Fact Statement)",
        "icon": "💰",
        "law": "RBI Digital Lending Guidelines 2022",
        "points": [
            "All lenders (banks, NBFCs, digital apps) must give you a Key Fact Statement (KFS).",
            "KFS shows: Annual Percentage Rate (APR), processing fee, prepayment penalty, and total cost.",
            "No hidden charges are allowed — any fee not in KFS is illegal.",
            "The KFS must be in a language you understand.",
        ],
        "action": "Ask for the KFS in writing before accepting any loan offer.",
    },
    {
        "title": "Right to Prepay or Foreclose Your Loan",
        "icon": "🔓",
        "law": "RBI Circular on Prepayment (2014)",
        "points": [
            "For floating rate loans: banks CANNOT charge a prepayment penalty.",
            "For fixed rate loans: penalty must be disclosed upfront in the agreement.",
            "You can repay the full loan early at any time.",
            "The lender must give you a No-Objection Certificate (NOC) after full repayment.",
        ],
        "action": "If you want to close the loan early, ask for the foreclosure statement in writing.",
    },
    {
        "title": "Recovery Agent Rules — What They CANNOT Do",
        "icon": "🛡️",
        "law": "RBI Recovery Agent Guidelines",
        "points": [
            "Recovery agents CANNOT contact you before 8:00 AM or after 7:00 PM.",
            "They CANNOT use abusive, threatening, or intimidating language.",
            "They CANNOT visit your workplace without your permission.",
            "They CANNOT harass your family members, neighbours, or colleagues.",
            "They CANNOT seize assets without a court order (except under SARFAESI for secured loans).",
            "They must show their authorization letter from the bank/NBFC if you ask.",
        ],
        "action": "If violated: Call RBI Ombudsman 14440, file complaint at cms.rbi.org.in, or call Police 100.",
    },
    {
        "title": "SARFAESI Act — Property Seizure Rules",
        "icon": "🏠",
        "law": "SARFAESI Act 2002",
        "points": [
            "Bank must send a written notice 60 days BEFORE taking any action on your property.",
            "During 60 days, you can repay the outstanding amount and stop the process.",
            "You can file an appeal before the Debt Recovery Tribunal (DRT) against wrongful seizure.",
            "Banks cannot seize agricultural land under SARFAESI.",
            "Personal loans and credit cards are NOT covered — SARFAESI applies only to secured loans.",
        ],
        "action": "If you receive a SARFAESI notice, immediately consult NALSA Legal Aid (15100) — it's free.",
    },
    {
        "title": "Digital Lending App Rights",
        "icon": "📱",
        "law": "RBI Digital Lending Guidelines Sep 2022",
        "points": [
            "Loan must be disbursed directly to your bank account — NOT through wallets.",
            "Repayments must be made directly to the lender's account — NOT to agent wallets.",
            "App cannot access your contacts, photos, or location beyond what is needed.",
            "A 3-day cooling-off period: you can return the loan within 3 days with no penalty.",
            "Any app not registered with RBI as an NBFC is operating illegally.",
            "Instant loan apps demanding upfront 'processing fee' before disbursement are fraudulent.",
        ],
        "action": "Check RBI NBFC list at rbi.org.in/Scripts/NBFCList.aspx before borrowing from any app.",
    },
    {
        "title": "Right to Complain — Free Grievance Channels",
        "icon": "📣",
        "law": "Consumer Protection Act 2019 + RBI Ombudsman Scheme",
        "points": [
            "Step 1: Complain to the bank/NBFC's Grievance Redressal Officer (GRO) — must respond in 30 days.",
            "Step 2: If unresolved, escalate to RBI Ombudsman (14440 / cms.rbi.org.in) — completely free.",
            "Step 3: File consumer complaint at edaakhil.nic.in — no lawyer required.",
            "Step 4: Approach NALSA for free legal representation (15100).",
            "Keep all records: SMS, emails, call logs, receipts — they are your evidence.",
        ],
        "action": "Always get a complaint reference number. Without it, the complaint can be closed without action.",
    },
]

# ── Digital Loan App Risk Checklist ──────────────────────────────────────────
DIGITAL_APP_CHECKLIST = [
    {
        "category": "Legitimacy Checks",
        "icon": "✅",
        "items": [
            ("Is the lender registered as an NBFC or bank with RBI?", True, "Verify at rbi.org.in — unregistered lenders are illegal."),
            ("Does the app/website show the NBFC/bank name and registration number?", True, "Legitimate lenders always display this."),
            ("Did you find the app on Google Play Store or Apple App Store (not a direct APK link)?", True, "APK-only apps bypass safety checks."),
        ],
    },
    {
        "category": "Loan Terms Transparency",
        "icon": "📋",
        "items": [
            ("Did they give you a Key Fact Statement (KFS) before approval?", True, "KFS is mandatory under RBI 2022 rules."),
            ("Is the Annual Percentage Rate (APR) clearly stated?", True, "Many apps hide the real cost — 'weekly fee' can equal 300%+ APR."),
            ("Are all fees (processing, insurance, GST) listed upfront in writing?", True, "Verbal promises are unenforceable."),
            ("Is there NO upfront fee demanded before loan disbursement?", True, "Upfront fee before disbursement is a classic scam pattern."),
        ],
    },
    {
        "category": "Privacy & Permissions",
        "icon": "🔒",
        "items": [
            ("Does the app ask for contacts, photos, or media access?", False, "RBI prohibits access to contacts or media — deny these permissions."),
            ("Does the app threaten to share your photos or contact your family if you miss EMI?", False, "This is harassment — file at cybercrime.gov.in immediately."),
            ("Does the app send SMS to your contacts without your permission?", False, "Illegal under IT Act and RBI guidelines."),
        ],
    },
    {
        "category": "Collection Practices",
        "icon": "📞",
        "items": [
            ("Do recovery calls come only between 8 AM and 7 PM?", True, "Calls outside this window violate RBI rules."),
            ("Does the lender have a working customer support number/email?", True, "No contact = no accountability."),
            ("Did you receive a physical or digital receipt for every repayment?", True, "Always demand receipts — they protect you."),
        ],
    },
]

AI_LEGAL_PROMPT = (
    "You are a financial legal aid advisor helping an Indian borrower in financial distress. "
    "The person is in India and may be dealing with banks, NBFCs, MFIs, cooperative banks, "
    "or illegal loan apps. Give practical, actionable advice in very simple language. Cover: "
    "1) What to do RIGHT NOW (most urgent action) "
    "2) Their legal rights under Indian law (RBI guidelines, SARFAESI Act, RERA, Consumer Protection Act) "
    "3) Who to contact for help — use Indian helplines: RBI Ombudsman 14440, Cyber Crime 1930, "
    "NALSA Legal Aid 15100, Consumer Helpline 1915, Police 100 "
    "4) What NOT to do "
    "5) If UPI/OTP fraud: steps to freeze account and file complaint at cybercrime.gov.in "
    "Keep it under 250 words, use bullet points, be reassuring but honest.\n\nSituation: "
)

RECOVERY_NOTICE_PROMPT = (
    "You are a legal expert helping an Indian borrower who has received a loan recovery notice. "
    "Analyze the notice text and provide: "
    "1) LEGITIMACY: Is this notice legally valid? Check for: lender name, loan account number, outstanding amount, legal sections cited, authorized signature. "
    "2) KEY DEADLINES: List any dates or response windows mentioned. "
    "3) YOUR RIGHTS: What rights does the borrower have under Indian law at this stage? "
    "4) IMMEDIATE ACTIONS: What should they do in the next 24-48 hours? "
    "5) RED FLAGS: Any suspicious elements that suggest this notice may be fake or illegal? "
    "Use simple language. Format with clear headers. Under 300 words.\n\nNotice text: "
)

# ── Mode & session setup ──────────────────────────────────────────────────────
mode = detect_mode()

_qp = st.query_params
if "user_language" not in st.session_state and _qp.get("l"):
    st.session_state["user_language"] = normalize_app_language(_qp.get("l", "English"))
    st.session_state["user_country"] = INDIA_COUNTRY_BADGE
    st.session_state["user_name"] = _qp.get("n", "")
    st.session_state["onboarding_done"] = True
st.session_state["user_country"] = INDIA_COUNTRY_BADGE

sidebar_header(mode)
inject_nav_drawer("Emergency Help")

_t = get_ui(st.session_state.get("user_language", "English"))
_lang = st.session_state.get("user_language", "English")

# ── All strings that need translation ────────────────────────────────────────
_EH_TRANS_KEYS = [
    # Category names
    "Financial Fraud",
    "Banking Complaints",
    "Legal Aid (Free)",
    "Police",
    # UI labels
    "click to see helpline numbers",
    # Helpline names
    "National Cyber Crime Helpline",
    "Cyber Crime Portal",
    "NPCI / UPI Help",
    "RBI Ombudsman",
    "RBI Complaint Portal",
    "National Consumer Helpline",
    "IRDAI Insurance Helpline",
    "NALSA Legal Aid",
    "Consumer Commission Portal",
    "Emergency Response",
    "Women Helpline",
    "Senior Citizen Helpline",
    # Helpline descriptions
    "Call immediately for UPI fraud, online loan app scams, and cyber financial fraud",
    "File an online financial fraud complaint",
    "UPI payment disputes and RuPay-related issues",
    "Free complaint resolution against banks and NBFCs",
    "File complaints against banks, NBFCs, digital lenders, and payment issues",
    "Consumer complaints about financial services",
    "Insurance claim and policy complaints",
    "Free legal help for eligible borrowers, women, senior citizens, SC/ST, and low-income families",
    "Online consumer complaint filing",
    "Immediate danger or harassment",
    "Local police emergency",
    "Violence, coercion, or financial exploitation of women",
    "Fraud or exploitation of elderly borrowers",
    # Tab 2 / Ask AI
    "Already signed a bad document? Facing fraud or harassment? Describe your situation and get step-by-step advice.",
    "Generating personalized guidance...",
    "Personalized Guidance",
    "AI unavailable - here is standard guidance:",
    "FINANCIAL FRAUD? Call 1930 / cybercrime.gov.in RIGHT NOW. The sooner you report, the higher the chance of recovering your money.",
    # Tab labels (standalone, without emoji)
    "Know Your Rights",
    "Recovery Notice",
    # Borrower Rights tab
    "Your Legal Rights as a Borrower",
    "These rights are guaranteed by Indian law — offline, no internet needed.",
    "Law / Source",
    "What to do",
    "Know Your Rights",
    # Recovery Notice tab
    "Received a recovery notice or legal threat? Paste it here for analysis.",
    "Paste Recovery Notice Text",
    "Analyze Notice",
    "Analyzing recovery notice...",
    "Notice Analysis",
    "Recovery Notice Tips",
    # Digital App Checklist tab
    "Is Your Loan App Safe?",
    "Check each item below to evaluate if a loan app is legitimate and safe.",
    "Safe",
    "Risk Found",
    "Your loan app passed all safety checks.",
    "Risk detected. See red items above.",
    "Proceed with caution — some items need attention.",
    "Reset Checklist",
]


def _is_good_eh_translation(val: str) -> bool:
    return bool(val) and "\n" not in val and len(val) < 500


# def _eh_t(text: str) -> str:
#     if not text or _lang == "English":
#         return text
#     cached = st.session_state.get(f"eh_t_{_lang}_{text}")
#     if _is_good_eh_translation(cached):
#         return cached
#     return text

# Inside pages/4_Emergency_Help.py

# Inside pages/8_Emergency_Help.py

def _eh_t(text: str) -> str:
    """Robust translation: Manual Dict -> AI Cache -> English Fallback."""
    if not text or _lang == "English":
        return text or ""
    
    # 1. ALWAYS check global manual translations FIRST (translations.py)
    manual_tr = _t.get(text)
    if manual_tr and manual_tr != text:
        return manual_tr
        
    # 2. Check local session cache (AI output)
    cached = st.session_state.get(f"eh_t_{_lang}_{text}")
    if cached and _is_good_eh_translation(cached):
        return str(cached)
        
    # 3. Final Fallback: Return original English text (never None)
    return str(text)

# # --- FIXED BANNER CODE ---
# _fraud_numbers = [num for _, num, _ in INDIA_CONTACTS.get("Financial Fraud", [])[:2]]
# _fraud_str = " / ".join(_fraud_numbers) if _fraud_numbers else "1930"

# # Using an f-string is safer than concatenation (+) to prevent None errors
# banner_text = _eh_t(f"FINANCIAL FRAUD? Call {_fraud_str} RIGHT NOW. The sooner you report, the higher the chance of recovering your money.")
# st.error(f"🚨 **{banner_text}**")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    _contacts_sidebar = INDIA_CONTACTS
    st.markdown("##### 🆘 Emergency Quick Reference")
    _lines = []
    for _cat, _items in _contacts_sidebar.items():
        for _name, _num, _desc in _items[:2]:
            _lines.append(f"🔴 **{_name}:** {_num}")
    st.markdown("\n\n".join(_lines[:6]))
    st.divider()
    st.markdown("**📥 Download Emergency Card**")
    _card_lines = ["EMERGENCY FINANCIAL HELPLINES", "=" * 32, ""]
    for _cat, _items in _contacts_sidebar.items():
        _card_lines.append(_cat)
        for _name, _num, _desc in _items:
            _card_lines.append(f"  {_name}: {_num}")
        _card_lines.append("")
    # Append borrower rights summary
    _card_lines += [
        "", "YOUR KEY RIGHTS AS A BORROWER", "=" * 32,
        "- Demand loan agreement BEFORE signing",
        "- Ask for Key Fact Statement (KFS) with all charges",
        "- Recovery agents cannot call before 8AM or after 7PM",
        "- 60-day notice required before property seizure (SARFAESI)",
        "- Cooling-off period: 3 days to return a digital loan",
        "- Free legal aid: NALSA 15100",
        "- Free complaint: RBI Ombudsman 14440",
    ]
    emergency_card = "\n".join(_card_lines)
    st.download_button("⬇️ Download Emergency Card", emergency_card,
                       file_name="emergency_helplines.txt", mime="text/plain")

# ── Back button — top left ────────────────────────────────────────────────────
_t = render_language_back_topbar("emergency", "btn_back_home_eh")
_lang = st.session_state.get("user_language", "English")
_eh_title = _t.get("emergency_page_title", "Already Signed? Here's What to Do")
st.markdown(f"### 🆘 {_eh_title}")
st.caption(_t.get("emergency_page_caption", "Facing fraud or loan harassment? Get emergency contacts and personalized guidance."))

# ── Emergency banner ──────────────────────────────────────────────────────────
_fraud_numbers = [num for _, num, _ in INDIA_CONTACTS.get("Financial Fraud", [])[:2]]
_fraud_str = " / ".join(_fraud_numbers) if _fraud_numbers else "1930"

banner_msg = f"FINANCIAL FRAUD? Call {_fraud_str} RIGHT NOW. The sooner you report, the higher the chance of recovering your money."
st.error(f"🚨 **{_eh_t(banner_msg)}**")

# st.error(
#     "🚨 **"
#     + _eh_t(
#         f"FINANCIAL FRAUD? Call {_fraud_str} RIGHT NOW. "
#         "The sooner you report, the higher the chance of recovering your money."
#     )
#     + "**"
# )

# ── 4 tabs ────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    _t.get("tab_emergency_contacts", "📞 Emergency Contacts"),
    _t.get("tab_rights", "📋 Know Your Rights"),
    _t.get("tab_recovery", "🔍 Recovery Notice"),
    _t.get("tab_ask_ai", "🤖 Ask AI"),
])
# tab1, tab2, tab3, tab4 = st.tabs([
#     _t.get("tab_emergency_contacts", "📞 Emergency Contacts"),
#     f"📋 {_eh_t('Know Your Rights')}",
#     f"🔍 {_eh_t('Recovery Notice')}",
#     _t.get("tab_ask_ai", "🤖 Ask AI"),
# ])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: Emergency Contacts
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    _user_country = st.session_state.get("user_country", "🇮🇳 India")
    st.caption(
        f"📞 {_t.get('eh_verified_for', 'Verified government helplines for')} "
        f"**{_user_country}**. {_t.get('eh_most_toll_free', 'Most are toll-free.')}"
    )

    _click_text = _t.get("eh_click_to_see", "click to see helpline numbers")
    for category, items in INDIA_CONTACTS.items():
        with st.expander(f"{_eh_t(category)}  —  {_eh_t(_click_text)}", expanded=False):
            for name, number, description in items:
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.markdown(f"**{_eh_t(name)}**")
                    st.caption(_eh_t(description))
                with c2:
                    st.code(number)
                st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: Borrower Rights — fully offline static content
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.caption(
        f"⚖️ {_eh_t('These rights are guaranteed by Indian law — offline, no internet needed.')}"
    )

    for right in BORROWER_RIGHTS:
        with st.expander(
            f"{right['icon']} **{_eh_t(right['title'])}**",
            expanded=False,
        ):
            st.markdown(
                f"<span style='background:#1e3a5f;color:#7eb8f7;"
                f"padding:2px 8px;border-radius:4px;font-size:.75rem;'>"
                f"📜 {_eh_t('Law / Source')}: {right['law']}</span>",
                unsafe_allow_html=True,
            )
            st.markdown("")
            for point in right["points"]:
                st.markdown(f"• {point}")
            st.success(f"✅ **{_eh_t('What to do')}:** {right['action']}")

    st.divider()

    # ── Digital Loan App Safety Checklist ────────────────────────────────────
    st.markdown(f"### 📱 {_eh_t('Is Your Loan App Safe?')}")
    st.caption(_eh_t("Check each item below to evaluate if a loan app is legitimate and safe."))

    if st.button(_eh_t("Reset Checklist"), key="reset_checklist"):
        for _key in list(st.session_state.keys()):
            if _key.startswith("chk_"):
                del st.session_state[_key]

    total_checks = 0
    passed_checks = 0
    failed_required = 0

    for section in DIGITAL_APP_CHECKLIST:
        st.markdown(f"**{section['icon']} {section['category']}**")
        for i, (question, safe_value, explanation) in enumerate(section["items"]):
            chk_key = f"chk_{section['category']}_{i}"
            total_checks += 1
            col_q, col_a = st.columns([4, 1])
            with col_q:
                st.caption(question)
                st.markdown(
                    f"<small style='color:#888'>{explanation}</small>",
                    unsafe_allow_html=True,
                )
            with col_a:
                answer = st.checkbox("Yes", key=chk_key)
                is_safe = (answer == safe_value)
                if answer:
                    if is_safe:
                        passed_checks += 1
                        st.markdown("✅")
                    else:
                        failed_required += 1
                        st.markdown("🚨")
        st.markdown("---")

    # Verdict
    if total_checks > 0 and passed_checks > 0:
        if failed_required == 0 and passed_checks >= total_checks * 0.8:
            st.success(f"✅ {_eh_t('Your loan app passed all safety checks.')}")
        elif failed_required > 0:
            st.error(f"🚨 {_eh_t('Risk detected. See red items above.')}")
        else:
            st.warning(f"⚠️ {_eh_t('Proceed with caution — some items need attention.')}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: Recovery Notice Analyzer
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.caption(_eh_t("Received a recovery notice or legal threat? Paste it here for analysis."))

    with st.expander("📌 Recovery Notice Tips", expanded=False):
        st.markdown("""
**What to check in any recovery notice:**

| Item | What to look for |
|------|-----------------|
| Lender identity | Full registered name + RBI/NBFC number |
| Loan account | Your account/loan number must be on it |
| Outstanding amount | Should match your last statement |
| Legal section | SARFAESI notice must cite Section 13(2) |
| Timeline | 60 days minimum for secured loans |
| Signature | Authorized officer name + designation |

**🚩 Red flags — likely fake notice:**
- No loan account number
- Asks you to pay to a personal bank account or UPI ID
- Threatens arrest within 24-48 hours (banks cannot arrest you)
- Sent by WhatsApp only, no physical copy
- Grammar errors, misspelled bank name
""")

    notice_text = st.text_area(
        _eh_t("Paste Recovery Notice Text"),
        height=200,
        placeholder=(
            "Paste the full text of the recovery notice, legal threat letter, "
            "or any written communication from a lender or recovery agent here..."
        ),
        key="recovery_notice_input",
    )

    if notice_text.strip():
        if st.button(_eh_t("Analyze Notice"), type="primary", use_container_width=True, key="analyze_notice_btn"):
            with st.spinner(_eh_t("Analyzing recovery notice...")):
                notice_response = generate(
                    RECOVERY_NOTICE_PROMPT + notice_text,
                    language=st.session_state.get("user_language", "English"),
                )

            if notice_response.startswith("⚠️"):
                st.warning(_eh_t("AI unavailable - here is standard guidance:"))
                st.markdown("""
**Standard checklist for any recovery notice:**

1. **Check legitimacy** — Does it have your loan account number, lender's RBI registration, and an authorized officer's signature?
2. **Check the timeline** — SARFAESI (secured loans) requires 60 days' notice. Check the date.
3. **Do NOT pay to personal accounts** — Only pay to the official account number on your original loan agreement.
4. **Call RBI Ombudsman 14440** — If you believe the notice is unfair or the process is wrong.
5. **Get free legal help** — Call NALSA at **15100** before responding to any legal notice.
6. **Keep the original notice** — Do not throw it away — it is evidence.
""")
            else:
                st.markdown(f"### 📋 {_eh_t('Notice Analysis')}")
                st.markdown(notice_response)

                st.info(
                    "⚖️ **Free legal help:** NALSA Legal Aid — **15100** | "
                    "RBI Ombudsman — **14440** | "
                    "Cyber Crime (if fraud) — **1930**"
                )

                # Download the analysis
                st.download_button(
                    "⬇️ Save Analysis",
                    data=f"RECOVERY NOTICE ANALYSIS\n{'='*40}\n\n{notice_response}\n\n"
                         f"Emergency contacts:\nNALSA: 15100\nRBI Ombudsman: 14440\nCyber Crime: 1930",
                    file_name="notice_analysis.txt",
                    mime="text/plain",
                )
    else:
        st.info("👆 Paste the recovery notice text above, then click **Analyze Notice**.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4: Ask AI
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.caption(_eh_t("Already signed a bad document? Facing fraud or harassment? Describe your situation and get step-by-step advice."))

    user_situation = st.text_area(
        _t.get("describe_situation_label", "Describe your situation:"),
        height=150,
        placeholder=(
            _eh_t(
                "Example: A bank agent called me and said my account is blocked. "
                "He asked for my OTP to unlock it. I gave him the OTP and now money is gone from my account. "
                "What should I do? The bank is not helping me."
            )
        ),
        key="ai_situation_input",
    )

    if user_situation.strip():
        if st.button(_t.get("get_guidance_btn", "🆘 Get Emergency Guidance"), type="primary", use_container_width=True):
            with st.spinner(_eh_t("Generating personalized guidance...")):
                response = generate(AI_LEGAL_PROMPT + user_situation, language=st.session_state.get("user_language", "English"))

            if response.startswith("⚠️"):
                st.warning(_eh_t("AI unavailable - here is standard guidance:"))
                _fallback_numbers = " | ".join(
                    f"{name}: {num}"
                    for cat_items in INDIA_CONTACTS.values()
                    for name, num, _ in cat_items[:1]
                )
                st.info(
                    "**Immediate steps for financial fraud:**\n\n"
                    "1. Call **1930** for cyber financial fraud, then call your bank immediately.\n"
                    "2. Ask the bank to freeze the transaction.\n"
                    "3. File an online complaint at **cybercrime.gov.in**.\n"
                    "4. Go to the police station and file a report.\n"
                    "5. Contact **RBI Ombudsman at 14440** or cms.rbi.org.in if the bank is uncooperative.\n\n"
                    f"Emergency contacts: {_fallback_numbers}"
                )
            else:
                st.markdown(f"### 📋 {_eh_t('Personalized Guidance')}")
                st.markdown(response)
                _user_country = st.session_state.get("user_country", "🇮🇳 India")
                _quick_refs = " | ".join(
                    f"{name}: {num}"
                    for cat_items in INDIA_CONTACTS.values()
                    for name, num, _ in cat_items[:1]
                )
                st.info(f"Emergency contacts for {_user_country}: {_quick_refs}")

# ── Silent one-shot Emergency Help translation ────────────────────────────────
if _lang != "English" and mode != "limited":
    _missing_eh = [t for t in _EH_TRANS_KEYS if not _is_good_eh_translation(st.session_state.get(f"eh_t_{_lang}_{t}"))]
    if _missing_eh:
        _saved_eh = False
        _eh_payload = json.dumps({f"k{i}": t for i, t in enumerate(_missing_eh)}, ensure_ascii=False)
        _eh_prompt = (
            f"Translate these UI phrases to {_lang}. "
            "Return ONLY a valid JSON object with the same keys and translated values. "
            "Keep numbers, phone numbers, and URLs unchanged. No extra text.\n\n"
            + _eh_payload
        )
        _resp_eh = generate(_eh_prompt, language=_lang, allow_online=(mode == "online")).strip()
        _translations_eh: dict = {}
        try:
            _s = _resp_eh.find("{")
            _e = _resp_eh.rfind("}") + 1
            if _s >= 0 and _e > _s:
                _translations_eh = json.loads(_resp_eh[_s:_e])
        except Exception:
            pass
        for i, _text in enumerate(_missing_eh):
            _tr = str(_translations_eh.get(f"k{i}", "")).strip()
            if _is_good_eh_translation(_tr) and not _tr.startswith("⚠️") and _tr != _text:
                st.session_state[f"eh_t_{_lang}_{_text}"] = _tr
                _saved_eh = True
        if not _translations_eh:
            for _text in _missing_eh[:8]:
                _r_eh = generate(
                    f"Translate to {_lang}. Return ONLY the translation, nothing else:\n\n{_text}",
                    language=_lang, allow_online=(mode == "online"),
                ).strip()
                if _is_good_eh_translation(_r_eh) and not _r_eh.startswith("⚠️"):
                    st.session_state[f"eh_t_{_lang}_{_text}"] = _r_eh
                    _saved_eh = True
        if _saved_eh:
            _save_eh_tr_cache()
            st.rerun()
