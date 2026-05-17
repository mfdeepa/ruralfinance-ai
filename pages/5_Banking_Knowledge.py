import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from services.ai_service import generate, detect_mode
from services.localization_service import translate_text
from utils.styles import inject_css, sidebar_header, inject_nav_drawer
from utils.translations import get_ui
from utils.india_config import INDIA_COUNTRY_BADGE, normalize_app_language, SUPPORTED_LANGUAGE_COPY
from utils.page_controls import render_language_back_topbar

# ── Disk-based translation cache (survives page reloads & browser sessions) ──
_CACHE_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_CACHE_FILE = os.path.join(_CACHE_DIR, "bk_translations.json")

def _load_bk_cache() -> dict:
    try:
        with open(_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_bk_cache(data: dict):
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

st.set_page_config(
    page_title="Know Your Terms — RuralFinance AI",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_css()

# ── Remove default top gap ────────────────────────────────────────────────
st.markdown("""
<style>
.main .block-container,
[data-testid="stMainBlockContainer"],
[data-testid="block-container"] {
    padding-top: 0.3rem !important;
}
</style>
""", unsafe_allow_html=True)

mode = detect_mode()

_qp = st.query_params
if "user_language" not in st.session_state and _qp.get("l"):
    st.session_state["user_language"] = normalize_app_language(_qp.get("l", "English"))
    st.session_state["user_country"] = INDIA_COUNTRY_BADGE
    st.session_state["user_name"] = _qp.get("n", "")
    st.session_state["onboarding_done"] = True
st.session_state["user_country"] = INDIA_COUNTRY_BADGE

sidebar_header(mode)
inject_nav_drawer("Understand Banking")
_t = get_ui(st.session_state.get("user_language", "English"))
_lang = st.session_state.get("user_language", "English")

BK_TEXT = {
    "Hindi": {
        "Offline mode — definitions work without internet.": "ऑफ़लाइन मोड — परिभाषाएँ बिना इंटरनेट काम करती हैं।",
        "Online — Gemma 4 deeper explanations available.": "ऑनलाइन — Gemma 4 से गहरी व्याख्या उपलब्ध है।",
        "words": "शब्द",
        "click to expand": "खोलने के लिए क्लिक करें",
        "banking & loan words — simple language, no internet needed — understand every word before you sign": "बैंकिंग और लोन शब्द — सरल भाषा, इंटरनेट की जरूरत नहीं — साइन करने से पहले हर शब्द समझें",
        "Showing available definitions now. Translating to": "अभी उपलब्ध परिभाषाएँ दिख रही हैं। अनुवाद हो रहा है:",
        "in the background...": "पृष्ठभूमि में...",
        "No terms found. Try a different word.": "कोई शब्द नहीं मिला। दूसरा शब्द खोजें।",
        "Deeper explanation (Gemma 4)": "गहरी व्याख्या (Gemma 4)",
        "Translation progress for": "अनुवाद प्रगति",
        "terms ready": "शब्द तैयार",
        "Translate next": "अगले अनुवाद करें",
        "terms to": "शब्द",
    },
    "Bengali": {
        "Offline mode — definitions work without internet.": "অফলাইন মোড — সংজ্ঞাগুলি ইন্টারনেট ছাড়া কাজ করে।",
        "Online — Gemma 4 deeper explanations available.": "অনলাইন — Gemma 4 দিয়ে গভীর ব্যাখ্যা পাওয়া যায়।",
        "words": "শব্দ",
        "click to expand": "খুলতে ক্লিক করুন",
        "banking & loan words — simple language, no internet needed — understand every word before you sign": "ব্যাংকিং ও ঋণের শব্দ — সহজ ভাষা, ইন্টারনেট দরকার নেই — সই করার আগে প্রতিটি শব্দ বুঝুন",
        "Showing available definitions now. Translating to": "এখন উপলব্ধ সংজ্ঞা দেখানো হচ্ছে। অনুবাদ হচ্ছে:",
        "in the background...": "পেছনে...",
        "No terms found. Try a different word.": "কোনো শব্দ পাওয়া যায়নি। অন্য শব্দ খুঁজুন।",
        "Deeper explanation (Gemma 4)": "গভীর ব্যাখ্যা (Gemma 4)",
        "Translation progress for": "অনুবাদের অগ্রগতি",
        "terms ready": "শব্দ প্রস্তুত",
        "Translate next": "পরবর্তী অনুবাদ করুন",
        "terms to": "শব্দ",
    },
}


def _bk_t(text: str) -> str:
    translated = BK_TEXT.get(_lang, {}).get(text)
    if translated:
        return translated
    if _lang.lower() != "english":
        return translate_text(text, _lang, context="RuralFinance banking knowledge UI", live=False)
    return text

# ── Header: title left, back button right ─────────────────────────────────
_t = render_language_back_topbar("banking", "btn_bk_home")
_lang = st.session_state.get("user_language", "English")
st.markdown(f"### 📖 {_t.get('banking_page_title', 'Know Your Terms')}")
st.caption(_t.get("banking_page_caption", "Simple definitions for every banking and loan word. Works 100% without internet."))

# ── All terms — written in simple language for low-literacy users ─────────
TERMS = {
    "🏦 Basic Banking": {
        "Bank": "A safe place to keep your money. The bank protects it and pays you a little extra (called interest) just for keeping it there. Example: SBI, HDFC Bank, Post Office Bank.",
        "Savings Account": "Your basic account to keep money safe. For every ₹100 you save, the bank gives you ₹3–4 extra every year. Take money out anytime using ATM card or passbook.",
        "Current Account": "An account mostly used by shopkeepers and businesses. The bank pays no extra money (interest) here. Useful only if you make many payments every day.",
        "Zero Balance Account": "A savings account where you do NOT need to always keep money in it. No fine if it goes to zero. Open this if you earn little or earn irregularly.",
        "Jan Dhan Account (PMJDY)": "A free government account for every poor family. No minimum balance needed. You get a free ATM card, ₹1 lakh accident cover, ₹30,000 life cover, and can borrow up to ₹10,000 if needed.",
        "KYC (Know Your Customer)": "The bank asks to see who you are before opening your account. Show your Aadhaar card + one more address proof. Done once. Protects you from fraud.",
        "Balance": "How much money is in your account right now. Always check before spending. Low balance can cause a penalty fee.",
        "Minimum Balance": "The smallest amount you must always keep in your account. If it falls below this, the bank deducts a fine. Zero-balance accounts have no such rule.",
        "Deposit": "Putting money INTO your account — at bank counter, ATM cash deposit machine, or by receiving a transfer.",
        "Withdrawal": "Taking money OUT of your account — at ATM, bank counter, or by sending it to someone else.",
        "Cheque": "A paper slip you write and sign telling the bank: 'Pay this much money to this person.' Torn from a chequebook. Bank pays out when the person deposits it.",
        "Demand Draft (DD)": "A safe bank-issued payment slip. It cannot fail like a cheque. Used for college fees, government payments. Bank charges a small fee to make it.",
        "Bank Statement": "A list of all money that went in and came out of your account. Ask for it every month. Check it carefully to catch any wrong deductions.",
        "Passbook": "A small booklet where all your account transactions are printed. Take it to the bank to update. Keep it safely — it shows your complete money history.",
        "IFSC Code": "An 11-letter code that identifies your bank branch. Give this to anyone who wants to send money to your account. Example: SBIN0001234.",
        "MICR Code": "A 9-digit number at the bottom of your cheque. Bank machines read this automatically to process cheques quickly.",
        "ATM": "A machine outside the bank where you can take out cash, check your balance, or get a mini statement — any time, day or night, without visiting the bank.",
        "Debit Card": "A card linked to your bank account. When you pay with it, money leaves your account immediately. Use at ATM, shops, and online.",
        "Credit Card": "A card where the bank lets you spend money now and pay later. You get 45 days free. BUT if you do not repay fully, they charge 36–42% interest per year — very costly.",
        "PIN": "A secret 4–6 digit number for your ATM or phone banking. NEVER tell this to anyone — not even bank staff or police.",
        "OTP (One Time Password)": "A 6-digit code sent to your phone to confirm a payment. Works only for a few minutes. NEVER give OTP to anyone — not on phone, WhatsApp, or any app.",
        "Nominee": "The person who gets your bank money if you die. Add your wife, husband, parent, or child as nominee when opening the account.",
        "Bank Locker": "A locked box inside the bank to store your gold, documents, property papers. You pay ₹500–₹3,000 per year as rent.",
        "Bank Charges": "Fees the bank takes from your account for services — ATM charges after 5 free uses per month, minimum balance fine, cheque return fee. Always ask for the full charges list.",
        "Simple Interest": "Interest calculated only on the original amount. Example: Borrow ₹10,000 at 10% for 2 years → interest = ₹2,000 total.",
        "Compound Interest": "Interest calculated on the original amount PLUS on previous interest. Your savings grow faster. But as a borrower, you owe more and more quickly.",
        "Signature": "Your personal sign on bank papers. Must look the same every time. Bank compares it to confirm it is really you.",
        "Overdraft (OD)": "Bank allows you to take out more money than you have in your account, up to a limit. You pay interest only on what you borrow. Good for short-term cash needs.",
        "Standing Instruction": "You tell the bank once: 'Automatically pay ₹X every month on date Y.' The bank does it without you needing to remember. Used for EMI, insurance premium.",
        "USSD Banking (*99#)": "Dial *99# on ANY mobile phone — even a basic button phone, no internet needed. Check balance, send money, get mini statement. Completely free.",
        "Missed Call Banking": "Give a missed call to your bank's number. Get your account balance as an SMS instantly. Free. Example: SBI number — 09223766666.",
        "Business Correspondent (BC)": "A bank agent who comes to your village with a handheld machine. Can open accounts, accept deposits, and give you cash. Like a mini bank at your doorstep.",
    },
    "💰 Loans & Credit": {
        "Loan": "Money you borrow from the bank today and promise to repay slowly over time with a little extra (interest). You repay in small monthly amounts called EMI.",
        "Principal": "The original amount you borrowed — not including the interest. Example: You took ₹1 lakh loan → ₹1 lakh is the principal.",
        "Interest": "The extra amount you pay to the bank for lending you money. Higher the rate, more you pay total. Always compare rates before taking any loan.",
        "EMI (Equated Monthly Installment)": "A fixed amount you pay every single month until the loan is fully repaid. It includes part of the loan amount + interest. Example: ₹2,000 every month for 24 months.",
        "Tenure": "Total time to repay the loan. Longer tenure = smaller EMI each month, but you pay more interest in total over time.",
        "Collateral / Security": "Something valuable you keep with the bank as a guarantee — like land papers, gold, vehicle. If you stop repaying, the bank can take and sell it.",
        "Mortgage": "Keeping your house or land papers with the bank as security for a loan. You live in your house but bank holds the papers until you fully repay the loan.",
        "Hypothecation": "Keeping your vehicle or machine as security while still using it. Example: In a car loan, your car is hypothecated to the bank.",
        "Pledge": "Physically giving your gold or valuables to the bank for a loan. You get them back only after you fully repay.",
        "Guarantor": "A person who signs your loan papers and promises to repay IF you cannot. If you default, the guarantor's own property and credit score are at risk.",
        "Co-borrower": "A second person who applies for the loan with you. Both are equally responsible to repay. Helps you get a bigger loan amount.",
        "Credit Score (CIBIL)": "A number from 300 to 900 that shows how reliably you repay loans. Above 750 is good. Higher score = you get loans faster and at lower interest rates.",
        "CIBIL Report": "A full record of all your loans and credit cards and whether you paid on time. Banks check this before giving any loan. Check your free report once a year.",
        "NPA (Non-Performing Asset)": "If you miss EMI for 3 months (90 days), your loan is labelled NPA. This badly damages your credit score. Bank can take legal action to recover money.",
        "Default": "Completely stopping EMI payment on a loan. Bank will seize your collateral and take you to court. You may not get any loan in future.",
        "Overdue": "EMI that is past its due date but less than 90 days late. Pay immediately! Every day adds penalty interest and your credit score drops.",
        "Foreclosure / Prepayment": "Paying off your entire remaining loan before the last due date. You save on future interest. Some banks charge a small penalty for early repayment — always ask.",
        "Processing Fee": "A one-time fee taken by the bank when approving your loan. Usually 0.5–2% of loan amount. Example: ₹1 lakh loan → fee of ₹500 to ₹2,000.",
        "Penal Interest": "Extra interest charged when you miss or delay an EMI payment. Usually 2–3% on top of normal rate. Avoid by always paying EMI on time.",
        "Secured Loan": "Loan where you provide security (land, gold, vehicle). Lower interest because bank has protection. Examples: home loan, gold loan, car loan.",
        "Unsecured Loan": "Loan with no security needed. Higher interest because bank takes more risk. Examples: personal loan, credit card.",
        "Personal Loan": "Loan for any personal purpose — medical, wedding, home repair. No security needed. Quick approval. Interest 10–20% per year. Repay as EMIs.",
        "Home Loan": "Loan to buy or build a house. Lowest interest rate (8–10%). Repay over up to 30 years. Your house papers are kept with the bank as security.",
        "Car Loan": "Loan to buy a car or two-wheeler. The vehicle is kept as security. Repay over 1–7 years.",
        "Education Loan": "Loan to pay college fees for your child. Repayment starts 6–12 months after course ends. Government may subsidize interest for weaker sections.",
        "Gold Loan": "Give your gold jewellery to the bank and get cash instantly. Fastest loan — no income proof needed. Get gold back after full repayment.",
        "Kisan Credit Card (KCC)": "Special credit card for farmers to buy seeds, fertilizers, and equipment. Pay back after harvest. Government subsidy brings interest down to just 7% per year.",
        "Mudra Loan": "Government loan for small businesses. No collateral needed. Shishu = up to ₹50,000. Kishore = up to ₹5 lakh. Tarun = up to ₹10 lakh.",
        "Microfinance": "Very small loans (₹5,000 to ₹1 lakh) for poor people with no collateral required. Repay weekly or monthly. Common through SHGs and NGOs.",
        "SHG Loan (Self Help Group)": "Loans given to a group of 10–20 women who save together regularly. Very low interest. No security needed. Great way for women to start small businesses.",
        "Debt Trap": "Taking a new loan to repay an old loan. Debt keeps growing and becomes impossible to repay. VERY DANGEROUS. Borrow only what you can clearly afford to repay.",
        "Loan Against Property (LAP)": "Large loan by keeping your house or land as security. Get 50–70% of property value as loan. Lower interest than personal loan.",
        "Credit Limit": "The maximum you can spend on a credit card or overdraft. Do not use the full limit — it can become very difficult to repay.",
        "Loan Eligibility": "How much loan the bank will give you. Based on your income, age, credit score, and existing loans. Total EMIs should not be more than 40–50% of your monthly income.",
    },
    "📱 Digital Banking": {
        "UPI (Unified Payments Interface)": "A free mobile payment system. Send or receive money instantly 24/7 using just a phone number or UPI ID. Maximum ₹1 lakh per transfer. Completely free.",
        "UPI ID / VPA": "Your personal address for receiving UPI payments. Format: yourname@bankname. Share this to receive money — no need to share your account number.",
        "UPI PIN": "A 4–6 digit secret number you set to approve every UPI payment. NEVER share this with anyone.",
        "BHIM App": "Government's free UPI app. Works on any smartphone. Available in 20 Indian languages. Supports all banks. Download from Play Store or App Store.",
        "QR Code": "A black-and-white square pattern that contains payment information. Scan it with your phone camera to pay — no typing of numbers needed.",
        "NEFT": "Send money to any bank account in India. Free in most banks. Money arrives within a few minutes to a few hours.",
        "RTGS": "For sending very large amounts (₹2 lakh or more) instantly. Available 24/7. Used for big property payments or business transactions.",
        "IMPS": "Instant money transfer up to ₹5 lakh. Works 24/7 including holidays. Use this when transfer is urgent.",
        "Net Banking": "Manage your bank account using your bank's website on a computer. Login with username + password + OTP. Never use on shared or public computers.",
        "Mobile Banking": "Manage your account using your bank's official app on your smartphone. More convenient than visiting branch.",
        "Transaction / Reference ID": "A unique number for every digital payment — like a receipt. Save it. Use it if payment fails or you need to raise a dispute.",
        "Beneficiary": "The person or account that receives your transferred money. Add them once with account number + IFSC before sending money.",
        "2-Factor Authentication": "Two steps to login — first your password, then an OTP. Makes it very hard for fraudsters to break into your account.",
        "Tokenization": "Your real card number is replaced with a random code for online shopping. Protects your actual card number from being stolen.",
        "Digital Wallet": "An app (Paytm, PhonePe) where you load money from your bank and spend from the app balance. Different from UPI — limited to wallet amount.",
        "NACH / Auto-debit": "Automatic monthly deduction from your account for EMI, insurance, or SIP. You give permission once. Bank deducts automatically on the same date every month.",
        "RuPay Card": "India's own debit card — made in India by NPCI. Works at all Indian ATMs and shops. Given free with Jan Dhan accounts. Lower fees than Visa or Mastercard.",
        "Contactless Payment": "Tap your card on the payment machine — no PIN needed for payments up to ₹5,000. Fast and safe.",
        "AePS (Aadhaar-enabled Payment)": "Withdraw or deposit money using only your Aadhaar number + fingerprint. No card or smartphone needed. Works at bank agents in villages. Free.",
        "SMS Alerts": "Text messages your bank sends for every transaction in your account. Always keep alerts ON. If you see a transaction you did not do — call your bank immediately.",
        "NPCI": "National Payments Corporation of India. It runs UPI, RuPay, IMPS, NACH and many digital payment systems used by Indian banks.",
    },
    "🛡️ Insurance": {
        "Insurance": "You pay a small amount regularly (called premium). If something bad happens — illness, accident, death — the company pays you a large amount to cover the loss.",
        "Premium": "The regular amount you pay to keep your insurance active. Pay monthly, quarterly, or yearly. Stopping payment cancels your coverage.",
        "Sum Assured / Coverage": "The maximum amount the insurance company pays you. Example: Term insurance of ₹50 lakh → your family gets ₹50 lakh if you die.",
        "Claim": "When something bad happens, you formally ask the insurance company to pay. Example: Submitting hospital bills to health insurance = making a claim.",
        "Claim Settlement Ratio": "The % of claims the company actually paid out. Example: 97% means they paid 97 out of every 100 claims. Always choose a company with 95% or above.",
        "Term Insurance": "Pure life insurance. Your family gets ₹50 lakh or ₹1 crore if you die. Very cheap — costs only ₹400–₹1,000 per month. Every earning member MUST have this.",
        "Endowment Policy": "Insurance + savings combined. Pay premium for years, get money back at the end or on death. Returns are low (4–5%). Much more expensive than term.",
        "ULIP": "Insurance mixed with stock market investment. Has high charges in starting years. Complex product. Only buy if you fully understand it.",
        "LIC": "Life Insurance Corporation — India's biggest and most trusted insurer. Government owned. Pays almost all valid claims. Good for first-time buyers.",
        "Health Insurance (Mediclaim)": "Pays your hospital bills when you are sick. Covers surgery, ICU, medicines. Show your insurance card — the hospital bills the company directly.",
        "Cashless Treatment": "Hospital bills your insurance company directly. You pay nothing upfront. Works ONLY at hospitals listed in your insurance company's network.",
        "Network Hospital": "Hospitals that have agreement with your insurance company for cashless treatment. Always check the network list before buying insurance.",
        "Pre-existing Disease (PED)": "Any health condition you already had BEFORE buying insurance. Usually not covered for the first 2–4 years. Always disclose honestly when buying.",
        "Waiting Period": "Time after buying insurance when certain conditions are not covered. Pre-existing diseases: wait 2–4 years. Maternity: wait 9–24 months.",
        "Copayment": "You pay a fixed % of every claim. Example: 20% copay → if hospital bill is ₹1 lakh, you pay ₹20,000 and insurance pays ₹80,000. Lower premium but you share cost.",
        "Ayushman Bharat (PM-JAY)": "Government health insurance for poor families. Completely FREE. Covers hospital treatment up to ₹5 lakh per year at government-listed hospitals.",
        "PMJJBY": "Government life insurance scheme. Only ₹436 per year deducted automatically from your bank account. Family gets ₹2 lakh if you die. Available for age 18–50.",
        "PMSBY": "Government accident insurance. Only ₹20 per year. Family gets ₹2 lakh if you die in accident, ₹1 lakh if permanently disabled. Available for age 18–70.",
        "PM Fasal Bima Yojana": "Crop insurance for farmers. Very low premium (1.5–5%). Government pays the rest. Covers crop loss due to flood, drought, storms, and pests.",
        "Motor Insurance (Third Party)": "Required by law for every vehicle. Pays for damage your vehicle causes to others. Driving without this = heavy police fine.",
        "No Claim Bonus (NCB)": "Discount on next year's insurance premium if you made no claims this year. Builds up each year — can save up to 50% after 5 years without a claim.",
        "Grace Period": "Extra 15–30 days after due date to pay overdue premium. Your insurance stays active during this time.",
        "Surrender Value": "Money you get if you cancel a life insurance policy before it matures. Always less than total premiums paid. Avoid cancelling unless absolutely necessary.",
        "IRDAI": "The government body that controls all insurance companies in India. If company refuses to pay valid claim, complain to IRDAI at helpline 155255. Free.",
    },
    "🏛️ Regulators & Economy": {
        "RBI (Reserve Bank of India)": "The 'boss bank' of India. Controls all banks, prints currency, and sets interest rates. If any bank cheats you, RBI can take action against them.",
        "Repo Rate": "The interest rate at which RBI lends to banks. When this goes up, bank loan rates increase for you. When it goes down, loan rates may also decrease.",
        "Reverse Repo Rate": "Rate at which banks park extra money with RBI. Lower than repo rate. Used by RBI to manage money in the economy.",
        "CRR (Cash Reserve Ratio)": "Banks must keep a portion of all customer deposits as cash with RBI. This ensures banks always have enough money if many customers want to withdraw.",
        "SLR (Statutory Liquidity Ratio)": "Banks must invest a portion of deposits in safe government bonds. Currently about 18%. This protects depositors if bank faces losses.",
        "MCLR": "The minimum interest rate banks can charge on loans. Banks cannot lend at a rate lower than this.",
        "EBLR": "Home loan rate directly linked to RBI's rate. When RBI changes its rate, your home loan EMI automatically changes in the next cycle.",
        "SEBI": "Government body controlling stock markets and mutual funds in India. All investment companies must be registered with SEBI. Protects investors from fraud.",
        "NABARD": "Special government bank that provides funds to rural banks and cooperatives. They then lend to farmers and rural businesses at low rates.",
        "PSU Banks": "Banks owned by the government — like SBI, PNB, Bank of Baroda. Very safe — government guarantees your deposits.",
        "Private Banks": "Banks owned by private companies — like HDFC Bank, ICICI Bank, Axis Bank. Usually have better mobile apps and service. Also safe and regulated by RBI.",
        "Small Finance Banks": "Banks that specifically serve poor people and small businesses. RBI licensed. Give higher interest on savings. Safe to keep money.",
        "Payment Banks": "Can accept deposits up to ₹2 lakh and do payments. CANNOT give loans. Examples: Paytm Payments Bank, Airtel Payments Bank.",
        "NBFC": "A financial company that gives loans but is NOT a bank. Examples: Bajaj Finance, Muthoot Finance. Regulated by RBI but deposits not covered by bank insurance.",
        "Banking Ombudsman": "A FREE complaint service by RBI. If bank doesn't solve your complaint in 30 days, file at cms.rbi.org.in or call RBI at 14440. No lawyer needed.",
        "Priority Sector Lending": "RBI's rule that banks must give 40% of all loans to farmers, small businesses, students, and poor people. Ensures rural areas get credit.",
        "Financial Inclusion": "Making sure every person — even the poorest in villages — can access banking, insurance, and credit. Jan Dhan Yojana is the main government tool.",
        "Capital Adequacy Ratio": "Minimum money banks must keep for safety. Kept at 9% in India. If bank makes losses, this protects your deposits from being lost.",
        "SHG / JLG Loan": "A group-based loan often used in rural India. Members support each other in repayment. Ask about weekly collection, total interest, and penalty rules.",
        "GDP": "Total value of all goods and services produced in India in one year. When GDP grows, more jobs are created and incomes improve.",
        "Inflation": "When prices of daily things keep going up every year. ₹100 today buys less than ₹100 did 5 years ago. RBI tries to keep inflation at 4–6% per year.",
        "Credit Rating (CRISIL/ICRA)": "Score given to companies and banks showing how safe they are. AAA = very safe. D = defaulted/bankrupt. Check this before investing money anywhere.",
        "DBT (Direct Benefit Transfer)": "Government sends subsidy money (gas, ration, scholarship) directly to your Aadhaar-linked bank account. No middlemen. No corruption possible.",
    },
    "🚨 Scam Protection": {
        "OTP Fraud": "Someone calls pretending to be bank/police/TRAI. Says account is blocked. Asks for OTP to 'fix' it. Giving OTP = they empty your account in minutes. NEVER share OTP — for ANY reason.",
        "Phishing": "Fake websites or emails that look exactly like your bank's. You type your password and they steal it. NEVER click links received in SMS or email.",
        "Vishing": "A fraud phone call from someone pretending to be bank staff or government. They ask for card number, PIN, or OTP. Real bank staff NEVER asks for any of these.",
        "Smishing": "A fraud SMS with a link saying 'account blocked' or 'you won a prize'. The link installs a virus on your phone or steals your login. Never tap links in unknown SMS.",
        "KYC Fraud": "Call says your KYC is expired and account will be blocked. Asks you to download AnyDesk or similar app. They then see your phone screen and steal your OTP.",
        "SIM Swap": "Fraudster gets your phone network blocked and takes out a new SIM in your name. Your phone suddenly loses network. All OTPs go to the fraudster. Call bank immediately.",
        "UPI Collect Scam": "Someone sends a payment 'collect' request on your UPI app. It LOOKS like you will receive money. But entering your PIN actually sends money TO them. Never enter PIN to 'receive'.",
        "Fake Loan App": "App gives instant loan without documents. Then collects your private photos and contacts. Later threatens to send photos to your contacts if you don't pay more. Only use RBI-registered lenders.",
        "Ponzi / Pyramid Scam": "Someone promises 20–30% monthly returns. Pays early investors using new investors' money. Eventually collapses and everyone loses. Never invest in such schemes.",
        "Lottery Scam": "SMS or call says you won ₹10 lakh in a lottery. Asks for ₹5,000 processing fee first. There is no lottery. Real lotteries NEVER ask for fees to claim prize.",
        "Card Skimming": "A device attached to ATM copies your card data. A hidden camera records your PIN. Always cover the keypad with your other hand when entering PIN.",
        "Investment WhatsApp Scam": "Fake 'investment tips' WhatsApp group. Shows fake profits on screen. You invest real money — then they disappear with it. Only use SEBI-registered advisors.",
        "Recovery Fraud": "You were already cheated. Now someone calls offering to recover your money for a fee upfront. This is ALSO a scam — no one can recover lost money for a fee.",
        "Report Cybercrime": "Call 1930 immediately. File a complaint at cybercrime.gov.in. Report to your bank within 24 hours. The sooner you report, the better chance to recover money.",
        "Golden Rule": "No bank, RBI, police, or any government officer will EVER ask for your OTP, PIN, CVV, or card number on phone or WhatsApp. Anyone asking is 100% a fraudster.",
    },
}


# Built-in offline definitions for the selected language.
# These show instantly, even when Gemma translation is slow or unavailable.
LOCAL_DEFINITIONS = {
    "Hindi": {
        "Bank": "बैंक पैसे रखने की सुरक्षित जगह है। बैंक आपका पैसा सुरक्षित रखता है और जमा पैसे पर थोड़ा ब्याज भी दे सकता है। उदाहरण: SBI, HDFC बैंक, पोस्ट ऑफिस बैंक।",
        "Savings Account": "बचत खाता आपका सामान्य बैंक खाता है। इसमें आप पैसा सुरक्षित रख सकते हैं, जरूरत पड़ने पर निकाल सकते हैं, और बैंक कुछ ब्याज भी दे सकता है।",
        "Current Account": "चालू खाता ज्यादातर दुकानदारों और व्यापारियों के लिए होता है। इसमें रोज बहुत सारे लेन-देन किए जा सकते हैं, लेकिन सामान्यतः ब्याज नहीं मिलता।",
        "Zero Balance Account": "शून्य बैलेंस खाते में हमेशा पैसा रखना जरूरी नहीं होता। अगर खाते में पैसा शून्य भी हो जाए तो सामान्यतः जुर्माना नहीं लगता।",
        "Jan Dhan Account (PMJDY)": "जन धन खाता गरीब और ग्रामीण परिवारों के लिए सरकार की योजना है। इसमें न्यूनतम बैलेंस जरूरी नहीं होता और बैंकिंग सुविधा आसानी से मिलती है।",
        "KYC (Know Your Customer)": "KYC में बैंक आपकी पहचान और पता जांचता है। इसके लिए आधार, पहचान पत्र या पता प्रमाण मांगा जा सकता है। यह धोखाधड़ी रोकने के लिए जरूरी है।",
        "Balance": "बैलेंस का मतलब है कि आपके खाते में अभी कितना पैसा उपलब्ध है। पैसा खर्च करने या EMI कटने से पहले बैलेंस जरूर जांचें।",
        "Minimum Balance": "न्यूनतम बैलेंस वह कम से कम रकम है जो खाते में रखनी पड़ती है। इससे कम होने पर बैंक शुल्क काट सकता है।",
        "Deposit": "डिपॉजिट का मतलब खाते में पैसा जमा करना है। यह बैंक काउंटर, नकद जमा मशीन या ऑनलाइन ट्रांसफर से हो सकता है।",
        "Withdrawal": "निकासी का मतलब खाते से पैसा निकालना है। यह ATM, बैंक काउंटर या डिजिटल ट्रांसफर से हो सकता है।",
        "Cheque": "चेक एक कागज होता है जिस पर आप लिखकर और हस्ताक्षर करके बैंक को किसी व्यक्ति को पैसा देने का आदेश देते हैं।",
        "Demand Draft (DD)": "डिमांड ड्राफ्ट बैंक द्वारा बनाया गया सुरक्षित भुगतान कागज है। यह चेक की तरह बाउंस नहीं होता, इसलिए फीस या सरकारी भुगतान में काम आता है।",
        "Bank Statement": "बैंक स्टेटमेंट में आपके खाते में आए और निकले हर पैसे की सूची होती है। गलत कटौती या धोखाधड़ी पकड़ने के लिए इसे देखते रहें।",
        "Passbook": "पासबुक छोटी किताब होती है जिसमें आपके खाते के लेन-देन छपे होते हैं। इसे बैंक में अपडेट कराया जा सकता है।",
        "IFSC Code": "IFSC कोड आपके बैंक शाखा की पहचान है। किसी को आपके खाते में पैसा भेजना हो तो उसे खाता नंबर के साथ IFSC चाहिए।",
        "MICR Code": "MICR कोड चेक पर लिखा 9 अंकों का नंबर होता है। बैंक मशीनें चेक को जल्दी पहचानने के लिए इसका उपयोग करती हैं।",
        "ATM": "ATM मशीन से आप बैंक जाए बिना नकद पैसा निकाल सकते हैं, बैलेंस देख सकते हैं और मिनी स्टेटमेंट ले सकते हैं।",
        "Debit Card": "डेबिट कार्ड आपके बैंक खाते से जुड़ा होता है। इससे भुगतान करते ही पैसा तुरंत आपके खाते से कट जाता है।",
        "Credit Card": "क्रेडिट कार्ड में बैंक आपको अभी खर्च करने और बाद में भुगतान करने की सुविधा देता है। पूरा भुगतान समय पर न करने पर बहुत ज्यादा ब्याज लग सकता है।",
        "PIN": "PIN आपका गुप्त नंबर है। इसे कभी किसी को न बताएं, बैंक कर्मचारी या पुलिस को भी नहीं।",
        "OTP (One Time Password)": "OTP कुछ मिनट के लिए आने वाला गुप्त कोड है। इसे किसी को बताने से आपका पैसा चोरी हो सकता है।",
        "Nominee": "नॉमिनी वह व्यक्ति है जिसे आपकी मृत्यु के बाद खाते का पैसा मिल सकता है। खाता खोलते समय भरोसेमंद परिवार सदस्य को नॉमिनी बनाएं।",
        "Bank Locker": "बैंक लॉकर बैंक के अंदर सुरक्षित डिब्बा होता है, जहां सोना, कागज या जरूरी दस्तावेज रखे जाते हैं। इसके लिए वार्षिक किराया देना पड़ता है।",
        "Bank Charges": "बैंक चार्ज वे शुल्क हैं जो बैंक सेवाओं के लिए काट सकता है, जैसे ATM शुल्क, न्यूनतम बैलेंस जुर्माना या चेक वापसी शुल्क।",
        "Simple Interest": "साधारण ब्याज केवल मूल रकम पर लगता है। उदाहरण: ₹10,000 पर 10% ब्याज एक साल में ₹1,000 होगा।",
        "Compound Interest": "चक्रवृद्धि ब्याज में ब्याज पर भी ब्याज लगता है। बचत में यह अच्छा है, लेकिन कर्ज में कुल भुगतान तेजी से बढ़ सकता है।",
        "Signature": "हस्ताक्षर आपकी पहचान का तरीका है। बैंक कागजों पर वही हस्ताक्षर करें जो आपके बैंक रिकॉर्ड में हैं।",
        "Overdraft (OD)": "ओवरड्राफ्ट में बैंक आपको खाते में मौजूद पैसे से अधिक रकम निकालने की अनुमति देता है। इस्तेमाल की गई रकम पर ब्याज देना पड़ता है।",
        "Standing Instruction": "स्टैंडिंग इंस्ट्रक्शन में आप बैंक को हर महीने तय तारीख पर अपने-आप भुगतान करने का निर्देश देते हैं, जैसे EMI या बीमा प्रीमियम।",
        "USSD Banking (*99#)": "*99# सेवा से साधारण मोबाइल पर भी बिना इंटरनेट बैंकिंग की कुछ सुविधाएं मिलती हैं, जैसे बैलेंस देखना या पैसा भेजना।",
        "Missed Call Banking": "मिस्ड कॉल बैंकिंग में बैंक के नंबर पर मिस्ड कॉल देकर SMS से बैलेंस या जानकारी मिलती है। यह सरल और तेज तरीका है।",
        "Business Correspondent (BC)": "बिजनेस कॉरेस्पॉन्डेंट गांव में बैंक एजेंट की तरह काम करता है। वह खाता खोलने, जमा और निकासी जैसी सेवाएं दे सकता है।",
        "Loan": "लोन वह पैसा है जो आप बैंक या संस्था से उधार लेते हैं और बाद में ब्याज सहित किस्तों में चुकाते हैं।",
        "Principal": "प्रिंसिपल यानी मूल कर्ज की रकम। इसमें ब्याज शामिल नहीं होता।",
        "Interest": "ब्याज वह अतिरिक्त पैसा है जो कर्ज लेने के बदले बैंक को देना पड़ता है। ब्याज दर जितनी अधिक होगी, कुल भुगतान उतना अधिक होगा।",
        "EMI (Equated Monthly Installment)": "EMI वह तय मासिक किस्त है जो आप हर महीने चुकाते हैं। इसमें मूल रकम और ब्याज दोनों शामिल होते हैं।",
        "Tenure": "टेन्योर यानी लोन चुकाने की कुल अवधि। अवधि लंबी होने पर EMI कम हो सकती है, लेकिन कुल ब्याज बढ़ सकता है।",
        "Processing Fee": "प्रोसेसिंग फीस लोन मंजूर करते समय बैंक द्वारा ली जाने वाली एक बार की फीस है। लोन लेने से पहले इसका पूरा हिसाब पूछें।",
        "Penal Interest": "पेनल ब्याज EMI देर से भरने या चूकने पर लगने वाला अतिरिक्त ब्याज है। यह कर्ज को महंगा बना सकता है।",
        "Collateral / Security": "कोलैटरल वह संपत्ति या चीज है जिसे बैंक सुरक्षा के रूप में रखता है। कर्ज न चुकाने पर बैंक उसे बेच सकता है।",
        "Credit Score (CIBIL)": "क्रेडिट स्कोर 300 से 900 तक का नंबर है जो बताता है कि आप कर्ज समय पर चुकाते हैं या नहीं। अच्छा स्कोर लोन लेने में मदद करता है।",
        "Default": "डिफॉल्ट का मतलब है लोन की किस्तें चुकाना बंद कर देना। इससे क्रेडिट स्कोर खराब होता है और कानूनी कार्रवाई हो सकती है।",
    }
}

CATEGORY_LABELS = {
    "Hindi": {
        "🏦 Basic Banking": "🏦 बुनियादी बैंकिंग",
        "💰 Loans & Credit": "💰 लोन और क्रेडिट",
        "📱 Digital Banking": "📱 डिजिटल बैंकिंग",
        "🛡️ Insurance": "🛡️ बीमा",
        "🏛️ Regulators & Economy": "🏛️ नियामक और अर्थव्यवस्था",
        "🚨 Scam Protection": "🚨 धोखाधड़ी से बचाव",
    },
    "Tamil": {
        "🏦 Basic Banking": "🏦 அடிப்படை வங்கி",
        "💰 Loans & Credit": "💰 கடன்கள் மற்றும் கடன்",
        "📱 Digital Banking": "📱 டிஜிட்டல் வங்கி",
        "🛡️ Insurance": "🛡️ காப்பீடு",
        "🏛️ Regulators & Economy": "🏛️ நிர்வாகிகள் மற்றும் பொருளாதாரம்",
        "🚨 Scam Protection": "🚨 மோசடி பாதுகாப்பு",
    },
    "Telugu": {
        "🏦 Basic Banking": "🏦 ప్రాథమిక బ్యాంకింగ్",
        "💰 Loans & Credit": "💰 రుణాలు మరియు క్రెడిట్",
        "📱 Digital Banking": "📱 డిజిటల్ బ్యాంకింగ్",
        "🛡️ Insurance": "🛡️ భీమా",
        "🏛️ Regulators & Economy": "🏛️ నియంత్రకులు మరియు ఆర్థిక వ్యవస్థ",
        "🚨 Scam Protection": "🚨 మోసం నుండి రక్షణ",
    },
    "Marathi": {
        "🏦 Basic Banking": "🏦 मूलभूत बँकिंग",
        "💰 Loans & Credit": "💰 कर्जे आणि क्रेडिट",
        "📱 Digital Banking": "📱 डिजिटल बँकिंग",
        "🛡️ Insurance": "🛡️ विमा",
        "🏛️ Regulators & Economy": "🏛️ नियामक आणि अर्थव्यवस्था",
        "🚨 Scam Protection": "🚨 फसवणूक संरक्षण",
    },
    "Gujarati": {
        "🏦 Basic Banking": "🏦 મૂળભૂત બૅન્કિંગ",
        "💰 Loans & Credit": "💰 લોન અને ક્રેડિટ",
        "📱 Digital Banking": "📱 ડિજિટલ બૅન્કિંગ",
        "🛡️ Insurance": "🛡️ વીમો",
        "🏛️ Regulators & Economy": "🏛️ નિયામક અને અર્થતંત્ર",
        "🚨 Scam Protection": "🚨 છેતરપિંડીથી રક્ષણ",
    },
    "Kannada": {
        "🏦 Basic Banking": "🏦 ಮೂಲಭೂತ ಬ್ಯಾಂಕಿಂಗ್",
        "💰 Loans & Credit": "💰 ಸಾಲ ಮತ್ತು ಕ್ರೆಡಿಟ್",
        "📱 Digital Banking": "📱 ಡಿಜಿಟಲ್ ಬ್ಯಾಂಕಿಂಗ್",
        "🛡️ Insurance": "🛡️ ವಿಮೆ",
        "🏛️ Regulators & Economy": "🏛️ ನಿಯಂತ್ರಕರು ಮತ್ತು ಆರ್ಥಿಕತೆ",
        "🚨 Scam Protection": "🚨 ವಂಚನೆ ರಕ್ಷಣೆ",
    },
    "Malayalam": {
        "🏦 Basic Banking": "🏦 അടിസ്ഥാന ബാങ്കിംഗ്",
        "💰 Loans & Credit": "💰 വായ്പകൾ ക്രെഡിറ്റ്",
        "📱 Digital Banking": "📱 ഡിജിറ്റൽ ബാങ്കിംഗ്",
        "🛡️ Insurance": "🛡️ ഇൻഷുറൻസ്",
        "🏛️ Regulators & Economy": "🏛️ നിയന്ത്രകർ സമ്പദ്‌വ്യവസ്ഥ",
        "🚨 Scam Protection": "🚨 തട്ടിപ്പ് സംരക്ഷണം",
    },
    "Bengali": {
        "🏦 Basic Banking": "🏦 প্রাথমিক ব্যাংকিং",
        "💰 Loans & Credit": "💰 লোন ও ক্রেডিট",
        "📱 Digital Banking": "📱 ডিজিটাল ব্যাংকিং",
        "🛡️ Insurance": "🛡️ বীমা",
        "🏛️ Regulators & Economy": "🏛️ নিয়ন্ত্রক ও অর্থনীতি",
        "🚨 Scam Protection": "🚨 স্ক্যাম সুরক্ষা",
    },
    "Punjabi": {
        "🏦 Basic Banking": "🏦 ਮੁੱਢਲੀ ਬੈਂਕਿੰਗ",
        "💰 Loans & Credit": "💰 ਕਰਜ਼ੇ ਅਤੇ ਕ੍ਰੈਡਿਟ",
        "📱 Digital Banking": "📱 ਡਿਜੀਟਲ ਬੈਂਕਿੰਗ",
        "🛡️ Insurance": "🛡️ ਬੀਮਾ",
        "🏛️ Regulators & Economy": "🏛️ ਨਿਯੰਤ੍ਰਕ ਅਤੇ ਅਰਥਵਿਵਸਥਾ",
        "🚨 Scam Protection": "🚨 ਧੋਖਾਧੜੀ ਤੋਂ ਸੁਰੱਖਿਆ",
    },
    "Urdu": {
        "🏦 Basic Banking": "🏦 بنیادی بینکاری",
        "💰 Loans & Credit": "💰 قرضے اور کریڈٹ",
        "📱 Digital Banking": "📱 ڈیجیٹل بینکاری",
        "🛡️ Insurance": "🛡️ بیمہ",
        "🏛️ Regulators & Economy": "🏛️ ریگولیٹرز اور معیشت",
        "🚨 Scam Protection": "🚨 دھوکہ دہی سے تحفظ",
    },
    "Kashmiri": {
        "🏦 Basic Banking": "🏦 بنیادی بینکاری",
        "💰 Loans & Credit": "💰 قرضہ تہ کریڈٹ",
        "📱 Digital Banking": "📱 ڈیجیٹل بینکاری",
        "🛡️ Insurance": "🛡️ بیمہ",
        "🏛️ Regulators & Economy": "🏛️ ریگولیٹر تہ معیشت",
        "🚨 Scam Protection": "🚨 دھوکہ تحفظ",
    },
    "Odia": {
        "🏦 Basic Banking": "🏦 ମୂଳ ବ୍ୟାଙ୍କିଙ୍ଗ",
        "💰 Loans & Credit": "💰 ଋଣ ଓ କ୍ରେଡିଟ",
        "📱 Digital Banking": "📱 ଡିଜିଟାଲ ବ୍ୟାଙ୍କିଙ୍ଗ",
        "🛡️ Insurance": "🛡️ ବୀମା",
        "🏛️ Regulators & Economy": "🏛️ ନିୟାମକ ଓ ଅର୍ଥନୀତି",
        "🚨 Scam Protection": "🚨 ଠଗ ସୁରକ୍ଷା",
    },
    "Assamese": {
        "🏦 Basic Banking": "🏦 মূল বেংকিং",
        "💰 Loans & Credit": "💰 ঋণ আৰু ক্ৰেডিট",
        "📱 Digital Banking": "📱 ডিজিটেল বেংকিং",
        "🛡️ Insurance": "🛡️ বীমা",
        "🏛️ Regulators & Economy": "🏛️ নিয়ন্ত্ৰক আৰু অৰ্থনীতি",
        "🚨 Scam Protection": "🚨 স্কেম সুৰক্ষা",
    },
}

import re as _re
import streamlit.components.v1 as _bk_comp

_BK_LANG_BCP47 = {
    "Hindi": "hi-IN", "Bengali": "bn-IN", "Tamil": "ta-IN", "Telugu": "te-IN",
    "Marathi": "mr-IN", "Gujarati": "gu-IN", "Kannada": "kn-IN", "Malayalam": "ml-IN",
    "Punjabi": "pa-IN", "Urdu": "ur-IN", "Odia": "or-IN", "Assamese": "as-IN",
    "Nepali": "ne-IN", "Kashmiri": "ks-IN", "English": "en-IN",
}


def _bk_tts(text: str, lang: str, uid: str):
    """Inline TTS button for a single banking term definition."""
    _lc = _BK_LANG_BCP47.get(lang, "en-IN")
    _safe = text.replace("\\", "").replace("`", "'").replace('"', "'").replace("\n", " ")[:2000]
    _bk_comp.html(f"""<div style="margin:4px 0">
<button id="bk{uid}" onclick="(function(){{
  var b=document.getElementById('bk{uid}');
  if(window['_bk{uid}']){{window.speechSynthesis.cancel();window['_bk{uid}']=false;
    b.innerHTML='🔊';b.style.background='#1e3a5f';b.title='Listen';return;}}
  var u=new SpeechSynthesisUtterance(`{_safe}`);
  u.lang='{_lc}';window['_bk{uid}']=true;
  b.innerHTML='⏹';b.style.background='#7f1d1d';b.title='Stop';
  u.onend=u.onerror=function(){{window['_bk{uid}']=false;
    b.innerHTML='🔊';b.style.background='#1e3a5f';b.title='Listen';}};
  window.speechSynthesis.speak(u);}})()"
title="Listen" style="background:#1e3a5f;color:#7eb8f7;border:1px solid #2563eb;
  border-radius:6px;padding:3px 10px;cursor:pointer;font-size:0.78rem">🔊</button>
<span style="font-size:0.70rem;color:#6b7280;margin-left:6px">Listen · works offline</span>
</div>""", height=38)


def _local_definition(lang: str, term: str) -> str:
    return LOCAL_DEFINITIONS.get(lang, {}).get(term, "")


def _category_label(lang: str, category: str) -> str:
    static = CATEGORY_LABELS.get(lang, {}).get(category)
    if static:
        return static
    if lang.lower() != "english":
        m = _re.match(r'^(\S+\s)', category)
        emoji = m.group(1) if m else ""
        text_part = category[len(emoji):]
        translated = translate_text(text_part, lang, context="banking category name", live=False)
        return f"{emoji}{translated}"
    return category

# ── Offline / Online status banner ───────────────────────────────────────
_local_ai_ready = mode == "offline"
_online_ai_available = mode == "online"

if _local_ai_ready:
    st.caption("🟢 Offline AI ready — definitions and AI details can work without internet.")
elif _online_ai_available:
    st.caption("📘 Offline definitions are ready. Online AI is available only after your permission.")
else:
    st.caption(f"📴 {_bk_t(_t.get('bk_offline_msg', 'Offline mode — definitions work without internet.'))}")

# ── TTS: Listen to Any Text ──────────────────────────────────────────────
with st.expander("🔊 Listen to Any Term (Text-to-Speech)", expanded=False):
    _tts_input = st.text_area(
        "Type or paste any banking term or definition to hear it spoken:",
        height=80,
        placeholder="Example: EMI means Equated Monthly Installment — a fixed amount you pay every month...",
        key="bk_tts_text",
        label_visibility="visible",
    )
    if _tts_input.strip():
        _bk_tts(_tts_input.strip(), _lang, uid="global")
    else:
        st.caption("Type text above and the Listen button will appear. Works 100% offline — no internet needed.")

# ── Search & filters ──────────────────────────────────────────────────────
_sc1, _sc2 = st.columns([3, 1])
with _sc1:
    search = st.text_input("🔍", placeholder=_t.get("search_word_placeholder", "Search any word…"), label_visibility="collapsed")
with _sc2:
    show_ai = st.toggle(f"🤖 {_t.get('ai_details_label', 'AI Details')}", value=False)

allow_online_ai = False
if show_ai and _online_ai_available:
    allow_online_ai = st.toggle("Allow online AI for this explanation", value=False)
    if not allow_online_ai:
        st.info("AI details will stay offline. Start local Gemma/Ollama, or allow online AI for this request.")

all_cats = list(TERMS.keys())
with st.expander(f"📂 {_t.get('filter_categories_label', 'Filter Categories')}", expanded=False):
    _cols = st.columns(3)
    selected_cats = []
    for i, cat in enumerate(all_cats):
        with _cols[i % 3]:
            if st.checkbox(_category_label(_lang, cat), value=True, key=f"cat_{cat}"):
                selected_cats.append(cat)

# ── Build filtered view ───────────────────────────────────────────────────

# Load disk cache into session_state (runs once per language per session)
if _lang != "English" and not st.session_state.get(f"bk_disk_loaded_{_lang}"):
    _disk = _load_bk_cache()
    for _dt, _dv in _disk.get(_lang, {}).items():
        _sk = f"bk_t_{_lang}_{_dt}"
        if not st.session_state.get(_sk) and _dv:
            st.session_state[_sk] = _dv
    for _dt, _dn in _disk.get(f"{_lang}_names", {}).items():
        _snk = f"bk_tn_{_lang}_{_dt}"
        if not st.session_state.get(_snk) and _dn:
            st.session_state[_snk] = _dn
    st.session_state[f"bk_disk_loaded_{_lang}"] = True

search_lower = search.strip().lower()

results = {}
for cat, terms_dict in TERMS.items():
    if cat not in selected_cats:
        continue
    matched = {}
    for term, defn in terms_dict.items():
        # Search against the selected-language definition first, then English.
        _disp = (
            _local_definition(_lang, term)
            or st.session_state.get(f"bk_t_{_lang}_{term}")
            or defn
        )
        if not search_lower or search_lower in term.lower() or search_lower in _disp.lower() or search_lower in defn.lower():
            matched[term] = defn
    if matched:
        results[cat] = matched


def _translate_terms_for_language(lang: str, items: list[tuple[str, str]], allow_online: bool = False) -> bool:
    """Translate term names + definitions for any language."""
    if lang == "English" or not items or mode == "limited":
        return False

    _saved_any = False
    _items_dict = dict(items)

    # ── Online mode: one batch call (fast, Google API handles format reliably) ──
    if allow_online:
        _batch_str = "\n".join(f"{t}|||{d}" for t, d in items)
        _tr_prompt = (
            f"Translate each banking term and definition to {lang}.\n"
            f"Return exactly {len(items)} lines using this format:\n"
            "ENGLISH_TERM|||TRANSLATED_TERM|||TRANSLATED_DEFINITION\n\n"
            "- ENGLISH_TERM: copy exactly as given\n"
            f"- TRANSLATED_TERM: term name in {lang}; keep acronyms (EMI, ATM, UPI, KYC, OTP, IFSC, NACH, CIBIL, LIC, NPA, RBI, NBFC, RTGS, NEFT, IMPS) unchanged\n"
            f"- TRANSLATED_DEFINITION: definition in {lang}, simple words, keep ₹ amounts and numbers unchanged\n"
            "No extra lines, no numbering.\n\n"
            + _batch_str
        )
        _tr_resp = generate(_tr_prompt, language="English", allow_online=True)
        if not _tr_resp.startswith("⚠️"):
            for line in _tr_resp.strip().split("\n"):
                if "|||" not in line:
                    continue
                parts = line.split("|||", 2)
                if len(parts) >= 3:
                    term, term_name_tr, translated = parts[0].strip(), parts[1].strip(), parts[2].strip()
                elif len(parts) == 2:
                    term, term_name_tr, translated = parts[0].strip(), None, parts[1].strip()
                else:
                    continue
                original = _items_dict.get(term)
                if translated and original and translated != original:
                    st.session_state[f"bk_t_{lang}_{term}"] = translated
                    _saved_any = True
                if term_name_tr and term_name_tr != term:
                    st.session_state[f"bk_tn_{lang}_{term}"] = term_name_tr

    # ── Per-term fallback: direct generate() — works for Ollama and missed online terms ──
    # Bypasses translate_text() which rejects valid Ollama output due to strict validation
    # (e.g. newline in preamble like "Here is the translation:\n\n..." kills short-text checks)

    for term, defn in items:
        if st.session_state.get(f"bk_t_{lang}_{term}"):
            continue
        defn_result = generate(
            f"Translate to {lang}. Return ONLY the translation, no explanation:\n\n{defn}",
            language=lang, allow_online=allow_online,
        ).strip()
        if defn_result and not defn_result.startswith("⚠️") and defn_result != defn and len(defn_result) > 10:
            st.session_state[f"bk_t_{lang}_{term}"] = defn_result
            _saved_any = True

        if not st.session_state.get(f"bk_tn_{lang}_{term}"):
            name_result = generate(
                f"Translate this banking term to {lang}. Return ONLY the {lang} translation:\n\n{term}",
                language=lang, allow_online=allow_online,
            ).strip()
            if name_result and not name_result.startswith("⚠️") and name_result != term and len(name_result) > 1:
                st.session_state[f"bk_tn_{lang}_{term}"] = name_result

    if _saved_any:
        _disk = _load_bk_cache()
        _disk.setdefault(lang, {})
        _disk.setdefault(f"{lang}_names", {})
        for term, defn in items:
            tr_defn = st.session_state.get(f"bk_t_{lang}_{term}")
            if tr_defn and tr_defn != defn:
                _disk[lang][term] = tr_defn
            tr_name = st.session_state.get(f"bk_tn_{lang}_{term}")
            if tr_name and tr_name != term:
                _disk[f"{lang}_names"][term] = tr_name
        _save_bk_cache(_disk)

    return _saved_any


# ── Stats ─────────────────────────────────────────────────────────────────
total_terms = sum(len(v) for v in results.values())
if search_lower:
    st.info(f"**{total_terms}** {_t.get('bk_terms_found_suffix', 'terms found for')} **'{search}'**")
else:
    all_total = sum(len(v) for v in TERMS.values())
    st.success(f"**{all_total}** {_bk_t(_t.get('bk_stats_suffix', 'banking & loan words — simple language, no internet needed — understand every word before you sign'))}")

# ── Display content immediately (English or cached translation) ────────────────
_words_lbl    = _bk_t(_t.get("bk_words_label", "words"))
_expand_lbl   = _bk_t(_t.get("bk_click_expand", "click to expand"))
_deeper_btn   = _bk_t(_t.get("bk_deeper_btn", "Deeper explanation (Gemma 4)"))
_no_terms_msg = _bk_t(_t.get("bk_no_terms_msg", "No terms found. Try a different word."))

if not results:
    st.warning(_no_terms_msg)
else:
    # for cat, terms_dict in results.items():
    #     term_count = len(terms_dict)
    #     with st.expander(
    #         f"{_category_label(_lang, cat)}  ·  {term_count} {_words_lbl}  —  {_expand_lbl}",
    #         expanded=bool(search_lower),
    #     ):
    for cat, terms_dict in results.items():
        term_count = len(terms_dict)
        with st.expander(
            f"{_category_label(_lang, cat)}  ·  {term_count} {_words_lbl}  —  {_expand_lbl}",
            expanded=bool(search_lower),
        ):
            _cat_desc_key = f"bk_cat_desc_{_lang}_{cat}"
            _display_cat_desc = st.session_state.get(_cat_desc_key)
            if _display_cat_desc:
                st.markdown(f"*{_display_cat_desc}*")
                st.divider()
            elif _lang != "English":
                # Quick live translation for the sub-text if it's not in the cache yet
                _quick_desc = translate_text(cat, _lang, context="banking category description", live=(mode != "limited"))
                st.markdown(f"*{_quick_desc}*")
                st.divider()
            cols = st.columns(2)
            col_idx = 0
            for term, defn in terms_dict.items():
                with cols[col_idx % 2]:
                    _display_defn = (
                        _local_definition(_lang, term)
                        or st.session_state.get(f"bk_t_{_lang}_{term}")
                        or defn
                    )
                    _term_display = st.session_state.get(f"bk_tn_{_lang}_{term}", term)
                    with st.expander(f"› {_term_display}", expanded=bool(search_lower)):
                        st.markdown(_display_defn)
                        if show_ai:
                            _ai_btn_icon = "🧠" if _local_ai_ready else "🌐"
                            if st.button(
                                f"{_ai_btn_icon} {_deeper_btn}",
                                key=f"ai_{cat}_{term}",
                                use_container_width=True,
                            ):
                                with st.spinner("Gemma 4…"):
                                    ai_response = generate(
                                        f"Explain '{term}' in very simple language with a real-life example "
                                        f"for a village person who has never taken a bank loan. Use ₹ amounts.",
                                        language=_lang,
                                        allow_online=allow_online_ai,
                                    )
                                st.session_state[f"ai_resp_{cat}_{term}"] = ai_response
                            if st.session_state.get(f"ai_resp_{cat}_{term}"):
                                _saved_ai = st.session_state[f"ai_resp_{cat}_{term}"]
                                st.markdown("---")
                                st.markdown(_saved_ai)
                                _bk_tts(_saved_ai, _lang, uid=f"ai{abs(hash(cat+term)) % 99991}")
                col_idx += 1

# ── Progressive translation — one batch per rerun, content already visible ────
if _lang != "English" and mode != "limited":
    _all_pending = [
        (term, defn)
        for terms_dict in TERMS.values()
        for term, defn in terms_dict.items()
        if not _local_definition(_lang, term)
        and not st.session_state.get(f"bk_t_{_lang}_{term}")
    ]
    if _all_pending:
        _total_all = sum(len(v) for v in TERMS.values())
        _done_count = _total_all - len(_all_pending)
        # Online (Google API): 25 per batch (1 fast call). Offline (Ollama): 5 per batch (10 calls ~30s)
        _batch_size = 25 if mode == "online" else 5
        _next_batch = _all_pending[:_batch_size]
        st.caption(f"Translating to {_lang}: {_done_count}/{_total_all} terms ready — {len(_all_pending)} remaining")
        with st.spinner(f"Translating {len(_next_batch)} terms to {_lang}… ({_done_count}/{_total_all} done)"):
            if _translate_terms_for_language(_lang, _next_batch, allow_online=(mode == "online")):
                st.rerun()
elif _lang != "English" and mode == "limited":
    st.warning(
        "AI is not available — showing English definitions. "
        "Start Ollama or add a Google API key to enable automatic translation."
    )
