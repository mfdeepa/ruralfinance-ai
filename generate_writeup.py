from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

section = doc.sections[0]
section.top_margin    = Inches(0.9)
section.bottom_margin = Inches(0.9)
section.left_margin   = Inches(1.0)
section.right_margin  = Inches(1.0)


def ps(para, before=0, after=5):
    para.paragraph_format.space_before = Pt(before)
    para.paragraph_format.space_after  = Pt(after)


def heading(text, level=1, color=(0x16, 0x65, 0x34)):
    h = doc.add_heading(text, level=level)
    h.alignment = WD_ALIGN_PARAGRAPH.LEFT
    ps(h, before=10 if level == 1 else 6, after=3)
    for run in h.runs:
        run.font.color.rgb = RGBColor(*color)
    return h


def body(text, size=11):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    ps(p)
    return p


def bullet(bold_text, rest_text, size=11):
    p = doc.add_paragraph(style="List Bullet")
    r1 = p.add_run(bold_text)
    r1.bold = True
    r1.font.size = Pt(size)
    r2 = p.add_run(rest_text)
    r2.font.size = Pt(size)
    ps(p, before=0, after=2)
    return p


def code_line(text, size=10):
    p = doc.add_paragraph()
    r = p.add_run("     " + text)
    r.font.size = Pt(size)
    r.font.color.rgb = RGBColor(0x1e, 0x3a, 0x5f)
    ps(p, before=0, after=1)
    return p


# ════════════════════════════════════════════════════════════
# TITLE BLOCK
# ════════════════════════════════════════════════════════════
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
tr = t.add_run("Before You Sign")
tr.font.size = Pt(22)
tr.font.bold = True
tr.font.color.rgb = RGBColor(0x16, 0x65, 0x34)
ps(t, before=0, after=3)

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sr = sub.add_run(
    "RuralFinance AI — A Gemma 4-Powered Loan Safety Assistant for India's Rural Borrowers"
)
sr.font.size = Pt(12)
sr.font.italic = True
sr.font.color.rgb = RGBColor(0x37, 0x47, 0x51)
ps(sub, before=0, after=3)

trk = doc.add_paragraph()
trk.alignment = WD_ALIGN_PARAGRAPH.CENTER
tkr = trk.add_run("Track: Safety & Trust  |  Gemma 4 Hackathon 2025")
tkr.font.size = Pt(10)
tkr.font.bold = True
tkr.font.color.rgb = RGBColor(0x15, 0x59, 0x24)
ps(trk, before=0, after=12)


# ════════════════════════════════════════════════════════════
# A. PROBLEM STATEMENT
# ════════════════════════════════════════════════════════════
heading("A. Problem Statement")

body(
    "I grew up watching people in my family sign loan documents they did not fully understand. "
    "A lender explains the terms in two minutes, points to the signature line, and that is it. "
    "India has over 500 million active loan accounts — farmers, daily-wage workers, small shop "
    "owners — and almost none of them have a way to independently verify what they just agreed to. "
    "The document is 6 to 10 pages of legal English. The borrower speaks Hindi, Tamil, or Odia. "
    "And the lender is already moving on to the next customer."
)

body(
    "The specific problems I kept seeing come up:"
)

for b, r in [
    ("Hidden charges that are never totalled",
     " — processing fees, GST, mandatory insurance, NACH/ECS mandates, and penalty clauses "
     "are each disclosed somewhere in the document, but nobody adds them up and shows the "
     "borrower what they are actually paying over the life of the loan."),
    ("Legal language designed for lawyers, not borrowers",
     " — arbitration clauses, acceleration clauses, and guarantor liability terms are written "
     "in a way that even educated borrowers misread. A rural farmer has no chance."),
    ("No internet when it matters most",
     " — the moment before signing a loan document in a bank branch or village MFI office "
     "is exactly when you cannot count on a stable connection. Cloud-only tools are useless here."),
    ("Flat-rate fraud disguised as reducing-balance",
     " — predatory lenders quote a flat 12% interest rate that is actually 21-22% effective. "
     "Most borrowers have no way to catch this without doing the math themselves."),
    ("No independent EMI verification",
     " — the borrower is quoted an EMI and signs. There is no quick way to check if that "
     "number is correct, inflated, or hiding a balloon payment."),
]:
    bullet(b, r)

doc.add_paragraph()


# ════════════════════════════════════════════════════════════
# B. THE SOLUTION
# ════════════════════════════════════════════════════════════
heading("B. The Solution")

body(
    "RuralFinance AI is a loan safety assistant that sits between a borrower and a document "
    "at the exact moment before they sign. You upload the loan paper — a photo from your phone, "
    "a PDF, or a scanned image — and the app tells you in plain language what you are agreeing to, "
    "what the hidden costs are, and what questions to ask before signing."
)

body(
    "The whole thing runs offline. No data leaves your device. It works in 23 Indian languages. "
    "And the AI never produces a number — every rupee figure comes from deterministic math, "
    "not a language model guessing."
)

for b, r in [
    ("Offline-first AI",
     " — the full risk analysis works without internet using a local Ollama model or a "
     "quantized HuggingFace model. The app degrades gracefully: online Gemma 4 when available, "
     "local model when not, rule-based analysis when neither is running."),
    ("Document scanner with OCR",
     " — works with phone photos, PDFs, and Word files. EasyOCR handles angled shots, "
     "low-quality images, and rubber-stamped text that breaks standard PDF parsers."),
    ("12-category risk engine",
     " — deterministic rules catch processing fees, insurance deductions, penal interest, "
     "prepayment penalties, NACH mandates, and 80+ other signals before Gemma even runs."),
    ("Loan Safety Score",
     " — a 0-100 score computed from the risk flags, fully deterministic. Gemma explains "
     "the score in the borrower's language. The AI never touches the calculation itself."),
    ("Explainable outputs",
     " — every flag in the report is labeled: rule-based detection or Gemma explanation. "
     "The borrower always knows where each finding came from."),
    ("23 languages, disk-cached",
     " — UI translations are generated once per language via a batch JSON prompt, saved to disk, "
     "and reused. After the first visit, there is zero translation latency."),
]:
    bullet(b, r)

doc.add_paragraph()


# ════════════════════════════════════════════════════════════
# C. HOW GEMMA 4 IS USED
# ════════════════════════════════════════════════════════════
heading("C. How Gemma 4 Is Used")

body(
    "Gemma 4 is not a chatbot wrapper here. It handles exactly three things: explaining what "
    "the numbers mean, translating the UI into regional languages, and reading document images "
    "that OCR cannot handle. Everything else — risk detection, scoring, EMI math — is "
    "deterministic Python."
)

heading("Deployment cascade", level=2, color=(0x15, 0x59, 0x24))
body(
    "Online: gemma-4-9b-it via Google AI API — fastest, full capability. "
    "Offline primary: gemma3:2b via Ollama, about 1.5 GB RAM, runs on a mid-range laptop "
    "or desktop connected to a phone hotspot. "
    "Offline fallback: google/gemma-4-E2B-it via HuggingFace Transformers with 4-bit NF4 "
    "quantization through bitsandbytes — brings the model under 2 GB, slow but functional "
    "on edge hardware. Limited mode: no AI at all, but the calculators, risk rules, and "
    "EMI math all still work. The cascade picks the best available option automatically."
)

heading("Prompt engineering", level=2, color=(0x15, 0x59, 0x24))
body(
    "Every Gemma call starts with a language-enforcement header: "
    "\"IMPORTANT: You must respond entirely in {language}. Do not use English.\" "
    "This is prepended before any user content so the model locks into regional-language "
    "output from the first token. For batch UI translation, I send all missing strings "
    "for a page in one JSON-structured prompt. The model returns a JSON object with the "
    "same keys and translated values. I validate each value (reject anything with a newline "
    "or over 400 characters), cache it to disk, and apply it on the next page render. "
    "This cut translation latency from 30+ seconds per page to a single extra rerun "
    "on first visit."
)

heading("RAG — retrieval-augmented generation", level=2, color=(0x15, 0x59, 0x24))
body(
    "I built a local ChromaDB vector store with RBI circulars, SARFAESI Act provisions, "
    "Fair Practices Code guidelines, and common loan term definitions. Before Gemma generates "
    "any explanation, the relevant chunks are retrieved and passed as context. This matters "
    "a lot for accuracy — a language model without grounding will confidently state wrong "
    "regulatory facts. The retrieval step keeps the output anchored to actual RBI rules."
)

heading("Financial safety guardrails", level=2, color=(0x15, 0x59, 0x24))
body(
    "The most important decision in the whole project: Gemma never computes a number. "
    "EMI figures, total repayment, processing fee totals, risk scores — all of it comes "
    "from deterministic Python functions in calculator_service.py. Gemma receives the "
    "results and explains them. It is never asked to derive them. This was not obvious "
    "at the start, but after seeing a language model confidently state a wrong EMI "
    "during early testing, I separated the two completely. Every numeric output in the UI "
    "is labeled: rule-based or AI-generated. The borrower always knows which is which."
)

heading("Four Gemma call types in the app", level=2, color=(0x15, 0x59, 0x24))
for b, r in [
    ("Before You Sign report",
     " — receives the flagged clauses and rule-based findings, generates a plain-language "
     "explanation at a Class 8 reading level with a specific action at the end of each point."),
    ("Multimodal vision",
     " — generate_with_image() reads document photos directly via Gemma 4's vision capability, "
     "catching handwritten annotations and rubber-stamped conditions that OCR misses entirely."),
    ("Batch UI translation",
     " — one JSON prompt per page, all 23 languages, written to disk on first run."),
    ("Recovery notice analysis",
     " — reads threatening recovery letters, checks them against RBI Fair Practices Code, "
     "flags illegal pressure tactics, and drafts a borrower response."),
]:
    bullet(b, r)

doc.add_paragraph()


# ════════════════════════════════════════════════════════════
# D. TECHNICAL ARCHITECTURE
# ════════════════════════════════════════════════════════════
heading("D. Technical Architecture")

body("Three layers, deliberately kept thin:")
for b, r in [
    ("Frontend",
     " — Streamlit multi-page app. Each page does UI rendering only. No business logic lives here."),
    ("Services layer",
     " — ai_service.py manages the inference cascade; ocr_service.py handles extraction; "
     "rag_service.py manages ChromaDB retrieval; localization_service.py handles cached translation."),
    ("Data layer",
     " — ChromaDB local vector store, per-page disk-cached JSON translation files. "
     "No cloud dependency. No database server. Everything runs from the file system."),
]:
    bullet(b, r)

doc.add_paragraph()
body("What happens when a document is uploaded:")
for line in [
    "User uploads image / PDF / Word / pastes text",
    "     ↓",
    "OCR + extraction  [EasyOCR → pdfplumber → python-docx]",
    "     ↓",
    "Text normalization  [strip artifacts, fix line breaks, reroute image-only PDFs]",
    "     ↓",
    "Rules engine  [12 risk categories, 80+ keyword signals — fully deterministic]",
    "     ↓",
    "Loan Safety Score  [weighted 0–100 — no AI involved]",
    "     ↓",
    "RAG retrieval  [ChromaDB local — RBI rules, borrower rights, SARFAESI provisions]",
    "     ↓",
    "Gemma 4 explanation  [language-aware, grounded in retrieved context]",
    "     ↓",
    "Before You Sign Report  [downloadable Word doc, every finding labeled by source]",
]:
    code_line(line)

doc.add_paragraph()


# ════════════════════════════════════════════════════════════
# E. CHALLENGES FACED
# ════════════════════════════════════════════════════════════
heading("E. Challenges Faced")

for b, r in [
    ("Local inference takes 20–30 seconds — and that is the point",
     " — Running a full language model locally on a laptop or mid-range device, "
     "with no data leaving the device, with RAG retrieval, with a multilingual prompt, "
     "takes 20 to 30 seconds. Early on I thought of this as a problem to solve. "
     "Then I reframed it: a borrower who is about to sign a document that will cost them "
     "₹2–5 lakh over three years will absolutely wait 25 seconds for a thorough analysis. "
     "The alternative is signing without understanding anything. The rules engine output and "
     "EMI calculations appear instantly — the wait is only for the AI explanation step. "
     "I added a progress indicator so the borrower knows something real is happening. "
     "On the online Gemma 4 API, the same analysis returns in 3–5 seconds. "
     "Streaming responses is on the roadmap to make the local wait feel shorter."),
    ("Running a language model under 2 GB RAM",
     " — The HuggingFace Gemma model at full precision is 9+ GB. "
     "I applied 4-bit NF4 quantization via bitsandbytes with accelerate's device_map='auto'. "
     "This brings it under 2 GB. Quality drops slightly but the model still produces "
     "coherent, useful explanations. Ollama's gemma3:2b is the better offline path "
     "for devices with 4 GB RAM — 1.5 GB, faster, easier to set up."),
    ("OCR on real Indian loan documents",
     " — Standard OCR pipelines assume clean scans. Real loan documents from rural branches "
     "have rubber stamps over text, handwritten additions in margins, skewed phone photos, "
     "and mixed scripts. I built a normalization layer that strips OCR noise, detects "
     "image-only PDFs and reroutes them to EasyOCR, and repairs broken hyphenation "
     "across line breaks before the text reaches the rules engine."),
    ("Stopping the model from making up numbers",
     " — Early testing showed the model confidently producing wrong EMI figures when asked "
     "to explain a document. The fix was complete separation: Gemma never receives a "
     "calculation task. Every number in the output comes from deterministic Python. "
     "The model only sees the results to explain in plain language."),
    ("Multilingual UI without per-string API calls",
     " — Translating each label individually on page load would add 30+ seconds per language. "
     "The batch JSON pattern — one API call per page, all missing keys at once, cached to disk "
     "— reduced this to a single extra rerun on first visit. Subsequent visits are instant."),
    ("Writing for someone who may not be financially literate",
     " — Prompts explicitly instruct Gemma to write at a Class 8 reading level, avoid "
     "jargon, and end every explanation with a specific action the borrower can take "
     "(e.g. 'Ask your lender: Is this insurance deduction mandatory or optional?'). "
     "Getting this right took more iteration than any other part of the prompt design."),
]:
    bullet(b, r)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)

doc.add_paragraph()


# ════════════════════════════════════════════════════════════
# F. WHY THESE CHOICES WERE CORRECT
# ════════════════════════════════════════════════════════════
heading("F. Why These Technical Choices Were Correct")

for b, r in [
    ("Local inference, even with the latency",
     " — A cloud-only tool that is fast in a city is useless in a village with "
     "2G connectivity at the moment of signing. The 20-30 second local wait is a "
     "trade-off I made deliberately. The borrower gets a thorough, private analysis "
     "that works with zero internet. That is worth the wait."),
    ("Gemma 4 specifically",
     " — Gemma 4 is multilingual, multimodal, small enough to run at the edge, and "
     "free to deploy. I could not find another openly available model that hits all "
     "four of those requirements for an India-specific offline borrower tool. "
     "The vision capability for reading document photos is particularly important — "
     "most loan documents in rural India are not digital PDFs."),
    ("Deterministic rules engine before AI",
     " — The rules engine catches hidden charges reliably, every single time, "
     "with no hallucination risk. Gemma then explains what the rules found. "
     "This ordering — deterministic first, AI second — is the right architecture "
     "for a financial safety tool. The borrower can trust the numbers because "
     "the numbers never came from a language model."),
    ("RAG over pure generation",
     " — Grounding Gemma's output in actual RBI circulars and borrower rights "
     "documentation makes a real difference in accuracy. Without it, the model "
     "produces plausible-sounding but sometimes incorrect regulatory claims. "
     "With it, the explanations stay anchored to what the RBI actually says."),
    ("Offline-first architecture",
     " — Connectivity is not a given in rural India. The cascade — online API → "
     "Ollama → quantized local model → limited mode — ensures some level of "
     "protection is always available, even if it degrades as connectivity drops."),
]:
    bullet(b, r)

doc.add_paragraph()


# ════════════════════════════════════════════════════════════
# G. FUTURE SCOPE
# ════════════════════════════════════════════════════════════
heading("G. Future Scope")

body(
    "The app right now focuses on the moment before signing. There is a longer journey "
    "a borrower goes through — before deciding, while repaying, and after things go wrong. "
    "Each of these is a place where RuralFinance AI could help:"
)

for b, r in [
    ("Streaming responses for local inference",
     " — The 20-30 second wait on local models would feel much shorter if the explanation "
     "appeared word by word as the model generates it, instead of all at once at the end. "
     "Streamlit's streaming support makes this straightforward to add."),
    ("Voice interface in regional languages",
     " — Text-to-speech and speech-to-text in Hindi, Tamil, Telugu, and other major languages "
     "would open the app to borrowers who are not comfortable reading on a screen. "
     "This is the single biggest accessibility gap right now."),
    ("Fine-tuned fraud detection",
     " — Train Gemma on a labeled corpus of predatory Indian loan agreements to catch "
     "fraud patterns that the current rules engine does not cover. The rules are good "
     "for known patterns; a fine-tuned model would generalize better to new tactics."),
    ("Government scheme matching",
     " — PM-Kisan, PMJDY, Mudra Loan, and Kisan Credit Card eligibility varies by state, "
     "crop, and income. An advisor that checks which formal credit schemes a borrower "
     "qualifies for could reduce dependence on moneylenders significantly."),
    ("WhatsApp interface",
     " — Most rural borrowers are already on WhatsApp daily. Removing the Streamlit app "
     "entirely and letting them send a document photo to a WhatsApp number would "
     "dramatically lower the barrier to use."),
    ("Post-signing monitoring",
     " — Alerts for EMI changes, floating rate resets, and unexpected NACH debits "
     "after the loan is active. The borrower's protection should not stop at signing."),
]:
    bullet(b, r)

doc.add_paragraph()

# ── Close ─────────────────────────────────────────────────────────────────────
body(
    "No borrower should sign a document they do not understand. That is simple to say "
    "and hard to solve — because the people who need help the most are the ones with "
    "the least access to lawyers, financial advisors, or stable internet. "
    "RuralFinance AI is my attempt to close that gap with tools that actually work "
    "in the conditions those borrowers face: offline, in their language, on a device "
    "they already own, with AI that is honest about what it knows and what it does not."
)

doc.add_paragraph()

footer_p = doc.add_paragraph()
footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
fr = footer_p.add_run(
    "RuralFinance AI  |  Gemma 4 Hackathon 2025  |  Safety & Trust Track"
)
fr.font.size = Pt(9)
fr.font.color.rgb = RGBColor(0x9c, 0xa3, 0xaf)
fr.font.italic = True

out = r"c:\Users\deepa\OneDrive\Desktop\gemma4_hackathon\ruralfinance-ai\RuralFinance_AI_Kaggle_Writeup.docx"
doc.save(out)
print("Saved:", out)
