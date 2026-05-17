"""India-specific product configuration for RuralFinance AI.

The app is now scoped to Indian borrowers. Keep product geography, language
selection, currency, and regulatory references centralized here so pages do not
reintroduce global assumptions.
"""

INDIA_COUNTRY_LABEL = "India"
INDIA_COUNTRY_BADGE = "IN India"
INDIA_CURRENCY_SYMBOL = "₹"

# India's 22 Eighth Schedule languages. English is kept separately as the
# product fallback language for setup, demos, and unsupported translation keys.
INDIA_OFFICIAL_LANGUAGES = [
    "Assamese",
    "Bengali",
    "Bodo",
    "Dogri",
    "Gujarati",
    "Hindi",
    "Kannada",
    "Kashmiri",
    "Konkani",
    "Maithili",
    "Malayalam",
    "Manipuri",
    "Marathi",
    "Nepali",
    "Odia",
    "Punjabi",
    "Sanskrit",
    "Santali",
    "Sindhi",
    "Tamil",
    "Telugu",
    "Urdu",
]

SUPPORTED_APP_LANGUAGES = ["English"] + INDIA_OFFICIAL_LANGUAGES
SUPPORTED_LANGUAGE_COPY = "supporting India's 22 official languages"

INDIA_FINANCE_CONTEXT = (
    "Indian banks, NBFCs, cooperative banks, microfinance institutions, "
    "digital loan apps, Aadhaar/PAN/KYC, UPI auto-debit, NACH/ECS, GST, "
    "RBI borrower awareness, RBI Ombudsman, agriculture credit, SHG/JLG loans, "
    "Kisan Credit Card, and rural/semi-urban Indian borrowers"
)

INDIA_RISK_TERMS = [
    "processing fee",
    "documentation fee",
    "GST",
    "stamp duty",
    "insurance premium",
    "credit shield",
    "EMI bounce charge",
    "NACH failure charge",
    "ECS failure charge",
    "penal interest",
    "foreclosure charge",
    "prepayment charge",
    "UPI auto-debit",
    "Aadhaar consent",
    "PAN/KYC misuse",
    "SMS/contact access",
    "recovery agent clause",
    "RBI Ombudsman",
]


def normalize_app_language(language: str | None) -> str:
    """Return a supported India-scope language, defaulting to English."""
    if language in SUPPORTED_APP_LANGUAGES:
        return language
    return "English"

