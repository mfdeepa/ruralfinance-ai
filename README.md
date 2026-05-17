# RuralFinance AI

**A loan safety assistant for Indian borrowers — built with Gemma 4, runs offline.**

> No borrower should sign a document they don't understand.

---

## What this is

I built this for the Gemma 4 Hackathon (Safety & Trust track). The idea came from watching people in my family sign loan documents they couldn't read — a lender explains in 2 minutes, points to the signature line, and moves on. The document is 6–10 pages of legal English. The borrower speaks Hindi or Marathi. Nobody adds up what the loan actually costs.

RuralFinance AI sits between a borrower and a loan document at the moment before signing. You upload the paper — a phone photo, a PDF, a Word file — and it tells you in plain language what you're agreeing to, what the hidden costs are, and what to ask before signing.

The whole thing runs offline. No data leaves your device. Works in 23 Indian languages.

---

## What it actually does

**Scan Loan Document** — upload a photo, PDF, or Word file. EasyOCR handles angled phone shots, rubber stamps over text, and low-quality scans. The text gets normalized and cleaned before anything else runs.

**Understand Document** — a 12-category rules engine checks for processing fees, insurance deductions, penal interest, NACH/ECS mandates, prepayment penalties, arbitration clauses, and 80+ other risk signals — all deterministic, no AI. Then Gemma 4 explains what was found in simple language at a Class 8 reading level, grounded in RBI circulars via a local ChromaDB vector store.

**Loan Safety Score** — a 0–100 score computed from the risk flags. Fully deterministic. Gemma explains the score. The AI never touches the math.

**Calculate EMI** — flat-rate vs reducing-balance comparison, total repayment, interest burden, savings growth. All pure Python math. No AI involved here at all.

**Understand Banking Words** — plain-language definitions of banking terms, penalty clauses, arbitration, SARFAESI, etc.

**Emergency Help** — India-specific guidance for loan harassment, recovery agent pressure, RBI complaint process, and borrower rights.

**Sign In / Login** — simple name + language setup. No password, no account required.

---

## How it's built

The app is a Streamlit multi-page app. Each page is thin — just UI. All logic lives in the services layer.

```
ruralfinance-ai/
  Home.py                         — dashboard
  pages/
    1_Login.py                    — sign in / setup
    2_Document_Scanner.py         — upload + OCR
    3_Calculator.py               — EMI tools
    5_Banking_Knowledge.py        — term definitions
    6_Understand_Document.py      — AI analysis
    8_Emergency_Help.py           — borrower rights
  services/
    ai_service.py                 — Gemma 4 inference cascade
    calculator_service.py         — all EMI / repayment math
    ocr_service.py                — EasyOCR + pdfplumber + python-docx
    rag_service.py                — ChromaDB local vector store
    localization_service.py       — batch translation cache
  utils/
    styles.py                     — nav drawer, CSS, shared UI
    translations.py               — multilingual UI strings
    india_config.py               — India-only config
  data/
    knowledge_base/               — RBI circulars, borrower rights, SARFAESI
```

### AI inference cascade

The app picks the best available model automatically:

1. **Online** — `gemma-4-9b-it` via Google AI API. Fastest, full capability including vision.
2. **Offline (Ollama)** — `gemma3:2b` running locally (~1.5 GB RAM). Recommended for offline use.
3. **Offline (HuggingFace)** — `google/gemma-4-E2B-it` with 4-bit NF4 quantization via bitsandbytes. Under 2 GB RAM.
4. **Limited mode** — no AI at all. EMI calculator, risk rules, and banking definitions still work.

### The most important design decision

Gemma never computes a number. Every rupee figure — EMI, total repayment, processing fee total, risk score — comes from deterministic Python. Gemma only explains what those numbers mean. Early in testing the model confidently produced wrong EMI figures, so I separated the two completely.

### RAG

A local ChromaDB store indexes RBI Fair Practices Code, SARFAESI Act provisions, borrower rights, and common loan term definitions. Every Gemma explanation call retrieves the top-k relevant chunks first and passes them as context. This keeps the output anchored to actual regulations instead of the model guessing.

### Multilingual UI

Batch JSON translation — one API call per page, all missing strings at once, cached to disk. After the first visit per language, translation overhead is zero. Supports all 23 Indian official languages.

---

## Honest about the latency

When the app runs locally (Ollama or HuggingFace), document analysis takes 20–30 seconds. That's a full language model running on your device, with RAG retrieval, with a multilingual prompt — no cloud, no data sent anywhere.

The rules engine output and EMI calculations appear instantly. The wait is only for the AI explanation step. A borrower who is about to sign a ₹3 lakh loan will wait 25 seconds for a real analysis. The alternative is signing without understanding anything.

On the Google AI API (online mode), the same analysis takes 3–5 seconds. Streaming responses are on the roadmap to make the local wait feel shorter.

---

## Setup

**Install dependencies:**

```bash
pip install -r requirements.txt
```

**For offline AI (recommended):**

```bash
# Install Ollama from https://ollama.com
ollama pull gemma3:2b
```

**For online AI (optional):**

Create a `.env` file:

```
GOOGLE_API_KEY=your_key_here
```

**Run:**

```bash
streamlit run Home.py
```

Open `http://localhost:8501`

---

## Requirements

- Python 3.10+
- ~2 GB free RAM for offline Ollama mode
- ~4 GB free RAM for offline HuggingFace mode
- Internet optional — core tools work fully offline

---

## Privacy

- No account required
- Uploaded documents are processed in the active session only
- Offline mode sends nothing to external servers
- `.env` and model weights should stay out of version control

---

## Track

Gemma 4 Hackathon 2025 — Safety & Trust
