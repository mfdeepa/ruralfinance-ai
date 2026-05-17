import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import importlib
from dotenv import load_dotenv
from services.ai_service import generate, detect_mode, generate_with_image
from services.rag_service import query as rag_query
from services.localization_service import translate_text
import services.ocr_service as ocr_service
ocr_service = importlib.reload(ocr_service)
extract_text_from_image = ocr_service.extract_text_from_image
extract_text_from_pdf = ocr_service.extract_text_from_pdf
extract_text_from_docx = ocr_service.extract_text_from_docx
extract_text_from_doc = ocr_service.extract_text_from_doc
is_ocr_available = ocr_service.is_ocr_available
is_pdf_support_available = ocr_service.is_pdf_support_available
is_docx_support_available = ocr_service.is_docx_support_available
get_pdf_page_count = ocr_service.get_pdf_page_count
normalize_ocr_text = ocr_service.normalize_ocr_text
from utils.styles import inject_css, sidebar_header, inject_nav_drawer
from utils.translations import get_ui
from utils.india_config import INDIA_COUNTRY_BADGE, normalize_app_language, SUPPORTED_APP_LANGUAGES

load_dotenv()

st.set_page_config(
    page_title="Document Scanner — RuralFinance AI",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
mode      = detect_mode()
_api_key  = os.getenv("GOOGLE_API_KEY", "")
_vision   = bool(_api_key) and _api_key != "your_google_api_key_here"

_qp = st.query_params
if "user_language" not in st.session_state and _qp.get("l"):
    st.session_state["user_language"] = normalize_app_language(_qp.get("l", "English"))
    st.session_state["user_country"] = INDIA_COUNTRY_BADGE
    st.session_state["user_name"] = _qp.get("n", "")
    st.session_state["onboarding_done"] = True
st.session_state["user_country"] = INDIA_COUNTRY_BADGE

sidebar_header(mode)
inject_nav_drawer("Scan Document")
_t = get_ui(st.session_state.get("user_language", "English"))

# ── Back button — top-right corner ───────────────────────────────────────────
st.markdown("""
<style>
.main .block-container,
[data-testid="stMainBlockContainer"] {
    padding-top: .4rem !important;
}
[data-testid="stMainBlockContainer"] > div:first-child {
    padding-top: 0 !important;
}
.rf-back-row {
    margin: -8px 0 8px 0;
}
.rf-back-row .stButton > button {
    width: auto !important;
    min-width: 104px !important;
    min-height: 36px !important;
    padding: 6px 14px !important;
    white-space: nowrap !important;
}
.rf-topbar-language [data-baseweb="select"] > div {
    min-height: 36px !important;
    border-radius: 12px !important;
}
</style>
""", unsafe_allow_html=True)

def _scan_page_language_changed():
    selected = normalize_app_language(st.session_state.get("_scan_page_language", "English"))
    st.session_state["user_language"] = selected
    # st.session_state["user_country"] = INDIA_COUNTRY_BADGE
    # st.query_params["li"] = "1"
    st.query_params["l"] = selected
    # st.query_params["c"] = INDIA_COUNTRY_BADGE
    # if st.session_state.get("user_name"):
        # st.query_params["n"] = st.session_state["user_name"]

_current_lang = normalize_app_language(st.session_state.get("user_language", "English"))
_lang_index = SUPPORTED_APP_LANGUAGES.index(_current_lang) if _current_lang in SUPPORTED_APP_LANGUAGES else 0

st.markdown('<div class="rf-back-row">', unsafe_allow_html=True)
_, col_lang, col_back = st.columns([6.4, 1.5, 0.9])
with col_lang:
    st.markdown('<div class="rf-topbar-language">', unsafe_allow_html=True)
    st.selectbox(
        "🌐 Language",
        SUPPORTED_APP_LANGUAGES,
        index=_lang_index,
        key="_scan_page_language",
        label_visibility="collapsed",
        on_change=_scan_page_language_changed,
    )
    st.markdown('</div>', unsafe_allow_html=True)
with col_back:
    if st.button(_t.get("back_btn", "🏠 Back"), key="btn_back_home", use_container_width=True):
        st.session_state["onboarding_done"] = True
        st.switch_page("Home.py")
st.markdown('</div>', unsafe_allow_html=True)
_t = get_ui(st.session_state.get("user_language", "English"))

# ══════════════════════════════════════════════════════════════════════════════
# PROMPTS
# ══════════════════════════════════════════════════════════════════════════════
def get_dynamic_prompts():
    """Fetches prompts with the current user language injected."""
    # This ensures the prompt updates immediately if the user changes language
    lang = st.session_state.get("user_language", "English")
    
    vision_prompt = f"""\
You are a financial safety expert protecting a rural Indian borrower from predatory lending.
CRITICAL: You MUST write the entire report in {lang}. Do not use English.
Analyse this financial document image and produce a COMPLETE SAFETY REPORT.

CRITICAL GROUNDING RULES:
- Use only facts that are visible in this document image.
- Do not invent fees, rates, clauses, penalties, EMI, GST, processing fee, stamp duty, documentation fee, prepayment penalty, acceleration clause, legal fee, or insurance amount.
- Every detected charge or risk must include a short evidence quote from the document.
- If a charge or risky clause is not visible, write "Not found in document" instead of guessing.
- If wording is vague, mark it as "Needs bank confirmation" and quote the exact vague wording.
- Do not calculate EMI or total repayment unless the loan amount, rate, and tenure are clearly available. If not enough data, say what is missing.
- For an SBI/KCC sanction letter, do not claim processing fee, GST, stamp duty, documentation fee, prepayment penalty, or acceleration unless those words or amounts are present.
- Write all explanations, summaries, and questions in {lang}.

**1. DOCUMENT TYPE**
What exactly is this? (Loan Agreement / KCC / Insurance Policy / EMI Schedule / Bank Notice / etc. in {user_lang})

**2. CHARGES FOUND IN THIS DOCUMENT**
List only charges, fees, penalties, insurance amounts, taxes, or costs explicitly visible in the document.
Format as a table:
| Charge | Amount / Rate | Mandatory? | Evidence quote |
If an important fee is not present, put it under "Not found / ask bank" instead of treating it as a real charge.

**3. KEY LOAN NUMBERS**
- Loan Amount:
- Interest Rate: (FLAT RATE or REDUCING BALANCE - state clearly)
- Monthly EMI:
- Loan Tenure:
- Total repayment:
- Missing information needed for exact calculation:
Only warn about flat rate if the document actually says flat rate.

**4. HIDDEN & RISKY CLAUSES FOUND**
Only report risky clauses that are actually present. For each finding:
| Category | Evidence quote | Why it matters | What to ask |
Check for interest changes, vague insurance wording, penalties, collateral/security, recovery terms, Aadhaar/PAN/KYC privacy consent, UPI/NACH/ECS auto-debit, digital loan app permissions, arbitration, waiver of rights, prepayment, GST, and ambiguous "as applicable" language.
Do not say a clause exists unless the document supports it.

**5. SAFETY SCORE: [X] / 100**
Give an honest score using only evidence-backed risks. Do not deduct for hypothetical charges not present in the document.

**6. PLAIN LANGUAGE SUMMARY**
In 3-4 sentences: explain what this document means for the borrower in the simplest possible words.
Imagine explaining to a farmer who has never taken a bank loan before.

**7. DO THIS BEFORE SIGNING**
4-5 specific actions based on WHAT YOU FOUND in this exact document. Be concrete.

**8. QUESTIONS TO ASK YOUR BANK OFFICER**
5 specific questions directly related to the risks you found above.

**9. YOUR RIGHTS**
2-3 relevant Indian borrower rights. Mention RBI Ombudsman/Fair Practices only when clearly relevant.
"""

UNDERSTAND_PROMPT = """\
You are a financial safety expert protecting a rural Indian borrower.
The borrower pasted this financial document text. Produce a COMPLETE SAFETY REPORT.
CRITICAL: You MUST output the entire report in {lang}. Do not use English.

CRITICAL GROUNDING RULES:
- Use only facts written in the provided document text.
- Do not invent fees, rates, clauses, penalties, EMI, GST, processing fee, stamp duty, documentation fee, prepayment penalty, acceleration clause, legal fee, or insurance amount.
- Every detected charge or risk must include a short evidence quote from the document.
- If a charge or risky clause is not found, write "Not found in document" instead of guessing.
- If wording is vague, mark it as "Needs bank confirmation" and quote the exact wording.
- Do not calculate EMI or total repayment unless the loan amount, rate, and tenure are clearly available. If not enough data, say what is missing.
- For an SBI/KCC sanction letter, do not claim processing fee, GST, stamp duty, documentation fee, prepayment penalty, or acceleration unless those words or amounts are present.
- Write all explanations, summaries, and questions in {lang}.

**1. DOCUMENT TYPE**
What exactly is this document?

**2. CHARGES FOUND IN THIS DOCUMENT**
List only charges, fees, penalties, insurance amounts, taxes, or costs explicitly written in the document.
Format as a table:
| Charge | Amount / Rate | Mandatory? | Evidence quote |
If an important fee is not present, put it under "Not found / ask bank" instead of treating it as a real charge.

**3. KEY LOAN NUMBERS**
- Loan Amount:
- Interest Rate: (FLAT RATE or REDUCING BALANCE - state clearly)
- Monthly EMI:
- Loan Tenure:
- Total repayment:
- Missing information needed for exact calculation:
Only warn about flat rate if the document actually says flat rate.

**4. HIDDEN & RISKY CLAUSES**
Only report risky clauses that are actually present. For each finding:
| Category | Evidence quote | Why it matters | What to ask |
Check for interest changes, vague insurance wording, penalties, collateral/security, recovery terms, Aadhaar/PAN/KYC privacy consent, UPI/NACH/ECS auto-debit, digital loan app permissions, arbitration, waiver of rights, prepayment, GST, and ambiguous "as applicable" language.
Do not say a clause exists unless the document supports it.

**5. SAFETY SCORE: [X] / 100**
Honest score using only evidence-backed risks. Do not deduct for hypothetical charges not present in the document.

**6. PLAIN LANGUAGE SUMMARY**
3-4 sentences explaining what this document means for the borrower in the simplest words.

**7. DO THIS BEFORE SIGNING**
4-5 concrete specific actions.

**8. QUESTIONS TO ASK YOUR BANK OFFICER**
5 specific questions based on what you found.

**9. YOUR RIGHTS**
2-3 relevant Indian borrower rights. Mention RBI Ombudsman/Fair Practices only when clearly relevant.

Document Text:
"""

RISKY_KEYWORDS = {
    "penalty":              "Extra charges if you miss payments or break any condition.",
    "foreclosure":          "Bank can take away your property if you can't repay the loan.",
    "prepayment":           "You'll be charged extra if you pay off the loan early.",
    "balloon":              "A large final payment due at the end — much bigger than regular EMIs.",
    "cross-default":        "Defaulting on one loan can trigger default on all your other loans.",
    "auto-renewal":         "Agreement renews automatically and charges you unless you cancel.",
    "arbitration":          "Disputes go to private arbitration — you cannot go to consumer court.",
    "irrevocable":          "This clause cannot be undone once you sign.",
    "collateral":           "Bank can seize your pledged property or asset.",
    "floating rate":        "Interest rate can increase anytime — your EMI may go up.",
    "processing fee":       "Upfront fee deducted from loan before you receive money.",
    "insurance":            "Insurance may be mandatory — often overpriced, commission for bank.",
    "personal guarantee":   "A family member's assets are also at risk if you default.",
    "unlimited liability":  "No cap on what you can owe — extremely dangerous clause.",
    "acceleration":         "If you miss one EMI, the ENTIRE loan becomes due immediately.",
    "penal interest":       "Extra interest (2–3%) charged on top of normal rate when you miss EMI.",
    "stamp duty":           "Government fee for registering the loan agreement.",
    "hypothecation":        "Bank holds rights over your asset (vehicle/machine) as security.",
}

RISKY_KEYWORDS.update({
    "administrative charge": "Extra administration cost added on top of interest.",
    "documentation fee": "Fee for paperwork. Ask whether it is deducted before disbursal.",
    "onboarding charge": "One-time joining charge that reduces the money you actually receive.",
    "verification fee": "Background-check fee. Ask for exact amount and refund rules.",
    "credit shield": "Bundled insurance. Ask if it is optional and refundable.",
    "loan protection": "Bundled protection plan that may increase total repayment.",
    "emi bounce": "Penalty charged every time an EMI auto-debit fails.",
    "ecs": "Auto-debit mandate. Ask bounce charges and cancellation process.",
    "nach": "Auto-debit mandate. Failed attempts can add repeated penalties.",
    "overdue interest": "Extra interest charged after a missed due date.",
    "daily penal interest": "Penalty interest may grow every day until paid.",
    "loan closure fee": "Extra fee to close the loan account.",
    "platform usage": "Digital platform charge that may be recurring.",
    "convenience fee": "Extra payment charge, often hidden in fine print.",
    "subscription fee": "Recurring fee that can continue unless cancelled.",
    "recovery agent": "Recovery cost may be added to your outstanding loan.",
    "repossession": "Lender may take the financed asset if you default.",
    "legal recovery cost": "Legal costs may be charged to the borrower.",
    "sms access": "Digital lender may read SMS data, which is a privacy risk.",
    "contact access": "Digital lender may access contacts, creating harassment risk.",
    "device tracking": "App may track device/location data.",
    "third-party data sharing": "Your data may be shared outside the lender.",
    "marketing consent": "You may be agreeing to promotional calls/messages.",
    "waiver of rights": "Borrower may be giving up legal protections.",
    "sole discretion": "Lender can decide or change terms unilaterally.",
    "charges may apply": "Vague fee language. Demand exact rupee amounts before signing.",
    "as applicable": "Undefined fee language. Ask for a written itemized schedule.",
    "subject to change": "Terms or charges may change after signing.",
})

DOC_TYPE_PATTERNS = {
    "Loan Agreement":        ["loan agreement", "borrower", "lender", "principal amount", "repayment"],
    "KCC / Agricultural Loan": ["kcc", "kisan credit", "agricultural", "crop loan", "kisaan"],
    "EMI Schedule":          ["emi schedule", "installment schedule", "repayment schedule"],
    "Bank Notice":           ["dear customer", "bank notice", "this is to inform", "kindly note"],
    "Insurance Policy":      ["insurance", "premium", "sum assured", "policy number", "insured"],
    "Investment Document":   ["mutual fund", "sip", "nav", "portfolio", "returns", "investment"],
    "Credit Card Statement": ["credit card", "minimum due", "credit limit", "outstanding", "statement"],
    "Property / Mortgage":   ["mortgage", "property", "title deed", "registration", "stamp duty"],
}


# ── Rule-based fallback (no AI) ───────────────────────────────────────────────
RISK_CATEGORIES = {
    "Charges & Fees": [
        "processing fee", "administrative charge", "documentation fee", "onboarding charge",
        "verification fee", "stamp duty", "legal fee", "inspection", "valuation fee", "gst",
        "platform usage", "convenience fee", "subscription fee",
    ],
    "Insurance & Add-ons": ["insurance", "insurance premium", "credit shield", "loan protection"],
    "Penalty & Repayment": [
        "penalty", "penal interest", "emi bounce", "ecs", "nach", "overdue interest",
        "daily penal interest", "prepayment", "foreclosure", "loan closure fee",
    ],
    "Interest Risk": ["floating rate", "subject to change", "as applicable", "flat rate"],
    "Security & Recovery": [
        "collateral", "hypothecation", "personal guarantee", "recovery agent",
        "repossession", "legal recovery cost", "foreclosure",
    ],
    "Privacy & Consent": [
        "sms access", "contact access", "device tracking", "third-party data sharing",
        "marketing consent",
    ],
    "Legal Rights": ["arbitration", "waiver of rights", "sole discretion", "irrevocable"],
    "Ambiguous Wording": ["charges may apply", "as applicable", "subject to change"],
}

FIELD_PATTERNS = {
    "Borrower": [r"name of the borrower\s+([^\n\r]+)", r"to,\s*\n\s*([a-z .]+)"],
    "Loan Amount / Sanction Limit": [
        r"(?:sanction limit|loan amount|principal amount|crop loan)\s*[:\-]?\s*(?:rs\.?|₹|inr)?\s*([\d,]+(?:\.\d+)?)",
        r"(?:rs\.?|₹|inr)\s*([\d,]+(?:\.\d+)?)\s*/?\-?\s*\([^)]+\)",
    ],
    "Interest Rate": [
        r"(?:interest rate|rate of interest)\s*[:\-]?\s*([^\n\r]+?%[^\n\r]*)",
        r"(\d+(?:\.\d+)?\s*%\s*(?:p\.a\.|per annum|per year)[^\n\r]*)",
    ],
    "Repayment Period": [r"(?:repayment period|tenure|loan tenure)\s*[:\-]?\s*([^\n\r]+)", r"within\s+(\d+\s*(?:months?|years?)[^\n\r]*)"],
    "Security": [r"(?:security|collateral)\s*[:\-]?\s*([^\n\r]+)", r"(hypothecation[^\n\r]+)"],
    "Insurance": [r"insurance\s*[:\-]?\s*([^\n\r]+)"],
    "Other Terms": [r"(?:other terms\s*&\s*conditions|terms and conditions)\s*[:\-]?\s*([^\n\r]+)"],
}


def _clean_value(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" :-|")[:160]


def _extract_key_fields(text: str) -> dict:
    compact = normalize_ocr_text(text)
    fields = {}
    for label, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            m = re.search(pattern, compact, flags=re.I)
            if m:
                value = _clean_value(m.group(1))
                if value:
                    fields[label] = value
                    break
    return fields


def _evidence_for(text: str, keyword: str) -> str:
    lines = [ln.strip() for ln in normalize_ocr_text(text).splitlines() if ln.strip()]
    for line in lines:
        if keyword.lower() in line.lower():
            return line[:220]
    m = re.search(rf".{{0,80}}{re.escape(keyword)}.{{0,100}}", normalize_ocr_text(text), flags=re.I)
    return _clean_value(m.group(0)) if m else "Found in extracted text"


def _risk_score(found_risks: dict, is_flat: bool) -> int:
    score = 0
    high = {"unlimited liability", "waiver of rights", "acceleration", "recovery agent", "repossession"}
    medium = {"penal interest", "foreclosure", "personal guarantee", "arbitration", "sole discretion"}
    for kw in found_risks:
        if kw in high:
            score += 18
        elif kw in medium:
            score += 12
        elif kw in ("as applicable", "subject to change", "charges may apply"):
            score += 8
        else:
            score += 6
    if is_flat:
        score += 12
    return max(0, min(100, score))


def _risk_label(score: int) -> str:
    if score <= 20:
        return "Safe"
    if score <= 40:
        return "Low Risk"
    if score <= 60:
        return "Medium Risk"
    if score <= 80:
        return "High Risk"
    return "Critical Risk"


def _missing_confirmations(fields: dict, charges: dict, risks: dict) -> list[str]:
    checks = []
    if "Loan Amount / Sanction Limit" not in fields:
        checks.append("Exact loan amount / sanction limit")
    if "Interest Rate" not in fields:
        checks.append("Exact interest rate and whether it can change")
    if "Repayment Period" not in fields:
        checks.append("Repayment period / due date")
    if not charges:
        checks.append("Full written list of processing fee, stamp duty, GST, insurance, and other charges")
    if "Insurance" in fields or "insurance" in risks:
        checks.append("Whether insurance is mandatory, optional, refundable, and its exact premium")
    if "Security" in fields or "hypothecation" in risks or "collateral" in risks:
        checks.append("What asset or document is kept as security and when it will be released")
    if "penal interest" in risks or "penalty" in risks:
        checks.append("Exact late-payment penalty and how it is calculated")
    if "as applicable" in risks or "subject to change" in risks:
        checks.append("All vague terms in fixed rupee amounts")
    return list(dict.fromkeys(checks))[:8]


def _questions_to_ask(fields: dict, risks: dict, charges: dict) -> list[str]:
    questions = [
        "What is the total amount I will repay, including interest and every fee?",
        "Which charges will be deducted before I receive the loan money?",
        "What happens if I miss one payment or pay after the due date?",
        "Can I get a signed copy of the full agreement and charges list today?",
    ]
    if "Interest Rate" in fields:
        questions.insert(1, "Is this interest rate fixed, floating, or changeable later?")
    if "insurance" in risks or "Insurance" in fields:
        questions.append("Is insurance compulsory? What is the exact premium and can I refuse it?")
    if "hypothecation" in risks or "Security" in fields:
        questions.append("Which asset or document is security, and when will the bank release it?")
    if charges:
        questions.append("Please write each fee separately: processing, stamp duty, GST, documentation, insurance, and penalty.")
    return list(dict.fromkeys(questions))[:7]


def _document_completeness_warnings(text: str, page_count: int = 0) -> list[str]:
    """Detect structural completeness issues and return plain-English warning strings."""
    warnings_list = []
    t = text.lower()

    # ── Page-number gap detection ───────────────────────────────────────────
    import re as _re
    page_nums_found = [int(m) for m in _re.findall(r'page\s*(\d+)', t)]
    if page_nums_found and len(page_nums_found) >= 2:
        page_nums_found = sorted(set(page_nums_found))
        for i in range(len(page_nums_found) - 1):
            if page_nums_found[i + 1] - page_nums_found[i] > 1:
                for missing_pg in range(page_nums_found[i] + 1, page_nums_found[i + 1]):
                    warnings_list.append(f"⚠️ Page {missing_pg} appears to be missing from this document.")
    elif page_count > 1 and not page_nums_found:
        pass  # PDF page count is reliable; no text-level gap detection needed

    # ── Required sections for loan documents ───────────────────────────────
    has_emi_schedule    = any(k in t for k in ["emi schedule", "repayment schedule", "payment schedule",
                                                "installment schedule", "amortization"])
    has_insurance       = any(k in t for k in ["insurance", "credit shield", "loan protection", "premium"])
    has_insurance_terms = any(k in t for k in ["insurance premium", "insurance amount", "insurance charge"])
    has_rate            = any(k in t for k in ["interest rate", "rate of interest", "apr", "% per annum", "% p.a"])
    has_tenure          = any(k in t for k in ["tenure", "repayment period", "loan period", "months", "years"])
    has_signature       = any(k in t for k in ["signature", "sign here", "borrower sign", "signed by",
                                                "applicant signature", "हस्ताक्षर"])
    has_emi_amount      = bool(_re.search(r'(?:emi|instalment|installment)[:\s]+(?:rs\.?|₹)?\s*[\d,]+', t))
    has_sanction_letter = any(k in t for k in ["sanction letter", "sanctioned amount", "loan sanctioned",
                                                "sanction limit"])
    has_foreclosure     = any(k in t for k in ["foreclosure", "prepayment", "pre-payment"])

    if not has_emi_schedule and not has_emi_amount:
        warnings_list.append("⚠️ EMI repayment schedule not found. Ask bank for the full month-by-month payment table.")
    if has_insurance and not has_insurance_terms:
        warnings_list.append("⚠️ Insurance is mentioned but premium amount/terms are not clear. Request the insurance annexure.")
    if not has_rate:
        warnings_list.append("⚠️ Interest rate section is not clearly visible. Verify the exact rate before signing.")
    if not has_tenure:
        warnings_list.append("⚠️ Loan tenure / repayment period not detected. Confirm the exact number of months.")
    if not has_signature:
        warnings_list.append("⚠️ Signature page not detected. Ensure you have the complete agreement with signature pages.")
    if has_sanction_letter and not has_emi_schedule:
        warnings_list.append("⚠️ Sanction letter detected but EMI schedule annexure appears missing.")
    if not has_foreclosure:
        warnings_list.append("ℹ️ Foreclosure / prepayment terms not found. Ask the bank what charges apply if you repay early.")

    return warnings_list


SCAN_TEXT = {
    "Hindi": {
        "instant_done": "तुरंत स्कैन पूरा — ऑफलाइन सुरक्षा रिपोर्ट तैयार है।",
        "instant_caption": "यह रिपोर्ट दस्तावेज़ से निकाले गए टेक्स्ट से तुरंत बनती है। यह Gemma का इंतज़ार नहीं करती, इसलिए स्कैन तेज़ रहता है।",
        "document_type": "दस्तावेज़ का प्रकार",
        "safety_score": "सुरक्षा स्कोर",
        "risk_level": "जोखिम स्तर",
        "flat_rate": "फ्लैट रेट मिला",
        "key_details": "1. मिली हुई मुख्य जानकारी",
        "charges": "2. शुल्क और फीस",
        "no_charges": "कोई साफ़ शुल्क राशि नहीं मिली। हस्ताक्षर करने से पहले बैंक से हर शुल्क की लिखित सूची लें।",
        "figures": "3. वित्तीय आंकड़े",
        "amounts": "रकम:",
        "tenure": "अवधि:",
        "interest_rates": "ब्याज दर:",
        "hidden_risks": "4. छिपे हुए जोखिम",
        "risk_terms": "4. जोखिम वाले शब्द",
        "no_risks": "4. छिपे हुए जोखिम\nइस टेक्स्ट स्कैन में कोई बड़ा जोखिम शब्द साफ़ नहीं मिला।",
        "evidence": "दस्तावेज़ में प्रमाण",
        "confirm": "5. हस्ताक्षर से पहले पुष्टि करें",
        "questions": "6. बैंक अधिकारी से पूछने वाले सवाल",
        "checklist": "**हस्ताक्षर से पहले जांचें:** कुल भुगतान · सभी शुल्क · जुर्माना · बीमा · सुरक्षा/गिरवी · देय तारीख · समझौते की हस्ताक्षरित कॉपी।",
        "issue": "मुद्दा",
        "Loan Agreement": "ऋण समझौता",
        "KCC / Agricultural Loan": "KCC / कृषि ऋण",
        "EMI Schedule": "EMI अनुसूची",
        "Bank Notice": "बैंक नोटिस",
        "Insurance Policy": "बीमा पॉलिसी",
        "Financial Document": "वित्तीय दस्तावेज़",
        "Safe": "सुरक्षित",
        "Low Risk": "कम जोखिम",
        "Medium Risk": "मध्यम जोखिम",
        "High Risk": "अधिक जोखिम",
        "Critical Risk": "गंभीर जोखिम",
        "Borrower": "उधारकर्ता",
        "Loan Amount / Sanction Limit": "ऋण राशि / स्वीकृत सीमा",
        "Interest Rate": "ब्याज दर",
        "Repayment Period": "भुगतान अवधि",
        "Security": "सुरक्षा / गिरवी",
        "Insurance": "बीमा",
        "Other Terms": "अन्य शर्तें",
        "Charges & Fees": "शुल्क और फीस",
        "Insurance & Add-ons": "बीमा और अतिरिक्त सेवाएं",
        "Penalty & Repayment": "जुर्माना और भुगतान",
        "Interest Risk": "ब्याज जोखिम",
        "Security & Recovery": "सुरक्षा और वसूली",
        "Privacy & Consent": "गोपनीयता और सहमति",
        "Legal Rights": "कानूनी अधिकार",
        "Ambiguous Wording": "अस्पष्ट भाषा",
        "Exact loan amount / sanction limit": "सटीक ऋण राशि / स्वीकृत सीमा",
        "Exact interest rate and whether it can change": "सटीक ब्याज दर और क्या यह बाद में बदल सकती है",
        "Repayment period / due date": "भुगतान अवधि / देय तारीख",
        "Full written list of processing fee, stamp duty, GST, insurance, and other charges": "प्रोसेसिंग फीस, स्टाम्प ड्यूटी, GST, बीमा और सभी शुल्क की लिखित सूची",
        "Whether insurance is mandatory, optional, refundable, and its exact premium": "बीमा अनिवार्य है या वैकल्पिक, रिफंड होगा या नहीं, और उसका सटीक प्रीमियम",
        "What asset or document is kept as security and when it will be released": "कौन सी संपत्ति या दस्तावेज़ सुरक्षा में रखा गया है और कब वापस मिलेगा",
        "Exact late-payment penalty and how it is calculated": "देरी से भुगतान का सटीक जुर्माना और उसकी गणना कैसे होगी",
        "All vague terms in fixed rupee amounts": "सभी अस्पष्ट शर्तों को निश्चित रुपये की राशि में लिखवाएं",
        "What is the total amount I will repay, including interest and every fee?": "ब्याज और हर शुल्क मिलाकर मुझे कुल कितना पैसा चुकाना होगा?",
        "Is this interest rate fixed, floating, or changeable later?": "यह ब्याज दर स्थिर है, बदलने वाली है, या बाद में बदली जा सकती है?",
        "Which charges will be deducted before I receive the loan money?": "लोन का पैसा मिलने से पहले कौन-कौन से शुल्क काटे जाएंगे?",
        "What happens if I miss one payment or pay after the due date?": "अगर मैं एक किस्त चूक जाऊं या देरी से भरूं तो क्या होगा?",
        "Can I get a signed copy of the full agreement and charges list today?": "क्या मुझे आज पूरा समझौता और शुल्क सूची की हस्ताक्षरित कॉपी मिल सकती है?",
        "Is insurance compulsory? What is the exact premium and can I refuse it?": "क्या बीमा अनिवार्य है? सटीक प्रीमियम कितना है और क्या मैं इसे मना कर सकता/सकती हूं?",
        "Which asset or document is security, and when will the bank release it?": "कौन सी संपत्ति या दस्तावेज़ सुरक्षा है, और बैंक उसे कब छोड़ेगा?",
        "Please write each fee separately: processing, stamp duty, GST, documentation, insurance, and penalty.": "कृपया हर शुल्क अलग-अलग लिखें: प्रोसेसिंग, स्टाम्प ड्यूटी, GST, दस्तावेज़, बीमा और जुर्माना।",
    },
    "Bengali": {
        "instant_done": "তাৎক্ষণিক স্ক্যান সম্পন্ন — অফলাইন নিরাপত্তা রিপোর্ট তৈরি হয়েছে।",
        "instant_caption": "এই রিপোর্টটি ডকুমেন্ট থেকে পাওয়া লেখা ব্যবহার করে সঙ্গে সঙ্গে তৈরি হয়। এটি Gemma-এর জন্য অপেক্ষা করে না, তাই স্ক্যান দ্রুত থাকে।",
        "document_type": "ডকুমেন্টের ধরন",
        "safety_score": "নিরাপত্তা স্কোর",
        "risk_level": "ঝুঁকির স্তর",
        "flat_rate": "ফ্ল্যাট রেট পাওয়া গেছে",
        "key_details": "1. পাওয়া প্রধান তথ্য",
        "charges": "2. চার্জ ও ফি",
        "no_charges": "কোনও পরিষ্কার ফি-র পরিমাণ পাওয়া যায়নি। সই করার আগে ব্যাংকের কাছ থেকে সব চার্জের লিখিত তালিকা নিন।",
        "figures": "3. আর্থিক সংখ্যা",
        "amounts": "টাকার পরিমাণ:",
        "tenure": "মেয়াদ:",
        "interest_rates": "সুদের হার:",
        "hidden_risks": "4. লুকানো ঝুঁকি",
        "risk_terms": "4. ঝুঁকিপূর্ণ শব্দ",
        "no_risks": "4. লুকানো ঝুঁকি\nএই টেক্সট স্ক্যানে বড় কোনও ঝুঁকিপূর্ণ শব্দ স্পষ্টভাবে পাওয়া যায়নি।",
        "evidence": "ডকুমেন্টে প্রমাণ",
        "confirm": "5. সই করার আগে নিশ্চিত করুন",
        "questions": "6. ব্যাংক কর্মকর্তাকে জিজ্ঞাসা করার প্রশ্ন",
        "checklist": "**সই করার আগে পরীক্ষা করুন:** মোট পরিশোধ · সব ফি · জরিমানা · বীমা · জামানত/সিকিউরিটি · শেষ তারিখ · চুক্তির সই করা কপি।",
        "issue": "সমস্যা",
        "Loan Agreement": "ঋণ চুক্তি",
        "KCC / Agricultural Loan": "KCC / কৃষি ঋণ",
        "EMI Schedule": "EMI সময়সূচি",
        "Bank Notice": "ব্যাংক নোটিশ",
        "Insurance Policy": "বীমা পলিসি",
        "Financial Document": "আর্থিক ডকুমেন্ট",
        "Safe": "নিরাপদ",
        "Low Risk": "কম ঝুঁকি",
        "Medium Risk": "মাঝারি ঝুঁকি",
        "High Risk": "উচ্চ ঝুঁকি",
        "Critical Risk": "গুরুতর ঝুঁকি",
        "Borrower": "ঋণগ্রহীতা",
        "Loan Amount / Sanction Limit": "ঋণের পরিমাণ / অনুমোদিত সীমা",
        "Interest Rate": "সুদের হার",
        "Repayment Period": "পরিশোধের সময়",
        "Security": "সিকিউরিটি / জামানত",
        "Insurance": "বীমা",
        "Other Terms": "অন্যান্য শর্ত",
        "Charges & Fees": "চার্জ ও ফি",
        "Insurance & Add-ons": "বীমা ও অতিরিক্ত পরিষেবা",
        "Penalty & Repayment": "জরিমানা ও পরিশোধ",
        "Interest Risk": "সুদের ঝুঁকি",
        "Security & Recovery": "সিকিউরিটি ও পুনরুদ্ধার",
        "Privacy & Consent": "গোপনীয়তা ও সম্মতি",
        "Legal Rights": "আইনি অধিকার",
        "Ambiguous Wording": "অস্পষ্ট ভাষা",
        "Exact loan amount / sanction limit": "সঠিক ঋণের পরিমাণ / অনুমোদিত সীমা",
        "Exact interest rate and whether it can change": "সঠিক সুদের হার এবং তা পরে বদলাতে পারে কি না",
        "Repayment period / due date": "পরিশোধের সময় / শেষ তারিখ",
        "Full written list of processing fee, stamp duty, GST, insurance, and other charges": "প্রসেসিং ফি, স্ট্যাম্প ডিউটি, GST, বীমা এবং সব চার্জের লিখিত তালিকা",
        "Whether insurance is mandatory, optional, refundable, and its exact premium": "বীমা বাধ্যতামূলক না ঐচ্ছিক, ফেরতযোগ্য কি না, এবং সঠিক প্রিমিয়াম কত",
        "What asset or document is kept as security and when it will be released": "কোন সম্পদ বা ডকুমেন্ট সিকিউরিটি হিসেবে রাখা হয়েছে এবং কখন ছাড়া হবে",
        "Exact late-payment penalty and how it is calculated": "দেরিতে পরিশোধের সঠিক জরিমানা এবং তা কীভাবে হিসাব হবে",
        "All vague terms in fixed rupee amounts": "সব অস্পষ্ট শর্ত নির্দিষ্ট টাকার পরিমাণে লিখিয়ে নিন",
        "What is the total amount I will repay, including interest and every fee?": "সুদ এবং সব ফি মিলিয়ে আমাকে মোট কত টাকা পরিশোধ করতে হবে?",
        "Is this interest rate fixed, floating, or changeable later?": "এই সুদের হার স্থির, পরিবর্তনশীল, নাকি পরে বদলানো যেতে পারে?",
        "Which charges will be deducted before I receive the loan money?": "ঋণের টাকা পাওয়ার আগে কোন কোন চার্জ কেটে নেওয়া হবে?",
        "What happens if I miss one payment or pay after the due date?": "আমি এক কিস্তি মিস করলে বা দেরিতে দিলে কী হবে?",
        "Can I get a signed copy of the full agreement and charges list today?": "আমি কি আজ সম্পূর্ণ চুক্তি এবং চার্জ তালিকার সই করা কপি পেতে পারি?",
        "Is insurance compulsory? What is the exact premium and can I refuse it?": "বীমা কি বাধ্যতামূলক? সঠিক প্রিমিয়াম কত এবং আমি কি এটি না নিতে পারি?",
        "Which asset or document is security, and when will the bank release it?": "কোন সম্পদ বা ডকুমেন্ট সিকিউরিটি, এবং ব্যাংক কখন সেটি ছাড়বে?",
        "Please write each fee separately: processing, stamp duty, GST, documentation, insurance, and penalty.": "প্রতিটি ফি আলাদা করে লিখুন: প্রসেসিং, স্ট্যাম্প ডিউটি, GST, ডকুমেন্টেশন, বীমা এবং জরিমানা।",
    },
    "Tamil": {
        "instant_done": "உடனடி ஸ்கேன் முடிந்தது — ஆஃப்லைன் பாதுகாப்பு அறிக்கை உருவாக்கப்பட்டது.",
        "instant_caption": "இந்த அறிக்கை ஆவணத்தில் இருந்து எடுத்த உரையிலிருந்து உடனே உருவாகிறது. இது Gemma-க்காக காத்திருக்காது, அதனால் ஸ்கேன் வேகமாக இருக்கும்.",
        "document_type": "ஆவண வகை",
        "safety_score": "பாதுகாப்பு மதிப்பெண்",
        "risk_level": "ஆபத்து நிலை",
        "flat_rate": "Flat rate கண்டறியப்பட்டது",
        "key_details": "1. கண்டறியப்பட்ட முக்கிய விவரங்கள்",
        "charges": "2. கட்டணங்கள் மற்றும் fees",
        "no_charges": "தெளிவான கட்டணத் தொகை கிடைக்கவில்லை. கையெழுத்திடுவதற்கு முன் எல்லா கட்டணங்களின் எழுத்துப் பட்டியலை வங்கியிடம் கேளுங்கள்.",
        "figures": "3. நிதி எண்கள்",
        "amounts": "தொகைகள்:",
        "tenure": "காலம்:",
        "interest_rates": "வட்டி விகிதங்கள்:",
        "hidden_risks": "4. மறைந்துள்ள ஆபத்துகள்",
        "risk_terms": "4. ஆபத்து சொற்கள்",
        "no_risks": "4. மறைந்துள்ள ஆபத்துகள்\nஇந்த உரை ஸ்கேனில் தெளிவான பெரிய ஆபத்து சொற்கள் இல்லை.",
        "evidence": "ஆவணத்தில் ஆதாரம்",
        "confirm": "5. கையெழுத்திடுவதற்கு முன் உறுதி செய்யுங்கள்",
        "questions": "6. வங்கி அதிகாரியிடம் கேட்க வேண்டிய கேள்விகள்",
        "checklist": "**கையெழுத்திடுவதற்கு முன் சரிபார்க்கவும்:** மொத்த திருப்பிச் செலுத்தல் · எல்லா கட்டணங்கள் · அபராதம் · காப்பீடு · அடமானம்/பாதுகாப்பு · கடைசி தேதி · ஒப்பந்தத்தின் கையெழுத்திட்ட நகல்.",
        "issue": "பிரச்சினை",
        "Loan Agreement": "கடன் ஒப்பந்தம்",
        "KCC / Agricultural Loan": "KCC / வேளாண் கடன்",
        "EMI Schedule": "EMI அட்டவணை",
        "Bank Notice": "வங்கி அறிவிப்பு",
        "Insurance Policy": "காப்பீட்டு பாலிசி",
        "Financial Document": "நிதி ஆவணம்",
        "Safe": "பாதுகாப்பானது",
        "Low Risk": "குறைந்த ஆபத்து",
        "Medium Risk": "நடுத்தர ஆபத்து",
        "High Risk": "அதிக ஆபத்து",
        "Critical Risk": "மிகவும் ஆபத்தானது",
        "Borrower": "கடன் பெறுபவர்",
        "Loan Amount / Sanction Limit": "கடன் தொகை / அங்கீகரிக்கப்பட்ட வரம்பு",
        "Interest Rate": "வட்டி விகிதம்",
        "Repayment Period": "திருப்பிச் செலுத்தும் காலம்",
        "Security": "பாதுகாப்பு / அடமானம்",
        "Insurance": "காப்பீடு",
        "Other Terms": "மற்ற நிபந்தனைகள்",
        "Charges & Fees": "கட்டணங்கள் மற்றும் fees",
        "Insurance & Add-ons": "காப்பீடு மற்றும் கூடுதல் சேவைகள்",
        "Penalty & Repayment": "அபராதம் மற்றும் திருப்பிச் செலுத்தல்",
        "Interest Risk": "வட்டி ஆபத்து",
        "Security & Recovery": "பாதுகாப்பு மற்றும் வசூல்",
        "Privacy & Consent": "தனியுரிமை மற்றும் சம்மதம்",
        "Legal Rights": "சட்ட உரிமைகள்",
        "Ambiguous Wording": "தெளிவில்லாத சொற்கள்",
        "Exact loan amount / sanction limit": "சரியான கடன் தொகை / அங்கீகரிக்கப்பட்ட வரம்பு",
        "Exact interest rate and whether it can change": "சரியான வட்டி விகிதம் மற்றும் அது பின்னர் மாறுமா",
        "Repayment period / due date": "திருப்பிச் செலுத்தும் காலம் / கடைசி தேதி",
        "Full written list of processing fee, stamp duty, GST, insurance, and other charges": "Processing fee, stamp duty, GST, காப்பீடு மற்றும் மற்ற கட்டணங்களின் முழு எழுத்துப் பட்டியல்",
        "Whether insurance is mandatory, optional, refundable, and its exact premium": "காப்பீடு கட்டாயமா, விருப்பமா, திரும்ப கிடைக்குமா, அதன் சரியான premium எவ்வளவு",
        "What asset or document is kept as security and when it will be released": "எந்த சொத்து அல்லது ஆவணம் பாதுகாப்பாக வைக்கப்பட்டுள்ளது, அது எப்போது விடுவிக்கப்படும்",
        "Exact late-payment penalty and how it is calculated": "தாமத கட்டணத்தின் சரியான அபராதம் மற்றும் அது எப்படிக் கணக்கிடப்படும்",
        "All vague terms in fixed rupee amounts": "அனைத்து தெளிவில்லாத நிபந்தனைகளையும் உறுதியான ரூபாய் தொகையாக எழுதச் சொல்லுங்கள்",
        "What is the total amount I will repay, including interest and every fee?": "வட்டி மற்றும் எல்லா கட்டணங்களும் சேர்த்து நான் மொத்தம் எவ்வளவு செலுத்த வேண்டும்?",
        "Is this interest rate fixed, floating, or changeable later?": "இந்த வட்டி விகிதம் நிலையானதா, மாறக்கூடியதா, அல்லது பின்னர் மாற்றப்படுமா?",
        "Which charges will be deducted before I receive the loan money?": "கடன் பணம் கிடைக்கும் முன் எந்த கட்டணங்கள் கழிக்கப்படும்?",
        "What happens if I miss one payment or pay after the due date?": "ஒரு தவணையை தவற விட்டால் அல்லது கடைசி தேதிக்குப் பிறகு செலுத்தினால் என்ன ஆகும்?",
        "Can I get a signed copy of the full agreement and charges list today?": "முழு ஒப்பந்தம் மற்றும் கட்டண பட்டியலின் கையெழுத்திட்ட நகலை இன்று பெற முடியுமா?",
        "Is insurance compulsory? What is the exact premium and can I refuse it?": "காப்பீடு கட்டாயமா? சரியான premium எவ்வளவு, அதை நான் மறுக்க முடியுமா?",
        "Which asset or document is security, and when will the bank release it?": "எந்த சொத்து அல்லது ஆவணம் பாதுகாப்பு, வங்கி அதை எப்போது விடுவிக்கும்?",
        "Please write each fee separately: processing, stamp duty, GST, documentation, insurance, and penalty.": "ஒவ்வொரு கட்டணத்தையும் தனித்தனியாக எழுதுங்கள்: processing, stamp duty, GST, documentation, insurance மற்றும் penalty.",
    },
}

RISK_TEXT = {
    "Hindi": {
        "penalty": "भुगतान चूकने या शर्त तोड़ने पर अतिरिक्त शुल्क लग सकता है।",
        "foreclosure": "लोन न चुकाने पर बैंक संपत्ति या सुरक्षा पर कार्रवाई कर सकता है।",
        "prepayment": "लोन जल्दी बंद करने पर अतिरिक्त शुल्क लग सकता है।",
        "floating rate": "ब्याज दर बाद में बढ़ सकती है, जिससे EMI या कुल भुगतान बढ़ सकता है।",
        "processing fee": "लोन मिलने से पहले काटा जाने वाला शुल्क।",
        "insurance": "बीमा अनिवार्य हो सकता है। इसकी कीमत और वैकल्पिकता लिखित में पूछें।",
        "hypothecation": "बैंक आपकी फसल/वाहन/दस्तावेज़ पर सुरक्षा अधिकार रख सकता है।",
        "penal interest": "EMI देर से भरने पर सामान्य ब्याज के ऊपर अतिरिक्त ब्याज लग सकता है।",
        "stamp duty": "लोन दस्तावेज़/रजिस्ट्रेशन के लिए सरकारी शुल्क।",
        "as applicable": "यह अस्पष्ट भाषा है। बैंक से सटीक राशि और नियम लिखित में लें।",
        "subject to change": "शर्तें या शुल्क बाद में बदल सकते हैं। लिखित पुष्टि लें।",
        "charges may apply": "यह अस्पष्ट शुल्क भाषा है। सभी शुल्क रुपये में लिखवाएं।",
    },
    "Bengali": {
        "penalty": "পেমেন্ট মিস করলে বা শর্ত ভাঙলে অতিরিক্ত চার্জ লাগতে পারে।",
        "foreclosure": "ঋণ না চুকালে ব্যাংক জামানত বা সম্পদের ওপর ব্যবস্থা নিতে পারে।",
        "prepayment": "ঋণ আগে বন্ধ করলে অতিরিক্ত চার্জ লাগতে পারে।",
        "floating rate": "সুদের হার পরে বাড়তে পারে, ফলে EMI বা মোট পরিশোধ বাড়তে পারে।",
        "processing fee": "ঋণের টাকা পাওয়ার আগে কাটা হতে পারে এমন ফি।",
        "insurance": "বীমা বাধ্যতামূলক হতে পারে। এর দাম এবং এটি ঐচ্ছিক কি না লিখিতভাবে জিজ্ঞাসা করুন।",
        "hypothecation": "ব্যাংক আপনার ফসল/যানবাহন/ডকুমেন্টের ওপর সিকিউরিটি অধিকার রাখতে পারে।",
        "penal interest": "EMI দেরিতে দিলে সাধারণ সুদের ওপর অতিরিক্ত সুদ লাগতে পারে।",
        "stamp duty": "ঋণ ডকুমেন্ট বা রেজিস্ট্রেশনের জন্য সরকারি ফি।",
        "as applicable": "এটি অস্পষ্ট ভাষা। ব্যাংকের কাছ থেকে সঠিক পরিমাণ ও নিয়ম লিখিতভাবে নিন।",
        "subject to change": "শর্ত বা চার্জ পরে বদলাতে পারে। লিখিত নিশ্চিতকরণ নিন।",
        "charges may apply": "এটি অস্পষ্ট চার্জ ভাষা। সব চার্জ টাকায় লিখিয়ে নিন।",
    },
    "Tamil": {
        "penalty": "பணம் செலுத்த தவறினால் அல்லது நிபந்தனை மீறினால் கூடுதல் கட்டணம் வரலாம்.",
        "foreclosure": "கடன் செலுத்தப்படாவிட்டால் வங்கி சொத்து அல்லது பாதுகாப்பு மீது நடவடிக்கை எடுக்கலாம்.",
        "prepayment": "கடனை முன்கூட்டியே முடித்தால் கூடுதல் கட்டணம் வரலாம்.",
        "floating rate": "வட்டி விகிதம் பின்னர் உயரலாம்; இதனால் EMI அல்லது மொத்த செலவு அதிகரிக்கலாம்.",
        "processing fee": "கடன் கிடைக்கும் முன் கழிக்கப்படும் கட்டணம்.",
        "insurance": "காப்பீடு கட்டாயமாக இருக்கலாம். அதன் செலவு மற்றும் விருப்பத் தன்மையை எழுத்தில் கேளுங்கள்.",
        "hypothecation": "வங்கி உங்கள் பயிர்/வாகனம்/ஆவணத்தின் மீது பாதுகாப்பு உரிமை வைத்திருக்கலாம்.",
        "penal interest": "EMI தாமதமாக செலுத்தினால் சாதாரண வட்டிக்கு மேல் கூடுதல் வட்டி வரலாம்.",
        "stamp duty": "கடன் ஆவணம் அல்லது பதிவு செய்வதற்கான அரசு கட்டணம்.",
        "as applicable": "இது தெளிவில்லாத சொல். வங்கியிடம் சரியான தொகை மற்றும் விதிகளை எழுத்தில் வாங்குங்கள்.",
        "subject to change": "நிபந்தனைகள் அல்லது கட்டணங்கள் பின்னர் மாறலாம். எழுத்து உறுதி பெறுங்கள்.",
        "charges may apply": "இது தெளிவில்லாத கட்டண மொழி. எல்லா கட்டணங்களையும் ரூபாயில் எழுதச் சொல்லுங்கள்.",
    },
    "Urdu": {
        "penalty": "ادائیگی چھوٹنے یا شرط توڑنے پر اضافی چارج لگ سکتا ہے۔",
        "foreclosure": "قرض نہ چکانے پر بینک ضمانت یا جائیداد پر کارروائی کر سکتا ہے۔",
        "prepayment": "قرض جلدی بند کرنے پر اضافی چارج لگ سکتا ہے۔",
        "floating rate": "سود کی شرح بعد میں بڑھ سکتی ہے جس سے EMI یا کل ادائیگی بڑھ سکتی ہے۔",
        "processing fee": "قرض ملنے سے پہلے کاٹی جانے والی فیس۔",
        "insurance": "بیمہ لازمی ہو سکتا ہے۔ اس کی قیمت اور اختیاری ہونا تحریری طور پر پوچھیں۔",
        "hypothecation": "بینک آپ کی فصل/گاڑی/دستاویز پر سیکیورٹی حق رکھ سکتا ہے۔",
        "penal interest": "EMI دیر سے دینے پر معمول کے سود کے اوپر اضافی سود لگ سکتا ہے۔",
        "stamp duty": "قرض دستاویز یا رجسٹریشن کے لیے سرکاری فیس۔",
        "as applicable": "یہ مبہم زبان ہے۔ بینک سے صحیح رقم اور شرائط تحریری طور پر لیں۔",
        "subject to change": "شرائط یا چارجز بعد میں بدل سکتے ہیں۔ تحریری تصدیق لیں۔",
        "charges may apply": "یہ مبہم چارج زبان ہے۔ تمام چارجز روپے میں لکھوائیں۔",
        "gst": "ٹیکس لگنے سے کل خرچ بڑھ سکتا ہے۔",
        "penal charges": "دیر سے ادائیگی پر اضافی چارجز۔",
    },
    "Kashmiri": {
        "penalty": "ادائیگی چھوٹنہ یا شرط توڑنہ پر اضافی چارج لگٕ سکٕنا چھیہ۔",
        "foreclosure": "قرضہ نہ چکانہ پر بینک ضمانت یا جائیداد پر کارروائی کٔرِ سکٕنا چھیہ۔",
        "prepayment": "قرضہ جلدی بند کرنہ پر اضافی چارج لگٕ سکٕنا چھیہ۔",
        "floating rate": "شرح سود بعد مٕنز بڑٕ سکٕنی چھیہ، ییلہ EMI یا کُل ادائیگی بٔڈھ سکٕنی چھیہ۔",
        "processing fee": "قرضہ ملنہ سے پہلہ کٔٹیٖ جانۍ فیس۔",
        "insurance": "بیمہ لازمی ہووٕ سکٕنا چھیہ۔ اِس کی قیمت تہ اختیاری ہووٕ تحریری پُچھٕو۔",
        "hypothecation": "بینک آپنۍ فصل/گاڑی/دستاویز پٔٹھ سیکیورٹی حق رٔکھِ سکٕنا چھیہ۔",
        "penal interest": "EMI دیر سٕ دِتٕ تہ معمول کس سودس اوپر اضافی سود لگٕ سکٕنا چھیہ۔",
        "as applicable": "یہ مبہم زبان چھیہ۔ بینک سٕ صحیح رقم تہ شرائط تحریری لٕو۔",
        "subject to change": "شرائط یا چارجز بعد مٕنز بدلٕ سکٕنا چھیہ۔ تحریری تصدیق لٕو۔",
        "charges may apply": "یہ مبہم چارج زبان چھیہ۔ سب چارجز روپیہ مٕنز لکھوٕو۔",
    },
}

VALUE_TRANSLATIONS = {
    "Hindi": {
        "Loan Agreement": "ऋण समझौता",
        "KCC / Agricultural Loan": "KCC / कृषि ऋण",
        "Financial Document": "वित्तीय दस्तावेज़",
        "7.00% p.a. (as applicable from time to time)": "7.00% प्रति वर्ष (समय-समय पर लागू)",
        "Within 12 months from the date of disbursement or as per crop cycle": "राशि मिलने की तारीख से 12 महीनों के भीतर या फसल चक्र के अनुसार",
        "Hypothecation of crop and KCC documents": "फसल और KCC दस्तावेज़ बैंक के पास सुरक्षा के रूप में रहेंगे",
        "As per applicable scheme of the Bank": "बैंक की लागू योजना के अनुसार",
        "As per Bank’s Kisan Credit Card Scheme guidelines": "बैंक की किसान क्रेडिट कार्ड योजना के नियमों के अनुसार",
        "As per Bank's Kisan Credit Card Scheme guidelines": "बैंक की किसान क्रेडिट कार्ड योजना के नियमों के अनुसार",
    },
    "Bengali": {
        "Loan Agreement": "ঋণ চুক্তি",
        "KCC / Agricultural Loan": "KCC / কৃষি ঋণ",
        "Financial Document": "আর্থিক ডকুমেন্ট",
        "7.00% p.a. (as applicable from time to time)": "7.00% প্রতি বছর (সময়ে সময়ে প্রযোজ্য)",
        "Within 12 months from the date of disbursement or as per crop cycle": "ঋণের টাকা পাওয়ার তারিখ থেকে 12 মাসের মধ্যে বা ফসল চক্র অনুযায়ী",
        "Hypothecation of crop and KCC documents": "ফসল এবং KCC ডকুমেন্ট ব্যাংকের কাছে সিকিউরিটি হিসেবে থাকবে",
        "As per applicable scheme of the Bank": "ব্যাংকের প্রযোজ্য স্কিম অনুযায়ী",
        "As per Bank’s Kisan Credit Card Scheme guidelines": "ব্যাংকের কিসান ক্রেডিট কার্ড স্কিমের নিয়ম অনুযায়ী",
        "As per Bank's Kisan Credit Card Scheme guidelines": "ব্যাংকের কিসান ক্রেডিট কার্ড স্কিমের নিয়ম অনুযায়ী",
    },
    "Tamil": {
        "Loan Agreement": "கடன் ஒப்பந்தம்",
        "KCC / Agricultural Loan": "KCC / வேளாண் கடன்",
        "Financial Document": "நிதி ஆவணம்",
        "7.00% p.a. (as applicable from time to time)": "7.00% ஆண்டுக்கு (காலத்துக்கு ஏற்ப பொருந்தும்)",
        "Within 12 months from the date of disbursement or as per crop cycle": "பணம் வழங்கிய தேதியிலிருந்து 12 மாதங்களுக்குள் அல்லது பயிர் சுழற்சிக்கு ஏற்ப",
        "Hypothecation of crop and KCC documents": "பயிர் மற்றும் KCC ஆவணங்கள் பாதுகாப்பாக வங்கியிடம் இருக்கும்",
        "As per applicable scheme of the Bank": "வங்கியின் பொருந்தும் திட்டப்படி",
        "As per Bank’s Kisan Credit Card Scheme guidelines": "வங்கியின் கிசான் கிரெடிட் கார்டு திட்ட விதிகளின்படி",
        "As per Bank's Kisan Credit Card Scheme guidelines": "வங்கியின் கிசான் கிரெடிட் கார்டு திட்ட விதிகளின்படி",
    }
}


def _scan_language() -> str:
    raw = str(st.session_state.get("user_language", "English") or "English").strip()
    aliases = {
        "gujarati": "Gujarati",
        "gujrati": "Gujarati",
        "gurati": "Gujarati",
        "gujarathi": "Gujarati",
        "ગુજરાતી": "Gujarati",
    }
    return aliases.get(raw.lower(), aliases.get(raw, raw))


def _scan_t(text: str) -> str:
    local_ui = {
        "Hindi": {
            "Text Extraction:": "टेक्स्ट निकाला गया:",
            "OCR extracted": "OCR ने निकाले",
            "characters": "अक्षर",
            "View extracted text": "निकाला गया टेक्स्ट देखें",
            "Understand This Document": "यह दस्तावेज़ समझें",
            "Analyse This Text": "इस टेक्स्ट का विश्लेषण करें",
            "Analysing document...": "दस्तावेज़ का विश्लेषण हो रहा है...",
            "Analysing...": "विश्लेषण हो रहा है...",
            "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "लंबी सरल व्याख्या चाहिए? तुरंत रिपोर्ट दिखने के बाद Gemma का उपयोग करें।",
            "Add Gemma detailed explanation": "Gemma से विस्तृत व्याख्या जोड़ें",
            "Gemma is preparing a deeper explanation...": "Gemma गहरी व्याख्या तैयार कर रहा है...",
            "Scan Another Document": "दूसरा दस्तावेज़ स्कैन करें",
            "Reading image with OCR...": "OCR से छवि पढ़ी जा रही है...",
            "Preview extracted text": "निकाले गए टेक्स्ट की झलक",
            "Extracted": "निकाले गए",
            "Read": "पढ़े गए",
            "File too large — maximum 10 MB.": "फ़ाइल बहुत बड़ी है — अधिकतम 10 MB।",
            "The uploaded file could not be read. Please remove it and upload again.": "अपलोड की गई फ़ाइल पढ़ी नहीं जा सकी। कृपया इसे हटाकर फिर अपलोड करें।",
        },
        "Bengali": {
            "Text Extraction:": "টেক্সট বের করা:",
            "OCR extracted": "OCR বের করেছে",
            "characters": "অক্ষর",
            "View extracted text": "বের করা টেক্সট দেখুন",
            "Understand This Document": "এই ডকুমেন্ট বুঝুন",
            "Analyse This Text": "এই টেক্সট বিশ্লেষণ করুন",
            "Analysing document...": "ডকুমেন্ট বিশ্লেষণ হচ্ছে...",
            "Analysing...": "বিশ্লেষণ হচ্ছে...",
            "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "আরও দীর্ঘ সহজ ব্যাখ্যা দরকার? তাৎক্ষণিক রিপোর্ট দেখার পরে Gemma ব্যবহার করুন।",
            "Add Gemma detailed explanation": "Gemma দিয়ে বিস্তারিত ব্যাখ্যা যোগ করুন",
            "Gemma is preparing a deeper explanation...": "Gemma গভীর ব্যাখ্যা প্রস্তুত করছে...",
            "Scan Another Document": "আরেকটি ডকুমেন্ট স্ক্যান করুন",
            "Reading image with OCR...": "OCR দিয়ে ছবি পড়া হচ্ছে...",
            "Preview extracted text": "বের করা টেক্সটের ঝলক",
            "Extracted": "বের করা হয়েছে",
            "Read": "পড়া হয়েছে",
            "File too large — maximum 10 MB.": "ফাইলটি খুব বড় — সর্বোচ্চ 10 MB।",
            "The uploaded file could not be read. Please remove it and upload again.": "আপলোড করা ফাইল পড়া যায়নি। এটি সরিয়ে আবার আপলোড করুন।",
        },
        "Tamil": {
            "Text Extraction:": "உரை எடுத்தல்:",
            "OCR extracted": "OCR எடுத்தது",
            "characters": "எழுத்துகள்",
            "View extracted text": "எடுத்த உரையைப் பாருங்கள்",
            "Understand This Document": "இந்த ஆவணத்தைப் புரிந்துகொள்ளுங்கள்",
            "Analyse This Text": "இந்த உரையை பகுப்பாய்வு செய்யுங்கள்",
            "Analysing document...": "ஆவணம் பகுப்பாய்வு செய்யப்படுகிறது...",
            "Analysing...": "பகுப்பாய்வு செய்யப்படுகிறது...",
            "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "மேலும் எளிய விளக்கம் வேண்டுமா? உடனடி அறிக்கை வந்த பிறகு Gemma-வை பயன்படுத்துங்கள்.",
            "Add Gemma detailed explanation": "Gemma விரிவான விளக்கத்தைச் சேர்க்கவும்",
            "Gemma is preparing a deeper explanation...": "Gemma ஆழமான விளக்கத்தைத் தயாரிக்கிறது...",
            "Scan Another Document": "மற்றொரு ஆவணத்தை ஸ்கேன் செய்யுங்கள்",
            "Reading image with OCR...": "OCR மூலம் படம் படிக்கப்படுகிறது...",
            "Preview extracted text": "எடுத்த உரையின் முன்னோட்டம்",
            "Extracted": "எடுக்கப்பட்டது",
            "Read": "படிக்கப்பட்டது",
            "File too large — maximum 10 MB.": "கோப்பு மிகப் பெரியது — அதிகபட்சம் 10 MB.",
            "The uploaded file could not be read. Please remove it and upload again.": "பதிவேற்றிய கோப்பைப் படிக்க முடியவில்லை. அதை அகற்றி மீண்டும் பதிவேற்றவும்.",
        },
        "Telugu": {
            "Text Extraction:": "టెక్స్ట్ తీసివేత:",
            "OCR extracted": "OCR తీసింది",
            "characters": "అక్షరాలు",
            "View extracted text": "తీసిన టెక్స్ట్ చూడండి",
            "Understand This Document": "ఈ పత్రాన్ని అర్థం చేసుకోండి",
            "Analyse This Text": "ఈ టెక్స్ట్‌ను విశ్లేషించండి",
            "Analysing document...": "పత్రం విశ్లేషిస్తోంది...",
            "Analysing...": "విశ్లేషిస్తోంది...",
            "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "ఇంకా సులభమైన వివరణ కావాలా? వెంటనే రిపోర్ట్ కనిపించిన తర్వాత Gemma ఉపయోగించండి.",
            "Add Gemma detailed explanation": "Gemma వివరణను జోడించండి",
            "Gemma is preparing a deeper explanation...": "Gemma మరింత లోతైన వివరణ సిద్ధం చేస్తోంది...",
            "Scan Another Document": "మరొక పత్రాన్ని స్కాన్ చేయండి",
            "Reading image with OCR...": "OCR తో చిత్రం చదువుతోంది...",
            "Preview extracted text": "తీసిన టెక్స్ట్ ప్రివ్యూ",
            "Extracted": "తీసింది",
            "Read": "చదివింది",
            "Download Safety Report": "సురక్షా రిపోర్ట్ డౌన్‌లోడ్ చేయండి",
            "File too large — maximum 10 MB.": "ఫైల్ చాలా పెద్దది — గరిష్ఠం 10 MB.",
            "The uploaded file could not be read. Please remove it and upload again.": "అప్‌లోడ్ చేసిన ఫైల్ చదవలేకపోయాం. దాన్ని తొలగించి మళ్లీ అప్‌లోడ్ చేయండి.",
        },
        "Nepali": {
            "Text Extraction:": "टेक्स्ट निकालिएको:",
            "OCR extracted": "OCR ले निकाल्यो",
            "characters": "अक्षर",
            "View extracted text": "निकालिएको टेक्स्ट हेर्नुहोस्",
            "Understand This Document": "यो कागजात बुझ्नुहोस्",
            "Analyse This Text": "यो टेक्स्ट विश्लेषण गर्नुहोस्",
            "Analysing document...": "कागजात विश्लेषण हुँदैछ...",
            "Analysing...": "विश्लेषण हुँदैछ...",
            "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "अझ सरल लामो व्याख्या चाहिन्छ? तत्काल रिपोर्ट देखिएपछि Gemma प्रयोग गर्नुहोस्।",
            "Add Gemma detailed explanation": "Gemma विस्तृत व्याख्या थप्नुहोस्",
            "Gemma is preparing a deeper explanation...": "Gemma विस्तृत व्याख्या तयार गर्दैछ...",
            "Scan Another Document": "अर्को कागजात स्क्यान गर्नुहोस्",
            "Reading image with OCR...": "OCR बाट छवि पढिँदैछ...",
            "Preview extracted text": "निकालिएको टेक्स्टको पूर्वावलोकन",
            "Extracted": "निकालियो",
            "Read": "पढियो",
            "Download Safety Report": "सुरक्षा रिपोर्ट डाउनलोड गर्नुहोस्",
            "File too large — maximum 10 MB.": "फाइल धेरै ठूलो छ — अधिकतम 10 MB।",
            "The uploaded file could not be read. Please remove it and upload again.": "अपलोड गरिएको फाइल पढ्न सकिएन। कृपया हटाएर फेरि अपलोड गर्नुहोस्।",
        },
    }
    local_ui["Gujarati"] = {
        "Text Extraction:": "ટેક્સ્ટ કાઢવું:",
        "OCR extracted": "OCR એ કાઢ્યા",
        "characters": "અક્ષરો",
        "View extracted text": "કાઢેલો ટેક્સ્ટ જુઓ",
        "Understand This Document": "આ દસ્તાવેજ સમજો",
        "Analyse This Text": "આ ટેક્સ્ટનું વિશ્લેષણ કરો",
        "Analysing document...": "દસ્તાવેજનું વિશ્લેષણ થઈ રહ્યું છે...",
        "Analysing...": "વિશ્લેષણ થઈ રહ્યું છે...",
        "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "વધુ સરળ વિગતવાર સમજ જોઈએ? તાત્કાલિક રિપોર્ટ દેખાયા પછી Gemma વાપરો.",
        "Add Gemma detailed explanation": "Gemma દ્વારા વિગતવાર સમજ ઉમેરો",
        "Gemma is preparing a deeper explanation...": "Gemma વધુ ઊંડી સમજ તૈયાર કરી રહ્યું છે...",
        "Scan Another Document": "બીજો દસ્તાવેજ સ્કેન કરો",
        "Reading image with OCR...": "OCR વડે છબી વાંચી રહ્યું છે...",
        "Preview extracted text": "કાઢેલા ટેક્સ્ટની ઝલક",
        "Extracted": "કાઢ્યું",
        "Read": "વાંચ્યું",
        "Download Safety Report": "સુરક્ષા રિપોર્ટ ડાઉનલોડ કરો",
        "File too large — maximum 10 MB.": "ફાઇલ ખૂબ મોટી છે — મહત્તમ 10 MB.",
        "The uploaded file could not be read. Please remove it and upload again.": "અપલોડ કરેલી ફાઇલ વાંચી શકાઈ નથી. કૃપા કરીને તેને દૂર કરીને ફરી અપલોડ કરો.",
        "instant_done": "તાત્કાલિક સ્કેન પૂર્ણ — ઓફલાઇન સુરક્ષા રિપોર્ટ તૈયાર છે.",
        "instant_caption": "આ રિપોર્ટ દસ્તાવેજમાંથી કાઢેલા ટેક્સ્ટ પરથી તરત બને છે. તે Gemmaની રાહ જોતો નથી, તેથી સ્કેન ઝડપી રહે છે.",
        "document_type": "દસ્તાવેજનો પ્રકાર",
        "safety_score": "સુરક્ષા સ્કોર",
        "risk_level": "જોખમ સ્તર",
        "flat_rate": "ફ્લેટ રેટ મળ્યો",
        "key_details": "1. મળેલી મુખ્ય માહિતી",
        "charges": "2. ચાર્જ અને ફી",
        "no_charges": "ચોક્કસ ફી રકમ સ્પષ્ટ મળી નથી. સહી કરતા પહેલાં બેંક પાસેથી દરેક ચાર્જની લખિત યાદી માગો.",
        "figures": "3. મળેલા નાણાકીય આંકડા",
        "amounts": "રકમ:",
        "tenure": "અવધિ:",
        "interest_rates": "વ્યાજ દર:",
        "hidden_risks": "4. છુપાયેલા જોખમો",
        "risk_terms": "4. જોખમી શબ્દો",
        "no_risks": "4. છુપાયેલા જોખમો\nઆ ટેક્સ્ટ સ્કેનમાં સ્પષ્ટ જોખમી શબ્દો મળ્યા નથી.",
        "evidence": "પુરાવો",
        "confirm": "5. સહી કરતા પહેલાં ખાતરી કરો",
        "questions": "6. બેંક અધિકારીને પૂછવાના પ્રશ્નો",
        "checklist": "**સહી કરતા પહેલાં ચેકલિસ્ટ:** કુલ ચુકવણી · બધી ફી · દંડ · વીમો · સુરક્ષા/કોલેટરલ · ચુકવણી તારીખ · કરારની સહી કરેલી નકલ.",
        "issue": "મુદ્દો",
        "Loan Agreement": "લોન કરાર",
        "KCC / Agricultural Loan": "KCC / કૃષિ લોન",
        "Financial Document": "નાણાકીય દસ્તાવેજ",
        "Safe": "સુરક્ષિત",
        "Low Risk": "ઓછું જોખમ",
        "Medium Risk": "મધ્યમ જોખમ",
        "High Risk": "ઊંચું જોખમ",
        "Critical Risk": "ગંભીર જોખમ",
        "Borrower": "લોન લેનાર",
        "Loan Amount / Sanction Limit": "લોન રકમ / મંજૂર મર્યાદા",
        "Interest Rate": "વ્યાજ દર",
        "Repayment Period": "ચુકવણી અવધિ",
        "Security": "સુરક્ષા",
        "Insurance": "વીમો",
        "Other Terms": "અન્ય શરતો",
        "Processing Charges": "પ્રોસેસિંગ ચાર્જ",
        "Insurance Charges": "વીમા ચાર્જ",
        "Penalty Charges": "દંડ ચાર્જ",
        "Hidden Taxes": "છુપાયેલા કર",
        "Interest Risks": "વ્યાજ જોખમ",
        "Legal Risks": "કાનૂની જોખમ",
        "Privacy Risks": "ગોપનીયતા જોખમ",
        "Recovery Risks": "વસૂલાત જોખમ",
        "Subscription Charges": "સબ્સ્ક્રિપ્શન ચાર્જ",
        "Ambiguous Clauses": "અસ્પષ્ટ શરતો",
    }

    # ── Marathi ──────────────────────────────────────────────────────────────
    local_ui["Marathi"] = {
        "instant_done": "त्वरित स्कॅन पूर्ण — ऑफलाइन सुरक्षा अहवाल तयार आहे.",
        "instant_caption": "हा अहवाल कागदपत्रातून काढलेल्या मजकुरातून लगेच बनतो. तो Gemmaची वाट पाहत नाही, म्हणून स्कॅन जलद राहतो.",
        "document_type": "कागदपत्राचा प्रकार",
        "safety_score": "सुरक्षा स्कोर",
        "risk_level": "जोखीम पातळी",
        "flat_rate": "फ्लॅट रेट आढळला",
        "key_details": "1. सापडलेली मुख्य माहिती",
        "charges": "2. शुल्क आणि फी",
        "no_charges": "कोणतीही स्पष्ट फी रक्कम सापडली नाही. सही करण्यापूर्वी बँकेकडून प्रत्येक शुल्काची लेखी यादी मागा.",
        "figures": "3. आर्थिक आकडे",
        "amounts": "रक्कम:",
        "tenure": "कालावधी:",
        "interest_rates": "व्याज दर:",
        "hidden_risks": "4. लपलेले धोके",
        "risk_terms": "4. धोकादायक शब्द",
        "no_risks": "4. लपलेले धोके\nया टेक्स्ट स्कॅनमध्ये कोणते मोठे धोकादायक शब्द स्पष्टपणे आढळले नाहीत.",
        "evidence": "पुरावा",
        "confirm": "5. सही करण्यापूर्वी खात्री करा",
        "questions": "6. बँक अधिकाऱ्याला विचारण्याचे प्रश्न",
        "checklist": "**सही करण्यापूर्वी तपासा:** एकूण परतफेड · सर्व शुल्क · दंड · विमा · सुरक्षा/तारण · देय तारीख · कराराची सही केलेली प्रत.",
        "issue": "मुद्दा",
        "Safe": "सुरक्षित", "Low Risk": "कमी जोखीम", "Medium Risk": "मध्यम जोखीम", "High Risk": "जास्त जोखीम", "Critical Risk": "गंभीर जोखीम",
        "Financial Document": "आर्थिक कागदपत्र", "Loan Agreement": "कर्ज करारनामा", "KCC / Agricultural Loan": "KCC / कृषी कर्ज",
        "EMI Schedule": "EMI वेळापत्रक", "Bank Notice": "बँक नोटीस", "Insurance Policy": "विमा पॉलिसी",
        "Borrower": "कर्जदार", "Loan Amount / Sanction Limit": "कर्ज रक्कम / मंजूर मर्यादा", "Interest Rate": "व्याज दर",
        "Repayment Period": "परतफेड कालावधी", "Security": "सुरक्षा / तारण", "Insurance": "विमा", "Other Terms": "इतर अटी",
        "Charges & Fees": "शुल्क आणि फी", "Insurance & Add-ons": "विमा आणि अतिरिक्त सेवा",
        "Penalty & Repayment": "दंड आणि परतफेड", "Interest Risk": "व्याज जोखीम",
        "Security & Recovery": "सुरक्षा आणि वसुली", "Privacy & Consent": "गोपनीयता आणि संमती",
        "Legal Rights": "कायदेशीर हक्क", "Ambiguous Wording": "अस्पष्ट भाषा",
        "Exact loan amount / sanction limit": "नेमकी कर्ज रक्कम / मंजूर मर्यादा",
        "Exact interest rate and whether it can change": "नेमका व्याज दर आणि तो नंतर बदलू शकतो का",
        "Repayment period / due date": "परतफेड कालावधी / देय तारीख",
        "Full written list of processing fee, stamp duty, GST, insurance, and other charges": "प्रोसेसिंग फी, स्टॅम्प ड्युटी, GST, विमा व सर्व शुल्कांची लेखी यादी",
        "Whether insurance is mandatory, optional, refundable, and its exact premium": "विमा अनिवार्य आहे का, पर्यायी आहे का, परतावा मिळेल का, आणि नेमका प्रीमियम किती",
        "What asset or document is kept as security and when it will be released": "कोणती मालमत्ता सुरक्षा म्हणून ठेवली आहे आणि ती कधी परत मिळेल",
        "Exact late-payment penalty and how it is calculated": "उशिरा भरण्याचा नेमका दंड आणि तो कसा मोजतात",
        "All vague terms in fixed rupee amounts": "सर्व अस्पष्ट अटी निश्चित रुपये रकमेत लिहून घ्या",
        "What is the total amount I will repay, including interest and every fee?": "व्याज आणि सर्व शुल्क मिळून मला एकूण किती पैसे द्यावे लागतील?",
        "Is this interest rate fixed, floating, or changeable later?": "हा व्याज दर निश्चित आहे, बदलणारा आहे, की नंतर बदलला जाऊ शकतो?",
        "Which charges will be deducted before I receive the loan money?": "कर्जाचे पैसे मिळण्यापूर्वी कोणते शुल्क कापले जातील?",
        "What happens if I miss one payment or pay after the due date?": "एखादा हप्ता चुकला किंवा उशीर झाला तर काय होईल?",
        "Can I get a signed copy of the full agreement and charges list today?": "मला आज पूर्ण करार व शुल्क यादीची सही केलेली प्रत मिळू शकते का?",
        "Is insurance compulsory? What is the exact premium and can I refuse it?": "विमा अनिवार्य आहे का? नेमका प्रीमियम किती आणि मी नकार देऊ शकतो का?",
        "Which asset or document is security, and when will the bank release it?": "कोणती मालमत्ता सुरक्षा आहे, आणि बँक ती कधी सोडेल?",
        "Please write each fee separately: processing, stamp duty, GST, documentation, insurance, and penalty.": "कृपया प्रत्येक शुल्क स्वतंत्रपणे लिहा: प्रोसेसिंग, स्टॅम्प ड्युटी, GST, दस्तऐवज, विमा आणि दंड.",
        "Text Extraction:": "मजकूर काढणे:", "OCR extracted": "OCR ने काढले", "characters": "अक्षरे",
        "View extracted text": "काढलेला मजकूर पाहा", "Understand This Document": "हे कागदपत्र समजा",
        "Analyse This Text": "हा मजकूर विश्लेषित करा", "Analysing document...": "कागदपत्र विश्लेषित होत आहे...",
        "Analysing...": "विश्लेषण होत आहे...", "Scan Another Document": "दुसरे कागदपत्र स्कॅन करा",
        "Reading image with OCR...": "OCR ने प्रतिमा वाचत आहे...", "Preview extracted text": "काढलेल्या मजकुराचे पूर्वावलोकन",
        "Extracted": "काढले", "Read": "वाचले", "Download Safety Report": "सुरक्षा अहवाल डाउनलोड करा",
        "File too large — maximum 10 MB.": "फाईल खूप मोठी — कमाल 10 MB.",
        "The uploaded file could not be read. Please remove it and upload again.": "अपलोड केलेली फाईल वाचता आली नाही. कृपया ती काढून पुन्हा अपलोड करा.",
    }

    # ── Kannada ──────────────────────────────────────────────────────────────
    local_ui["Kannada"] = {
        "instant_done": "ತಕ್ಷಣ ಸ್ಕ್ಯಾನ್ ಮುಗಿದಿದೆ — ಆಫ್‌ಲೈನ್ ಸುರಕ್ಷತಾ ವರದಿ ಸಿದ್ಧ.",
        "instant_caption": "ಈ ವರದಿ ದಾಖಲೆಯಿಂದ ತೆಗೆದ ಪಠ್ಯದಿಂದ ತಕ್ಷಣ ರಚಿಸಲ್ಪಡುತ್ತದೆ. ಇದು Gemma ಗಾಗಿ ಕಾಯುವುದಿಲ್ಲ.",
        "document_type": "ದಾಖಲೆಯ ವಿಧ",
        "safety_score": "ಸುರಕ್ಷತಾ ಸ್ಕೋರ್",
        "risk_level": "ಅಪಾಯ ಮಟ್ಟ",
        "flat_rate": "ಫ್ಲಾಟ್ ರೇಟ್ ಕಂಡುಬಂದಿದೆ",
        "key_details": "1. ಸಿಕ್ಕ ಮುಖ್ಯ ಮಾಹಿತಿ",
        "charges": "2. ಶುಲ್ಕ ಮತ್ತು ಫೀ",
        "no_charges": "ನಿಖರ ಫೀ ಮೊತ್ತ ಸ್ಪಷ್ಟವಾಗಿ ಸಿಗಲಿಲ್ಲ. ಸಹಿ ಹಾಕುವ ಮೊದಲು ಬ್ಯಾಂಕ್‌ನಿಂದ ಎಲ್ಲ ಶುಲ್ಕಗಳ ಲಿಖಿತ ಪಟ್ಟಿ ಪಡೆಯಿರಿ.",
        "figures": "3. ಆರ್ಥಿಕ ಸಂಖ್ಯೆಗಳು",
        "amounts": "ಮೊತ್ತ:", "tenure": "ಅವಧಿ:", "interest_rates": "ಬಡ್ಡಿ ದರ:",
        "hidden_risks": "4. ಅಡಗಿರುವ ಅಪಾಯಗಳು",
        "risk_terms": "4. ಅಪಾಯಕಾರಿ ಪದಗಳು",
        "no_risks": "4. ಅಡಗಿರುವ ಅಪಾಯಗಳು\nಈ ಪಠ್ಯ ಸ್ಕ್ಯಾನ್‌ನಲ್ಲಿ ಸ್ಪಷ್ಟ ಅಪಾಯಕಾರಿ ಪದಗಳು ಕಂಡುಬಂದಿಲ್ಲ.",
        "evidence": "ಪುರಾವೆ", "confirm": "5. ಸಹಿ ಹಾಕುವ ಮೊದಲು ಖಚಿತಪಡಿಸಿ",
        "questions": "6. ಬ್ಯಾಂಕ್ ಅಧಿಕಾರಿಗೆ ಕೇಳಬೇಕಾದ ಪ್ರಶ್ನೆಗಳು",
        "checklist": "**ಸಹಿ ಹಾಕುವ ಮೊದಲು ತಪಾಸಿಸಿ:** ಒಟ್ಟು ಮರುಪಾವತಿ · ಎಲ್ಲ ಶುಲ್ಕ · ದಂಡ · ವಿಮೆ · ಭದ್ರತೆ · ಗಡುವು ದಿನಾಂಕ · ಒಪ್ಪಂದದ ಸಹಿ ನಕಲು.",
        "issue": "ಸಮಸ್ಯೆ",
        "Safe": "ಸುರಕ್ಷಿತ", "Low Risk": "ಕಡಿಮೆ ಅಪಾಯ", "Medium Risk": "ಮಧ್ಯಮ ಅಪಾಯ", "High Risk": "ಹೆಚ್ಚು ಅಪಾಯ", "Critical Risk": "ಗಂಭೀರ ಅಪಾಯ",
        "Financial Document": "ಆರ್ಥಿಕ ದಾಖಲೆ", "Loan Agreement": "ಸಾಲ ಒಪ್ಪಂದ", "KCC / Agricultural Loan": "KCC / ಕೃಷಿ ಸಾಲ",
        "EMI Schedule": "EMI ವೇಳಾಪಟ್ಟಿ", "Bank Notice": "ಬ್ಯಾಂಕ್ ನೋಟಿಸ್", "Insurance Policy": "ವಿಮಾ ಪಾಲಿಸಿ",
        "Borrower": "ಸಾಲಗಾರ", "Loan Amount / Sanction Limit": "ಸಾಲ ಮೊತ್ತ / ಅನುಮೋದಿತ ಮಿತಿ",
        "Interest Rate": "ಬಡ್ಡಿ ದರ", "Repayment Period": "ಮರುಪಾವತಿ ಅವಧಿ",
        "Security": "ಭದ್ರತೆ / ಅಡಮಾನ", "Insurance": "ವಿಮೆ", "Other Terms": "ಇತರ ಷರತ್ತುಗಳು",
        "Charges & Fees": "ಶುಲ್ಕ ಮತ್ತು ಫೀ", "Insurance & Add-ons": "ವಿಮೆ ಮತ್ತು ಹೆಚ್ಚುವರಿ ಸೇವೆ",
        "Penalty & Repayment": "ದಂಡ ಮತ್ತು ಮರುಪಾವತಿ", "Interest Risk": "ಬಡ್ಡಿ ಅಪಾಯ",
        "Security & Recovery": "ಭದ್ರತೆ ಮತ್ತು ವಸೂಲಿ", "Privacy & Consent": "ಗೌಪ್ಯತೆ ಮತ್ತು ಒಪ್ಪಿಗೆ",
        "Legal Rights": "ಕಾನೂನು ಹಕ್ಕುಗಳು", "Ambiguous Wording": "ಅಸ್ಪಷ್ಟ ಭಾಷೆ",
        "Exact loan amount / sanction limit": "ನಿಖರ ಸಾಲ ಮೊತ್ತ / ಅನುಮೋದಿತ ಮಿತಿ",
        "Exact interest rate and whether it can change": "ನಿಖರ ಬಡ್ಡಿ ದರ ಮತ್ತು ಅದು ಬದಲಾಗಬಹುದೇ",
        "Repayment period / due date": "ಮರುಪಾವತಿ ಅವಧಿ / ಗಡುವು ದಿನಾಂಕ",
        "Full written list of processing fee, stamp duty, GST, insurance, and other charges": "ಪ್ರಕ್ರಿಯಾ ಶುಲ್ಕ, ಸ್ಟಾಂಪ್ ಡ್ಯೂಟಿ, GST, ವಿಮೆ ಮತ್ತು ಎಲ್ಲ ಶುಲ್ಕಗಳ ಲಿಖಿತ ಪಟ್ಟಿ",
        "Whether insurance is mandatory, optional, refundable, and its exact premium": "ವಿಮೆ ಕಡ್ಡಾಯವೇ, ಐಚ್ಛಿಕವೇ, ಮರುಪಾವತಿ ಸಿಗುತ್ತದೆಯೇ, ಮತ್ತು ನಿಖರ ಪ್ರೀಮಿಯಂ ಎಷ್ಟು",
        "What asset or document is kept as security and when it will be released": "ಯಾವ ಆಸ್ತಿ ಭದ್ರತೆಯಾಗಿ ಇದೆ ಮತ್ತು ಅದು ಯಾವಾಗ ಬಿಡುಗಡೆ ಆಗುತ್ತದೆ",
        "Exact late-payment penalty and how it is calculated": "ತಡ ಪಾವತಿ ದಂಡ ಮತ್ತು ಅದನ್ನು ಹೇಗೆ ಲೆಕ್ಕ ಹಾಕುತ್ತಾರೆ",
        "All vague terms in fixed rupee amounts": "ಎಲ್ಲ ಅಸ್ಪಷ್ಟ ಷರತ್ತುಗಳನ್ನು ನಿಗದಿ ರೂಪಾಯಿ ಮೊತ್ತದಲ್ಲಿ ಬರೆಸಿ",
        "What is the total amount I will repay, including interest and every fee?": "ಬಡ್ಡಿ ಮತ್ತು ಎಲ್ಲ ಶುಲ್ಕ ಸೇರಿ ನಾನು ಒಟ್ಟು ಎಷ್ಟು ಹಣ ಕಟ್ಟಬೇಕು?",
        "Is this interest rate fixed, floating, or changeable later?": "ಈ ಬಡ್ಡಿ ದರ ಸ್ಥಿರವೇ, ಬದಲಾಗುವುದೇ, ಅಥವಾ ನಂತರ ಬದಲಾಯಿಸಬಹುದೇ?",
        "Which charges will be deducted before I receive the loan money?": "ಸಾಲದ ಹಣ ಸಿಗುವ ಮೊದಲು ಯಾವ ಶುಲ್ಕ ಕಡಿತ ಆಗುತ್ತದೆ?",
        "What happens if I miss one payment or pay after the due date?": "ಒಂದು ಕಂತು ತಪ್ಪಿದರೆ ಅಥವಾ ತಡವಾಗಿ ಕಟ್ಟಿದರೆ ಏನಾಗುತ್ತದೆ?",
        "Can I get a signed copy of the full agreement and charges list today?": "ಇಂದು ಪೂರ್ಣ ಒಪ್ಪಂದ ಮತ್ತು ಶುಲ್ಕ ಪಟ್ಟಿಯ ಸಹಿ ನಕಲು ಪಡೆಯಬಹುದೇ?",
        "Is insurance compulsory? What is the exact premium and can I refuse it?": "ವಿಮೆ ಕಡ್ಡಾಯವೇ? ನಿಖರ ಪ್ರೀಮಿಯಂ ಎಷ್ಟು ಮತ್ತು ನಾನು ನಿರಾಕರಿಸಬಹುದೇ?",
        "Which asset or document is security, and when will the bank release it?": "ಯಾವ ಆಸ್ತಿ ಭದ್ರತೆ, ಮತ್ತು ಬ್ಯಾಂಕ್ ಅದನ್ನು ಯಾವಾಗ ಬಿಡುಗಡೆ ಮಾಡುತ್ತದೆ?",
        "Please write each fee separately: processing, stamp duty, GST, documentation, insurance, and penalty.": "ದಯವಿಟ್ಟು ಪ್ರತಿ ಶುಲ್ಕ ಪ್ರತ್ಯೇಕವಾಗಿ ಬರೆಯಿರಿ: ಪ್ರಕ್ರಿಯಾ, ಸ್ಟಾಂಪ್ ಡ್ಯೂಟಿ, GST, ದಾಖಲೆ, ವಿಮೆ ಮತ್ತು ದಂಡ.",
        "Text Extraction:": "ಪಠ್ಯ ತೆಗೆಯುವಿಕೆ:", "OCR extracted": "OCR ತೆಗೆಯಿತು", "characters": "ಅಕ್ಷರಗಳು",
        "View extracted text": "ತೆಗೆದ ಪಠ್ಯ ನೋಡಿ", "Understand This Document": "ಈ ದಾಖಲೆ ಅರ್ಥ ಮಾಡಿ",
        "Analyse This Text": "ಈ ಪಠ್ಯ ವಿಶ್ಲೇಷಿಸಿ", "Analysing document...": "ದಾಖಲೆ ವಿಶ್ಲೇಷಣೆ ಆಗುತ್ತಿದೆ...",
        "Analysing...": "ವಿಶ್ಲೇಷಣೆ ಆಗುತ್ತಿದೆ...", "Scan Another Document": "ಇನ್ನೊಂದು ದಾಖಲೆ ಸ್ಕ್ಯಾನ್ ಮಾಡಿ",
        "Reading image with OCR...": "OCR ಮೂಲಕ ಚಿತ್ರ ಓದುತ್ತಿದೆ...", "Preview extracted text": "ತೆಗೆದ ಪಠ್ಯ ಮುನ್ನೋಟ",
        "Extracted": "ತೆಗೆದಿದೆ", "Read": "ಓದಿದೆ", "Download Safety Report": "ಸುರಕ್ಷತಾ ವರದಿ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ",
        "File too large — maximum 10 MB.": "ಫೈಲ್ ತುಂಬಾ ದೊಡ್ಡದು — ಗರಿಷ್ಠ 10 MB.",
        "The uploaded file could not be read. Please remove it and upload again.": "ಅಪ್‌ಲೋಡ್ ಮಾಡಿದ ಫೈಲ್ ಓದಲಾಗಲಿಲ್ಲ. ಅದನ್ನು ತೆಗೆದು ಮತ್ತೆ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ.",
    }

    # ── Malayalam ─────────────────────────────────────────────────────────────
    local_ui["Malayalam"] = {
        "instant_done": "ഉടനടി സ്കാൻ പൂർത്തി — ഓഫ്‌ലൈൻ സുരക്ഷാ റിപ്പോർട്ട് തയ്യാർ.",
        "instant_caption": "ഈ റിപ്പോർട്ട് രേഖയിൽ നിന്ന് എടുത്ത ടെക്‌സ്‌റ്റ് ഉപയോഗിച്ച് ഉടനടി തയ്യാറാക്കുന്നു. ഇത് Gemma-ക്കായി കാത്തിരിക്കില്ല.",
        "document_type": "രേഖയുടെ തരം",
        "safety_score": "സുരക്ഷാ സ്കോർ",
        "risk_level": "അപകട നില",
        "flat_rate": "ഫ്ലാറ്റ് റേറ്റ് കണ്ടെത്തി",
        "key_details": "1. കണ്ടെത്തിയ പ്രധാന വിവരങ്ങൾ",
        "charges": "2. ചാർജ് & ഫീ",
        "no_charges": "കൃത്യമായ ഫീ തുക ലഭ്യമായില്ല. ഒപ്പിടുന്നതിന് മുൻപ് ബാങ്കിൽ നിന്ന് ഓരോ ചാർജിന്റെ ലിഖിത പട്ടിക വാങ്ങൂ.",
        "figures": "3. സാമ്പത്തിക കണക്കുകൾ",
        "amounts": "തുക:", "tenure": "കാലാവധി:", "interest_rates": "പലിശ നിരക്ക്:",
        "hidden_risks": "4. മറഞ്ഞ അപകടങ്ങൾ",
        "risk_terms": "4. അപകടകരമായ പദങ്ങൾ",
        "no_risks": "4. മറഞ്ഞ അപകടങ്ങൾ\nഈ ടെക്‌സ്‌റ്റ് സ്കാനിൽ വ്യക്തമായ അപകടകരമായ പദങ്ങൾ കണ്ടെത്തിയില്ല.",
        "evidence": "തെളിവ്", "confirm": "5. ഒപ്പിടുന്നതിന് മുൻപ് ഉറപ്പ് വരുത്തൂ",
        "questions": "6. ബാങ്ക് ഉദ്യോഗസ്ഥനോട് ചോദിക്കേണ്ട ചോദ്യങ്ങൾ",
        "checklist": "**ഒപ്പിടുന്നതിന് മുൻപ് പരിശോധിക്കൂ:** മൊത്തം തിരിച്ചടവ് · എല്ലാ ഫീ · പിഴ · ഇൻഷുറൻസ് · ജാമ്യം · അവസാന തീയതി · കരാറിന്റെ ഒപ്പ് നകൽ.",
        "issue": "പ്രശ്നം",
        "Safe": "സുരക്ഷിതം", "Low Risk": "കുറഞ്ഞ അപകടം", "Medium Risk": "മധ്യ അപകടം", "High Risk": "ഉയർന്ന അപകടം", "Critical Risk": "ഗുരുതര അപകടം",
        "Financial Document": "സാമ്പത്തിക രേഖ", "Loan Agreement": "വായ്പ കരാർ", "KCC / Agricultural Loan": "KCC / കൃഷി വായ്പ",
        "EMI Schedule": "EMI ഷെഡ്യൂൾ", "Bank Notice": "ബാങ്ക് നോട്ടീസ്", "Insurance Policy": "ഇൻഷുറൻസ് പോളിസി",
        "Borrower": "കടക്കാരൻ", "Loan Amount / Sanction Limit": "വായ്പ തുക / അനുവദിച്ച പരിധി",
        "Interest Rate": "പലിശ നിരക്ക്", "Repayment Period": "തിരിച്ചടവ് കാലാവധി",
        "Security": "ജാമ്യം / പണയം", "Insurance": "ഇൻഷുറൻസ്", "Other Terms": "മറ്റ് നിബന്ധനകൾ",
        "Charges & Fees": "ചാർജ് & ഫീ", "Insurance & Add-ons": "ഇൻഷുറൻസ് & അഡ്ഡ്-ഓൺ",
        "Penalty & Repayment": "പിഴ & തിരിച്ചടവ്", "Interest Risk": "പലിശ അപകടം",
        "Security & Recovery": "ജാമ്യം & വസൂലാക്കൽ", "Privacy & Consent": "സ്വകാര്യത & സമ്മതം",
        "Legal Rights": "നിയമ അവകാശങ്ങൾ", "Ambiguous Wording": "അവ്യക്ത ഭാഷ",
        "Exact loan amount / sanction limit": "കൃത്യ വായ്പ തുക / അനുവദിച്ച പരിധി",
        "Exact interest rate and whether it can change": "കൃത്യ പലിശ നിരക്ക്, അത് മാറ്റാൻ കഴിയുമോ",
        "Repayment period / due date": "തിരിച്ചടവ് കാലാവധി / ദൈനംദിന തീയതി",
        "Full written list of processing fee, stamp duty, GST, insurance, and other charges": "പ്രോസസിംഗ് ഫീ, സ്റ്റാമ്പ് ഡ്യൂട്ടി, GST, ഇൻഷുറൻസ്, മറ്റ് ചാർജുകളുടെ ലിഖിത പട്ടിക",
        "Whether insurance is mandatory, optional, refundable, and its exact premium": "ഇൻഷുറൻസ് നിർബന്ധമോ, ഐഛ്ഛികമോ, തിരിച്ചടക്കാൻ കഴിയുമോ, കൃത്യ പ്രീമിയം എന്ത്",
        "What asset or document is kept as security and when it will be released": "ഏത് ആസ്തി ജാമ്യമായി ഉണ്ട്, അത് എപ്പോൾ തിരിച്ചു കിട്ടും",
        "Exact late-payment penalty and how it is calculated": "വൈകിയ പേമെന്റ് പിഴ, അത് എങ്ങനെ കണക്കാക്കുന്നു",
        "All vague terms in fixed rupee amounts": "എല്ലാ അവ്യക്ത നിബന്ധനകളും നിശ്ചിത രൂപ തുകയിൽ എഴുതി വാങ്ങൂ",
        "What is the total amount I will repay, including interest and every fee?": "പലിശ, ഫീ, ചാർജ് ഉൾപ്പെടെ ഞാൻ ആകെ എത്ര തുക തിരിച്ചടക്കണം?",
        "Is this interest rate fixed, floating, or changeable later?": "ഈ പലിശ നിരക്ക് നിശ്ചിതമോ, ഫ്ലോട്ടിംഗോ, പിന്നീട് മാറ്റാൻ പറ്റുമോ?",
        "Which charges will be deducted before I receive the loan money?": "വായ്പ തുക കിട്ടുന്നതിന് മുൻപ് ഏത് ചാർജ് കിഴിക്കും?",
        "What happens if I miss one payment or pay after the due date?": "ഒരു ഇൻസ്റ്റോൾമെൻ്റ് മിസ്സ് ആയാൽ അല്ലെങ്കിൽ വൈകിയാൽ എന്ത് സംഭവിക്കും?",
        "Can I get a signed copy of the full agreement and charges list today?": "ഇന്ന് പൂർണ കരാർ, ചാർജ് പട്ടികയുടെ ഒപ്പ് നകൽ ലഭിക്കുമോ?",
        "Is insurance compulsory? What is the exact premium and can I refuse it?": "ഇൻഷുറൻസ് നിർബന്ധമോ? കൃത്യ പ്രീമിയം എത്ര, ഞാൻ നിരസിക്കാൻ കഴിയുമോ?",
        "Which asset or document is security, and when will the bank release it?": "ഏത് ആസ്തി ജാമ്യം, ബാങ്ക് അത് എപ്പോൾ തിരിച്ചു നൽകും?",
        "Please write each fee separately: processing, stamp duty, GST, documentation, insurance, and penalty.": "ദയവായി ഓരോ ചാർജും പ്രത്യേകം എഴുതൂ: പ്രോസസിംഗ്, സ്റ്റാമ്പ് ഡ്യൂട്ടി, GST, ഡോക്യുമെന്റ്, ഇൻഷുറൻസ്, പിഴ.",
        "Text Extraction:": "ടെക്‌സ്‌റ്റ് എടുക്കൽ:", "OCR extracted": "OCR എടുത്തു", "characters": "അക്ഷരങ്ങൾ",
        "View extracted text": "എടുത്ത ടെക്‌സ്‌റ്റ് നോക്കൂ", "Understand This Document": "ഈ രേഖ മനസ്സിലാക്കൂ",
        "Analyse This Text": "ഈ ടെക്‌സ്‌റ്റ് വിശകലനം ചെയ്യൂ", "Analysing document...": "രേഖ വിശകലനം ചെയ്യുന്നു...",
        "Analysing...": "വിശകലനം ചെയ്യുന്നു...", "Scan Another Document": "മറ്റൊരു രേഖ സ്കാൻ ചെയ്യൂ",
        "Reading image with OCR...": "OCR ഉപയോഗിച്ച് ചിത്രം വായിക്കുന്നു...", "Preview extracted text": "എടുത്ത ടെക്‌സ്‌റ്റ് പ്രിവ്യൂ",
        "Extracted": "എടുത്തു", "Read": "വായിച്ചു", "Download Safety Report": "സുരക്ഷാ റിപ്പോർട്ട് ഡൗൺലോഡ്",
        "File too large — maximum 10 MB.": "ഫയൽ വളരെ വലുതാണ് — പരമാവധി 10 MB.",
        "The uploaded file could not be read. Please remove it and upload again.": "അപ്‌ലോഡ് ചെയ്ത ഫയൽ വായിക്കാൻ കഴിഞ്ഞില്ല. ഫയൽ നീക്കി വീണ്ടും അപ്‌ലോഡ് ചെയ്യൂ.",
    }

    # ── Punjabi ───────────────────────────────────────────────────────────────
    local_ui["Punjabi"] = {
        "instant_done": "ਤੁਰੰਤ ਸਕੈਨ ਪੂਰਾ — ਆਫਲਾਈਨ ਸੁਰੱਖਿਆ ਰਿਪੋਰਟ ਤਿਆਰ ਹੈ।",
        "instant_caption": "ਇਹ ਰਿਪੋਰਟ ਦਸਤਾਵੇਜ਼ ਤੋਂ ਕੱਢੇ ਟੈਕਸਟ ਤੋਂ ਤੁਰੰਤ ਬਣਦੀ ਹੈ। ਇਹ Gemma ਦੀ ਉਡੀਕ ਨਹੀਂ ਕਰਦੀ, ਇਸ ਲਈ ਸਕੈਨ ਤੇਜ਼ ਰਹਿੰਦਾ ਹੈ।",
        "document_type": "ਦਸਤਾਵੇਜ਼ ਦੀ ਕਿਸਮ",
        "safety_score": "ਸੁਰੱਖਿਆ ਸਕੋਰ",
        "risk_level": "ਜੋਖਮ ਪੱਧਰ",
        "flat_rate": "ਫਲੈਟ ਰੇਟ ਮਿਲਿਆ",
        "key_details": "1. ਮਿਲੀ ਮੁੱਖ ਜਾਣਕਾਰੀ",
        "charges": "2. ਚਾਰਜ ਅਤੇ ਫ਼ੀਸ",
        "no_charges": "ਕੋਈ ਸਪੱਸ਼ਟ ਫ਼ੀਸ ਰਕਮ ਨਹੀਂ ਮਿਲੀ। ਦਸਤਖਤ ਕਰਨ ਤੋਂ ਪਹਿਲਾਂ ਬੈਂਕ ਤੋਂ ਹਰ ਚਾਰਜ ਦੀ ਲਿਖਤੀ ਸੂਚੀ ਲਓ।",
        "figures": "3. ਵਿੱਤੀ ਅੰਕੜੇ",
        "amounts": "ਰਕਮ:", "tenure": "ਮਿਆਦ:", "interest_rates": "ਵਿਆਜ ਦਰ:",
        "hidden_risks": "4. ਲੁਕੇ ਖ਼ਤਰੇ",
        "risk_terms": "4. ਖ਼ਤਰਨਾਕ ਸ਼ਬਦ",
        "no_risks": "4. ਲੁਕੇ ਖ਼ਤਰੇ\nਇਸ ਟੈਕਸਟ ਸਕੈਨ ਵਿੱਚ ਕੋਈ ਵੱਡੇ ਖ਼ਤਰਨਾਕ ਸ਼ਬਦ ਸਪੱਸ਼ਟ ਨਹੀਂ ਮਿਲੇ।",
        "evidence": "ਸਬੂਤ", "confirm": "5. ਦਸਤਖਤ ਕਰਨ ਤੋਂ ਪਹਿਲਾਂ ਪੁਸ਼ਟੀ ਕਰੋ",
        "questions": "6. ਬੈਂਕ ਅਧਿਕਾਰੀ ਨੂੰ ਪੁੱਛਣ ਵਾਲੇ ਸਵਾਲ",
        "checklist": "**ਦਸਤਖਤ ਕਰਨ ਤੋਂ ਪਹਿਲਾਂ ਜਾਂਚੋ:** ਕੁੱਲ ਵਾਪਸੀ · ਸਾਰੀਆਂ ਫ਼ੀਸਾਂ · ਜੁਰਮਾਨਾ · ਬੀਮਾ · ਸੁਰੱਖਿਆ · ਭੁਗਤਾਨ ਦਿਨ · ਇਕਰਾਰਨਾਮੇ ਦੀ ਦਸਤਖਤ ਕਾਪੀ।",
        "issue": "ਮੁੱਦਾ",
        "Safe": "ਸੁਰੱਖਿਅਤ", "Low Risk": "ਘੱਟ ਜੋਖਮ", "Medium Risk": "ਦਰਮਿਆਨਾ ਜੋਖਮ", "High Risk": "ਵੱਧ ਜੋਖਮ", "Critical Risk": "ਗੰਭੀਰ ਜੋਖਮ",
        "Financial Document": "ਵਿੱਤੀ ਦਸਤਾਵੇਜ਼", "Loan Agreement": "ਕਰਜ਼ਾ ਇਕਰਾਰਨਾਮਾ", "KCC / Agricultural Loan": "KCC / ਖੇਤੀਬਾੜੀ ਕਰਜ਼ਾ",
        "EMI Schedule": "EMI ਸਮਾਂ-ਸੂਚੀ", "Bank Notice": "ਬੈਂਕ ਨੋਟਿਸ", "Insurance Policy": "ਬੀਮਾ ਪਾਲਿਸੀ",
        "Borrower": "ਕਰਜ਼ਦਾਰ", "Loan Amount / Sanction Limit": "ਕਰਜ਼ਾ ਰਕਮ / ਮਨਜ਼ੂਰ ਸੀਮਾ",
        "Interest Rate": "ਵਿਆਜ ਦਰ", "Repayment Period": "ਵਾਪਸੀ ਮਿਆਦ",
        "Security": "ਸੁਰੱਖਿਆ / ਗਿਰਵੀ", "Insurance": "ਬੀਮਾ", "Other Terms": "ਹੋਰ ਸ਼ਰਤਾਂ",
        "Charges & Fees": "ਚਾਰਜ ਅਤੇ ਫ਼ੀਸਾਂ", "Insurance & Add-ons": "ਬੀਮਾ ਅਤੇ ਵਾਧੂ ਸੇਵਾਵਾਂ",
        "Penalty & Repayment": "ਜੁਰਮਾਨਾ ਅਤੇ ਵਾਪਸੀ", "Interest Risk": "ਵਿਆਜ ਜੋਖਮ",
        "Security & Recovery": "ਸੁਰੱਖਿਆ ਅਤੇ ਵਸੂਲੀ", "Privacy & Consent": "ਨਿੱਜਤਾ ਅਤੇ ਸਹਿਮਤੀ",
        "Legal Rights": "ਕਾਨੂੰਨੀ ਹੱਕ", "Ambiguous Wording": "ਅਸਪੱਸ਼ਟ ਭਾਸ਼ਾ",
        "Exact loan amount / sanction limit": "ਸਹੀ ਕਰਜ਼ਾ ਰਕਮ / ਮਨਜ਼ੂਰ ਸੀਮਾ",
        "Exact interest rate and whether it can change": "ਸਹੀ ਵਿਆਜ ਦਰ ਅਤੇ ਕੀ ਇਹ ਬਦਲ ਸਕਦੀ ਹੈ",
        "Repayment period / due date": "ਵਾਪਸੀ ਮਿਆਦ / ਭੁਗਤਾਨ ਤਾਰੀਖ",
        "Full written list of processing fee, stamp duty, GST, insurance, and other charges": "ਪ੍ਰੋਸੈਸਿੰਗ ਫ਼ੀਸ, ਸਟੈਂਪ ਡਿਊਟੀ, GST, ਬੀਮਾ ਅਤੇ ਸਾਰੇ ਚਾਰਜਾਂ ਦੀ ਲਿਖਤੀ ਸੂਚੀ",
        "Whether insurance is mandatory, optional, refundable, and its exact premium": "ਕੀ ਬੀਮਾ ਲਾਜ਼ਮੀ ਹੈ, ਵਿਕਲਪਿਕ ਹੈ, ਵਾਪਸ ਮਿਲੇਗਾ, ਅਤੇ ਸਹੀ ਪ੍ਰੀਮੀਅਮ ਕਿੰਨਾ ਹੈ",
        "What asset or document is kept as security and when it will be released": "ਕਿਹੜੀ ਜਾਇਦਾਦ ਸੁਰੱਖਿਆ ਵਜੋਂ ਹੈ ਅਤੇ ਇਹ ਕਦੋਂ ਵਾਪਸ ਮਿਲੇਗੀ",
        "Exact late-payment penalty and how it is calculated": "ਦੇਰੀ ਨਾਲ ਭੁਗਤਾਨ ਦਾ ਜੁਰਮਾਨਾ ਅਤੇ ਇਹ ਕਿਵੇਂ ਹਿਸਾਬ ਲਾਉਂਦੇ ਹਨ",
        "All vague terms in fixed rupee amounts": "ਸਾਰੀਆਂ ਅਸਪੱਸ਼ਟ ਸ਼ਰਤਾਂ ਨਿਸ਼ਚਿਤ ਰੁਪਏ ਦੀ ਰਕਮ ਵਿੱਚ ਲਿਖਵਾਓ",
        "What is the total amount I will repay, including interest and every fee?": "ਵਿਆਜ ਅਤੇ ਸਾਰੀਆਂ ਫ਼ੀਸਾਂ ਮਿਲਾ ਕੇ ਮੈਨੂੰ ਕੁੱਲ ਕਿੰਨੇ ਪੈਸੇ ਵਾਪਸ ਕਰਨੇ ਹਨ?",
        "Is this interest rate fixed, floating, or changeable later?": "ਇਹ ਵਿਆਜ ਦਰ ਸਥਿਰ ਹੈ, ਬਦਲਣ ਵਾਲੀ ਹੈ, ਜਾਂ ਬਾਅਦ ਵਿੱਚ ਬਦਲੀ ਜਾ ਸਕਦੀ ਹੈ?",
        "Which charges will be deducted before I receive the loan money?": "ਕਰਜ਼ੇ ਦੇ ਪੈਸੇ ਮਿਲਣ ਤੋਂ ਪਹਿਲਾਂ ਕਿਹੜੇ ਚਾਰਜ ਕੱਟੇ ਜਾਣਗੇ?",
        "What happens if I miss one payment or pay after the due date?": "ਜੇ ਇੱਕ ਕਿਸ਼ਤ ਚੁੱਕ ਜਾਵੇ ਜਾਂ ਦੇਰੀ ਨਾਲ ਭਰੀ ਜਾਵੇ ਤਾਂ ਕੀ ਹੋਵੇਗਾ?",
        "Can I get a signed copy of the full agreement and charges list today?": "ਕੀ ਮੈਨੂੰ ਅੱਜ ਪੂਰੇ ਇਕਰਾਰਨਾਮੇ ਅਤੇ ਚਾਰਜ ਸੂਚੀ ਦੀ ਦਸਤਖਤ ਕਾਪੀ ਮਿਲ ਸਕਦੀ ਹੈ?",
        "Is insurance compulsory? What is the exact premium and can I refuse it?": "ਕੀ ਬੀਮਾ ਲਾਜ਼ਮੀ ਹੈ? ਸਹੀ ਪ੍ਰੀਮੀਅਮ ਕਿੰਨਾ ਹੈ ਅਤੇ ਕੀ ਮੈਂ ਮਨ੍ਹਾ ਕਰ ਸਕਦਾ ਹਾਂ?",
        "Which asset or document is security, and when will the bank release it?": "ਕਿਹੜੀ ਜਾਇਦਾਦ ਸੁਰੱਖਿਆ ਹੈ, ਅਤੇ ਬੈਂਕ ਇਸਨੂੰ ਕਦੋਂ ਵਾਪਸ ਕਰੇਗਾ?",
        "Please write each fee separately: processing, stamp duty, GST, documentation, insurance, and penalty.": "ਕਿਰਪਾ ਕਰਕੇ ਹਰ ਫ਼ੀਸ ਵੱਖਰੀ ਲਿਖੋ: ਪ੍ਰੋਸੈਸਿੰਗ, ਸਟੈਂਪ ਡਿਊਟੀ, GST, ਦਸਤਾਵੇਜ਼, ਬੀਮਾ ਅਤੇ ਜੁਰਮਾਨਾ।",
        "Text Extraction:": "ਟੈਕਸਟ ਕੱਢਣਾ:", "OCR extracted": "OCR ਨੇ ਕੱਢੇ", "characters": "ਅੱਖਰ",
        "View extracted text": "ਕੱਢਿਆ ਟੈਕਸਟ ਦੇਖੋ", "Understand This Document": "ਇਹ ਦਸਤਾਵੇਜ਼ ਸਮਝੋ",
        "Analyse This Text": "ਇਸ ਟੈਕਸਟ ਦਾ ਵਿਸ਼ਲੇਸ਼ਣ ਕਰੋ", "Analysing document...": "ਦਸਤਾਵੇਜ਼ ਦਾ ਵਿਸ਼ਲੇਸ਼ਣ ਹੋ ਰਿਹਾ ਹੈ...",
        "Analysing...": "ਵਿਸ਼ਲੇਸ਼ਣ ਹੋ ਰਿਹਾ ਹੈ...", "Scan Another Document": "ਦੂਜਾ ਦਸਤਾਵੇਜ਼ ਸਕੈਨ ਕਰੋ",
        "Reading image with OCR...": "OCR ਨਾਲ ਤਸਵੀਰ ਪੜ੍ਹੀ ਜਾ ਰਹੀ ਹੈ...", "Preview extracted text": "ਕੱਢੇ ਟੈਕਸਟ ਦੀ ਝਲਕ",
        "Extracted": "ਕੱਢੇ", "Read": "ਪੜ੍ਹੇ", "Download Safety Report": "ਸੁਰੱਖਿਆ ਰਿਪੋਰਟ ਡਾਊਨਲੋਡ ਕਰੋ",
        "File too large — maximum 10 MB.": "ਫ਼ਾਈਲ ਬਹੁਤ ਵੱਡੀ ਹੈ — ਵੱਧ ਤੋਂ ਵੱਧ 10 MB।",
        "The uploaded file could not be read. Please remove it and upload again.": "ਅਪਲੋਡ ਕੀਤੀ ਫ਼ਾਈਲ ਪੜ੍ਹੀ ਨਹੀਂ ਜਾ ਸਕੀ। ਕਿਰਪਾ ਕਰਕੇ ਹਟਾ ਕੇ ਦੁਬਾਰਾ ਅਪਲੋਡ ਕਰੋ।",
    }

    # ── Urdu ──────────────────────────────────────────────────────────────────
    local_ui["Urdu"] = {
        "instant_done": "فوری اسکین مکمل — آف لائن سلامتی رپورٹ تیار ہے۔",
        "instant_caption": "یہ رپورٹ دستاویز سے نکالے گئے متن سے فوراً بنتی ہے۔ یہ Gemma کا انتظار نہیں کرتی، اس لیے اسکین تیز رہتا ہے۔",
        "document_type": "دستاویز کی قسم",
        "safety_score": "سلامتی سکور",
        "risk_level": "خطرے کا درجہ",
        "flat_rate": "فلیٹ ریٹ ملا",
        "key_details": "1. ملی ہوئی اہم معلومات",
        "charges": "2. چارجز اور فیس",
        "no_charges": "کوئی واضح فیس رقم نہیں ملی۔ دستخط کرنے سے پہلے بینک سے ہر چارج کی تحریری فہرست لیں۔",
        "figures": "3. مالی اعداد و شمار",
        "amounts": "رقم:", "tenure": "مدت:", "interest_rates": "شرح سود:",
        "hidden_risks": "4. چھپے ہوئے خطرات",
        "risk_terms": "4. خطرناک الفاظ",
        "no_risks": "4. چھپے ہوئے خطرات\nاس ٹیکسٹ اسکین میں کوئی واضح خطرناک الفاظ نہیں ملے۔",
        "evidence": "ثبوت", "confirm": "5. دستخط سے پہلے تصدیق کریں",
        "questions": "6. بینک افسر سے پوچھنے والے سوالات",
        "checklist": "**دستخط سے پہلے جانچیں:** کل واپسی · تمام فیس · جرمانہ · بیمہ · ضمانت · ادائیگی کی تاریخ · معاہدے کی دستخط شدہ نقل۔",
        "issue": "مسئلہ",
        "Safe": "محفوظ", "Low Risk": "کم خطرہ", "Medium Risk": "درمیانہ خطرہ", "High Risk": "زیادہ خطرہ", "Critical Risk": "سنگین خطرہ",
        "Financial Document": "مالی دستاویز", "Loan Agreement": "قرض معاہدہ", "KCC / Agricultural Loan": "KCC / زرعی قرضہ",
        "EMI Schedule": "EMI شیڈول", "Bank Notice": "بینک نوٹس", "Insurance Policy": "بیمہ پالیسی",
        "Borrower": "قرض دار", "Loan Amount / Sanction Limit": "قرض رقم / منظور حد",
        "Interest Rate": "شرح سود", "Repayment Period": "واپسی کی مدت",
        "Security": "ضمانت / گروی", "Insurance": "بیمہ", "Other Terms": "دیگر شرائط",
        "Charges & Fees": "چارجز اور فیس", "Insurance & Add-ons": "بیمہ اور اضافی خدمات",
        "Penalty & Repayment": "جرمانہ اور واپسی", "Interest Risk": "سود کا خطرہ",
        "Security & Recovery": "ضمانت اور وصولی", "Privacy & Consent": "رازداری اور رضامندی",
        "Legal Rights": "قانونی حقوق", "Ambiguous Wording": "مبہم زبان",
        "Exact loan amount / sanction limit": "صحیح قرض رقم / منظور حد",
        "Exact interest rate and whether it can change": "صحیح شرح سود اور کیا یہ بعد میں بدل سکتی ہے",
        "Repayment period / due date": "واپسی کی مدت / ادائیگی کی تاریخ",
        "Full written list of processing fee, stamp duty, GST, insurance, and other charges": "پروسیسنگ فیس، اسٹیمپ ڈیوٹی، GST، بیمہ اور تمام چارجز کی تحریری فہرست",
        "Whether insurance is mandatory, optional, refundable, and its exact premium": "کیا بیمہ لازمی ہے، اختیاری ہے، واپس ملے گا، اور صحیح پریمیم کتنا ہے",
        "What asset or document is kept as security and when it will be released": "کون سی جائیداد ضمانت میں ہے اور یہ کب واپس ملے گی",
        "Exact late-payment penalty and how it is calculated": "دیر سے ادائیگی کا صحیح جرمانہ اور یہ کیسے حساب ہوتا ہے",
        "All vague terms in fixed rupee amounts": "تمام مبہم شرائط کو مقررہ روپے کی رقم میں لکھوائیں",
        "What is the total amount I will repay, including interest and every fee?": "سود اور تمام فیس ملا کر مجھے کل کتنی رقم واپس کرنی ہے؟",
        "Is this interest rate fixed, floating, or changeable later?": "یہ شرح سود مقررہ ہے، بدلتی ہے، یا بعد میں تبدیل ہو سکتی ہے؟",
        "Which charges will be deducted before I receive the loan money?": "قرض کے پیسے ملنے سے پہلے کون کون سے چارج کاٹے جائیں گے؟",
        "What happens if I miss one payment or pay after the due date?": "اگر ایک قسط چھوٹ جائے یا دیر سے دی جائے تو کیا ہوگا؟",
        "Can I get a signed copy of the full agreement and charges list today?": "کیا مجھے آج پورے معاہدے اور چارج فہرست کی دستخط شدہ نقل مل سکتی ہے؟",
        "Is insurance compulsory? What is the exact premium and can I refuse it?": "کیا بیمہ لازمی ہے؟ صحیح پریمیم کتنا ہے اور کیا میں انکار کر سکتا ہوں؟",
        "Which asset or document is security, and when will the bank release it?": "کون سی جائیداد ضمانت ہے، اور بینک اسے کب چھوڑے گا؟",
        "Please write each fee separately: processing, stamp duty, GST, documentation, insurance, and penalty.": "براہ کرم ہر فیس الگ الگ لکھیں: پروسیسنگ، اسٹیمپ ڈیوٹی، GST، دستاویز، بیمہ اور جرمانہ۔",
        "Text Extraction:": "متن نکالنا:", "OCR extracted": "OCR نے نکالے", "characters": "حروف",
        "View extracted text": "نکالا ہوا متن دیکھیں", "Understand This Document": "یہ دستاویز سمجھیں",
        "Analyse This Text": "اس متن کا تجزیہ کریں", "Analysing document...": "دستاویز کا تجزیہ ہو رہا ہے...",
        "Analysing...": "تجزیہ ہو رہا ہے...", "Scan Another Document": "دوسرا دستاویز اسکین کریں",
        "Reading image with OCR...": "OCR سے تصویر پڑھی جا رہی ہے...", "Preview extracted text": "نکالے متن کی جھلک",
        "Extracted": "نکالے", "Read": "پڑھے", "Download Safety Report": "سلامتی رپورٹ ڈاؤن لوڈ کریں",
        "File too large — maximum 10 MB.": "فائل بہت بڑی ہے — زیادہ سے زیادہ 10 MB۔",
        "The uploaded file could not be read. Please remove it and upload again.": "اپلوڈ کی گئی فائل نہیں پڑھی جا سکی۔ کپڑا ہٹا کر دوبارہ اپلوڈ کریں۔",
    }

    # ── Kashmiri ─────────────────────────────────────────────────────────────
    local_ui["Kashmiri"] = {
        "instant_done": "فوری اسکین مکمل — آف لائن سلامتی رپورٹ تیار چھیہ۔",
        "instant_caption": "یہ رپورٹ دستاویز سٕ نکالۍ متن پیٹھہ فوری بنٕ چھیہ۔ یہ Gemma کہ انتظار نہ کرٕ چھیہ، اِس لیہ اسکین تیز رٕہِ چھیہ۔",
        "document_type": "دستاویز کا قسم",
        "safety_score": "سلامتی سکور",
        "risk_level": "خطرہ کا درجہ",
        "flat_rate": "فلیٹ ریٹ ملٕ",
        "key_details": "1. ملٕ مُہِم معلومات",
        "charges": "2. چارجز تہ فیس",
        "no_charges": "کُنہِ وَضح فیس رقم نہ ملٕ۔ دستخط کرنہ سے پہلہ بینک سٕ ہر چارج کی تحریری فہرست لٕو۔",
        "figures": "3. مالی اعداد",
        "amounts": "رقم:", "tenure": "مدت:", "interest_rates": "شرح سود:",
        "hidden_risks": "4. لُکۍ خطرات",
        "risk_terms": "4. خطرناک لفظ",
        "no_risks": "4. لُکۍ خطرات\nاِس ٹیکسٹ اسکین مٕنز کُنہِ وضح خطرناک لفظ نہ ملٕ۔",
        "evidence": "ثبوت", "confirm": "5. دستخط کرنہ سے پہلہ تصدیق کٔرِو",
        "questions": "6. بینک افسر سٕ پُچھنۍ سوال",
        "checklist": "**دستخط کرنہ سے پہلہ جانچٕو:** کُل واپسی · تمام فیس · جرمانہ · بیمہ · ضمانت · ادائیگی کی تاریخ · معاہدہ کی دستخط شدہ نقل۔",
        "issue": "مسئلہ",
        "Safe": "محفوظ", "Low Risk": "کم خطرہ", "Medium Risk": "درمیانہ خطرہ", "High Risk": "زیادہ خطرہ", "Critical Risk": "سنگین خطرہ",
        "Financial Document": "مالی دستاویز", "Loan Agreement": "قرضہ معاہدہ", "KCC / Agricultural Loan": "KCC / زرعی قرضہ",
        "EMI Schedule": "EMI شیڈول", "Bank Notice": "بینک نوٹس", "Insurance Policy": "بیمہ پالیسی",
        "Borrower": "قرض دار", "Loan Amount / Sanction Limit": "قرضہ رقم / منظور حد",
        "Interest Rate": "شرح سود", "Repayment Period": "واپسی کی مدت",
        "Security": "ضمانت / گروی", "Insurance": "بیمہ", "Other Terms": "دیگر شرائط",
        "Charges & Fees": "چارجز تہ فیس", "Insurance & Add-ons": "بیمہ تہ اضافی خدمات",
        "Penalty & Repayment": "جرمانہ تہ واپسی", "Interest Risk": "سود کا خطرہ",
        "Security & Recovery": "ضمانت تہ وصولی", "Privacy & Consent": "رازداری تہ رضامندی",
        "Legal Rights": "قانونی حقوق", "Ambiguous Wording": "مبہم زبان",
        "Exact loan amount / sanction limit": "صحیح قرضہ رقم / منظور حد",
        "Exact interest rate and whether it can change": "صحیح شرح سود تہ کیا یہ بعد مٕنز بدلٕ سکٕنی چھیہ",
        "Repayment period / due date": "واپسی کی مدت / ادائیگی کی تاریخ",
        "Full written list of processing fee, stamp duty, GST, insurance, and other charges": "پروسیسنگ فیس، اسٹیمپ ڈیوٹی، GST، بیمہ تہ تمام چارجز کی تحریری فہرست",
        "Whether insurance is mandatory, optional, refundable, and its exact premium": "کیا بیمہ لازمی چھیہ، اختیاری چھیہ، واپس ملٕ، تہ صحیح پریمیم کِتنا چھیہ",
        "What asset or document is kept as security and when it will be released": "کُنہِ جائیداد ضمانت مٕنز چھیہ تہ یہ کاہِ وقت واپس ملٕ",
        "Exact late-payment penalty and how it is calculated": "دیر سٕ ادائیگی کا صحیح جرمانہ تہ یہ کیوٕ حساب ہوٕ چھیہ",
        "All vague terms in fixed rupee amounts": "تمام مبہم شرائط کو مقررہ روپے کی رقم مٕنز لکھوٕو",
        "What is the total amount I will repay, including interest and every fee?": "سود تہ تمام فیس ملا کر مُنز کُل کِتنی رقم واپس کٔرنی چھیہ؟",
        "Is this interest rate fixed, floating, or changeable later?": "یہ شرح سود مقررہ چھیہ، بدلتی چھیہ، یا بعد مٕنز بدلٕ سکٕنی چھیہ؟",
        "Which charges will be deducted before I receive the loan money?": "قرضہ کے پیسے ملنہ سے پہلہ کُنہِ کُنہِ چارج کٔٹیٖ جان چھیہ؟",
        "What happens if I miss one payment or pay after the due date?": "اگر اِک قسط چھوٹٕ یا دیر سٕ دِتٕ جاوٕ تہ کیا ہوٕ چھیہ؟",
        "Can I get a signed copy of the full agreement and charges list today?": "کیا مُنز آج پورۍ معاہدہ تہ چارج فہرست کی دستخط شدہ نقل ملٕ سکٕنی چھیہ؟",
        "Is insurance compulsory? What is the exact premium and can I refuse it?": "کیا بیمہ لازمی چھیہ؟ صحیح پریمیم کِتنا چھیہ تہ کیا مُنز انکار کٔرِ سکاں؟",
        "Which asset or document is security, and when will the bank release it?": "کُنہِ جائیداد ضمانت چھیہ، تہ بینک کاہِ وقت چھوڈٕ چھیہ؟",
        "Please write each fee separately: processing, stamp duty, GST, documentation, insurance, and penalty.": "مہربانی کٔرِ ہر فیس الگ لکھٕو: پروسیسنگ، اسٹیمپ ڈیوٹی، GST، دستاویز، بیمہ تہ جرمانہ۔",
        "Text Extraction:": "متن نکالنا:", "OCR extracted": "OCR نٕ نکالۍ", "characters": "حرف",
        "View extracted text": "نکالۍ متن ؤنڈٕو", "Understand This Document": "یہ دستاویز سمجھٕو",
        "Analyse This Text": "اِس متن کا تجزیہ کٔرِو", "Analysing document...": "دستاویز کا تجزیہ ہوٕ چھیہ...",
        "Analysing...": "تجزیہ ہوٕ چھیہ...", "Scan Another Document": "دوسرا دستاویز اسکین کٔرِو",
        "Reading image with OCR...": "OCR سٕ تصویر پٔڈٕ چھیہ...", "Preview extracted text": "نکالۍ متن کی جھلک",
        "Extracted": "نکالۍ", "Read": "پٔڈٕ", "Download Safety Report": "سلامتی رپورٹ ڈاؤن لوڈ کٔرِو",
        "File too large — maximum 10 MB.": "فائل بہُت بوڑ چھیہ — زیادہ سٕ زیادہ 10 MB۔",
        "The uploaded file could not be read. Please remove it and upload again.": "اَپلوڈ کٕرمٕت فائل نہ پٔڈٕ ہٕکوو۔ مہربانی کٔرِ ہٹٕوِ تہ دوبارہ اَپلوڈ کٔرِو۔",
    }

    # ── Odia ──────────────────────────────────────────────────────────────────
    local_ui["Odia"] = {
        "Text Extraction:": "ଟେକ୍ସ୍ଟ ବାହାର କରିବା:",
        "OCR extracted": "OCR ବାହାର କଲା",
        "characters": "ଅକ୍ଷର",
        "View extracted text": "ବାହାର କରାଯାଇଥିବା ଟେକ୍ସ୍ଟ ଦେଖନ୍ତୁ",
        "Understand This Document": "ଏହି ଦଲିଲ ବୁଝନ୍ତୁ",
        "Analyse This Text": "ଏହି ଟେକ୍ସ୍ଟ ବିଶ୍ଳେଷଣ କରନ୍ତୁ",
        "Analysing document...": "ଦଲିଲ ବିଶ୍ଳେଷଣ ହେଉଛି...",
        "Analysing...": "ବିଶ୍ଳେଷଣ ହେଉଛି...",
        "Scan Another Document": "ଆଉ ଏକ ଦଲିଲ ସ୍କ୍ୟାନ କରନ୍ତୁ",
        "Reading image with OCR...": "OCR ଦ୍ୱାରା ଛବି ପଢ଼ୁଛି...",
        "Preview extracted text": "ବାହାର ଟେକ୍ସ୍ଟ ପ୍ରିଭ୍ୟୁ",
        "Extracted": "ବାହାର ହେଲା", "Read": "ପଢ଼ିଲା",
        "Download Safety Report": "ସୁରକ୍ଷା ରିପୋର୍ଟ ଡାଉନଲୋଡ଼ କରନ୍ତୁ",
        "File too large — maximum 10 MB.": "ଫାଇଲ ବହୁ ବଡ଼ — ସର୍ବାଧିକ 10 MB।",
        "The uploaded file could not be read. Please remove it and upload again.": "ଅପଲୋଡ଼ ଫାଇଲ ପଢ଼ି ହେଲା ନାହିଁ। ଦୟାକରି ହଟାଇ ପୁଣି ଅପଲୋଡ଼ କରନ୍ତୁ।",
        "instant_done": "ତୁରନ୍ତ ସ୍କ୍ୟାନ ଶେଷ — ଅଫଲାଇନ ସୁରକ୍ଷା ରିପୋର୍ଟ ପ୍ରସ୍ତୁତ।",
        "instant_caption": "ଏହି ରିପୋର୍ଟ ଦଲିଲରୁ ବାହାର ଟେକ୍ସ୍ଟ ଦ୍ୱାରା ତୁରନ୍ତ ତିଆରି ହୁଏ।",
        "document_type": "ଦଲିଲ ପ୍ରକାର", "safety_score": "ସୁରକ୍ଷା ସ୍କୋର", "risk_level": "ଜୋଖିମ ସ୍ତର",
        "flat_rate": "ଫ୍ଲାଟ ରେଟ ମିଳିଲା", "key_details": "1. ମୁଖ୍ୟ ତଥ୍ୟ",
        "charges": "2. ଚାର୍ଜ ଓ ଫି", "no_charges": "ସ୍ପଷ୍ଟ ଫି ମିଳିଲା ନାହିଁ। ସ୍ୱାକ୍ଷର ପୂର୍ବରୁ ବ୍ୟାଙ୍କରୁ ଲିଖିତ ତାଲିକା ମାଗନ୍ତୁ।",
        "figures": "3. ଆର୍ଥିକ ସଂଖ୍ୟା", "amounts": "ରାଶି:", "tenure": "ଅବଧି:", "interest_rates": "ସୁଧ ହାର:",
        "hidden_risks": "4. ଲୁଚାଯାଇଥିବା ଜୋଖିମ", "risk_terms": "4. ଜୋଖିମ ଶବ୍ଦ",
        "no_risks": "4. ଲୁଚାଯାଇଥିବା ଜୋଖିମ\nଏହି ସ୍କ୍ୟାନରେ ସ୍ପଷ୍ଟ ଜୋଖିମ ଶବ୍ଦ ମିଳିଲା ନାହିଁ।",
        "evidence": "ପ୍ରମାଣ", "confirm": "5. ସ୍ୱାକ୍ଷର ପୂର୍ବରୁ ନିଶ୍ଚିତ କରନ୍ତୁ",
        "questions": "6. ବ୍ୟାଙ୍କ ଅଧିକାରୀଙ୍କୁ ପ୍ରଶ୍ନ",
        "checklist": "**ସ୍ୱାକ୍ଷର ପୂର୍ବରୁ:** ମୋଟ ଭୁଗ୍ତାନ · ସମସ୍ତ ଫି · ଦଣ୍ଡ · ବୀମା · ସୁରକ୍ଷା · ତାରିଖ · ଚୁକ୍ତିର ନକଲ।",
        "issue": "ସମସ୍ୟା",
        "Safe": "ସୁରକ୍ଷିତ", "Low Risk": "କମ ଜୋଖିମ", "Medium Risk": "ମଧ୍ୟ ଜୋଖିମ", "High Risk": "ଉଚ୍ଚ ଜୋଖିମ", "Critical Risk": "ଗୁରୁତ୍ୱ ଜୋଖିମ",
        "Financial Document": "ଆର୍ଥିକ ଦଲିଲ", "Loan Agreement": "ଋଣ ଚୁକ୍ତି", "KCC / Agricultural Loan": "KCC / କୃଷି ଋଣ",
        "Charges & Fees": "ଚାର୍ଜ ଓ ଫି", "Penalty & Repayment": "ଦଣ୍ଡ ଓ ଭୁଗ୍ତାନ",
        "Borrower": "ଋଣ ଗ୍ରହୀତା", "Loan Amount / Sanction Limit": "ଋଣ ପରିମାଣ / ଅନୁମୋଦନ ସୀମା",
        "Interest Rate": "ସୁଧ ହାର", "Repayment Period": "ଭୁଗ୍ତାନ ଅବଧି",
        "Security": "ଜାମିନ", "Insurance": "ବୀମା", "Other Terms": "ଅନ୍ୟ ଶର୍ତ",
        "Insurance & Add-ons": "ବୀମା ଓ ଅଡ-ଅନ", "Interest Risk": "ସୁଧ ଜୋଖିମ",
        "Security & Recovery": "ଜାମିନ ଓ ଆଦାୟ", "Privacy & Consent": "ଗୋପନୀୟତା ଓ ସମ୍ମତି",
        "Legal Rights": "ଆଇନ ଅଧିକାର", "Ambiguous Wording": "ଅସ୍ପଷ୍ଟ ଭାଷା",
        "EMI Schedule": "EMI ଅନୁସୂଚି", "Bank Notice": "ବ୍ୟାଙ୍କ ନୋଟିସ", "Insurance Policy": "ବୀମା ପଲିସି",
        "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "ଦୀର୍ଘ ସରଳ ବ୍ୟାଖ୍ୟା ଦରକାର? ତୁରନ୍ତ ରିପୋର୍ଟ ଦେଖା ଯାଇଛି — Gemma ବ୍ୟବହାର କରନ୍ତୁ।",
        "Add Gemma detailed explanation": "Gemma ଦ୍ୱାରା ବିସ୍ତୃତ ବ୍ୟାଖ୍ୟା ଯୋଡ଼ନ୍ତୁ",
        "Gemma is preparing a deeper explanation...": "Gemma ଗଭୀର ବ୍ୟାଖ୍ୟା ପ୍ରସ୍ତୁତ କରୁଛି...",
    }

    # ── Assamese ──────────────────────────────────────────────────────────────
    local_ui["Assamese"] = {
        "Text Extraction:": "টেক্সট উলিওৱা:",
        "OCR extracted": "OCR উলিয়াইছে",
        "characters": "আখৰ",
        "View extracted text": "উলিওৱা টেক্সট চাওক",
        "Understand This Document": "এই দস্তাবেজ বুজক",
        "Analyse This Text": "এই টেক্সট বিশ্লেষণ কৰক",
        "Analysing document...": "দস্তাবেজ বিশ্লেষণ হৈছে...",
        "Analysing...": "বিশ্লেষণ হৈছে...",
        "Scan Another Document": "আন এখন দস্তাবেজ স্কেন কৰক",
        "Reading image with OCR...": "OCR দ্বাৰা ছবি পঢ়া হৈছে...",
        "Preview extracted text": "উলিওৱা টেক্সটৰ পূৰ্বদৰ্শন",
        "Extracted": "উলিওৱা হৈছে", "Read": "পঢ়া হৈছে",
        "Download Safety Report": "সুৰক্ষা প্ৰতিবেদন ডাউনলোড কৰক",
        "File too large — maximum 10 MB.": "ফাইল বহুত ডাঙৰ — সৰ্বোচ্চ 10 MB।",
        "The uploaded file could not be read. Please remove it and upload again.": "আপলোড কৰা ফাইল পঢ়িব পৰা নগ'ল। আঁতৰাই পুনৰ আপলোড কৰক।",
        "instant_done": "তাৎক্ষণিক স্কেন সম্পূৰ্ণ — অফলাইন সুৰক্ষা প্ৰতিবেদন সাজু।",
        "instant_caption": "এই প্ৰতিবেদন দস্তাবেজৰ টেক্সটৰ পৰা তাৎক্ষণিকভাৱে তৈয়াৰ হয়।",
        "document_type": "দস্তাবেজৰ প্ৰকাৰ", "safety_score": "সুৰক্ষা স্কোৰ", "risk_level": "আশংকাৰ স্তৰ",
        "flat_rate": "ফ্লেট ৰেট পোৱা গ'ল", "key_details": "1. মূল তথ্য",
        "charges": "2. চাৰ্জ আৰু ফি", "no_charges": "স্পষ্ট ফি পোৱা নগ'ল। স্বাক্ষৰ কৰাৰ আগত বেংকৰ পৰা লিখিত তালিকা লওক।",
        "figures": "3. আৰ্থিক সংখ্যা", "amounts": "পৰিমাণ:", "tenure": "মেয়াদ:", "interest_rates": "সুদৰ হাৰ:",
        "hidden_risks": "4. লুকাই থকা আশংকা", "risk_terms": "4. আশংকাজনক শব্দ",
        "no_risks": "4. লুকাই থকা আশংকা\nএই স্কেনত স্পষ্ট আশংকাজনক শব্দ পোৱা নগ'ল।",
        "evidence": "প্ৰমাণ", "confirm": "5. স্বাক্ষৰ কৰাৰ আগত নিশ্চিত কৰক",
        "questions": "6. বেংক বিষয়াক প্ৰশ্ন",
        "checklist": "**স্বাক্ষৰ কৰাৰ আগত:** মুঠ পৰিশোধ · সকলো ফি · জৰিমনা · বীমা · সুৰক্ষা · তাৰিখ · চুক্তিৰ নকল।",
        "issue": "সমস্যা",
        "Safe": "সুৰক্ষিত", "Low Risk": "কম আশংকা", "Medium Risk": "মধ্য আশংকা", "High Risk": "উচ্চ আশংকা", "Critical Risk": "গুৰুতৰ আশংকা",
        "Financial Document": "আৰ্থিক দস্তাবেজ", "Loan Agreement": "ঋণ চুক্তি", "KCC / Agricultural Loan": "KCC / কৃষি ঋণ",
        "Charges & Fees": "চাৰ্জ আৰু ফি", "Penalty & Repayment": "জৰিমনা আৰু পৰিশোধ",
        "Borrower": "ঋণগ্ৰহীতা", "Loan Amount / Sanction Limit": "ঋণৰ পৰিমাণ / অনুমোদিত সীমা",
        "Interest Rate": "সুদৰ হাৰ", "Repayment Period": "পৰিশোধৰ সময়",
        "Security": "জামানত", "Insurance": "বীমা", "Other Terms": "অন্যান্য চৰ্ত",
        "Insurance & Add-ons": "বীমা আৰু সংযোজন", "Interest Risk": "সুদৰ আশংকা",
        "Security & Recovery": "জামানত আৰু পুনৰুদ্ধাৰ", "Privacy & Consent": "গোপনীয়তা আৰু সন্মতি",
        "Legal Rights": "আইনী অধিকাৰ", "Ambiguous Wording": "অস্পষ্ট ভাষা",
        "EMI Schedule": "EMI সময়সূচী", "Bank Notice": "বেংক জাননী", "Insurance Policy": "বীমা পলিচি",
        "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "দীঘল সহজ ব্যাখ্যা লাগে? তাৎক্ষণিক প্ৰতিবেদন দেখা দিলে Gemma ব্যৱহাৰ কৰক।",
        "Add Gemma detailed explanation": "Gemma বিস্তৃত ব্যাখ্যা যোগ কৰক",
        "Gemma is preparing a deeper explanation...": "Gemma গভীৰ ব্যাখ্যা প্ৰস্তুত কৰিছে...",
    }

    # ── Maithili ──────────────────────────────────────────────────────────────
    local_ui["Maithili"] = {
        "Text Extraction:": "टेक्स्ट निकासी:",
        "OCR extracted": "OCR निकासल",
        "characters": "अक्षर",
        "View extracted text": "निकासल टेक्स्ट देखू",
        "Understand This Document": "इ दस्तावेज बुझू",
        "Analyse This Text": "इ टेक्स्ट विश्लेषण करू",
        "Analysing document...": "दस्तावेज विश्लेषण भ रहल अछि...",
        "Analysing...": "विश्लेषण भ रहल अछि...",
        "Scan Another Document": "दोसर दस्तावेज स्कैन करू",
        "Reading image with OCR...": "OCR सँ छवि पढ़ल जा रहल अछि...",
        "Preview extracted text": "निकासल टेक्स्ट पूर्वावलोकन",
        "Extracted": "निकासल", "Read": "पढ़ल",
        "Download Safety Report": "सुरक्षा रिपोर्ट डाउनलोड करू",
        "File too large — maximum 10 MB.": "फाइल बहुत पैघ — अधिकतम 10 MB।",
        "The uploaded file could not be read. Please remove it and upload again.": "अपलोड फाइल पढ़ल नहि गेल। हटा कऽ फेर अपलोड करू।",
        "instant_done": "तुरंत स्कैन पूर्ण — ऑफलाइन सुरक्षा रिपोर्ट तैयार।",
        "instant_caption": "इ रिपोर्ट दस्तावेजक निकासल टेक्स्ट सँ तुरंत बनैत अछि।",
        "document_type": "दस्तावेज प्रकार", "safety_score": "सुरक्षा स्कोर", "risk_level": "जोखिम स्तर",
        "flat_rate": "फ्लैट रेट भेटल", "key_details": "1. मुख्य जानकारी",
        "charges": "2. शुल्क आ फीस", "no_charges": "स्पष्ट फीस नहि भेटल। दस्तखत सँ पहिने बैंक सँ लिखित सूची मांगू।",
        "figures": "3. वित्तीय आँकड़ा", "amounts": "राशि:", "tenure": "अवधि:", "interest_rates": "ब्याज दर:",
        "hidden_risks": "4. लुकाओल जोखिम", "risk_terms": "4. जोखिमपूर्ण शब्द",
        "no_risks": "4. लुकाओल जोखिम\nइ स्कैनमे स्पष्ट जोखिमपूर्ण शब्द नहि भेटल।",
        "evidence": "प्रमाण", "confirm": "5. दस्तखत सँ पहिने सुनिश्चित करू",
        "questions": "6. बैंक अधिकारीकें पूछबाक प्रश्न",
        "checklist": "**दस्तखत सँ पहिने:** कुल भुगतान · सब शुल्क · दंड · बीमा · सुरक्षा · तारीख · समझौताक नकल।",
        "issue": "मुद्दा",
        "Safe": "सुरक्षित", "Low Risk": "कम जोखिम", "Medium Risk": "मध्यम जोखिम", "High Risk": "अधिक जोखिम", "Critical Risk": "गंभीर जोखिम",
        "Financial Document": "वित्तीय दस्तावेज", "Loan Agreement": "ऋण समझौता", "KCC / Agricultural Loan": "KCC / कृषि ऋण",
        "Charges & Fees": "शुल्क आ फीस", "Penalty & Repayment": "दंड आ भुगतान",
        "Borrower": "ऋण लेनिहार", "Loan Amount / Sanction Limit": "ऋण राशि / स्वीकृति सीमा",
        "Interest Rate": "ब्याज दर", "Repayment Period": "भुगतान अवधि",
        "Security": "जमानत", "Insurance": "बीमा", "Other Terms": "अन्य शर्त",
        "Insurance & Add-ons": "बीमा आ अड-ऑन", "Interest Risk": "ब्याज जोखिम",
        "Security & Recovery": "जमानत आ वसूली", "Privacy & Consent": "गोपनीयता आ सहमति",
        "Legal Rights": "कानूनी अधिकार", "Ambiguous Wording": "अस्पष्ट भाषा",
        "EMI Schedule": "EMI अनुसूची", "Bank Notice": "बैंक नोटिस", "Insurance Policy": "बीमा पॉलिसी",
        "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "लंबा सरल व्याख्या चाही? तुरंत रिपोर्ट देखाइ दैत Gemma उपयोग करू।",
        "Add Gemma detailed explanation": "Gemma सँ विस्तृत व्याख्या जोड़ू",
        "Gemma is preparing a deeper explanation...": "Gemma गहिन व्याख्या तैयार कऽ रहल अछि...",
    }

    # ── Santali ───────────────────────────────────────────────────────────────
    local_ui["Santali"] = {
        "Text Extraction:": "ᱴᱮᱠᱥᱴ ᱵᱟᱦᱟᱨ:",
        "OCR extracted": "OCR ᱵᱟᱦᱟᱨ ᱠᱮᱫ",
        "characters": "ᱚᱠᱥᱚᱨ",
        "View extracted text": "ᱵᱟᱦᱟᱨ ᱴᱮᱠᱥᱴ ᱧᱮᱞ",
        "Understand This Document": "ᱤᱭᱟ ᱠᱟᱜᱚᱡ ᱵᱩᱡᱷᱩ",
        "Analyse This Text": "ᱤᱭᱟ ᱴᱮᱠᱥᱴ ᱵᱤᱥᱞᱮᱥᱚᱱ",
        "Analysing document...": "ᱠᱟᱜᱚᱡ ᱵᱤᱥᱞᱮᱥᱚᱱ ᱟᱫᱟ...",
        "Analysing...": "ᱵᱤᱥᱞᱮᱥᱚᱱ...",
        "Scan Another Document": "ᱵᱮᱞ ᱠᱟᱜᱚᱡ ᱥᱠᱮᱱ ᱢᱮᱛᱟᱜ",
        "Reading image with OCR...": "OCR ᱫᱚ ᱪᱷᱚᱵᱤ ᱯᱟᱲᱦᱟᱣ...",
        "Preview extracted text": "ᱵᱟᱦᱟᱨ ᱴᱮᱠᱥᱴ ᱯᱨᱤᱵᱷᱤᱭᱩ",
        "Extracted": "ᱵᱟᱦᱟᱨ", "Read": "ᱯᱟᱲᱦᱟᱣ",
        "Download Safety Report": "ᱥᱩᱨᱚᱠᱷᱟ ᱨᱤᱯᱚᱨᱴ ᱰᱟᱣᱱᱞᱳᱰ",
        "File too large — maximum 10 MB.": "ᱯᱷᱟᱭᱞ ᱵᱟᱦᱟ ᱵᱳᱲᱳ — ᱡᱟᱥᱛᱤ 10 MB।",
        "The uploaded file could not be read. Please remove it and upload again.": "ᱟᱯᱞᱳᱰ ᱯᱷᱟᱭᱞ ᱯᱟᱲᱦᱟᱣ ᱢᱮᱫ ᱠᱟᱱᱟ। ᱦᱚᱲᱟᱣ ᱫᱚ ᱫᱟᱨᱤ ᱟᱯᱞᱳᱰ ᱢᱮᱛᱟᱜ।",
        "instant_done": "ᱴᱩᱨᱩᱱᱛ ᱥᱠᱮᱱ ᱥᱮᱞᱮᱫ — ᱑ᱚᱯᱞᱟᱭᱤᱱ ᱥᱩᱨᱚᱠᱷᱟ ᱨᱤᱯᱚᱨᱴ ᱛᱮᱭᱟᱨ।",
        "instant_caption": "ᱤᱭᱟ ᱨᱤᱯᱚᱨᱴ ᱠᱟᱜᱚᱡᱟᱜ ᱴᱮᱠᱥᱴ ᱫᱚ ᱴᱩᱨᱩᱱᱛ ᱛᱮᱭᱟᱨ ᱟᱠᱟᱱᱟ।",
        "document_type": "ᱠᱟᱜᱚᱡ ᱯᱨᱚᱠᱟᱨ", "safety_score": "ᱥᱩᱨᱚᱠᱷᱟ ᱥᱠᱳᱨ", "risk_level": "ᱡᱚᱠᱷᱤᱢ ᱥᱛᱚᱨ",
        "flat_rate": "ᱯᱞᱮᱴ ᱨᱮᱴ ᱯᱟᱞ", "key_details": "1. ᱢᱩᱠᱷᱭ ᱡᱟᱱᱠᱟᱨᱤ",
        "charges": "2. ᱪᱟᱨᱡ ᱟᱨ ᱯᱷᱤᱥ", "no_charges": "ᱥᱯᱚᱥᱴ ᱯᱷᱤᱥ ᱯᱟᱞ ᱠᱟᱱᱟ। ᱮᱥᱴᱚᱠᱱᱟᱢᱮ ᱵᱤᱱᱫᱟ ᱵᱮᱱᱠ ᱫᱚ ᱞᱤᱠᱷᱤᱛ ᱞᱤᱥᱴ ᱢᱮᱛᱟᱜ।",
        "figures": "3. ᱑ᱤᱛᱤᱭ ᱑ᱟᱹᱠᱫᱟ", "amounts": "ᱴᱟᱠᱟ:", "tenure": "ᱢᱮᱭᱟᱫ:", "interest_rates": "ᱥᱩᱫ ᱦᱟᱨ:",
        "hidden_risks": "4. ᱞᱩᱠᱩ ᱡᱚᱠᱷᱤᱢ", "risk_terms": "4. ᱡᱚᱠᱷᱤᱢ ᱥᱚᱵᱫ",
        "no_risks": "4. ᱞᱩᱠᱩ ᱡᱚᱠᱷᱤᱢ\nᱤᱭᱟ ᱥᱠᱮᱱᱟᱜ ᱥᱯᱚᱥᱴ ᱡᱚᱠᱷᱤᱢ ᱥᱚᱵᱫ ᱯᱟᱞ ᱠᱟᱱᱟ।",
        "evidence": "ᱯ᱑ᱩᱢᱟᱱ", "confirm": "5. ᱮᱥᱴᱚᱠᱱᱟᱢᱮ ᱵᱤᱱᱫᱟ ᱱᱤᱥᱪᱤᱛ ᱢᱮᱛᱟᱜ",
        "questions": "6. ᱵᱮᱱᱠ ᱑᱑ᱤᱠᱟᱨᱤᱠᱤ ᱥᱚᱫᱷᱩ",
        "checklist": "**ᱮᱥᱴᱚᱠᱱᱟᱢᱮ ᱵᱤᱱᱫᱟ:** ᱥᱚᱵ ᱵᱦᱩᱜᱛᱟᱱ · ᱯᱷᱤᱥ · ᱡᱩᱨᱢᱟᱱᱟ · ᱵᱤᱢᱟ · ᱥᱩᱨᱚᱠᱷᱟ · ᱛᱟᱨᱤᱠᱷ · ᱪᱩᱠᱛᱤ ᱱᱚᱠᱞ।",
        "issue": "ᱥᱚᱢᱚᱥᱟ",
        "Safe": "ᱥᱩᱨᱚᱠᱷᱤᱛ", "Low Risk": "ᱠᱚᱢ ᱡᱚᱠᱷᱤᱢ", "Medium Risk": "ᱢᱚᱡᱷᱤᱢ ᱡᱚᱠᱷᱤᱢ", "High Risk": "ᱵᱟᱹᱲᱛᱤ ᱡᱚᱠᱷᱤᱢ", "Critical Risk": "ᱜᱚᱵᱷᱤᱨ ᱡᱚᱠᱷᱤᱢ",
        "Financial Document": "᱑ᱤᱛᱤᱭ ᱠᱟᱜᱚᱡ", "Loan Agreement": "ᱫᱟᱞᱟᱱ ᱪᱩᱠᱛᱤ", "KCC / Agricultural Loan": "KCC / ᱠᱷᱮᱛᱤ ᱫᱟᱞᱟᱱ",
        "Charges & Fees": "ᱪᱟᱨᱡ ᱟᱨ ᱯᱷᱤᱥ", "Penalty & Repayment": "ᱡᱩᱨᱢᱟᱱᱟ ᱟᱨ ᱵᱦᱩᱜᱛᱟᱱ",
        "Borrower": "ᱫᱟᱞᱟᱱ ᱞᱮᱫᱚ", "Loan Amount / Sanction Limit": "ᱫᱟᱞᱟᱱ ᱴᱟᱠᱟ / ᱢᱟᱱᱡᱩᱨ ᱥᱤᱢᱟ",
        "Interest Rate": "ᱥᱩᱫ ᱦᱟᱨ", "Repayment Period": "ᱵᱦᱩᱜᱛᱟᱱ ᱢᱮᱭᱟᱫ",
        "Security": "ᱡᱟᱢᱤᱱ", "Insurance": "ᱵᱤᱢᱟ", "Other Terms": "ᱟᱹᱨᱤ ᱥᱚᱨᱛ",
        "Insurance & Add-ons": "ᱵᱤᱢᱟ ᱟᱨ ᱑ᱚᱞᱟᱠ", "Interest Risk": "ᱥᱩᱫ ᱡᱚᱠᱷᱤᱢ",
        "Security & Recovery": "ᱡᱟᱢᱤᱱ ᱟᱨ ᱵᱟᱯᱟᱪ", "Privacy & Consent": "ᱜᱩᱯᱛᱤ ᱟᱨ ᱢᱟᱱᱦᱟ",
        "Legal Rights": "ᱠᱟᱱᱩᱱ ᱑ᱦᱤᱠᱟᱨ", "Ambiguous Wording": "᱑ᱥᱯᱚᱥᱴ ᱵᱷᱟᱥᱟ",
        "EMI Schedule": "EMI ᱥᱚᱢᱭ ᱥᱩᱪᱤ", "Bank Notice": "ᱵᱮᱱᱠ ᱱᱳᱴᱤᱥ", "Insurance Policy": "ᱵᱤᱢᱟ ᱯᱚᱞᱤᱥᱤ",
        "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "ᱞᱟᱹᱵᱟ ᱥᱦᱚᱡ ᱵᱩᱡᱷᱟᱣ ᱫᱚᱨᱠᱟᱨ? ᱴᱩᱨᱩᱱᱛ ᱨᱤᱯᱚᱨᱴ ᱫᱤᱥᱩᱢ ᱞᱮ Gemma ᱵᱮᱵᱷᱟᱨ ᱢᱮᱛᱟᱜ।",
        "Add Gemma detailed explanation": "Gemma ᱵᱤᱥᱛᱟᱨ ᱵᱩᱡᱷᱟᱣ ᱡᱚᱲᱟᱣ",
        "Gemma is preparing a deeper explanation...": "Gemma ᱜᱷᱚᱨᱟ ᱵᱩᱡᱷᱟᱣ ᱛᱮᱭᱟᱨ ᱟᱫᱟ...",
    }

    # ── Sindhi ────────────────────────────────────────────────────────────────
    local_ui["Sindhi"] = {
        "Text Extraction:": "متن ڪڍڻ:",
        "OCR extracted": "OCR ڪڍيو",
        "characters": "اکر",
        "View extracted text": "ڪڍيل متن ڏسو",
        "Understand This Document": "هي دستاويز سمجهو",
        "Analyse This Text": "هي متن جائزو وٺو",
        "Analysing document...": "دستاويز جو جائزو ٿي رهيو آهي...",
        "Analysing...": "جائزو ٿي رهيو آهي...",
        "Scan Another Document": "ٻيو دستاويز اسڪين ڪريو",
        "Reading image with OCR...": "OCR سان تصوير پڙهي رهيو آهي...",
        "Preview extracted text": "ڪڍيل متن پريويو",
        "Extracted": "ڪڍيو", "Read": "پڙهيو",
        "Download Safety Report": "حفاظتي رپورٽ ڊائونلوڊ ڪريو",
        "File too large — maximum 10 MB.": "فائيل تمام وڏي آهي — وڌ ۾ وڌ 10 MB.",
        "The uploaded file could not be read. Please remove it and upload again.": "اپلوڊ ڪيل فائيل پڙهي نه سگهيو. هٽائي ٻيهر اپلوڊ ڪريو.",
        "instant_done": "فوري اسڪين مڪمل — آف لائن حفاظتي رپورٽ تيار.",
        "instant_caption": "هي رپورٽ دستاويز جي متن مان فوري ٺهي ٿي.",
        "document_type": "دستاويز جو قسم", "safety_score": "حفاظتي اسڪور", "risk_level": "خطري جو درجو",
        "flat_rate": "فليٽ ريٽ مليو", "key_details": "1. اهم تفصيل",
        "charges": "2. چارج ۽ فيس", "no_charges": "واضح فيس نه ملي. دستخط کان اڳ بينڪ کان لکيل فهرست وٺو.",
        "figures": "3. مالي انگ", "amounts": "رقم:", "tenure": "مدت:", "interest_rates": "سود جو شرح:",
        "hidden_risks": "4. لڪيل خطرا", "risk_terms": "4. خطرناڪ لفظ",
        "no_risks": "4. لڪيل خطرا\nهن اسڪين ۾ واضح خطرناڪ لفظ نه مليا.",
        "evidence": "ثبوت", "confirm": "5. دستخط کان اڳ تصديق ڪريو",
        "questions": "6. بينڪ آفيسر کان پڇڻ جا سوال",
        "checklist": "**دستخط کان اڳ:** ڪل واپسي · سڀ فيس · جرمانو · بيمو · ضمانت · تاريخ · معاهدي جي نقل.",
        "issue": "مسئلو",
        "Safe": "محفوظ", "Low Risk": "گهٽ خطرو", "Medium Risk": "وچولو خطرو", "High Risk": "وڌيڪ خطرو", "Critical Risk": "سنگين خطرو",
        "Financial Document": "مالي دستاويز", "Loan Agreement": "قرض معاهدو", "KCC / Agricultural Loan": "KCC / زرعي قرضو",
        "Charges & Fees": "چارج ۽ فيس", "Penalty & Repayment": "جرمانو ۽ واپسي",
        "Borrower": "قرضدار", "Loan Amount / Sanction Limit": "قرض جي رقم / منظور حد",
        "Interest Rate": "سود جو شرح", "Repayment Period": "واپسي جو عرصو",
        "Security": "ضمانت", "Insurance": "بيمو", "Other Terms": "ٻيون شرطون",
        "Insurance & Add-ons": "بيمو ۽ اضافي", "Interest Risk": "سود جو خطرو",
        "Security & Recovery": "ضمانت ۽ وصولي", "Privacy & Consent": "رازداري ۽ رضامندي",
        "Legal Rights": "قانوني حق", "Ambiguous Wording": "غيرواضح ٻولي",
        "EMI Schedule": "EMI شيڊول", "Bank Notice": "بينڪ نوٽيس", "Insurance Policy": "بيمي جي پاليسي",
        "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "ڊگهي سادي وضاحت گهرجي؟ فوري رپورٽ اچڻ بعد Gemma استعمال ڪريو.",
        "Add Gemma detailed explanation": "Gemma سان تفصيلي وضاحت شامل ڪريو",
        "Gemma is preparing a deeper explanation...": "Gemma گهري وضاحت تيار ڪري رهيو آهي...",
    }

    # ── Dogri ─────────────────────────────────────────────────────────────────
    local_ui["Dogri"] = {
        "Text Extraction:": "टेक्स्ट कडना:",
        "OCR extracted": "OCR ने कड्ढे",
        "characters": "अक्खर",
        "View extracted text": "कड्ढे टेक्स्ट देखो",
        "Understand This Document": "इ दस्तावेज समझो",
        "Analyse This Text": "इ टेक्स्ट दा विश्लेषण करो",
        "Analysing document...": "दस्तावेज दा विश्लेषण होंदा पेया ऐ...",
        "Analysing...": "विश्लेषण होंदा पेया ऐ...",
        "Scan Another Document": "दूआ दस्तावेज स्कैन करो",
        "Reading image with OCR...": "OCR कन्नै तस्वीर पढ़ी जा रई ऐ...",
        "Preview extracted text": "कड्ढे टेक्स्ट दा झलक",
        "Extracted": "कड्ढे", "Read": "पढ़े",
        "Download Safety Report": "सुरक्षा रिपोर्ट डाउनलोड करो",
        "File too large — maximum 10 MB.": "फाइल बड्डी ऐ — ज्यादा 10 MB नेईं।",
        "The uploaded file could not be read. Please remove it and upload again.": "अपलोड फाइल पढ़ी नेईं गई। हटा करी दुबारा अपलोड करो।",
        "instant_done": "तुरत स्कैन मुकम्मल — ऑफलाइन सुरक्षा रिपोर्ट तैयार ऐ।",
        "instant_caption": "इ रिपोर्ट दस्तावेज दे टेक्स्ट थमां तुरत बनदी ऐ।",
        "document_type": "दस्तावेज दी किस्म", "safety_score": "सुरक्षा स्कोर", "risk_level": "खतरे दा दर्जा",
        "flat_rate": "फ्लैट रेट मिलेया", "key_details": "1. मुक्ख जानकारी",
        "charges": "2. चार्ज ते फीस", "no_charges": "साफ फीस नेईं मिली। दस्तखत करने थमां पहलें बैंक थमां लिखती सूची लओ।",
        "figures": "3. मालियाती आंकड़े", "amounts": "रकम:", "tenure": "मुद्दत:", "interest_rates": "ब्याज दर:",
        "hidden_risks": "4. छपे खतरे", "risk_terms": "4. खतरनाक शब्द",
        "no_risks": "4. छपे खतरे\nइस स्कैन च साफ खतरनाक शब्द नेईं मिले।",
        "evidence": "सबूत", "confirm": "5. दस्तखत थमां पहलें पक्का करो",
        "questions": "6. बैंक अधिकारी थमां पुच्छने आले सवाल",
        "checklist": "**दस्तखत थमां पहलें:** कुल वापसी · सारी फीसां · जुर्माना · बीमा · जमानत · तारीख · इकरारनामे दी नकल।",
        "issue": "मुद्दा",
        "Safe": "सुरक्षित", "Low Risk": "घट्ट खतरा", "Medium Risk": "दरमियाना खतरा", "High Risk": "बड्डा खतरा", "Critical Risk": "गंभीर खतरा",
        "Financial Document": "मालियाती दस्तावेज", "Loan Agreement": "कर्जा इकरारनामा", "KCC / Agricultural Loan": "KCC / खेतीबाड़ी कर्जा",
        "Charges & Fees": "चार्ज ते फीसां", "Penalty & Repayment": "जुर्माना ते वापसी",
        "Borrower": "कर्जदार", "Loan Amount / Sanction Limit": "कर्जे दी रकम / मंजूरी सीमा",
        "Interest Rate": "ब्याज दर", "Repayment Period": "वापसी दी मुद्दत",
        "Security": "जमानत", "Insurance": "बीमा", "Other Terms": "दूजी शर्तां",
        "Insurance & Add-ons": "बीमा ते अड-ऑन", "Interest Risk": "ब्याज दा खतरा",
        "Security & Recovery": "जमानत ते वसूली", "Privacy & Consent": "निजता ते सहमति",
        "Legal Rights": "कानूनी हक्क", "Ambiguous Wording": "अस्पष्ट बोली",
        "EMI Schedule": "EMI शिड्यूल", "Bank Notice": "बैंक नोटिस", "Insurance Policy": "बीमा पॉलिसी",
        "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "लम्मी सरल वजाहत चाहिदी ऐ? तुरत रिपोर्ट दिखने दे बाद Gemma इस्तेमाल करो।",
        "Add Gemma detailed explanation": "Gemma कन्नै विस्तृत वजाहत जोड़ो",
        "Gemma is preparing a deeper explanation...": "Gemma गहरी वजाहत तैयार करदा पेया ऐ...",
    }

    # ── Konkani ───────────────────────────────────────────────────────────────
    local_ui["Konkani"] = {
        "Text Extraction:": "मजकूर काडप:",
        "OCR extracted": "OCR काडलो",
        "characters": "अक्षरां",
        "View extracted text": "काडिल्लो मजकूर पळयात",
        "Understand This Document": "हो दस्तऐवज समजात",
        "Analyse This Text": "ह्या मजकुराचें विश्लेषण करात",
        "Analysing document...": "दस्तऐवजाचें विश्लेषण जाता आसा...",
        "Analysing...": "विश्लेषण जाता आसा...",
        "Scan Another Document": "दुसरो दस्तऐवज स्कॅन करात",
        "Reading image with OCR...": "OCR न इमेज वाचतलो...",
        "Preview extracted text": "काडिल्ल्या मजकुराचो प्रिव्ह्यू",
        "Extracted": "काडलो", "Read": "वाचलो",
        "Download Safety Report": "सुरक्षा रिपोर्ट डाउनलोड करात",
        "File too large — maximum 10 MB.": "फाइल खूब वडली — जास्तीत जास्त 10 MB.",
        "The uploaded file could not be read. Please remove it and upload again.": "अपलोड केल्लो फाइल वाचूंक जालो नहि. हाडून परत अपलोड करात.",
        "instant_done": "तात्काळ स्कॅन पुरो — ऑफलाइन सुरक्षा रिपोर्ट तयार.",
        "instant_caption": "हो रिपोर्ट दस्तऐवजाच्या मजकुरावेल्यान तात्काळ तयार जाता.",
        "document_type": "दस्तऐवजाचो प्रकार", "safety_score": "सुरक्षा स्कोर", "risk_level": "जोखीम पातळी",
        "flat_rate": "फ्लॅट रेट सापडलो", "key_details": "1. मुख्य माहिती",
        "charges": "2. चार्ज आनी फी", "no_charges": "स्पष्ट फी सापडली नहि. सही करचे आदीं बँकेकडेन लिखीत यादी मागात.",
        "figures": "3. आर्थिक आकडे", "amounts": "रक्कम:", "tenure": "मुदत:", "interest_rates": "व्याज दर:",
        "hidden_risks": "4. लपिल्ले जोखीम", "risk_terms": "4. जोखमी शब्द",
        "no_risks": "4. लपिल्ले जोखीम\nह्या स्कॅनात स्पष्ट जोखमी शब्द सापडले नहित.",
        "evidence": "पुरावो", "confirm": "5. सही करचे आदीं खात्री करात",
        "questions": "6. बँक अधिकाऱ्याक विचारपाचे प्रश्न",
        "checklist": "**सही करचे आदीं:** एकूण परतफेड · सगळे चार्ज · दंड · विमो · जामीन · तारीख · कराराची सही केल्ली प्रत.",
        "issue": "मुद्दो",
        "Safe": "सुरक्षित", "Low Risk": "उणो जोखीम", "Medium Risk": "मध्यम जोखीम", "High Risk": "चड जोखीम", "Critical Risk": "गंभीर जोखीम",
        "Financial Document": "आर्थिक दस्तऐवज", "Loan Agreement": "कर्ज करार", "KCC / Agricultural Loan": "KCC / शेती कर्ज",
        "Charges & Fees": "चार्ज आनी फी", "Penalty & Repayment": "दंड आनी परतफेड",
        "Borrower": "कर्जदार", "Loan Amount / Sanction Limit": "कर्ज रक्कम / मंजुरी मर्यादा",
        "Interest Rate": "व्याज दर", "Repayment Period": "परतफेड मुदत",
        "Security": "जामीन", "Insurance": "विमो", "Other Terms": "इतर शर्ती",
        "Insurance & Add-ons": "विमो आनी अड-ऑन", "Interest Risk": "व्याज जोखीम",
        "Security & Recovery": "जामीन आनी वसुली", "Privacy & Consent": "खाजगीपण आनी संमती",
        "Legal Rights": "कायदेशीर हक्क", "Ambiguous Wording": "अस्पष्ट भास",
        "EMI Schedule": "EMI वेळापत्रक", "Bank Notice": "बँक नोटीस", "Insurance Policy": "विमा पॉलिसी",
        "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "व्हडलो सोपो खुलासो जाय? तात्काळ रिपोर्ट दिसतकच Gemma वापरात.",
        "Add Gemma detailed explanation": "Gemma कडेन विस्तृत खुलासो घालात",
        "Gemma is preparing a deeper explanation...": "Gemma खोल खुलासो तयार करता...",
    }

    # ── Manipuri ──────────────────────────────────────────────────────────────
    local_ui["Manipuri"] = {
        "Text Extraction:": "꯴ꯦꯛꯁꯇ ꯁꯤꯔꯤꯕꯥ:",
        "OCR extracted": "OCR ꯁꯤꯔꯔꯦ",
        "characters": "ꯑꯀ꯭ꯁꯔ",
        "View extracted text": "ꯁꯤꯔꯔꯤꯕꯥ ꯴ꯦꯛꯁꯇ ꯎꯕꯤꯌꯨ",
        "Understand This Document": "ꯃꯁꯤ ꯍꯟꯗꯛ ꯕꯨꯖꯤꯌꯨ",
        "Analyse This Text": "ꯃꯁꯤ ꯴ꯦꯛꯁꯇ ꯑꯦꯅꯦꯂꯥꯏꯖ ꯇꯧꯌꯨ",
        "Analysing document...": "ꯍꯟꯗꯛ ꯑꯦꯅꯦꯂꯥꯏꯖ ꯇꯧꯔꯤ...",
        "Analysing...": "ꯑꯦꯅꯦꯂꯥꯏꯖ...",
        "Scan Another Document": "ꯌꯥꯝꯅꯥ ꯍꯟꯗꯛ ꯁꯛꯦꯟ ꯇꯧꯌꯨ",
        "Reading image with OCR...": "OCR ꯅꯥ ꯏꯃꯦꯖ ꯂꯧꯔꯤ...",
        "Preview extracted text": "ꯁꯤꯔꯔꯤꯕꯥ ꯴ꯦꯛꯁꯇ ꯄ꯭ꯔꯤꯚꯤꯌꯨ",
        "Extracted": "ꯁꯤꯔꯔꯦ", "Read": "ꯂꯧꯔꯦ",
        "Download Safety Report": "ꯁꯨꯔꯛꯁꯥ ꯔꯤꯄꯣꯔꯇ ꯗꯥꯎꯅꯂꯣꯗ ꯇꯧꯌꯨ",
        "File too large — maximum 10 MB.": "ꯐꯥꯏꯜ ꯁꯜ ꯑꯃꯗꯝ ꯕꯥꯔꯤ — ꯖꯥꯁ꯭ꯇꯤ 10 MB।",
        "The uploaded file could not be read. Please remove it and upload again.": "ꯑꯄꯂꯧꯗ ꯐꯥꯏꯜ ꯂꯧꯕꯥ ꯉꯝꯗꯦ। ꯍꯩꯕꯤꯌꯨ ꯑꯃꯁꯨꯡ ꯄꯨꯅꯥ ꯑꯄꯂꯧꯗ ꯇꯧꯌꯨ।",
        "instant_done": "꯴ꯣꯔꯝ ꯁꯛꯦꯟ ꯁꯦꯜꯂꯦ — ꯑꯣꯐꯂꯥꯏꯅ ꯁꯨꯔꯛꯁꯥ ꯔꯤꯄꯣꯔꯇ ꯇꯦꯌꯥꯔ।",
        "instant_caption": "ꯃꯁꯤ ꯔꯤꯄꯣꯔꯇ ꯍꯟꯗꯛꯀꯤ ꯴ꯦꯛꯁꯇꯁꯤꯅ ꯴ꯣꯔꯝ ꯑꯣꯌ।",
        "document_type": "ꯍꯟꯗꯛ ꯃꯔꯨꯑꯣꯏꯕ", "safety_score": "ꯁꯨꯔꯛꯁꯥ ꯁꯀꯣꯔ", "risk_level": "ꯔꯤꯁ꯭ꯛ ꯂꯦꯚꯦꯜ",
        "flat_rate": "ꯐ꯭ꯂꯦꯠ ꯔꯦꯠ ꯄꯥꯡꯊꯣꯛꯔꯦ", "key_details": "1. ꯃꯨꯛꯅꯥ ꯃꯔꯨꯑꯣꯏꯕ",
        "charges": "2. ꯆꯥꯔꯖ ꯑꯃꯁꯨꯡ ꯐꯤꯁ", "no_charges": "ꯁ꯭ꯄꯁ꯭ꯠ ꯐꯤꯁ ꯉꯃꯗꯦ। ꯁꯥꯢꯟ ꯇꯧꯒꯗꯕꯥ ꯃꯇꯝꯗꯥ ꯕꯦꯛꯀꯗꯥ ꯂꯤꯈꯤꯠ ꯂꯤꯁ꯭ꯇ ꯂꯧꯌꯨ।",
        "figures": "3. ꯄꯥꯢꯁꯥꯒꯤ ꯑꯦꯝꯑꯧꯟꯇ", "amounts": "ꯑꯃꯥꯎꯟꯇ:", "tenure": "ꯇꯦꯡꯕꯥ:", "interest_rates": "ꯏꯟꯇ꯭ꯔꯦꯁꯇ ꯔꯦꯠ:",
        "hidden_risks": "4. ꯂꯤꯐꯨ ꯔꯤꯁ꯭ꯛ", "risk_terms": "4. ꯔꯤꯁ꯭ꯛ ꯑꯣꯏꯕꯥ ꯑꯣꯌꯕꯒꯤ ꯑꯣꯢ",
        "no_risks": "4. ꯂꯤꯐꯨ ꯔꯤꯁ꯭ꯛ\nꯃꯁꯤ ꯁꯛꯦꯅꯗꯥ ꯁ꯭ꯄꯁ꯭ꯠ ꯔꯤꯁ꯭ꯛ ꯑꯣꯢ ꯉꯃꯗꯦ।",
        "evidence": "ꯑꯦꯚꯤꯗꯦꯟꯁ", "confirm": "5. ꯁꯥꯢꯟ ꯇꯧꯒꯗꯕꯥ ꯃꯇꯝꯗꯥ ꯀꯟꯐꯥꯔꯝ ꯇꯧꯌꯨ",
        "questions": "6. ꯕꯦꯛ ꯑꯣꯐꯤꯁꯔꯒꯥ ꯍꯥꯌꯕꯤꯌꯨ",
        "checklist": "**ꯁꯥꯢꯟ ꯇꯧꯒꯗꯕꯥ ꯃꯇꯝꯗꯥ:** ꯇꯣꯇꯦꯜ ꯔꯤꯄꯦꯃꯦꯟꯇ · ꯐꯤꯁ · ꯄꯦꯅꯦꯜꯇꯤ · ꯏꯟꯁꯨꯔꯦꯟꯁ · ꯁꯤꯀꯨꯔꯤꯇꯤ · ꯗꯦꯠ · ꯑꯒꯨꯝꯒꯤ ꯀꯄꯤ।",
        "issue": "ꯃꯁꯤꯒꯤ ꯃꯔꯨꯑꯣꯏꯕ",
        "Safe": "ꯁꯨꯔꯛꯁꯤꯠ", "Low Risk": "ꯀꯃ ꯔꯤꯁ꯭ꯛ", "Medium Risk": "ꯃꯩꯅꯤꯡ ꯔꯤꯁ꯭ꯛ", "High Risk": "ꯋꯥꯈꯜ ꯔꯤꯁ꯭ꯛ", "Critical Risk": "ꯃꯁꯤꯒꯤ ꯔꯤꯁ꯭ꯛ",
        "Financial Document": "ꯄꯥꯢꯁꯥꯒꯤ ꯍꯟꯗꯛ", "Loan Agreement": "ꯂꯣꯟ ꯑꯒꯨꯝꯗꯝꯕꯥ", "KCC / Agricultural Loan": "KCC / ꯂꯝꯗꯝ ꯂꯣꯟ",
        "Charges & Fees": "ꯆꯥꯔꯖ ꯑꯃꯁꯨꯡ ꯐꯤꯁ", "Penalty & Repayment": "ꯄꯦꯅꯦꯜꯇꯤ ꯑꯃꯁꯨꯡ ꯔꯤꯄꯦꯃꯦꯟꯇ",
        "Borrower": "ꯂꯣꯟ ꯂꯩꯕꯥ", "Loan Amount / Sanction Limit": "ꯂꯣꯟ ꯑꯃꯥꯎꯟꯇ / ꯁꯦꯂꯛꯁꯟ ꯂꯤꯃꯤꯠ",
        "Interest Rate": "ꯏꯟꯇ꯭ꯔꯦꯁꯇ ꯔꯦꯠ", "Repayment Period": "ꯔꯤꯄꯦꯃꯦꯟꯇ ꯃꯇꯝ",
        "Security": "ꯁꯤꯀꯨꯔꯤꯇꯤ", "Insurance": "ꯏꯟꯁꯨꯔꯦꯟꯁ", "Other Terms": "ꯌꯥꯝꯅꯥ ꯇꯔꯝꯁ",
        "Insurance & Add-ons": "ꯏꯟꯁꯨꯔꯦꯟꯁ ꯑꯃꯁꯨꯡ ꯑꯦꯗ-ꯑꯅꯁ", "Interest Risk": "ꯏꯟꯇ꯭ꯔꯦꯁꯇ ꯔꯤꯁ꯭ꯛ",
        "Security & Recovery": "ꯁꯤꯀꯨꯔꯤꯇꯤ ꯑꯃꯁꯨꯡ ꯔꯤꯀꯚꯔꯤ", "Privacy & Consent": "ꯄ꯭ꯔꯥꯏꯚꯦꯁꯤ ꯑꯃꯁꯨꯡ ꯀꯟꯁꯦꯟꯠ",
        "Legal Rights": "ꯂꯤꯒꯦꯜ ꯔꯥꯏꯠꯁ", "Ambiguous Wording": "ꯑꯁ꯭ꯄꯁ꯭ꯠ ꯋꯣꯔꯗꯤꯡ",
        "EMI Schedule": "EMI ꯁꯛꯦꯖꯨꯜ", "Bank Notice": "ꯕꯦꯛ ꯅꯣꯇꯤꯁ", "Insurance Policy": "ꯏꯟꯁꯨꯔꯦꯟꯁ ꯄꯣꯂꯤꯁꯤ",
        "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "ꯋꯥꯈꯜ ꯁꯤꯃꯄꯜ ꯚꯥꯏꯅꯤꯡ ꯗꯔꯀꯥꯔ? ꯴ꯣꯔꯝ ꯔꯤꯄꯣꯔꯇ ꯗꯤꯁꯨꯝ ꯂꯩꯅꯥ Gemma ꯚꯦꯕꯦꯔ ꯇꯧꯌꯨ।",
        "Add Gemma detailed explanation": "Gemma ꯗꯤꯇꯦꯂꯗ ꯕꯥꯢꯅꯤꯡ ꯌꯥꯎꯅꯥ ꯂꯩꯁꯤꯜꯂꯨ",
        "Gemma is preparing a deeper explanation...": "Gemma ꯒꯥꯐꯨ ꯚꯥꯢꯅꯤꯡ ꯇꯦꯌꯥꯔ ꯇꯧꯔꯤ...",
    }

    # ── Bodo ──────────────────────────────────────────────────────────────────
    local_ui["Bodo"] = {
        "Text Extraction:": "टेक्स्ट बाहिर करना:",
        "OCR extracted": "OCR ने बाहिर कैल",
        "characters": "अक्खर",
        "View extracted text": "बाहिर कैल टेक्स्ट नागिरो",
        "Understand This Document": "बे दस्तावेज बुजिमो",
        "Analyse This Text": "बे टेक्स्ट दा विश्लेषण करो",
        "Analysing document...": "दस्तावेज विश्लेषण जाया...",
        "Analysing...": "विश्लेषण जाया...",
        "Scan Another Document": "फारसे दस्तावेज स्कैन करो",
        "Reading image with OCR...": "OCR न इमेज पढ़ाया...",
        "Preview extracted text": "बाहिर टेक्स्ट प्रिव्ह्यू",
        "Extracted": "बाहिर", "Read": "पढ़ाया",
        "Download Safety Report": "सुरक्षा रिपोर्ट डाउनलोड करो",
        "File too large — maximum 10 MB.": "फाइल जोबथा बोड़ो — जास्त 10 MB नहि।",
        "The uploaded file could not be read. Please remove it and upload again.": "अपलोड फाइल पढ़ाया नाय। हाबिलाय दाय फारसे अपलोड करो।",
        "instant_done": "तुरत स्कैन पुरो — अफलाइन सुरक्षा रिपोर्ट थैयार।",
        "instant_caption": "बे रिपोर्ट दस्तावेजनि टेक्स्ट थमा तुरत थैयार जाय।",
        "document_type": "दस्तावेज प्रकार", "safety_score": "सुरक्षा स्कोर", "risk_level": "जुलाव दर्जा",
        "flat_rate": "फ्लैट रेट पाया", "key_details": "1. मुखुड जानकारी",
        "charges": "2. चार्ज आरो फीस", "no_charges": "सिगाङ फीस सिगाङ नाय। दस्तखत करना आगु बैंकनि थमा लिखित सूची लाबो।",
        "figures": "3. मालि जानकारी", "amounts": "टाका:", "tenure": "समय:", "interest_rates": "ब्याज दर:",
        "hidden_risks": "4. सिमाय जुलाव", "risk_terms": "4. जुलाव शब्द",
        "no_risks": "4. सिमाय जुलाव\nबे स्कैनाव सिगाङ जुलाव शब्द सिगाङ नाय।",
        "evidence": "सबुत", "confirm": "5. दस्तखत करना आगु नियोरो",
        "questions": "6. बैंक अफिसार थमा थावनाय प्रश्न",
        "checklist": "**दस्तखत करना आगु:** सिगाङ भुगतान · सिगाङ फीस · जुर्मान · बिमा · जामिन · तारिख · इकरारनामा नकल।",
        "issue": "समस्या",
        "Safe": "सुरक्षित", "Low Risk": "गुबुन जुलाव", "Medium Risk": "मजलाय जुलाव", "High Risk": "जोबथा जुलाव", "Critical Risk": "गंभीर जुलाव",
        "Financial Document": "मालि दस्तावेज", "Loan Agreement": "उनाव गोसो इकरारनामा", "KCC / Agricultural Loan": "KCC / खेति उनाव गोसो",
        "Charges & Fees": "चार्ज आरो फीस", "Penalty & Repayment": "जुर्माना आरो भुगतान",
        "Borrower": "उनाव लेनिहार", "Loan Amount / Sanction Limit": "उनाव टाका / स्वीकृति सीमा",
        "Interest Rate": "ब्याज दर", "Repayment Period": "भुगतान समय",
        "Security": "जामिन", "Insurance": "बिमा", "Other Terms": "फारसे शर्त",
        "Insurance & Add-ons": "बिमा आरो अड-ऑन", "Interest Risk": "ब्याज जुलाव",
        "Security & Recovery": "जामिन आरो वसूली", "Privacy & Consent": "गोपनीयता आरो अनुमति",
        "Legal Rights": "कानूनि हक", "Ambiguous Wording": "अस्पष्ट भाषा",
        "EMI Schedule": "EMI समयसूची", "Bank Notice": "बैंक नोटिस", "Insurance Policy": "बिमा पॉलिसी",
        "Need a longer plain-language explanation? Use Gemma after the instant report is already shown.": "लाम्बा सोंदोर बुजाय लाबो? तुरत रिपोर्ट बाहागो जानाय उनावनि Gemma बाहागो लाबो।",
        "Add Gemma detailed explanation": "Gemma नि फोसाब बुजाय जोड़ो",
        "Gemma is preparing a deeper explanation...": "Gemma जोबथा बुजाय थैयार जाया...",
    }

    if text in local_ui.get(_scan_language(), {}):
        return local_ui[_scan_language()][text]
    english_labels = {
        "instant_done": "Instant scan complete — offline safety report generated.",
        "instant_caption": "This report is created immediately from the extracted document text. It does not wait for Gemma, so the scan stays fast.",
        "document_type": "Document Type",
        "safety_score": "Safety Score",
        "risk_level": "Risk Level",
        "flat_rate": "Flat rate detected",
        "key_details": "1. Key Details Found",
        "charges": "2. Charges & Fees",
        "no_charges": "No exact fee amount was clearly found. Ask the bank for a written list of every charge before signing.",
        "figures": "3. Financial Figures Found",
        "amounts": "Amounts:",
        "tenure": "Tenure:",
        "interest_rates": "Interest Rates:",
        "hidden_risks": "4. Hidden Risks Found",
        "risk_terms": "4. Risky Terms",
        "no_risks": "4. Hidden Risks\nNo obvious risky terms detected in this text scan.",
        "evidence": "Evidence",
        "confirm": "5. Confirm Before Signing",
        "questions": "6. Questions To Ask Bank Officer",
        "checklist": "**Before signing checklist:** total repayment · all fees · penalty · insurance · security/collateral · due date · signed copy of agreement.",
        "issue": "issue",
    }
    lang = _scan_language()
    translated = local_ui.get(lang, {}).get(text) or SCAN_TEXT.get(lang, {}).get(text)
    if translated:
        return translated
    resolved = english_labels.get(text) or text
    if lang.lower() != "english":
        return translate_text(resolved, lang, context="RuralFinance document scanner UI label", live=True)
    return resolved


def _scan_upload_button_text() -> str:
    return {
        "Hindi": "फ़ाइल चुनें",
        "Bengali": "ফাইল বেছে নিন",
        "Tamil": "கோப்பு தேர்வு",
        "Gujarati": "ફાઇલ પસંદ કરો",
    }.get(_scan_language(), translate_text("Upload", _scan_language(), context="file upload button label") if _scan_language().lower() != "english" else "Upload")


def _scan_value(text: str) -> str:
    lang = _scan_language()
    if not text:
        return text
    exact = VALUE_TRANSLATIONS.get(lang, {}).get(text)
    if exact:
        return exact
    if lang == "Hindi":
        text = text.replace("p.a.", "प्रति वर्ष")
        text = text.replace("as applicable from time to time", "समय-समय पर लागू")
        text = text.replace("Within", "के भीतर")
        text = text.replace("months", "महीने")
        text = text.replace("month", "महीना")
    elif lang == "Bengali":
        text = text.replace("p.a.", "প্রতি বছর")
        text = text.replace("as applicable from time to time", "সময়ে সময়ে প্রযোজ্য")
        text = text.replace("Within", "এর মধ্যে")
        text = text.replace("months", "মাস")
        text = text.replace("month", "মাস")
        text = text.replace("from the date of disbursement", "ঋণের টাকা পাওয়ার তারিখ থেকে")
        text = text.replace("as per crop cycle", "ফসল চক্র অনুযায়ী")
        text = text.replace("Hypothecation", "হাইপোথেকেশন")
        text = text.replace("of crop and KCC documents", "ফসল এবং KCC ডকুমেন্টের")
        text = text.replace("As per applicable scheme of the Bank", "ব্যাংকের প্রযোজ্য স্কিম অনুযায়ী")
    elif lang == "Gujarati":
        text = text.replace("p.a.", "વાર્ષિક")
        text = text.replace("as applicable from time to time", "સમયાંતરે લાગુ પડે તે મુજબ")
        text = text.replace("Within", "અંદર")
        text = text.replace("months", "મહિના")
        text = text.replace("month", "મહિનો")
        text = text.replace("from the date of disbursement", "રકમ મળ્યાની તારીખથી")
        text = text.replace("as per crop cycle", "પાક ચક્ર મુજબ")
        text = text.replace("Hypothecation", "હાઇપોથેકેશન")
        text = text.replace("of crop and KCC documents", "પાક અને KCC દસ્તાવેજોનું")
        text = text.replace("As per applicable scheme of the Bank", "બેંકની લાગુ પડતી યોજના મુજબ")
    if lang.lower() != "english":
        return translate_text(text, lang, context="loan document extracted field value", live=False)
    return text


def _risk_meaning(keyword: str, fallback: str) -> str:
    lang = _scan_language()
    if lang == "Gujarati":
        gujarati_risks = {
            "penalty": "ચુકવણી ચૂકી જવાથી અથવા શરત તોડવાથી વધારાનો ચાર્જ લાગી શકે છે.",
            "foreclosure": "લોન ન ચૂકવાય તો બેંક સુરક્ષા અથવા સંપત્તિ પર કાર્યવાહી કરી શકે છે.",
            "prepayment": "લોન વહેલી બંધ કરવાથી વધારાનો ચાર્જ લાગી શકે છે.",
            "insurance": "વીમો ફરજિયાત હોઈ શકે છે અને ઘણીવાર ખર્ચ વધારી શકે છે.",
            "penal interest": "મોડી EMI પર વધારાનું વ્યાજ લાગી શકે છે.",
            "as applicable": "આ અસ્પષ્ટ ભાષા છે. સહી કરતા પહેલાં ચોક્કસ રકમ લખિતમાં લો.",
            "subject to change": "શરતો પછીથી બદલાઈ શકે છે. બેંક પાસેથી સ્થિર લખિત શરતો માંગો.",
            "processing fee": "લોન મળતા પહેલાં કાપવામાં આવતી ફી.",
            "gst": "કર ઉમેરવાથી કુલ ખર્ચ વધી શકે છે.",
        }
        if keyword in gujarati_risks:
            return gujarati_risks[keyword]
    translated = RISK_TEXT.get(lang, {}).get(keyword)
    if translated:
        return translated
    if lang.lower() != "english":
        return translate_text(fallback, lang, context="loan document risk meaning", live=True)
    return fallback


def _manual_scan_report_language() -> bool:
    return True


def _scan_report_markdown(fb: dict) -> str:
    """Build the full deterministic scan report once, then translate as one unit."""
    lines = [
        "# Instant Scan Complete - Offline Safety Report",
        "This report is created immediately from the extracted document text. It does not wait for Gemma, so the scan stays fast.",
        "",
        "## Summary",
        f"- Document Type: {fb.get('doc_type', 'Financial Document')}",
        f"- Safety Score: {fb.get('risk_score', 0)}/100",
        f"- Risk Level: {'Flat rate detected' if fb.get('is_flat') else fb.get('risk_label', 'Safe')}",
        "",
    ]

    if fb.get("fields"):
        lines.append("## 1. Key Details Found")
        for name, value in fb["fields"].items():
            lines.append(f"- {name}: {value}")
        lines.append("")

    lines.append("## 2. Charges & Fees")
    if fb.get("charges"):
        for name, value in fb["charges"].items():
            lines.append(f"- {name}: {value}")
    else:
        lines.append("- No exact fee amount was clearly found. Ask the bank for a written list of every charge before signing.")
    lines.append("")

    if fb.get("completeness"):
        lines.append("## ⚠️ Document Completeness Warnings")
        for w in fb["completeness"]:
            lines.append(f"- {w}")
        lines.append("")

    if fb.get("amounts") or fb.get("percents") or fb.get("tenures"):
        lines.append("## 3. Financial Figures Found")
        if fb.get("amounts"):
            lines.append("- Amounts: " + ", ".join(a.upper() for a in fb["amounts"]))
        if fb.get("percents"):
            lines.append("- Interest Rates: " + ", ".join(fb["percents"]))
        if fb.get("tenures"):
            lines.append("- Tenure: " + ", ".join(fb["tenures"]))
        lines.append("")

    lines.append("## 4. Hidden Risks Found")
    if fb.get("categorised"):
        for cat, items in fb["categorised"].items():
            lines.append(f"### {cat} - {len(items)} issue(s)")
            for kw, info in items.items():
                lines.append(f"- {kw.upper()}: {info['meaning']}")
                lines.append(f"  Evidence: {info['evidence']}")
    elif fb.get("risks"):
        for kw, desc in fb["risks"].items():
            lines.append(f"- {kw.upper()}: {desc}")
    else:
        lines.append("- No obvious risky terms detected in this text scan.")
    lines.append("")

    if fb.get("missing"):
        lines.append("## 5. Confirm Before Signing")
        for item in fb["missing"]:
            lines.append(f"- {item}")
        lines.append("")

    if fb.get("questions"):
        lines.append("## 6. Questions To Ask Bank Officer")
        for q in fb["questions"]:
            lines.append(f"- {q}")
        lines.append("")

    lines.append("## Before Signing Checklist")
    lines.append("- Total repayment")
    lines.append("- All fees")
    lines.append("- Penalty")
    lines.append("- Insurance")
    lines.append("- Security or collateral")
    lines.append("- Due date")
    lines.append("- Signed copy of agreement")
    return "\n".join(lines)


def _fallback_analysis(text: str) -> dict:
    text = normalize_ocr_text(text)
    t = text.lower()
    doc_type = "Financial Document"
    for dtype, kws in DOC_TYPE_PATTERNS.items():
        if any(k in t for k in kws):
            doc_type = dtype
            break

    risks = {kw: desc for kw, desc in RISKY_KEYWORDS.items() if kw in t}
    fields = _extract_key_fields(text)
    amounts  = re.findall(r'(?:rs\.?|₹|inr)\s*[\d,]+(?:\.\d+)?(?:\s*(?:lakh|crore|thousand))?', t)
    percents = re.findall(r'\d+(?:\.\d+)?\s*%(?:\s*(?:per annum|pa|p\.a\.|per year|flat))?', t)
    tenures  = re.findall(r'\d+\s*(?:months?|years?)', t)

    charges = {}
    for fee_kw in [
        "processing fee", "administrative charge", "documentation fee", "onboarding charge",
        "verification fee", "stamp duty", "insurance premium", "credit shield",
        "loan protection", "legal fee", "inspection", "valuation fee", "gst",
        "penal interest", "emi bounce", "ecs", "nach", "overdue interest",
        "prepayment", "foreclosure", "loan closure fee", "subscription fee",
        "platform usage", "convenience fee", "recovery agent", "repossession",
        "legal recovery cost",
    ]:
        if fee_kw in t:
            m = re.search(
                fee_kw.replace(" ", r"\s*") + r'[:\s]+(?:rs\.?|₹)?\s*([\d,.]+)\s*(?:%|lakh|crore)?', t)
            charges[fee_kw.title()] = m.group(1) if m else "Found (amount unclear)"

    is_flat = bool(re.search(r'flat\s*rate|flat\s*interest|interest.*flat', t))
    categorised = {}
    for cat, kws in RISK_CATEGORIES.items():
        found = {
            kw: {"meaning": risks[kw], "evidence": _evidence_for(text, kw)}
            for kw in kws if kw in risks
        }
        if found:
            categorised[cat] = found
    score = _risk_score(risks, is_flat)
    return {
        "doc_type": doc_type, "risks": risks, "amounts": list(dict.fromkeys(amounts))[:8],
        "percents": list(dict.fromkeys(percents))[:6], "tenures": list(dict.fromkeys(tenures))[:4],
        "charges": charges, "is_flat": is_flat, "word_count": len(text.split()),
        "fields": fields, "categorised": categorised, "risk_score": score,
        "risk_label": _risk_label(score),
        "missing": _missing_confirmations(fields, charges, risks),
        "questions": _questions_to_ask(fields, risks, charges),
        "completeness": _document_completeness_warnings(text),
    }

def _render_fallback(fb: dict):
    """
    Renders the instant safety scan report using a unified translated markdown block
    to ensure no English text leaks into the final output.
    """
    # 1. Get current language from session state
    lang = st.session_state.get("user_language", "English")
    
    # 2. Generate the complete report as a single Markdown string first.
    # This captures all metrics, charges, and risks in one go.
    report = _scan_report_markdown(fb)
    
    # 3. Translate the entire generated block as one context.
    # This is much more accurate than translating individual labels.
    if lang.lower() != "english":
        from services.localization_service import translate_text
        # live=True ensures immediate processing for the current scan result
        report = translate_text(
            report, 
            lang, 
            context="complete borrower safety scan report", 
            live=True
        )

    # 4. Display success status and caption in the local language
    st.success(_scan_t("instant_done"))
    st.caption(_scan_t("instant_caption"))

    # 4b. Show prominent document completeness warnings BEFORE the report
    completeness_issues = fb.get("completeness", [])
    if completeness_issues:
        _comp_heading = "📋 Document Completeness Check"
        if lang.lower() != "english":
            _comp_heading = "📋 " + translate_text("Document Completeness Check", lang,
                                                    context="document section heading", live=True)
        st.markdown(f"#### {_comp_heading}")
        for w in completeness_issues:
            # strip leading emoji so translation is cleaner, then reattach
            _emoji = w[:2] if w and w[0] in "⚠️ℹ️" else ""
            _w_text = w[2:].strip() if _emoji else w
            if lang.lower() != "english":
                _w_text = translate_text(_w_text, lang,
                                         context="loan document completeness warning", live=True)
            _w_full = f"{_emoji} {_w_text}".strip() if _emoji else _w_text
            if w.startswith("⚠️"):
                st.warning(_w_full)
            else:
                st.info(_w_full)

    # 5. Display the fully translated unified report
    st.markdown(report)

    # 6. Handle the download button (using the translated version)
    st.download_button(
        _scan_t("Download Safety Report"),
        report,
        file_name=f"safety_report_{lang.lower()}.txt",
        mime="text/plain",
        use_container_width=True,
        key=f"dl_scan_fast_{lang.lower()}",
    )
    
    # 7. CRITICAL: We return here.
    # We stop execution so the old English-only code below does not run.
    return 

    # --- OLD MANUAL UI BLOCKS REMOVED ---
    # The code below is now ignored to prevent language mixing issues.

def _render_ai_result(ai_text: str, key_suffix: str = "scan"):
    """
    Renders the AI safety report and ensures the content is 
    translated into the user's selected language.
    """
    # 1. Fetch the user's selected language from the session
    user_lang = st.session_state.get("user_language", "English")
    _t = get_ui(user_lang)
    
    # 2. Force translation if the language is not English
    if user_lang.lower() != "english":
        with st.spinner(_t.get("analyzing", "Translating Report...")):
            # Update: Using a more direct translation prompt
            translation_prompt = (
                f"You are a professional translator. Translate this financial safety report "
                f"entirely into {user_lang}. Do not leave any English words except for "
                f"proper names. Keep all Markdown tables and scores: {ai_text}"
            )
            # Re-assigning ai_text ensures the translated version is used below
            ai_text = generate(translation_prompt, language=user_lang)
    
    # 3. Success message in the local language
    st.success(_t.get("analysis_complete", "Analysis Complete"))
    
    # 4. Display the updated text
    st.markdown(ai_text)
    
    # 5. Download button with the translated text
    st.download_button(
        _t.get("download_report", "Download Safety Report"),
        ai_text,
        file_name=f"safety_report_{user_lang.lower()}.txt",
        mime="text/plain",
        use_container_width=True,
        # Adding user_lang to the key prevents Streamlit state conflicts
        key=f"dl_report_{key_suffix}_{user_lang}",
    )

def _run_text_analysis(text: str) -> dict:
    """Return the fast default scan report without waiting for an LLM."""
    return {"type": "fallback", "data": _fallback_analysis(text)}

# def _run_gemma_text_analysis(text: str) -> dict:
#     # Get the language from session state so Gemma knows which language to use
#     user_lang = st.session_state.get("user_language", "English") 
    
#     rag_ctx = rag_query(text[:500], n=3)
#     ctx_block = f"\n\nReference Knowledge:\n{rag_ctx}\n\n" if rag_ctx else ""
#     text_for_ai = text[:4500] + "\n[...truncated...]" if len(text) > 4500 else text
    
#     # Change 'language="English"' to 'language=user_lang'
#     resp = generate(
#         UNDERSTAND_PROMPT + ctx_block + text_for_ai,
#         language=user_lang, 
#     )
#     if resp.startswith("⚠️"):
#         return {"type": "fallback", "data": _fallback_analysis(text)}
#     return {"type": "ai", "data": resp}

def _run_gemma_text_analysis(text: str, lang: str = "English") -> dict:
    # 1. Fetch the dynamic prompts right before the AI call
    _, u_prompt = get_dynamic_prompts() 
    
    rag_ctx = rag_query(text[:500], n=3)
    ctx_block = f"\n\nReference Knowledge:\n{rag_ctx}\n\n" if rag_ctx else ""
    text_for_ai = text[:4500] + "\n[...truncated...]" if len(text) > 4500 else text
    
    # 2. Use the dynamic 'u_prompt' instead of the old 'UNDERSTAND_PROMPT'
    resp = generate(
        u_prompt + ctx_block + text_for_ai,
        language=lang, 
    )
    if resp.startswith("⚠️"):
        return {"type": "fallback", "data": _fallback_analysis(text)}
    return {"type": "ai", "data": resp}

# ══════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

# Clear any stale scanner_default_tab (navigation now uses separate pages)
st.session_state.pop("scanner_default_tab", None)

if True:  # main scan block
    st.markdown(f"#### 📤 {_scan_t('Scan Your Document')}")
    st.caption(_scan_t("Upload a photo or file — AI reads all charges, fees and risky clauses."))
    uploaded = st.file_uploader(
        _scan_t("Upload document (Photo, PDF, Word)"),
        type=[
            "jpg", "jpeg", "jfif", "pjpeg", "pjp", "png", "bmp", "tif", "tiff",
            "webp", "gif", "heic", "heif", "pdf", "docx", "doc", "txt",
        ],
        help=_scan_t("Supported: common image files, PDF, Word, and text files — Max 10 MB"),
        key="scan_upload",
    )

    if uploaded and uploaded.size > 10 * 1024 * 1024:
        st.error(_scan_t("File too large — maximum 10 MB."))
        uploaded = None

    if uploaded:
        file_bytes = uploaded.getvalue()
        if not file_bytes:
            st.error(_scan_t("The uploaded file could not be read. Please remove it and upload again."))
            st.stop()
        ext        = os.path.splitext(uploaded.name.lower())[1]
        ocr_ok     = is_ocr_available()

        # ── Image files ─────────────────────────────────────────────────────
        if ext in (".jpg", ".jpeg", ".jfif", ".pjpeg", ".pjp", ".png", ".bmp",
                   ".tiff", ".tif", ".webp", ".gif", ".heic", ".heif"):
            with st.expander(f"🖼️ {_scan_t('View uploaded image')}", expanded=False):
                st.image(file_bytes, use_container_width=True)

            st.markdown(f"**{_scan_t('Text Extraction:')}**")

            # Step 1 — try EasyOCR / Tesseract (up to 12 preprocessing passes)
            raw_text = ""
            ocr_ran = False
            if ocr_ok:
                with st.spinner(f"🔍 {_scan_t('Reading image with OCR...')}"):
                    raw_text = extract_text_from_image(
                        file_bytes,
                        uploaded.name,
                        languages=[_scan_language()],
                    )
                ocr_ran = True
                ocr_message = raw_text
                if raw_text.startswith("OCR") or raw_text.startswith("No text"):
                    raw_text = ""
                elif raw_text.strip():
                    st.success(f"✅ {_scan_t('OCR extracted')} {len(raw_text):,} {_scan_t('characters')}")
                    with st.expander(_scan_t("View extracted text"), expanded=False):
                        st.text(raw_text[:800] + ("…" if len(raw_text) > 800 else ""))

            # Step 2 — Vision AI or manual fallback when OCR unavailable / insufficient
            if not raw_text.strip():
                if _vision:
                    user_lang = st.session_state.get("user_language", "English")
                    v_prompt, _ = get_dynamic_prompts()

                    with st.spinner(_scan_t("Gemma AI Vision is reading your image...")):
                        vision_result = generate_with_image(
                            v_prompt,
                            file_bytes,
                            mime_type="image/png" if ext == ".png" else "image/jpeg",
                            language=user_lang,
                            # language=_scan_language(),
                        )
                    if vision_result and vision_result != "__VISION_UNAVAILABLE__" \
                            and not vision_result.startswith("⚠️"):
                        st.session_state["scan_result"] = {"type": "ai", "data": vision_result}
                        st.rerun()
                    else:
                        st.error(_scan_t("AI Vision could not read this image. Please paste text below."))
                elif ocr_ran:
                    st.warning(f"⚠️ {_scan_t('OCR could not read this image.')} {ocr_message}")
                    st.info(_scan_t("Try a clearer photo, or paste the text manually below."))
                    pasted_img = st.text_area(
                        _scan_t("Paste the extracted text here:"),
                        height=220,
                        placeholder=_scan_t("Copy text from Google Lens / Google Docs and paste here..."),
                        key="img_paste_fallback",
                    )
                    if pasted_img.strip():
                        st.success(f"✅ {_scan_t('Read')} {len(pasted_img.strip()):,} {_scan_t('characters')}")
                        st.session_state["scan_raw_text"] = pasted_img.strip()
                        if st.button(f"🔍 {_scan_t('Understand This Document')}", type="primary", use_container_width=True):
                            with st.spinner(_scan_t("Analysing document...")):
                            # Get the language again to be safe
                                curr_lang = st.session_state.get("user_language", "English")
                                st.session_state["scan_result"] = _run_gemma_text_analysis(raw_text, lang=curr_lang)
                            st.rerun()


                        # if st.button(f"🔍 {_scan_t('Analyse This Text')}", type="primary",
                        #              use_container_width=True, key="btn_img_paste_analyse"):
                        #     with st.spinner(_scan_t("Analysing...")):
                        #         st.session_state["scan_result"] = _run_text_analysis(pasted_img.strip())
                        #     st.rerun()
                else:
                    st.warning(_scan_t("EasyOCR is not installed - cannot read text from images automatically."))
                    st.info(
                        _scan_t("Install EasyOCR once for offline image reading, or paste copied text below.")
                        + "\n\n"
                        "```\npip install easyocr\n```\n\n"
                        + _scan_t("Or use Google Lens: copy the text and paste below.")
                    )
                    pasted_img = st.text_area(
                        _scan_t("Paste the copied text here:"),
                        height=220,
                        placeholder=_scan_t("Paste text from Google Lens / Google Docs here..."),
                        key="img_paste_fallback",
                    )
                    if pasted_img.strip():
                        st.success(f"✅ {_scan_t('Read')} {len(pasted_img.strip()):,} {_scan_t('characters')}")
                        st.session_state["scan_raw_text"] = pasted_img.strip()
                        if st.button(f"🔍 {_scan_t('Analyse This Text')}", type="primary",
                                     use_container_width=True, key="btn_img_paste_analyse"):
                            with st.spinner(_scan_t("Analysing...")):
                                st.session_state["scan_result"] = _run_text_analysis(pasted_img.strip())
                            st.rerun()

            # If OCR succeeded, show Understand button
            if raw_text.strip():
                st.divider()
                st.session_state["scan_raw_text"] = raw_text
                if st.button(f"🔍 {_scan_t('Understand This Document')}", type="primary",
                             use_container_width=True, key="btn_from_scan"):
                    with st.spinner(_scan_t("Analysing document...")):
                        st.session_state["scan_result"] = _run_text_analysis(raw_text)
                    st.rerun()

        # ── PDF ──────────────────────────────────────────────────────────────
        elif ext == ".pdf":
            if not is_pdf_support_available():
                st.error(_scan_t("PDF support not installed. Run: `pip install pymupdf`"))
            else:
                pages = get_pdf_page_count(file_bytes)
                st.info(f"📄 {_scan_t('PDF file')} - {pages} {_scan_t('page(s)')} · {_scan_t('Extracting text...')}")
                with st.spinner(f"{_scan_t('Reading')} {pages} {_scan_t('page(s)...')}"):
                    raw_text = extract_text_from_pdf(file_bytes)
                _pdf_ok = raw_text and not raw_text.startswith("PDF extraction") and len(raw_text) >= 200
                if not _pdf_ok:
                    raw_text = ""
                    st.warning(_scan_t("This PDF appears to contain scanned images - text could not be extracted automatically."))
                    st.info(_scan_t("Paste the PDF text below. Open in browser or Acrobat, select all, copy, then paste here."))
                    pasted_pdf = st.text_area(_scan_t("Paste PDF text:"), height=200, key="pdf_paste_fallback",
                                              placeholder=_scan_t("Paste the full loan document text here..."))
                    if pasted_pdf.strip():
                        raw_text = pasted_pdf.strip()
                        st.success(f"✅ {_scan_t('Read')} {len(raw_text):,} {_scan_t('characters')}")
                        st.session_state["scan_raw_text"] = raw_text
                        if st.button(f"🔍 {_scan_t('Understand This Document')}", type="primary",
                                     use_container_width=True, key="btn_pdf_paste_understand"):
                            with st.spinner(_scan_t("Analysing document...")):
                                st.session_state["scan_result"] = _run_text_analysis(raw_text)
                            st.rerun()
                else:
                    st.success(f"✅ {_scan_t('Extracted')} {len(raw_text):,} {_scan_t('characters from')} {pages} {_scan_t('page(s)')}")
                    with st.expander(_scan_t("Preview extracted text"), expanded=False):
                        st.text(raw_text[:1000] + "…")
                    st.session_state["scan_raw_text"] = raw_text
                    if st.button(f"🔍 {_scan_t('Understand This Document')}", type="primary",
                                 use_container_width=True, key="btn_pdf_understand"):
                        with st.spinner(_scan_t("Analysing document...")):
                            st.session_state["scan_result"] = _run_text_analysis(raw_text)
                        st.rerun()

        # ── DOCX / DOC ────────────────────────────────────────────────────────
        elif ext in (".docx", ".doc"):
            if not is_docx_support_available():
                st.error(_scan_t("Word support not installed. Run: `pip install python-docx docx2txt`"))
            else:
                with st.spinner(_scan_t("Reading Word document...")):
                    raw_text = extract_text_from_docx(file_bytes) if ext == ".docx" \
                               else extract_text_from_doc(file_bytes)
                _docx_ok = raw_text and not raw_text.startswith("DOCX") \
                    and not raw_text.startswith("No text") and not raw_text.startswith("DOC") \
                    and len(raw_text) >= 50
                if not _docx_ok:
                    raw_text = ""

                    # ── Try Gemma Vision on embedded images inside the DOCX ──────
                    # Many Word files are just screenshots pasted as images.
                    # Extract images from the DOCX zip and send to Vision API.
                    _docx_vision_done = False
                    if _vision and ext == ".docx":
                        with st.spinner(f"🔍 {_scan_t('Gemma AI Vision is reading your image...')}"):
                            import zipfile as _zf2
                            from io import BytesIO as _BIO2
                            try:
                                _img_names = []
                                with _zf2.ZipFile(_BIO2(file_bytes)) as _zfp:
                                    _img_names = sorted([
                                        n for n in _zfp.namelist()
                                        if n.startswith("word/media/")
                                        and n.lower().endswith(
                                            (".png", ".jpg", ".jpeg", ".bmp",
                                             ".tif", ".tiff", ".webp")
                                        )
                                    ])
                                    # Try each embedded image; use first that Gemma can read
                                    for _iname in _img_names[:8]:
                                        _ibytes = _zfp.read(_iname)
                                        _iext   = os.path.splitext(_iname.lower())[1]
                                        _imime  = "image/png" if _iext == ".png" else "image/jpeg"
                                        _vr = generate_with_image(
                                            VISION_PROMPT, _ibytes,
                                            mime_type=_imime, language=_scan_language(),
                                        )
                                        if (_vr and _vr != "__VISION_UNAVAILABLE__"
                                                and not _vr.startswith("⚠️")
                                                and len(_vr) > 100):
                                            st.session_state["scan_result"] = {
                                                "type": "ai", "data": _vr,
                                            }
                                            _docx_vision_done = True
                                            break
                            except Exception:
                                pass
                        if _docx_vision_done:
                            st.rerun()

                    if not _docx_vision_done:
                        st.warning(
                            _scan_t("Could not extract readable text from this Word document. This happens when the document contains scanned images or is password-protected.")
                        )
                        st.info(_scan_t("Paste the document text below to continue with analysis."))
                        pasted_docx = st.text_area(
                            _scan_t("Paste document text here:"),
                            height=220,
                            placeholder=_scan_t("Open the Word file, select all, copy, and paste here..."),
                            key="docx_paste_fallback",
                        )
                        if pasted_docx.strip():
                            raw_text = pasted_docx.strip()
                            st.success(f"✅ {_scan_t('Read')} {len(raw_text):,} {_scan_t('characters')}")
                            st.session_state["scan_raw_text"] = raw_text
                            if st.button(f"🔍 {_scan_t('Understand This Document')}", type="primary",
                                         use_container_width=True, key="btn_docx_paste_understand"):
                                with st.spinner(_scan_t("Analysing document...")):
                                    st.session_state["scan_result"] = _run_text_analysis(raw_text)
                                st.rerun()
                else:
                    st.success(f"✅ {_scan_t('Extracted')} {len(raw_text):,} {_scan_t('characters')}")
                    with st.expander(_scan_t("Preview extracted text"), expanded=False):
                        st.text(raw_text[:1000] + "…")
                    st.session_state["scan_raw_text"] = raw_text
                    if st.button(f"🔍 {_scan_t('Understand This Document')}", type="primary",
                                 use_container_width=True, key="btn_doc_understand"):
                        with st.spinner(_scan_t("Analysing document...")):
                            st.session_state["scan_result"] = _run_text_analysis(raw_text)
                        st.rerun()

        elif ext == ".txt":
            raw_text = file_bytes.decode("utf-8", errors="replace").strip()
            if raw_text:
                st.success(f"✅ {_scan_t('Read')} {len(raw_text):,} {_scan_t('characters')}")
                st.session_state["scan_raw_text"] = raw_text
                if st.button(f"🔍 {_scan_t('Understand This Document')}", type="primary",
                             use_container_width=True, key="btn_txt_understand"):
                    with st.spinner(_scan_t("Analysing document...")):
                        st.session_state["scan_result"] = _run_text_analysis(raw_text)
                    st.rerun()
            else:
                st.warning(_scan_t("This text file is empty."))

    # Show result (from scan)
    if st.session_state.get("scan_result"):
        st.divider()
        res = st.session_state["scan_result"]
        if res["type"] == "ai":
            _render_ai_result(res["data"])
        else:
            _render_fallback(res["data"])
            if mode != "limited" and st.session_state.get("scan_raw_text"):
                st.info(_scan_t("Need a longer plain-language explanation? Use Gemma after the instant report is already shown."))
                if st.button(f"✨ {_scan_t('Add Gemma detailed explanation')}", use_container_width=True, key="btn_scan_gemma_detail"):
                    with st.spinner(_scan_t("Gemma is preparing a deeper explanation...")):
                        st.session_state["scan_result"] = _run_gemma_text_analysis(st.session_state["scan_raw_text"])
                    st.rerun()
        if st.button(f"🔄 {_scan_t('Scan Another Document')}", use_container_width=True, key="btn_scan_reset"):
            st.session_state.pop("scan_result", None)
            st.session_state.pop("scan_raw_text", None)
            st.rerun()
