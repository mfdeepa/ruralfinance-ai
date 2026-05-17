import sys, os, re, hashlib, importlib, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
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
from utils.india_config import INDIA_COUNTRY_BADGE, normalize_app_language
from utils.page_controls import render_language_back_topbar

load_dotenv()

st.set_page_config(
    page_title="Understand Document — RuralFinance AI",
    page_icon="🔍",
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
inject_nav_drawer("Understand Document")
_t = get_ui(st.session_state.get("user_language", "English"))
_lang = st.session_state.get("user_language", "English")

_api_key = os.getenv("GOOGLE_API_KEY", "")
_vision_ok = bool(_api_key) and _api_key != "your_google_api_key_here" and mode == "online"

_MIN_CHARS = 200

# ── Back button — fixed top-right corner ─────────────────────────────────────
_t = render_language_back_topbar("understand_doc", "btn_back_home_ud")
_lang = st.session_state.get("user_language", "English")

# ── Prompts ───────────────────────────────────────────────────────────────────
UNDERSTAND_PROMPT = """\
You are a financial safety expert protecting a rural or semi-urban Indian borrower.
The borrower provided this Indian financial document. Produce a COMPLETE SAFETY REPORT.

CRITICAL GROUNDING RULES:
- Use only facts written in the provided document text or visible in the image.
- Do not invent fees, rates, clauses, penalties, EMI, GST, processing fee, stamp duty, documentation fee, prepayment penalty, acceleration clause, legal fee, insurance amount, Aadhaar/PAN/KYC consent, UPI auto-debit, or NACH/ECS mandate.
- Every detected charge or risk must include a short evidence quote from the document.
- If a charge or risky clause is not found, write "Not found in document" instead of guessing.
- If wording is vague, mark it as "Needs bank confirmation" and quote the exact wording.
- Do not calculate EMI or total repayment unless the loan amount, rate, and tenure are clearly available. If not enough data, say what is missing.
- For an SBI/KCC sanction letter, do not claim processing fee, GST, stamp duty, documentation fee, prepayment penalty, or acceleration unless those words or amounts are present.

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

**4. HIDDEN & RISKY CLAUSES - CATEGORIZED**
Only report risky clauses that are actually present. For each finding:
| Category | Evidence quote | Why it matters | What to ask |
Check these India-specific categories, but do not mark them as found unless supported by evidence:
Processing Charges | Insurance Charges | Penalty Charges | GST/Hidden Taxes | Interest Risks | Legal Risks | Aadhaar/PAN/KYC Privacy Risks | UPI/NACH/ECS Auto-debit Risks | Recovery Agent Risks | Digital Loan App Risks | Ambiguous Clauses

**5. RISK SCORE: [X] / 100**
Risk scale: 0-20 Safe | 21-40 Low Risk | 41-60 Medium Risk | 61-80 High Risk | 81-100 Critical
Score using only evidence-backed risks. Do not deduct for hypothetical charges not present in the document.

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
    # ── Core Loan Risks ───────────────────────────────────────────────────────
    "penalty": "Extra charges if you miss payments or break any condition.",
    "foreclosure": "Bank can take away your property if you can't repay.",
    "prepayment": "You'll be charged extra if you pay off the loan early.",
    "balloon": "A large final payment due at the end — many borrowers can't afford it.",
    "cross-default": "Defaulting on one loan can trigger default on all other loans.",
    "auto-renewal": "Agreement renews automatically unless you explicitly cancel.",
    "arbitration": "Disputes go to private arbitration — not consumer court.",
    "irrevocable": "This clause cannot be undone once you sign.",
    "collateral": "Bank can seize your pledged property.",
    "floating rate": "Interest rate can increase anytime without your consent.",
    "processing fee": "Upfront fee deducted from loan before you receive money.",
    "insurance": "Insurance may be mandatory and often overpriced.",
    "personal guarantee": "A family member's assets are also at risk.",
    "unlimited liability": "No cap on what you can owe — extremely dangerous.",
    "acceleration": "If you miss one EMI, the ENTIRE loan becomes due immediately.",
    "penal interest": "Extra interest charged when you miss EMI.",
    "stamp duty": "Government fee for registering the loan agreement.",
    # ── Penalty & Bounce Charges ──────────────────────────────────────────────
    "bounce charge": "Fee charged every time your auto-debit or cheque fails.",
    "dishonour": "Penalty for failed payment — charged per failed attempt.",
    "ecs": "Auto-debit mandate — bank deducts EMI automatically from account.",
    "nach": "Auto-debit system — bank deducts EMI automatically. Bounce fee applies.",
    "overdue": "Amount unpaid past due date — attracts additional interest charges.",
    "penal": "Penalty interest on overdue amounts — can be 2-3% extra per month.",
    # ── Hidden Taxes ─────────────────────────────────────────────────────────
    "gst": "18% GST is often charged extra on top of fees — ask for total with GST.",
    "igst": "Integrated GST — charged on top of fees, often not shown upfront.",
    "cgst": "Central GST — adds to the total cost beyond what's advertised.",
    "sgst": "State GST — adds to the total cost beyond what's advertised.",
    # ── Privacy & Digital Risks ───────────────────────────────────────────────
    "sms access": "App may read your SMS messages — a serious privacy risk.",
    "contact access": "App may access all your phone contacts — risk of misuse.",
    "data sharing": "Your personal data may be shared with third parties.",
    "third party": "Information shared with outside companies — review carefully.",
    "marketing consent": "You may be agreeing to receive unlimited marketing calls/messages.",
    "location": "App may track your location — can be used for pressure if you default.",
    # ── Subscription & Platform Charges ──────────────────────────────────────
    "subscription": "Recurring fee charged monthly/annually — check if it ever ends.",
    "platform fee": "Fee for using the digital loan platform — often hidden in terms.",
    "convenience fee": "Extra fee charged for using digital payment or access — often vague.",
    "service charge": "Recurring service fee — ask for exact amount and end date.",
    # ── Ambiguous Clauses ─────────────────────────────────────────────────────
    "charges may apply": "Vague language allowing lender to add any charges later.",
    "as applicable": "Undefined charges — demand exact rupee amounts before signing.",
    "sole discretion": "Lender can make any decision unilaterally — very risky.",
    "at our discretion": "Lender can change terms without your agreement.",
    "subject to change": "Terms can be changed after you sign — very risky.",
    # ── Recovery Risks ────────────────────────────────────────────────────────
    "recovery agent": "Agent fees may be added to your outstanding balance.",
    "repossession": "Property can be taken — check exact conditions and notice period.",
    "legal cost": "Legal fees for recovery are charged to the borrower.",
    "enforcement": "Enforcement costs added to balance — can be very large.",
}


# Risk category weights for offline scoring
_RISK_WEIGHTS = {
    "unlimited liability": 25, "cross-default": 20, "acceleration": 15,
    "balloon": 15, "floating rate": 15, "collateral": 15,
    "sole discretion": 15, "data sharing": 15, "sms access": 15,
    "irrevocable": 10, "arbitration": 10, "auto-renewal": 10,
    "subscription": 10, "platform fee": 10, "charges may apply": 10,
    "subject to change": 10, "recovery agent": 10, "repossession": 10,
    "personal guarantee": 10, "prepayment": 10, "insurance": 10,
    "nach": 8, "ecs": 8, "bounce charge": 8, "dishonour": 8,
    "processing fee": 5, "convenience fee": 5, "marketing consent": 5,
    "gst": 5, "igst": 5, "cgst": 5, "sgst": 5,
    "penalty": 5, "penal interest": 5, "foreclosure": 5, "legal cost": 10,
}

# Group RISKY_KEYWORDS by category for organised display
_RISK_CATEGORIES = {
    "💳 Processing Charges":    ["processing fee", "stamp duty", "documentation fee", "legal fee", "inspection", "onboarding"],
    "🛡️ Insurance Charges":     ["insurance", "credit shield", "loan protection"],
    "⚡ Penalty Charges":        ["penalty", "penal interest", "penal", "bounce charge", "dishonour", "nach", "ecs", "overdue"],
    "💸 Hidden Taxes":           ["gst", "igst", "cgst", "sgst"],
    "📈 Interest Risks":         ["floating rate"],
    "⚖️ Legal Risks":            ["acceleration", "cross-default", "balloon", "arbitration", "irrevocable", "personal guarantee", "collateral", "unlimited liability"],
    "🔒 Privacy Risks":          ["sms access", "contact access", "data sharing", "third party", "marketing consent", "location"],
    "🚨 Recovery Risks":         ["recovery agent", "repossession", "legal cost", "enforcement"],
    "🔄 Subscription Charges":   ["subscription", "platform fee", "convenience fee", "service charge", "auto-renewal"],
    "❓ Ambiguous Clauses":       ["charges may apply", "as applicable", "sole discretion", "at our discretion", "subject to change"],
}


UD_TEXT = {
    "Hindi": {
        "Instant safety report complete — offline analysis generated.": "तुरंत सुरक्षा रिपोर्ट पूरी — ऑफलाइन विश्लेषण तैयार है।",
        "This report is created immediately from the extracted document text. Gemma can be used later for a deeper explanation.": "यह रिपोर्ट निकाले गए दस्तावेज़ टेक्स्ट से तुरंत बनती है। अधिक गहरी व्याख्या के लिए बाद में Gemma का उपयोग किया जा सकता है।",
        "Document Risk Score": "दस्तावेज़ जोखिम स्कोर",
        "Risk Score": "जोखिम स्कोर",
        "Risk Clauses Found": "मिले जोखिम वाले क्लॉज़",
        "Rate Type": "दर का प्रकार",
        "Reducing Balance": "घटते बैलेंस वाली दर",
        "FLAT RATE — True cost ≈ stated rate × 1.83": "फ्लैट रेट — वास्तविक लागत लगभग बताई गई दर × 1.83 हो सकती है",
        "Risks by Category": "श्रेणी के अनुसार जोखिम",
        "Risky Terms Detected": "जोखिम वाले शब्द मिले",
        "No obvious risky terms detected in plain text scan.": "इस टेक्स्ट स्कैन में कोई स्पष्ट बड़ा जोखिम शब्द नहीं मिला।",
        "issue(s) found": "मुद्दे मिले",
        "SAFE": "सुरक्षित",
        "LOW RISK": "कम जोखिम",
        "MEDIUM RISK": "मध्यम जोखिम",
        "HIGH RISK": "अधिक जोखिम",
        "CRITICAL RISK": "गंभीर जोखिम",
        "0=Safe · 100=Critical": "0=सुरक्षित · 100=गंभीर",
        "Upload document file (PDF, Word, Image)": "दस्तावेज़ फ़ाइल अपलोड करें (PDF, Word, Image)",
        "File is ready. Click **Understand This Document** to read and analyse it.": "फ़ाइल तैयार है। पढ़ने और विश्लेषण के लिए **यह दस्तावेज़ समझें** पर क्लिक करें।",
        "OCR text is ready. Click Understand This Document, or add one short request.": "OCR टेक्स्ट तैयार है। यह दस्तावेज़ समझें पर क्लिक करें, या एक छोटा सवाल जोड़ें।",
        "Text from Scan Document is ready. Click **Understand This Document** below.": "स्कैन दस्तावेज़ का टेक्स्ट तैयार है। नीचे **यह दस्तावेज़ समझें** पर क्लिक करें।",
        "Add a short question or paste text manually": "छोटा सवाल जोड़ें या टेक्स्ट मैन्युअली पेस्ट करें",
        "View uploaded image": "अपलोड की गई छवि देखें",
        "Text extracted — click **Understand This Document** below.": "टेक्स्ट निकल गया — नीचे **यह दस्तावेज़ समझें** पर क्लिक करें।",
        "Reading uploaded file... extracting text from document and screenshots...": "अपलोड की गई फ़ाइल पढ़ी जा रही है... दस्तावेज़ और स्क्रीनशॉट से टेक्स्ट निकाला जा रहा है...",
        "Reading your document... finding all charges, hidden fees, and risky clauses...": "आपका दस्तावेज़ पढ़ा जा रहा है... सभी शुल्क, छिपी फीस और जोखिम खोजे जा रहे हैं...",
        "Need a longer plain-language explanation? Use Gemma after the instant safety report is already visible.": "लंबी सरल व्याख्या चाहिए? तुरंत सुरक्षा रिपोर्ट दिखने के बाद Gemma का उपयोग करें।",
        "File too large — maximum 10 MB.": "फ़ाइल बहुत बड़ी है — अधिकतम 10 MB।",
        "The uploaded file could not be read. Please remove it and upload again.": "अपलोड की गई फ़ाइल पढ़ी नहीं जा सकी। कृपया इसे हटाकर फिर अपलोड करें।",
        "Add Gemma detailed explanation": "Gemma से विस्तृत व्याख्या जोड़ें",
        "Gemma is preparing a deeper explanation...": "Gemma गहरी व्याख्या तैयार कर रहा है...",
        "Try a Sample Loan Document": "नमूना ऋण दस्तावेज़ आज़माएँ",
        "Analyse This Sample": "इस नमूने का विश्लेषण करें",
    },
    "Bengali": {
        "Instant safety report complete — offline analysis generated.": "তাৎক্ষণিক নিরাপত্তা রিপোর্ট সম্পন্ন — অফলাইন বিশ্লেষণ তৈরি হয়েছে।",
        "This report is created immediately from the extracted document text. Gemma can be used later for a deeper explanation.": "এই রিপোর্টটি ডকুমেন্ট থেকে পাওয়া টেক্সট দিয়ে সঙ্গে সঙ্গে তৈরি হয়। পরে আরও গভীর ব্যাখ্যার জন্য Gemma ব্যবহার করা যেতে পারে।",
        "Document Risk Score": "ডকুমেন্ট ঝুঁকি স্কোর",
        "Risk Score": "ঝুঁকি স্কোর",
        "Risk Clauses Found": "পাওয়া ঝুঁকিপূর্ণ শর্ত",
        "Rate Type": "হারের ধরন",
        "Reducing Balance": "হ্রাসমান ব্যালেন্স পদ্ধতি",
        "FLAT RATE — True cost ≈ stated rate × 1.83": "ফ্ল্যাট রেট — প্রকৃত খরচ প্রায় ঘোষিত হার × 1.83 হতে পারে",
        "Risks by Category": "বিভাগ অনুযায়ী ঝুঁকি",
        "Risky Terms Detected": "ঝুঁকিপূর্ণ শব্দ পাওয়া গেছে",
        "No obvious risky terms detected in plain text scan.": "এই টেক্সট স্ক্যানে স্পষ্ট বড় ঝুঁকিপূর্ণ শব্দ পাওয়া যায়নি।",
        "issue(s) found": "সমস্যা পাওয়া গেছে",
        "SAFE": "নিরাপদ",
        "LOW RISK": "কম ঝুঁকি",
        "MEDIUM RISK": "মাঝারি ঝুঁকি",
        "HIGH RISK": "উচ্চ ঝুঁকি",
        "CRITICAL RISK": "গুরুতর ঝুঁকি",
        "0=Safe · 100=Critical": "0=নিরাপদ · 100=গুরুতর",
        "Upload document file (PDF, Word, Image)": "ডকুমেন্ট ফাইল আপলোড করুন (PDF, Word, Image)",
        "File is ready. Click **Understand This Document** to read and analyse it.": "ফাইল প্রস্তুত। পড়া ও বিশ্লেষণের জন্য **এই ডকুমেন্ট বুঝুন** ক্লিক করুন।",
        "OCR text is ready. Click Understand This Document, or add one short request.": "OCR টেক্সট প্রস্তুত। এই ডকুমেন্ট বুঝুন ক্লিক করুন, অথবা একটি ছোট অনুরোধ যোগ করুন।",
        "Text from Scan Document is ready. Click **Understand This Document** below.": "স্ক্যান ডকুমেন্টের টেক্সট প্রস্তুত। নিচে **এই ডকুমেন্ট বুঝুন** ক্লিক করুন।",
        "Add a short question or paste text manually": "ছোট প্রশ্ন যোগ করুন বা টেক্সট ম্যানুয়ালি পেস্ট করুন",
        "View uploaded image": "আপলোড করা ছবি দেখুন",
        "Text extracted — click **Understand This Document** below.": "টেক্সট বের হয়েছে — নিচে **এই ডকুমেন্ট বুঝুন** ক্লিক করুন।",
        "Reading uploaded file... extracting text from document and screenshots...": "আপলোড করা ফাইল পড়া হচ্ছে... ডকুমেন্ট ও স্ক্রিনশট থেকে টেক্সট বের করা হচ্ছে...",
        "Reading your document... finding all charges, hidden fees, and risky clauses...": "আপনার ডকুমেন্ট পড়া হচ্ছে... সব চার্জ, লুকানো ফি ও ঝুঁকি খোঁজা হচ্ছে...",
        "Need a longer plain-language explanation? Use Gemma after the instant safety report is already visible.": "আরও দীর্ঘ সহজ ব্যাখ্যা দরকার? তাৎক্ষণিক নিরাপত্তা রিপোর্ট দেখার পরে Gemma ব্যবহার করুন।",
        "File too large — maximum 10 MB.": "ফাইলটি খুব বড় — সর্বোচ্চ 10 MB।",
        "The uploaded file could not be read. Please remove it and upload again.": "আপলোড করা ফাইল পড়া যায়নি। এটি সরিয়ে আবার আপলোড করুন।",
        "Add Gemma detailed explanation": "Gemma দিয়ে বিস্তারিত ব্যাখ্যা যোগ করুন",
        "Gemma is preparing a deeper explanation...": "Gemma গভীর ব্যাখ্যা প্রস্তুত করছে...",
        "Try a Sample Loan Document": "নমুনা ঋণ ডকুমেন্ট চেষ্টা করুন",
        "Analyse This Sample": "এই নমুনা বিশ্লেষণ করুন",
    },
    "Telugu": {
        "Upload document file (PDF, Word, Image)": "పత్రం ఫైల్ అప్‌లోడ్ చేయండి (PDF, Word, Image)",
        "File is ready. Click **Understand This Document** to read and analyse it.": "ఫైల్ సిద్ధంగా ఉంది. చదివి విశ్లేషించడానికి **ఈ పత్రాన్ని అర్థం చేసుకోండి** క్లిక్ చేయండి.",
        "OCR text is ready. Click Understand This Document, or add one short request.": "OCR టెక్స్ట్ సిద్ధంగా ఉంది. ఈ పత్రాన్ని అర్థం చేసుకోండి క్లిక్ చేయండి, లేదా చిన్న ప్రశ్న జోడించండి.",
        "Text from Scan Document is ready. Click **Understand This Document** below.": "స్కాన్ పత్రం టెక్స్ట్ సిద్ధంగా ఉంది. క్రింద **ఈ పత్రాన్ని అర్థం చేసుకోండి** క్లిక్ చేయండి.",
        "Add a short question or paste text manually": "చిన్న ప్రశ్న జోడించండి లేదా టెక్స్ట్‌ను చేతితో పేస్ట్ చేయండి",
        "View uploaded image": "అప్‌లోడ్ చేసిన చిత్రాన్ని చూడండి",
        "Text extracted — click **Understand This Document** below.": "టెక్స్ట్ తీసింది — క్రింద **ఈ పత్రాన్ని అర్థం చేసుకోండి** క్లిక్ చేయండి.",
        "Reading uploaded file... extracting text from document and screenshots...": "అప్‌లోడ్ చేసిన ఫైల్ చదువుతోంది... పత్రం మరియు స్క్రీన్‌షాట్‌ల నుండి టెక్స్ట్ తీస్తోంది...",
        "Reading your document... finding all charges, hidden fees, and risky clauses...": "మీ పత్రం చదువుతోంది... అన్ని ఛార్జీలు, దాచిన ఫీజులు, ప్రమాదకర నిబంధనలు వెతుకుతోంది...",
        "Need a longer plain-language explanation? Use Gemma after the instant safety report is already visible.": "ఇంకా సులభమైన వివరణ కావాలా? వెంటనే రిపోర్ట్ కనిపించిన తర్వాత Gemma ఉపయోగించండి.",
        "File too large — maximum 10 MB.": "ఫైల్ చాలా పెద్దది — గరిష్ఠం 10 MB.",
        "The uploaded file could not be read. Please remove it and upload again.": "అప్‌లోడ్ చేసిన ఫైల్ చదవలేకపోయాం. దాన్ని తొలగించి మళ్లీ అప్‌లోడ్ చేయండి.",
        "Add Gemma detailed explanation": "Gemma వివరణను జోడించండి",
        "Gemma is preparing a deeper explanation...": "Gemma మరింత లోతైన వివరణ సిద్ధం చేస్తోంది...",
        "Try a Sample Loan Document": "నమూనా లోన్ పత్రాన్ని ప్రయత్నించండి",
        "Analyse This Sample": "ఈ నమూనాను విశ్లేషించండి",
    },
    "Nepali": {
        "Upload document file (PDF, Word, Image)": "कागजात फाइल अपलोड गर्नुहोस् (PDF, Word, Image)",
        "File is ready. Click **Understand This Document** to read and analyse it.": "फाइल तयार छ। पढ्न र विश्लेषण गर्न **यो कागजात बुझ्नुहोस्** क्लिक गर्नुहोस्।",
        "OCR text is ready. Click Understand This Document, or add one short request.": "OCR टेक्स्ट तयार छ। यो कागजात बुझ्नुहोस् क्लिक गर्नुहोस्, वा छोटो अनुरोध थप्नुहोस्।",
        "Text from Scan Document is ready. Click **Understand This Document** below.": "स्क्यान कागजातको टेक्स्ट तयार छ। तल **यो कागजात बुझ्नुहोस्** क्लिक गर्नुहोस्।",
        "Add a short question or paste text manually": "छोटो प्रश्न थप्नुहोस् वा टेक्स्ट आफैं पेस्ट गर्नुहोस्",
        "View uploaded image": "अपलोड गरिएको छवि हेर्नुहोस्",
        "Text extracted — click **Understand This Document** below.": "टेक्स्ट निकालियो — तल **यो कागजात बुझ्नुहोस्** क्लिक गर्नुहोस्।",
        "Reading uploaded file... extracting text from document and screenshots...": "अपलोड गरिएको फाइल पढिँदैछ... कागजात र स्क्रिनसटबाट टेक्स्ट निकालिँदैछ...",
        "Reading your document... finding all charges, hidden fees, and risky clauses...": "तपाईंको कागजात पढिँदैछ... सबै शुल्क, लुकेका फि, र जोखिमपूर्ण सर्तहरू खोजिँदैछ...",
        "Need a longer plain-language explanation? Use Gemma after the instant safety report is already visible.": "अझ सरल लामो व्याख्या चाहिन्छ? तत्काल रिपोर्ट देखिएपछि Gemma प्रयोग गर्नुहोस्।",
        "File too large — maximum 10 MB.": "फाइल धेरै ठूलो छ — अधिकतम 10 MB।",
        "The uploaded file could not be read. Please remove it and upload again.": "अपलोड गरिएको फाइल पढ्न सकिएन। कृपया हटाएर फेरि अपलोड गर्नुहोस्।",
        "Add Gemma detailed explanation": "Gemma विस्तृत व्याख्या थप्नुहोस्",
        "Gemma is preparing a deeper explanation...": "Gemma विस्तृत व्याख्या तयार गर्दैछ...",
        "Try a Sample Loan Document": "नमुना ऋण कागजात प्रयोग गर्नुहोस्",
        "Analyse This Sample": "यो नमुना विश्लेषण गर्नुहोस्",
    },
}

UD_RISK_TEXT = {
    "Hindi": {
        "insurance": "बीमा अनिवार्य हो सकता है और अक्सर महंगा होता है।",
        "penalty": "भुगतान चूकने या शर्त तोड़ने पर अतिरिक्त शुल्क लग सकता है।",
        "penal interest": "EMI देर से भरने पर अतिरिक्त ब्याज लग सकता है।",
        "processing fee": "लोन मिलने से पहले काटा जाने वाला शुल्क।",
        "stamp duty": "लोन दस्तावेज़/रजिस्ट्रेशन के लिए सरकारी शुल्क।",
        "floating rate": "ब्याज दर बाद में बढ़ सकती है।",
        "as applicable": "यह अस्पष्ट भाषा है। सटीक राशि लिखित में लें।",
        "subject to change": "शर्तें बाद में बदल सकती हैं। लिखित पुष्टि लें।",
    },
    "Bengali": {
        "insurance": "বীমা বাধ্যতামূলক হতে পারে এবং অনেক সময় বেশি খরচের হয়।",
        "penalty": "পেমেন্ট মিস করলে বা শর্ত ভাঙলে অতিরিক্ত চার্জ লাগতে পারে।",
        "penal interest": "EMI দেরিতে দিলে অতিরিক্ত সুদ লাগতে পারে।",
        "processing fee": "ঋণের টাকা পাওয়ার আগে কাটা হতে পারে এমন ফি।",
        "stamp duty": "ঋণ ডকুমেন্ট বা রেজিস্ট্রেশনের জন্য সরকারি ফি।",
        "floating rate": "সুদের হার পরে বাড়তে পারে।",
        "as applicable": "এটি অস্পষ্ট ভাষা। সঠিক পরিমাণ লিখিতভাবে নিন।",
        "subject to change": "শর্ত পরে বদলাতে পারে। লিখিত নিশ্চিতকরণ নিন।",
    },
}

UD_CATEGORY_TEXT = {
    "Hindi": {
        "Processing Charges": "प्रोसेसिंग शुल्क",
        "Insurance Charges": "बीमा शुल्क",
        "Penalty Charges": "जुर्माना शुल्क",
        "Hidden Taxes": "छिपे हुए टैक्स",
        "Interest Risks": "ब्याज जोखिम",
        "Legal Risks": "कानूनी जोखिम",
        "Privacy Risks": "गोपनीयता जोखिम",
        "Recovery Risks": "वसूली जोखिम",
        "Subscription Charges": "सब्सक्रिप्शन शुल्क",
        "Ambiguous Clauses": "अस्पष्ट क्लॉज़",
    },
    "Bengali": {
        "Processing Charges": "প্রসেসিং চার্জ",
        "Insurance Charges": "বীমা চার্জ",
        "Penalty Charges": "জরিমানা চার্জ",
        "Hidden Taxes": "লুকানো কর",
        "Interest Risks": "সুদের ঝুঁকি",
        "Legal Risks": "আইনি ঝুঁকি",
        "Privacy Risks": "গোপনীয়তার ঝুঁকি",
        "Recovery Risks": "পুনরুদ্ধার ঝুঁকি",
        "Subscription Charges": "সাবস্ক্রিপশন চার্জ",
        "Ambiguous Clauses": "অস্পষ্ট শর্ত",
    },
}


_UD_TR_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ud_translations.json"
)

_UD_TRANS_KEYS = [
    "Upload document file (PDF, Word, Image)",
    "File too large — maximum 10 MB.",
    "The uploaded file could not be read. Please remove it and upload again.",
    "View uploaded image",
    "Reading image with OCR...",
    "Reading",
    "page(s)...",
    "Extracted",
    "characters from",
    "page(s)",
    "Reading Word document...",
    "characters",
    "Read",
    "characters from text file",
    "Text extracted — click **Understand This Document** below.",
    "File is ready. Click **Understand This Document** to read and analyse it.",
    "Gemma AI Vision is reading your image...",
    "AI Vision could not read this image. Please paste the text below.",
    "OCR could not extract readable text from this image.",
    "The image may have low contrast or unclear text. Try a clearer photo. Or paste the text manually below.",
    "EasyOCR is not installed - cannot read text from images automatically.",
    "Install EasyOCR once for offline image reading, or paste copied text below.",
    "Paste text manually",
    "Paste text",
    "Paste copied text here...",
    "This file appears to contain scanned images - readable text could not be extracted.",
    "If OCR cannot read this file, open the file, copy the text, then paste it manually.",
    "Paste document text manually",
    "Paste loan agreement / bank letter text here...",
    "OCR text is ready. Click Understand This Document, or add one short request.",
    "Text from Scan Document is ready. Click **Understand This Document** below.",
    "Add a short question or paste text manually",
    "Reading uploaded file... extracting text from document and screenshots...",
    "Reading your document... finding all charges, hidden fees, and risky clauses...",
    "Need a longer plain-language explanation? Use Gemma after the instant safety report is already visible.",
    "Add Gemma detailed explanation",
    "Gemma is preparing a deeper explanation...",
    "Try a Sample Loan Document",
    "Analyse This Sample",
    "Risk Score",
    "Risk Clauses Found",
    "FLAT RATE — True cost ≈ stated rate × 1.83",
    "Rate Type",
    "Reducing Balance",
    "Risks by Category",
    "issue(s) found",
    "Risky Terms Detected",
    "No obvious risky terms detected in plain text scan.",
    "SAFE",
    "LOW RISK",
    "MEDIUM RISK",
    "HIGH RISK",
    "CRITICAL RISK",
    "0=Safe · 100=Critical",
]


def _is_good_ud_translation(val: str) -> bool:
    return bool(val) and "\n" not in val and len(val) < 500


def _load_ud_tr_cache():
    try:
        with open(_UD_TR_CACHE, "r", encoding="utf-8") as _f:
            for k, v in json.load(_f).items():
                if k not in st.session_state:
                    st.session_state[k] = v
    except Exception:
        pass


def _save_ud_tr_cache():
    existing = {}
    try:
        with open(_UD_TR_CACHE, "r", encoding="utf-8") as _f:
            existing = json.load(_f)
    except Exception:
        pass
    for k, v in st.session_state.items():
        if k.startswith("udt_") and _is_good_ud_translation(v):
            existing[k] = v
        elif k.startswith("udt_") and k in existing:
            del existing[k]
    os.makedirs(os.path.dirname(_UD_TR_CACHE), exist_ok=True)
    with open(_UD_TR_CACHE, "w", encoding="utf-8") as _f:
        json.dump(existing, _f, ensure_ascii=False)


_load_ud_tr_cache()


def _ud_t(text: str) -> str:
    # 1. Manual translations (Hindi / Bengali)
    translated = UD_TEXT.get(_lang, {}).get(text)
    if translated:
        return translated
    if _lang.lower() == "english":
        return text
    # 2. Session-state cache (populated by batch translator below)
    cached = st.session_state.get(f"udt_{_lang}_{text}")
    if _is_good_ud_translation(cached):
        return cached
    # 3. Fallback to English until batch translator fires on next rerun
    return text


def _ud_upload_button_text() -> str:
    return {
        "Hindi": "फ़ाइल चुनें",
        "Bengali": "ফাইল বেছে নিন",
    }.get(_lang, translate_text("Upload", _lang, context="file upload button label") if _lang.lower() != "english" else "Upload")


def _ud_risk(keyword: str, fallback: str) -> str:
    translated = UD_RISK_TEXT.get(_lang, {}).get(keyword)
    if translated:
        return translated
    if _lang.lower() != "english":
        return translate_text(fallback, _lang, context="loan document risk meaning")
    return fallback


def _ud_category(category: str) -> str:
    lang_map = UD_CATEGORY_TEXT.get(_lang, {})
    for english, translated in lang_map.items():
        if english in category:
            icon = category.split(" ", 1)[0] if " " in category else ""
            return f"{icon} {translated}".strip()
    if _lang.lower() != "english":
        icon = category.split(" ", 1)[0] if " " in category else ""
        plain = category.split(" ", 1)[1] if " " in category else category
        return f"{icon} {translate_text(plain, _lang, context='loan risk category label')}".strip()
    return category


UD_LABELS = {
    "Hindi": {
        "Loan / Money Amounts": "लोन / पैसे की रकम",
        "Interest / Percentage Terms": "ब्याज / प्रतिशत शर्तें",
        "Repayment Time": "भुगतान समय",
        "Key Loan Numbers Found": "मिले हुए मुख्य लोन नंबर",
        "What This Means For The Borrower": "इसका उधारकर्ता के लिए मतलब",
        "Before Signing, Ask These Questions": "हस्ताक्षर से पहले ये सवाल पूछें",
        "Understand Document purpose": "दस्तावेज़ समझने का उद्देश्य",
        "this page explains contract behavior and consequences. Use it after Scan Document when the borrower needs meaning, risk categories, likely impact, and questions to ask.": "यह पेज अनुबंध का व्यवहार और परिणाम समझाता है। स्कैन दस्तावेज़ के बाद इसका उपयोग करें जब उधारकर्ता को अर्थ, जोखिम श्रेणियां, संभावित प्रभाव और पूछने वाले सवाल चाहिए।",
        "penal": "जुर्माना ब्याज",
        "penalty": "जुर्माना",
        "insurance": "बीमा",
        "as applicable": "जैसा लागू हो",
        "processing fee": "प्रोसेसिंग शुल्क",
        "stamp duty": "स्टाम्प ड्यूटी",
        "floating rate": "बदलती ब्याज दर",
        "subject to change": "बदल सकता है",
        "overdue": "देरी से बकाया",
        "bounce charge": "बाउंस शुल्क",
        "dishonour": "भुगतान असफल",
    },
    "Bengali": {
        "Loan / Money Amounts": "ঋণ / টাকার পরিমাণ",
        "Interest / Percentage Terms": "সুদ / শতাংশ শর্ত",
        "Repayment Time": "পরিশোধের সময়",
        "Key Loan Numbers Found": "পাওয়া প্রধান ঋণ সংখ্যা",
        "What This Means For The Borrower": "এটি ঋণগ্রহীতার জন্য কী বোঝায়",
        "Before Signing, Ask These Questions": "সই করার আগে এই প্রশ্নগুলি করুন",
        "Understand Document purpose": "ডকুমেন্ট বোঝার উদ্দেশ্য",
        "this page explains contract behavior and consequences. Use it after Scan Document when the borrower needs meaning, risk categories, likely impact, and questions to ask.": "এই পেজটি চুক্তির আচরণ ও ফলাফল ব্যাখ্যা করে। স্ক্যান ডকুমেন্টের পরে এটি ব্যবহার করুন যখন ঋণগ্রহীতার অর্থ, ঝুঁকি বিভাগ, সম্ভাব্য প্রভাব এবং প্রশ্ন দরকার।",
        "penal": "জরিমানা সুদ",
        "penalty": "জরিমানা",
        "insurance": "বীমা",
        "as applicable": "যা প্রযোজ্য",
        "processing fee": "প্রসেসিং ফি",
        "stamp duty": "স্ট্যাম্প ডিউটি",
        "floating rate": "পরিবর্তনশীল সুদের হার",
        "subject to change": "পরিবর্তন হতে পারে",
        "overdue": "বকেয়া",
        "bounce charge": "বাউন্স চার্জ",
        "dishonour": "পেমেন্ট ব্যর্থ",
    },
}

UD_SENTENCES = {
    "Hindi": {
        "This document appears to use flat-rate wording. Flat-rate loans can cost more than they look because interest may be calculated on the full original amount.": "इस दस्तावेज़ में फ्लैट-रेट जैसी भाषा दिखती है। फ्लैट-रेट लोन दिखने से महंगा हो सकता है क्योंकि ब्याज पूरी मूल राशि पर लग सकता है।",
        "Insurance is mentioned. The borrower should confirm whether it is compulsory, optional, refundable, and how much premium is added to the loan.": "बीमा का उल्लेख है। उधारकर्ता को पुष्टि करनी चाहिए कि यह अनिवार्य है या वैकल्पिक, रिफंड होगा या नहीं, और कितना प्रीमियम लोन में जोड़ा गया है।",
        "Late payment or failed auto-debit can add extra cost. The borrower should ask the exact rupee penalty and how many times it can be charged.": "देर से भुगतान या ऑटो-डेबिट असफल होने पर अतिरिक्त खर्च जुड़ सकता है। उधारकर्ता को सटीक जुर्माना और कितनी बार लग सकता है, यह पूछना चाहिए।",
        "Some charges may reduce the money the borrower actually receives. Ask for all deductions before disbursal.": "कुछ शुल्क उधारकर्ता को मिलने वाली वास्तविक राशि कम कर सकते हैं। पैसा मिलने से पहले सभी कटौतियों की जानकारी लें।",
        "The lender may have rights over an asset or may recover extra costs if repayment fails. Ask what can be taken and what notice will be given.": "भुगतान असफल होने पर lender किसी संपत्ति पर अधिकार या अतिरिक्त वसूली कर सकता है। पूछें कि क्या लिया जा सकता है और कितनी नोटिस मिलेगी।",
        "Some wording is vague. Vague wording can allow later charges or changed terms, so the bank should give fixed written numbers before signing.": "कुछ भाषा अस्पष्ट है। अस्पष्ट भाषा बाद में शुल्क या बदली हुई शर्तों की अनुमति दे सकती है, इसलिए बैंक से हस्ताक्षर से पहले निश्चित लिखित राशि लें।",
        "No major risky wording was detected in the extracted text, but the borrower should still confirm total repayment, all fees, penalty, insurance, and due dates in writing.": "निकाले गए टेक्स्ट में कोई बड़ा जोखिम शब्द नहीं मिला, फिर भी उधारकर्ता को कुल भुगतान, सभी शुल्क, जुर्माना, बीमा और देय तारीख लिखित में पुष्टि करनी चाहिए।",
        "What is the total amount I will repay, including interest and all charges?": "ब्याज और सभी शुल्क मिलाकर मुझे कुल कितना भुगतान करना होगा?",
        "Which fees will be deducted before I receive the loan money?": "लोन का पैसा मिलने से पहले कौन-कौन से शुल्क काटे जाएंगे?",
        "What is the exact penalty if I miss one EMI or pay late?": "अगर मैं एक EMI चूक जाऊं या देर से भुगतान करूं तो सटीक जुर्माना क्या होगा?",
        "Can I get a signed copy of the agreement and full fee list today?": "क्या मुझे आज समझौते और पूरी शुल्क सूची की हस्ताक्षरित कॉपी मिल सकती है?",
        "Is this interest rate fixed, floating, or changeable later?": "क्या यह ब्याज दर स्थिर है, बदलती है, या बाद में बदल सकती है?",
        "Is insurance compulsory, and what is the exact premium?": "क्या बीमा अनिवार्य है, और सटीक प्रीमियम कितना है?",
        "Which asset or document is security, and when will it be released?": "कौन सी संपत्ति या दस्तावेज़ सुरक्षा है, और वह कब छोड़ा जाएगा?",
    },
    "Bengali": {
        "This document appears to use flat-rate wording. Flat-rate loans can cost more than they look because interest may be calculated on the full original amount.": "এই ডকুমেন্টে ফ্ল্যাট-রেট ধরনের ভাষা দেখা যাচ্ছে। ফ্ল্যাট-রেট ঋণ দেখতে কম লাগলেও বেশি খরচ হতে পারে, কারণ সুদ পুরো মূল টাকার ওপর হিসাব হতে পারে।",
        "Insurance is mentioned. The borrower should confirm whether it is compulsory, optional, refundable, and how much premium is added to the loan.": "বীমার কথা আছে। ঋণগ্রহীতার নিশ্চিত করা উচিত এটি বাধ্যতামূলক নাকি ঐচ্ছিক, ফেরতযোগ্য কি না, এবং কত প্রিমিয়াম ঋণে যোগ হয়েছে।",
        "Late payment or failed auto-debit can add extra cost. The borrower should ask the exact rupee penalty and how many times it can be charged.": "দেরিতে পেমেন্ট বা অটো-ডেবিট ব্যর্থ হলে অতিরিক্ত খরচ যোগ হতে পারে। ঋণগ্রহীতার সঠিক জরিমানা এবং কতবার চার্জ হতে পারে তা জিজ্ঞাসা করা উচিত।",
        "Some charges may reduce the money the borrower actually receives. Ask for all deductions before disbursal.": "কিছু চার্জ ঋণগ্রহীতার হাতে পাওয়া আসল টাকা কমিয়ে দিতে পারে। টাকা ছাড়ার আগে সব কাটার হিসাব জিজ্ঞাসা করুন।",
        "The lender may have rights over an asset or may recover extra costs if repayment fails. Ask what can be taken and what notice will be given.": "পরিশোধ ব্যর্থ হলে ঋণদাতার কোনো সম্পদের ওপর অধিকার থাকতে পারে বা অতিরিক্ত খরচ আদায় করতে পারে। কী নেওয়া যেতে পারে এবং কত নোটিশ দেওয়া হবে তা জিজ্ঞাসা করুন।",
        "Some wording is vague. Vague wording can allow later charges or changed terms, so the bank should give fixed written numbers before signing.": "কিছু ভাষা অস্পষ্ট। অস্পষ্ট ভাষা পরে চার্জ বা শর্ত পরিবর্তনের সুযোগ দিতে পারে, তাই সই করার আগে ব্যাংকের কাছ থেকে নির্দিষ্ট লিখিত সংখ্যা নিন।",
        "No major risky wording was detected in the extracted text, but the borrower should still confirm total repayment, all fees, penalty, insurance, and due dates in writing.": "নেওয়া টেক্সটে বড় ঝুঁকিপূর্ণ ভাষা পাওয়া যায়নি, তবুও ঋণগ্রহীতার মোট পরিশোধ, সব ফি, জরিমানা, বীমা এবং শেষ তারিখ লিখিতভাবে নিশ্চিত করা উচিত।",
        "What is the total amount I will repay, including interest and all charges?": "সুদ এবং সব চার্জসহ আমাকে মোট কত টাকা পরিশোধ করতে হবে?",
        "Which fees will be deducted before I receive the loan money?": "ঋণের টাকা পাওয়ার আগে কোন কোন ফি কাটা হবে?",
        "What is the exact penalty if I miss one EMI or pay late?": "আমি একটি EMI মিস করলে বা দেরিতে দিলে সঠিক জরিমানা কত হবে?",
        "Can I get a signed copy of the agreement and full fee list today?": "আমি কি আজ চুক্তি এবং সম্পূর্ণ ফি তালিকার সই করা কপি পেতে পারি?",
        "Is this interest rate fixed, floating, or changeable later?": "এই সুদের হার কি স্থির, পরিবর্তনশীল, নাকি পরে বদলাতে পারে?",
        "Is insurance compulsory, and what is the exact premium?": "বীমা কি বাধ্যতামূলক, এবং সঠিক প্রিমিয়াম কত?",
        "Which asset or document is security, and when will it be released?": "কোন সম্পদ বা ডকুমেন্ট সিকিউরিটি, এবং কখন সেটি ছাড়া হবে?",
    },
}


def _ud_label(text: str) -> str:
    translated = UD_LABELS.get(_lang, {}).get(text)
    if translated:
        return translated
    if _lang.lower() != "english":
        return translate_text(text, _lang, context="loan document report label")
    return text


def _ud_sentence(text: str) -> str:
    translated = UD_SENTENCES.get(_lang, {}).get(text)
    if translated:
        return translated
    if _lang.lower() != "english":
        return translate_text(text, _lang, context="borrower-friendly loan explanation")
    return text


def _visible_numbers(fb: dict) -> list[tuple[str, str]]:
    items = []
    if fb.get("amounts"):
        items.append((_ud_label("Loan / Money Amounts"), ", ".join(a.upper() for a in fb["amounts"][:4])))
    if fb.get("percents"):
        items.append((_ud_label("Interest / Percentage Terms"), ", ".join(fb["percents"][:4])))
    if fb.get("tenures"):
        items.append((_ud_label("Repayment Time"), ", ".join(fb["tenures"][:4])))
    return items


_MANUAL_TRANSLATION_LANGS = {"english", "hindi", "bengali"}


def _manual_ud_report_language() -> bool:
    """True only for languages with complete manual translations in UD_TEXT/UD_LABELS/UD_SENTENCES.
    All other languages use the single-pass English→target translation path."""
    return _lang.lower() in _MANUAL_TRANSLATION_LANGS


def _ud_report_markdown(fb: dict) -> str:
    """Build a complete English understanding report, then translate once."""
    lines = [
        "# Document Understanding Report",
        "This report explains what the loan clauses mean for the borrower before signing.",
        "",
        "## Document Risk Score",
        f"- Risk Score: {fb.get('risk_score', 0)}/100",
        f"- Risk Clauses Found: {len(fb.get('risks', {}))}",
        f"- Rate Type: {'Flat Rate' if fb.get('is_flat') else 'Reducing Balance'}",
        "",
    ]

    key_numbers = _visible_numbers(fb)
    if key_numbers:
        lines.append("## Key Loan Numbers Found")
        for label, value in key_numbers:
            lines.append(f"- {label}: {value}")
        lines.append("")

    lines.append("## Risks by Category")
    if fb.get("categorised"):
        for cat, items in fb["categorised"].items():
            plain_cat = cat.split(" ", 1)[1] if " " in cat else cat
            lines.append(f"### {plain_cat} - {len(items)} issue(s)")
            for kw, desc in items.items():
                lines.append(f"- {kw.upper()}: {desc}")
    elif fb.get("risks"):
        for kw, desc in fb["risks"].items():
            lines.append(f"- {kw.upper()}: {desc}")
    else:
        lines.append("- No obvious risky terms detected in the extracted text.")
    lines.append("")

    lines.append("## What This Means For The Borrower")
    for bullet in _meaning_bullets(fb):
        lines.append(f"- {bullet}")
    lines.append("")

    lines.append("## Before Signing, Ask These Questions")
    for question in _questions_for_borrower(fb):
        lines.append(f"- {question}")
    lines.append("")

    lines.append("## Purpose")
    lines.append("This page explains contract behavior and consequences. Use it after Scan Document when the borrower needs meaning, risk categories, likely impact, and questions to ask.")
    return "\n".join(lines)


def _meaning_bullets(fb: dict) -> list[str]:
    risks = fb.get("risks", {})
    bullets = []
    if fb.get("is_flat"):
        bullets.append(_ud_sentence("This document appears to use flat-rate wording. Flat-rate loans can cost more than they look because interest may be calculated on the full original amount."))
    if "insurance" in risks:
        bullets.append(_ud_sentence("Insurance is mentioned. The borrower should confirm whether it is compulsory, optional, refundable, and how much premium is added to the loan."))
    if any(k in risks for k in ("penalty", "penal interest", "penal", "overdue", "bounce charge", "dishonour")):
        bullets.append(_ud_sentence("Late payment or failed auto-debit can add extra cost. The borrower should ask the exact rupee penalty and how many times it can be charged."))
    if any(k in risks for k in ("processing fee", "stamp duty", "gst", "service charge", "platform fee")):
        bullets.append(_ud_sentence("Some charges may reduce the money the borrower actually receives. Ask for all deductions before disbursal."))
    if any(k in risks for k in ("collateral", "repossession", "hypothecation", "recovery agent", "legal cost")):
        bullets.append(_ud_sentence("The lender may have rights over an asset or may recover extra costs if repayment fails. Ask what can be taken and what notice will be given."))
    if any(k in risks for k in ("as applicable", "subject to change", "sole discretion", "charges may apply")):
        bullets.append(_ud_sentence("Some wording is vague. Vague wording can allow later charges or changed terms, so the bank should give fixed written numbers before signing."))
    if not bullets:
        bullets.append(_ud_sentence("No major risky wording was detected in the extracted text, but the borrower should still confirm total repayment, all fees, penalty, insurance, and due dates in writing."))
    return bullets


def _questions_for_borrower(fb: dict) -> list[str]:
    risks = fb.get("risks", {})
    questions = [
        _ud_sentence("What is the total amount I will repay, including interest and all charges?"),
        _ud_sentence("Which fees will be deducted before I receive the loan money?"),
        _ud_sentence("What is the exact penalty if I miss one EMI or pay late?"),
        _ud_sentence("Can I get a signed copy of the agreement and full fee list today?"),
    ]
    if fb.get("percents"):
        questions.insert(1, _ud_sentence("Is this interest rate fixed, floating, or changeable later?"))
    if "insurance" in risks:
        questions.append(_ud_sentence("Is insurance compulsory, and what is the exact premium?"))
    if any(k in risks for k in ("collateral", "repossession", "hypothecation")):
        questions.append(_ud_sentence("Which asset or document is security, and when will it be released?"))
    return questions[:7]


def _fallback_analysis(text: str) -> dict:
    t = text.lower()
    doc_type = "Financial Document"
    risks = {kw: desc for kw, desc in RISKY_KEYWORDS.items() if kw in t}
    amounts  = re.findall(r'(?:rs\.?|₹|inr)\s*[\d,]+(?:\.\d+)?', t)
    percents = re.findall(r'\d+(?:\.\d+)?\s*%', t)
    tenures  = re.findall(r'\d+\s*(?:months?|years?)', t)
    is_flat  = bool(re.search(r'flat\s*rate|flat\s*interest', t))

    # Compute risk score (0=safe, 100=critical)
    risk = sum(_RISK_WEIGHTS.get(kw, 5) for kw in risks)
    for rate_str in re.findall(r'(\d+(?:\.\d+)?)\s*%', t):
        try:
            r = float(rate_str)
            if r > 28:   risk += 25
            elif r > 24: risk += 18
            elif r > 18: risk += 10
            elif r > 14: risk += 4
            break
        except ValueError:
            pass
    if is_flat:
        risk += 10
    risk_score = max(0, min(100, risk))

    # Group found risks by category
    categorised = {}
    for cat, keywords in _RISK_CATEGORIES.items():
        found = {kw: RISKY_KEYWORDS[kw] for kw in keywords if kw in risks}
        if found:
            categorised[cat] = found

    return {
        "doc_type": doc_type, "risks": risks, "categorised": categorised,
        "risk_score": risk_score,
        "amounts": list(dict.fromkeys(amounts))[:8],
        "percents": list(dict.fromkeys(percents))[:6],
        "tenures": list(dict.fromkeys(tenures))[:4],
        "is_flat": is_flat, "word_count": len(text.split()),
    }


def _risk_score_html(risk_score: int) -> str:
    color = (
        "#22c55e" if risk_score <= 20 else
        "#86efac" if risk_score <= 40 else
        "#eab308" if risk_score <= 60 else
        "#f97316" if risk_score <= 80 else
        "#ef4444"
    )
    band = (
        "SAFE" if risk_score <= 20 else
        "LOW RISK" if risk_score <= 40 else
        "MEDIUM RISK" if risk_score <= 60 else
        "HIGH RISK" if risk_score <= 80 else
        "CRITICAL RISK"
    )
    pct = risk_score
    return f"""
  <div style="border:1px solid {color};border-radius:10px;padding:12px 16px;background:{color}18;margin-bottom:8px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
    <span style="font-size:1.5rem;font-weight:800;color:{color};">{risk_score}/100</span>
    <span style="font-size:.85rem;font-weight:700;color:{color};">{_ud_t(band)}</span>
    <span style="font-size:.7rem;color:#6b7280;">{_ud_t("0=Safe · 100=Critical")}</span>
  </div>
  <div style="background:#e5e7eb;border-radius:4px;height:8px;overflow:hidden;">
    <div style="width:{pct}%;height:100%;background:{color};border-radius:4px;transition:width .4s;"></div>
  </div>
</div>"""


# ── Language → BCP-47 for Web Speech API ────────────────────────────────────
_LANG_BCP47 = {
    "Hindi": "hi-IN", "Bengali": "bn-IN", "Tamil": "ta-IN", "Telugu": "te-IN",
    "Marathi": "mr-IN", "Gujarati": "gu-IN", "Kannada": "kn-IN", "Malayalam": "ml-IN",
    "Punjabi": "pa-IN", "Urdu": "ur-IN", "Odia": "or-IN", "Assamese": "as-IN",
    "Nepali": "ne-IN", "Kashmiri": "ks-IN", "Sindhi": "sd-IN", "Dogri": "doi-IN",
    "Konkani": "kok-IN", "Maithili": "mai-IN", "Bodo": "brx-IN", "Manipuri": "mni-IN",
    "Santhali": "sat-IN", "English": "en-IN",
}


def _ud_tts_panel(text: str, lang: str):
    """Render a single TTS button that speaks `text` in `lang` via Web Speech API."""
    import streamlit.components.v1 as _comp
    _lc = _LANG_BCP47.get(lang, "en-IN")
    _safe = (text.replace("\\", "").replace("`", "'")
             .replace('"', "'").replace("\n", " ")[:3000])
    _uid = abs(hash(_safe[:80])) % 999983
    _comp.html(f"""<div style="margin:6px 0">
<button id="tts{_uid}" onclick="(function(){{
  var b=document.getElementById('tts{_uid}');
  if(window['_x{_uid}']){{window.speechSynthesis.cancel();window['_x{_uid}']=false;
    b.innerHTML='🔊 Listen';b.style.background='#1e3a5f';return;}}
  var u=new SpeechSynthesisUtterance(`{_safe}`);
  u.lang='{_lc}';window['_x{_uid}']=true;
  b.innerHTML='⏹ Stop';b.style.background='#7f1d1d';
  u.onend=u.onerror=function(){{window['_x{_uid}']=false;
    b.innerHTML='🔊 Listen';b.style.background='#1e3a5f';}};
  window.speechSynthesis.speak(u);}})()"
style="background:#1e3a5f;color:#7eb8f7;border:1px solid #2563eb;
       border-radius:8px;padding:5px 14px;cursor:pointer;font-size:0.82rem">
🔊 Listen</button>
<span style="font-size:0.72rem;color:#6b7280;margin-left:8px">
  Reads summary aloud · Works offline
</span></div>""", height=46)


def _render_fallback(fb: dict):
    if not _manual_ud_report_language():
        report = _ud_report_markdown(fb)
        report = translate_text(report, _lang, context="complete borrower document understanding report", live=True)
        st.markdown(report)
        st.download_button(
            _t["download_report"],
            report,
            file_name="document_understanding_report.txt",
            mime="text/plain",
            use_container_width=True,
            key="dl_ud_fast_translated_report",
        )
        return

    # ── Large visual Safety Verdict ──────────────────────────────────────
    _rs = fb["risk_score"]
    _vc = (
        "#22c55e" if _rs <= 20 else
        "#86efac" if _rs <= 40 else
        "#eab308" if _rs <= 60 else
        "#f97316" if _rs <= 80 else
        "#ef4444"
    )
    _ve = "✅" if _rs <= 20 else ("⚠️" if _rs <= 60 else "🚨")
    _vl = (
        _ud_t("SAFE") if _rs <= 20 else
        _ud_t("LOW RISK") if _rs <= 40 else
        _ud_t("MEDIUM RISK") if _rs <= 60 else
        _ud_t("HIGH RISK") if _rs <= 80 else
        _ud_t("CRITICAL RISK")
    )
    _va = (
        "Low risk — confirm total repayment and all fees in writing before signing." if _rs <= 20 else
        "A few items to check — review highlighted terms before signing." if _rs <= 40 else
        "Important clauses found — carefully read all highlighted risks before signing." if _rs <= 60 else
        "High risk — strongly consider getting free legal advice (NALSA: 15100) before signing." if _rs <= 80 else
        "Critical risks found — DO NOT SIGN without consulting a lawyer or NALSA (15100)."
    )
    st.markdown(f"""
<div style="background:{_vc}20;border:3px solid {_vc};border-radius:14px;
            padding:20px 24px;text-align:center;margin-bottom:14px;">
  <div style="font-size:2.6rem;line-height:1.1">{_ve}</div>
  <div style="font-size:1.5rem;font-weight:800;color:{_vc};margin:6px 0">{_vl}</div>
  <div style="font-size:2rem;font-weight:700;color:{_vc}">{_rs}<span style="font-size:1rem;font-weight:400;color:#9ca3af">/100</span></div>
  <div style="font-size:0.85rem;color:#9ca3af;margin-top:6px">{_va}</div>
</div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric(_ud_t("Risk Score"), f"{fb['risk_score']}/100")
    c2.metric(_ud_t("Risk Clauses Found"), len(fb["risks"]))
    if fb["is_flat"]:
        c3.error("⚠️ " + _ud_t("FLAT RATE — True cost ≈ stated rate × 1.83"))
    else:
        c3.metric(_ud_t("Rate Type"), _ud_t("Reducing Balance"))

    # ── Evidence: How was this score calculated? ──────────────────────────
    with st.expander("🔎 How was this score calculated?", expanded=False):
        st.caption(
            "This score is generated by automatic keyword detection on your document text. "
            "Each detected keyword adds points. AI (Gemma) analysis provides more accurate scoring."
        )
        if fb.get("risks"):
            _ev_rows = [
                {
                    "Keyword Found": kw.upper(),
                    "Points Added": f"+{_RISK_WEIGHTS.get(kw, 5)}",
                    "Why It Matters": desc[:90] + ("…" if len(desc) > 90 else ""),
                }
                for kw, desc in fb["risks"].items()
            ]
            try:
                import pandas as _pd_ev
                st.dataframe(_pd_ev.DataFrame(_ev_rows), use_container_width=True, hide_index=True)
            except Exception:
                for _r in _ev_rows:
                    st.markdown(f"• **{_r['Keyword Found']}** ({_r['Points Added']}): {_r['Why It Matters']}")
        else:
            st.success("No risky keywords were detected in the extracted text.")
        if fb.get("is_flat"):
            st.info("⚠️ +10 points: Flat-rate interest language detected in this document.")

    key_numbers = _visible_numbers(fb)
    if key_numbers:
        st.markdown(f"#### 📌 {_ud_label('Key Loan Numbers Found')}")
        number_cols = st.columns(min(3, len(key_numbers)))
        for idx, (label, value) in enumerate(key_numbers):
            with number_cols[idx % len(number_cols)]:
                st.info(f"**{label}**\n\n{value}")

    # Categorised risks
    if fb["categorised"]:
        st.markdown(f"#### ⚠️ {_ud_t('Risks by Category')}")
        for cat, items in fb["categorised"].items():
            with st.expander(f"{_ud_category(cat)} — {len(items)} {_ud_t('issue(s) found')}", expanded=True):
                for kw, desc in items.items():
                    risk_name = _ud_label(kw)
                    if _lang.lower() == "english":
                        risk_name = risk_name.upper()
                    st.error(f"**{risk_name}** — {_ud_risk(kw, desc)}")
    elif fb["risks"]:
        st.markdown(f"#### ⚠️ {_ud_t('Risky Terms Detected')}")
        for kw, desc in fb["risks"].items():
            risk_name = _ud_label(kw)
            if _lang.lower() == "english":
                risk_name = risk_name.upper()
            st.error(f"**{risk_name}** — {_ud_risk(kw, desc)}")
    else:
        st.success(_ud_t("No obvious risky terms detected in plain text scan."))

    st.markdown(f"#### 🧠 {_ud_label('What This Means For The Borrower')}")
    _sum_bullets = _meaning_bullets(fb)
    for bullet in _sum_bullets:
        st.markdown(f"- {bullet}")
    _ud_tts_panel(" ".join(_sum_bullets), _lang)

    st.markdown(f"#### ✋ {_ud_label('Before Signing, Ask These Questions')}")
    for question in _questions_for_borrower(fb):
        st.markdown(f"- {question}")

    st.info(
        f"**{_ud_label('Understand Document purpose')}:** "
        + _ud_label("this page explains contract behavior and consequences. Use it after Scan Document when the borrower needs meaning, risk categories, likely impact, and questions to ask.")
    )


def _render_ai_result(ai_text: str):
    if _lang.lower() != "english":
        ai_text = translate_text(ai_text, _lang, context="complete loan document safety report", live=True)
    st.success(_t["analysis_complete"])
    st.markdown(ai_text)
    st.download_button(
        _t["download_report"],
        ai_text,
        file_name="document_safety_report.txt",
        mime="text/plain",
        use_container_width=True,
        key="dl_report_understand",
    )


def _run_analysis(text: str) -> dict:
    """Fast default analysis for document understanding.

    This avoids long waits on local/online LLM calls during the main borrower flow.
    """
    text = normalize_ocr_text(text)
    return {"type": "fallback", "data": _fallback_analysis(text)}


def _run_gemma_analysis(text: str) -> dict:
    text = normalize_ocr_text(text)
    rag_ctx = rag_query(text[:500], n=3)
    ctx_block = f"\n\nReference Knowledge:\n{rag_ctx}\n\n" if rag_ctx else ""
    text_for_ai = text[:4500] + "\n[...truncated...]" if len(text) > 4500 else text
    resp = generate(UNDERSTAND_PROMPT + ctx_block + text_for_ai, language=_lang)
    if resp.startswith("⚠️"):
        return {"type": "fallback", "data": _fallback_analysis(text)}
    return {"type": "ai", "data": resp}


def _extract_uploaded_document(file_bytes: bytes, filename: str) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext in (".jpg", ".jpeg", ".jfif", ".pjpeg", ".pjp", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif", ".heic", ".heif"):
        return extract_text_from_image(file_bytes, filename, languages=[_lang])
    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes) if is_pdf_support_available() else ""
    if ext == ".docx":
        return extract_text_from_docx(file_bytes) if is_docx_support_available() else ""
    if ext == ".doc":
        return extract_text_from_doc(file_bytes) if is_docx_support_available() else ""
    if ext == ".txt":
        return file_bytes.decode("utf-8", errors="replace").strip()
    return ""


# ── Page header ───────────────────────────────────────────────────────────────
st.markdown(f"## 🔍 {_t['understand_page_title']}")
st.caption(_t["understand_page_caption"])
st.markdown("<div style='margin-bottom:8px'></div>", unsafe_allow_html=True)

# ── Upload section ────────────────────────────────────────────────────────────
_upload_title = _ud_t("Upload document file (PDF, Word, Image)")
with st.container():
    uploaded = st.file_uploader(
        _upload_title,
        type=[
            "jpg", "jpeg", "jfif", "pjpeg", "pjp", "png", "bmp", "tif", "tiff",
            "webp", "gif", "heic", "heif", "pdf", "docx", "doc", "txt",
        ],
        help="Supported: common image files, PDF, Word, and text files — Max 10 MB",
        key="ud_upload",
    )
    if uploaded and uploaded.size > 10 * 1024 * 1024:
        st.error(_ud_t("File too large — maximum 10 MB."))
        uploaded = None

    if uploaded:
        file_bytes = uploaded.getvalue()
        if not file_bytes:
            st.error(_ud_t("The uploaded file could not be read. Please remove it and upload again."))
            st.stop()
        file_sig = (
            f"{uploaded.name}:{uploaded.size}:"
            f"{hashlib.sha1(file_bytes[:1024 * 1024]).hexdigest()}"
        )
        if st.session_state.get("ud_upload_sig") != file_sig:
            st.session_state["ud_upload_sig"] = file_sig
            st.session_state.pop("ud_uploaded_text", None)
            st.session_state.pop("ud_result", None)

        ext = os.path.splitext(uploaded.name.lower())[1]
        raw_text = st.session_state.get("ud_uploaded_text", "")
        _auto_extract_now = False
        _is_image = ext in (".jpg", ".jpeg", ".jfif", ".pjpeg", ".pjp", ".png", ".bmp",
                            ".tiff", ".tif", ".webp", ".gif", ".heic", ".heif")

        # ── Image ────────────────────────────────────────────────────────────
        _ocr_ran = False
        if _is_image:
            with st.expander("🖼️ " + _ud_t("View uploaded image"), expanded=False):
                st.image(file_bytes, use_container_width=True)
            if raw_text.strip():
                pass
            elif _auto_extract_now and is_ocr_available():
                with st.spinner(_ud_t("Reading image with OCR...")):
                    raw_text = extract_text_from_image(file_bytes, uploaded.name, languages=[_lang])
                _ocr_ran = True
                if raw_text.startswith("OCR") or raw_text.startswith("No text") \
                        or len(raw_text.strip()) < 10:
                    raw_text = ""

        # ── PDF ──────────────────────────────────────────────────────────────
        elif ext == ".pdf":
            if raw_text.strip():
                pass
            elif _auto_extract_now and is_pdf_support_available():
                pages = get_pdf_page_count(file_bytes)
                with st.spinner(f"{_ud_t('Reading')} {pages} {_ud_t('page(s)...')}"):
                    raw_text = extract_text_from_pdf(file_bytes)
                if raw_text and not raw_text.startswith("PDF") and len(raw_text) >= _MIN_CHARS:
                    st.success(f"✅ {_ud_t('Extracted')} {len(raw_text):,} {_ud_t('characters from')} {pages} {_ud_t('page(s)')}")
                else:
                    raw_text = ""

        # ── DOCX / DOC ────────────────────────────────────────────────────────
        elif ext in (".docx", ".doc"):
            if raw_text.strip():
                pass
            elif _auto_extract_now and is_docx_support_available():
                with st.spinner(_ud_t("Reading Word document...")):
                    raw_text = extract_text_from_docx(file_bytes) if ext == ".docx" \
                               else extract_text_from_doc(file_bytes)
                if raw_text and not raw_text.startswith("DOCX") and not raw_text.startswith("DOC") \
                        and not raw_text.startswith("No text") and len(raw_text) >= _MIN_CHARS:
                    st.success(f"✅ {_ud_t('Extracted')} {len(raw_text):,} {_ud_t('characters')}")
                else:
                    raw_text = ""

        elif ext == ".txt" and _auto_extract_now and not raw_text.strip():
            raw_text = file_bytes.decode("utf-8", errors="replace").strip()
            if raw_text:
                st.success(f"✅ {_ud_t('Read')} {len(raw_text):,} {_ud_t('characters from text file')}")

        # ── Extraction result ─────────────────────────────────────────────────
        if raw_text.strip():
            st.session_state["ud_uploaded_text"] = raw_text
            st.success(_ud_t("Text extracted — click **Understand This Document** below."))
        elif not _auto_extract_now:
            st.info(_ud_t("File is ready. Click **Understand This Document** to read and analyse it."))
        else:
            # ── Auto Vision AI for images (no button needed) ──────────────────
            if _is_image and _vision_ok:
                with st.spinner(_ud_t("Gemma AI Vision is reading your image...")):
                    _mime = "image/png" if ext == ".png" else "image/jpeg"
                    vision_result = generate_with_image(
                        UNDERSTAND_PROMPT, file_bytes, mime_type=_mime, language=_lang,
                    )
                if vision_result and not vision_result.startswith("⚠️") \
                        and vision_result != "__VISION_UNAVAILABLE__":
                    st.session_state["ud_result"] = {"type": "ai", "data": vision_result}
                    st.rerun()
                else:
                    st.error(_ud_t("AI Vision could not read this image. Please paste the text below."))

            elif _is_image and not _vision_ok:
                if _ocr_ran:
                    # OCR ran but found no readable text
                    st.warning(_ud_t("OCR could not extract readable text from this image."))
                    st.info(
                        _ud_t("The image may have low contrast or unclear text. Try a clearer photo. Or paste the text manually below.")
                    )
                else:
                    # EasyOCR not installed
                    st.warning(_ud_t("EasyOCR is not installed - cannot read text from images automatically."))
                st.info(_ud_t("Install EasyOCR once for offline image reading, or paste copied text below."))
                with st.expander("✍️ " + _ud_t("Paste text manually"), expanded=False):
                    pasted = st.text_area(
                        _ud_t("Paste text"),
                        height=90,
                        placeholder=_ud_t("Paste copied text here..."),
                        key="ud_paste_fallback",
                        label_visibility="collapsed",
                    )
                    if pasted.strip() and len(pasted.strip()) >= 20:
                        st.success(f"✅ {len(pasted.strip()):,} characters ready.")
                        if st.button(_t["analyse_btn"], type="primary",
                                     use_container_width=True, key="btn_ud_paste_go"):
                            st.session_state["ud_manual_text"] = pasted.strip()
                            st.session_state["ud_result"] = _run_analysis(pasted.strip())
                            st.rerun()

            else:
                # DOCX / PDF with scanned content — Ctrl+A works here
                st.warning(_ud_t("This file appears to contain scanned images - readable text could not be extracted."))
                st.info(_ud_t("If OCR cannot read this file, open the file, copy the text, then paste it manually."))
                with st.expander("✍️ " + _ud_t("Paste document text manually"), expanded=False):
                    pasted = st.text_area(
                        _ud_t("Paste text"),
                        height=90,
                        placeholder=_ud_t("Paste loan agreement / bank letter text here..."),
                        key="ud_paste_fallback",
                        label_visibility="collapsed",
                    )
                    if pasted.strip() and len(pasted.strip()) >= 20:
                        st.success(f"✅ {len(pasted.strip()):,} characters ready.")
                        if st.button(_t["analyse_btn"], type="primary",
                                     use_container_width=True, key="btn_ud_paste_go"):
                            st.session_state["ud_manual_text"] = pasted.strip()
                            st.session_state["ud_result"] = _run_analysis(pasted.strip())
                            st.rerun()

# ── Optional text/question area ───────────────────────────────────────────────
_scan_text = st.session_state.get("scan_raw_text", "").strip()
_uploaded_text = st.session_state.get("ud_uploaded_text", "").strip()
_uploaded_file_ready = "uploaded" in globals() and uploaded is not None

if _uploaded_text:
    st.caption(_ud_t("OCR text is ready. Click Understand This Document, or add one short request."))
elif _scan_text:
    st.info(_ud_t("Text from Scan Document is ready. Click **Understand This Document** below."))

manual_text = ""
with st.expander("✍️ " + _ud_t("Add a short question or paste text manually"), expanded=not (_uploaded_text or _scan_text)):
    manual_text = st.text_area(
        _t.get("ask_paste_label", "Ask about this document, or paste document text here:"),
        height=90,
        placeholder=(
            "Example: explain this document in simple words, find hidden charges, "
            "or tell me what questions to ask before signing."
        ),
        key="ud_manual_text",
        label_visibility="collapsed",
    )

if _uploaded_text:
    doc_text = _uploaded_text
    if manual_text.strip():
        doc_text += "\n\nUser request: " + manual_text.strip()
elif _scan_text:
    doc_text = _scan_text
    if manual_text.strip():
        doc_text += "\n\nUser request: " + manual_text.strip()
else:
    doc_text = manual_text.strip()

col_a, col_b = st.columns([3, 1])
with col_a:
    analyse_clicked = st.button(
        _t["analyse_btn"],
        type="primary",
        use_container_width=True,
        key="btn_ud_analyse",
        disabled=not (doc_text.strip() or _uploaded_file_ready),
    )
with col_b:
    if st.button(_t.get("clear_btn", "Clear"), use_container_width=True, key="btn_ud_clear"):
        st.session_state.pop("ud_result", None)
        st.session_state.pop("scan_raw_text", None)
        st.session_state.pop("ud_manual_text", None)
        st.session_state.pop("ud_upload_sig", None)
        st.session_state.pop("ud_uploaded_text", None)
        st.rerun()

if analyse_clicked:
    if not doc_text.strip() and _uploaded_file_ready:
        with st.spinner(_ud_t("Reading uploaded file... extracting text from document and screenshots...")):
            extracted_text = _extract_uploaded_document(uploaded.getvalue(), uploaded.name)
        if extracted_text and not extracted_text.startswith(("DOCX", "DOC", "PDF", "OCR", "No text")) and len(extracted_text.strip()) >= 20:
            st.session_state["ud_uploaded_text"] = extracted_text.strip()
            st.session_state["ud_result"] = _run_analysis(extracted_text.strip())
            st.rerun()
        else:
            st.warning("Readable text could not be extracted from this file. Open the manual paste box and paste copied text.")
    elif doc_text.strip():
        with st.spinner(_ud_t("Reading your document... finding all charges, hidden fees, and risky clauses...")):
            st.session_state["ud_result"] = _run_analysis(doc_text)
        st.rerun()

if st.session_state.get("ud_result"):
    st.divider()
    res = st.session_state["ud_result"]
    if res["type"] == "ai":
        _render_ai_result(res["data"])
    else:
        _render_fallback(res["data"])
        if mode != "limited" and doc_text.strip():
            st.info(_ud_t("Need a longer plain-language explanation? Use Gemma after the instant safety report is already visible."))
            if st.button("✨ " + _ud_t("Add Gemma detailed explanation"), use_container_width=True, key="btn_ud_gemma_detail"):
                with st.spinner(_ud_t("Gemma is preparing a deeper explanation...")):
                    st.session_state["ud_result"] = _run_gemma_analysis(doc_text)
                st.rerun()
    if st.button(_t.get("analyse_another_btn", "🔄 Analyse Another Document"), use_container_width=True, key="btn_ud_reset"):
        st.session_state.pop("ud_result", None)
        st.session_state.pop("ud_manual_text", None)
        st.session_state.pop("ud_upload_sig", None)
        st.session_state.pop("ud_uploaded_text", None)
        st.rerun()

# ── Sample document ───────────────────────────────────────────────────────────
with st.expander("📌 " + _ud_t("Try a Sample Loan Document")):
    sample = (
        "LOAN AGREEMENT — ABC Microfinance Ltd\n"
        "Loan Amount: ₹2,00,000 | Interest Rate: 18% per annum flat rate\n"
        "Tenure: 24 months | EMI: ₹10,167\n"
        "Processing Fee: 3% (deducted upfront). Stamp Duty: ₹500.\n"
        "Mandatory Insurance Premium: ₹5,000 (non-refundable, non-optional).\n"
        "GST on fees: 18%.\n"
        "Prepayment Penalty: 5% if closed before 12 months.\n"
        "Penal Interest: 3% per month on overdue EMI.\n"
        "Acceleration Clause: On 30-day default, entire loan + 24% penal interest due immediately.\n"
        "Arbitration: All disputes to binding arbitration only. Consumer court rights waived.\n"
        "Personal Guarantee: Family member must sign as guarantor."
    )
    st.code(sample, language=None)
    if st.button(_ud_t("Analyse This Sample"), key="btn_ud_sample", use_container_width=True):
        with st.spinner("Analysing sample…"):
            st.session_state["ud_result"] = _run_analysis(sample)
        st.rerun()

# ── Silent one-shot Understand Document translation ───────────────────────────
if _lang not in ("English",) and _lang not in ("Hindi", "Bengali") and mode != "limited":
    _missing_ud = [
        k for k in _UD_TRANS_KEYS
        if not _is_good_ud_translation(st.session_state.get(f"udt_{_lang}_{k}"))
    ]
    if _missing_ud:
        _saved_ud = False
        _ud_payload = json.dumps({k: k for k in _missing_ud}, ensure_ascii=False)
        _ud_prompt = (
            f"Translate these UI phrases to {_lang}. "
            "Return ONLY a valid JSON object with the same keys and translated values. "
            "Keep numbers, currency symbols, and technical terms unchanged. No extra text.\n\n"
            + _ud_payload
        )
        _ud_resp = generate(_ud_prompt, language=_lang, allow_online=(mode == "online")).strip()
        _ud_translations: dict = {}
        try:
            _s = _ud_resp.find("{")
            _e = _ud_resp.rfind("}") + 1
            if _s >= 0 and _e > _s:
                _ud_translations = json.loads(_ud_resp[_s:_e])
        except Exception:
            pass
        for _uk in _missing_ud:
            _utr = str(_ud_translations.get(_uk, "")).strip()
            if _is_good_ud_translation(_utr) and _utr != _uk:
                st.session_state[f"udt_{_lang}_{_uk}"] = _utr
                _saved_ud = True
        if not _ud_translations:
            for _uk in _missing_ud[:10]:
                _ur = generate(
                    f"Translate to {_lang}. Return ONLY the translation, nothing else:\n\n{_uk}",
                    language=_lang, allow_online=(mode == "online"),
                ).strip()
                if _is_good_ud_translation(_ur) and _ur != _uk:
                    st.session_state[f"udt_{_lang}_{_uk}"] = _ur
                    _saved_ud = True
        if _saved_ud:
            _save_ud_tr_cache()
            st.rerun()
