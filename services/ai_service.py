"""
AI Service — RuralFinance AI
Inference priority cascade:
  1. Online  → Gemma 4 via Google AI API  (internet + API key)
  2. Offline → Ollama local  (gemma3:2b ~1.5 GB — run: ollama pull gemma3:2b)
  3. Offline → HuggingFace local  (9.7 GB legacy — high RAM)
  4. Limited → No AI  (calculators + knowledge base still work)

Extra capabilities (online only):
  • generate_with_image()   — Gemma 4 multimodal vision
  • generate_with_tools()   — Gemma 4 structured function calling
"""
import os
import socket
import requests as _requests
from dotenv import load_dotenv

load_dotenv()

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

GOOGLE_API_KEY   = os.getenv("GOOGLE_API_KEY", "")
MODEL_ONLINE     = os.getenv("GEMMA_MODEL_ONLINE", "gemma-4-9b-it")
MODEL_OFFLINE_HF = os.getenv("HF_MODEL", "google/gemma-4-E2B-it")
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL", "gemma3:2b")
OLLAMA_HOST      = os.getenv("OLLAMA_HOST", "http://localhost:11434")
HF_TOKEN         = os.getenv("HF_TOKEN", "")

_env_cache = os.getenv("HF_CACHE_DIR", "")
HF_CACHE_DIR = _env_cache if (_env_cache and os.path.isabs(_env_cache)) else os.path.join(_ROOT, "models")

_PLACEHOLDER_KEY = "your_google_api_key_here"
_hf_pipe = None


# ── Availability checks ────────────────────────────────────────────────────────

def _is_internet_available() -> bool:
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except Exception:
        return False


def _is_ollama_available() -> bool:
    """Ollama running locally with any Gemma model loaded."""
    try:
        resp = _requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
        if resp.status_code == 200:
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            return any("gemma" in m.lower() for m in models)
        return False
    except Exception:
        return False


def _snapshot_path() -> str:
    try:
        folder = "models--" + MODEL_OFFLINE_HF.replace("/", "--")
        snap_root = os.path.join(HF_CACHE_DIR, folder, "snapshots")
        if not os.path.isdir(snap_root):
            return ""
        for entry in os.listdir(snap_root):
            full = os.path.join(snap_root, entry)
            if os.path.isdir(full):
                return full
        return ""
    except Exception:
        return ""


def _is_local_gemma4_available() -> bool:
    try:
        snap = _snapshot_path()
        if not snap:
            return False
        return any(f.endswith(".safetensors") for f in os.listdir(snap))
    except Exception:
        return False


# ── Mode detection ─────────────────────────────────────────────────────────────

def detect_mode() -> str:
    api_key = os.getenv("GOOGLE_API_KEY", GOOGLE_API_KEY)
    if api_key == _PLACEHOLDER_KEY:
        api_key = ""
    if api_key and _is_internet_available():
        return "online"
    if _is_ollama_available():
        return "offline"
    if _is_local_gemma4_available():
        return "offline"
    return "limited"


def get_status() -> dict:
    api_key = os.getenv("GOOGLE_API_KEY", GOOGLE_API_KEY)
    if api_key == _PLACEHOLDER_KEY:
        api_key = ""
    ollama_ok = _is_ollama_available()
    return {
        "mode":            detect_mode(),
        "internet":        _is_internet_available(),
        "api_key_set":     bool(api_key),
        "local_gemma4":    _is_local_gemma4_available(),
        "ollama":          ollama_ok,
        "ollama_model":    OLLAMA_MODEL if ollama_ok else "—",
        "model_online":    MODEL_ONLINE,
        "model_offline":   f"Ollama {OLLAMA_MODEL}" if ollama_ok else MODEL_OFFLINE_HF,
        "hf_cache":        HF_CACHE_DIR,
    }


# ── 1. TEXT GENERATION ─────────────────────────────────────────────────────────

def generate(
    prompt: str,
    system_prompt: str = "",
    context: str = "",
    language: str = "English",
    allow_online: bool = False,
) -> str:
    """
    Text generation.
    - Default: Ollama -> HF local -> Limited. No internet/API call.
    - allow_online=True: Online API -> Ollama -> HF local -> Limited.
    """
    full_prompt = prompt
    if context:
        full_prompt = (
            f"Use only the following reference information to answer.\n\n"
            f"{context}\n\n---\n\nQuestion: {prompt}"
        )

    effective_system = system_prompt or _default_system_prompt()
    if language and language.lower() != "english":
        effective_system = (
            f"IMPORTANT: You must respond entirely in {language}. Do not use English. "
            + effective_system
        )

    api_key = os.getenv("GOOGLE_API_KEY", GOOGLE_API_KEY)
    if api_key == _PLACEHOLDER_KEY:
        api_key = ""

    # ── Online: Gemma 4 Google AI API ─────────────────────────────────────────
    if allow_online and api_key and _is_internet_available():
        try:
            result = _generate_online(full_prompt, effective_system, api_key)
            if result and not result.startswith("❌"):
                return result
        except Exception as e:
            return (
                "⚠️ **Google AI API error**\n\n"
                f"`{e}`\n\n"
                "**Fix:** add a valid `GOOGLE_API_KEY` in `.env`, then restart."
            )
        return "⚠️ **Google AI API returned empty response.** Check your API key and quota."

    # ── Offline: Ollama (gemma3:2b — ~1.5 GB, 4 GB RAM) ──────────────────────
    if _is_ollama_available():
        try:
            result = _generate_ollama(full_prompt, effective_system)
            if result:
                return result
        except Exception:
            pass

    # ── Offline: HuggingFace local (9.7 GB — legacy) ──────────────────────────
    if _is_local_gemma4_available():
        print("[AI] Offline mode — loading local Gemma 4 E2B (first load takes a few minutes)…")
        try:
            result = _generate_local_hf(full_prompt, effective_system)
            if result and not result.startswith("❌"):
                return result
        except Exception:
            pass

    # ── Limited mode ───────────────────────────────────────────────────────────
    if not allow_online:
        return (
            "⚠️ **Offline AI is not running**\n\n"
            "Start local Gemma/Ollama to use AI without internet:\n"
            f"1. Run: `ollama pull {OLLAMA_MODEL}`\n"
            "2. Start Ollama\n"
            "3. Restart this app\n\n"
            "_Offline banking definitions still work without AI._"
        )

    return (
        "⚠️ **AI not available — Limited Mode**\n\n"
        "**Option A — Online (Gemma 4 API, free):**\n"
        "Add `GOOGLE_API_KEY=your_key` in `.env` — get a free key at "
        "https://aistudio.google.com/app/apikey\n\n"
        "**Option B — Offline (Ollama, ~1.5 GB, works on 4 GB RAM):**\n"
        "1. Install Ollama: https://ollama.ai\n"
        "2. Run: `ollama pull gemma3:2b`\n"
        "3. Restart this app — AI switches to offline automatically.\n\n"
        "_EMI Calculator and Banking Knowledge work without AI._"
    )


# ── 2. MULTIMODAL VISION — Gemma 4 reads images directly ──────────────────────

def generate_with_image(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    system_prompt: str = "",
    language: str = "English",
) -> str:
    """
    Gemma 4 Vision — pass image bytes directly (no OCR needed).
    Reads loan documents, scam screenshots, cheques — anything visual.
    Falls back gracefully when offline.
    """
    api_key = os.getenv("GOOGLE_API_KEY", GOOGLE_API_KEY)
    if api_key == _PLACEHOLDER_KEY:
        api_key = ""

    if not api_key or not _is_internet_available():
        return "__VISION_UNAVAILABLE__"

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        sys_instr = system_prompt or _default_system_prompt()
        if language and language.lower() != "english":
            sys_instr = f"IMPORTANT: You must respond entirely in {language}. Do not use English. " + sys_instr

        last_error = None
        for model_name in [MODEL_ONLINE, "gemma-2-2b-it", "gemma-3-2b-it"]:
            try:
                model = genai.GenerativeModel(model_name, system_instruction=sys_instr)
                response = model.generate_content([
                    prompt,
                    genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ])
                if response.text:
                    return response.text
            except Exception as e:
                last_error = e
                continue

        return f"⚠️ Gemma 4 Vision failed: {last_error}"
    except Exception as e:
        return f"⚠️ Vision error: {e}"


# ── 3. STRUCTURED FUNCTION CALLING — Gemma 4 calls financial tools ────────────

def generate_with_tools(
    prompt: str,
    system_prompt: str = "",
    context: str = "",
    language: str = "English",
) -> dict:
    """
    Gemma 4 structured function calling.
    Gemma decides when to call calculate_emi, loan_safety_score, or scam_risk.
    Returns: {"response": str, "tool_calls": list, "tool_results": dict}
    """
    api_key = os.getenv("GOOGLE_API_KEY", GOOGLE_API_KEY)
    if api_key == _PLACEHOLDER_KEY:
        api_key = ""

    # Offline fallback — try to detect intent and run tools manually
    if not api_key or not _is_internet_available():
        return _offline_tool_dispatch(prompt, language)

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        sys_instr = system_prompt or _default_system_prompt()
        if language and language.lower() != "english":
            sys_instr = f"IMPORTANT: You must respond entirely in {language}. Do not use English. " + sys_instr
        tools = _build_finance_tools()
        full_prompt = f"Context:\n{context}\n\nUser: {prompt}" if context else prompt

        for model_name in [MODEL_ONLINE, "gemma-2-2b-it"]:
            try:
                model = genai.GenerativeModel(
                    model_name,
                    system_instruction=sys_instr,
                    tools=tools,
                )
                response = model.generate_content(full_prompt)

                tool_calls = []
                tool_results = {}

                # Collect all function calls from response parts
                if response.candidates:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, "function_call") and part.function_call.name:
                            fn_name = part.function_call.name
                            fn_args = dict(part.function_call.args)
                            tool_calls.append({"name": fn_name, "args": fn_args})
                            tool_results[fn_name] = _execute_tool(fn_name, fn_args)

                # If Gemma called tools, send results back for final answer
                if tool_calls:
                    tool_resp_parts = [
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=tc["name"],
                                response={"result": tool_results[tc["name"]]},
                            )
                        )
                        for tc in tool_calls
                    ]
                    chat = model.start_chat()
                    chat.send_message(full_prompt)
                    followup = chat.send_message(tool_resp_parts)
                    final_text = followup.text or ""
                else:
                    final_text = response.text or ""

                return {
                    "response":     final_text,
                    "tool_calls":   tool_calls,
                    "tool_results": tool_results,
                }
            except Exception:
                continue

    except Exception:
        pass

    # Final fallback
    return _offline_tool_dispatch(prompt)


# ── Tool definitions ───────────────────────────────────────────────────────────

def _build_finance_tools():
    """Return Gemma 4 function calling tool declarations."""
    import google.generativeai as genai
    S = genai.protos.Schema
    T = genai.protos.Type

    return [genai.protos.Tool(function_declarations=[

        genai.protos.FunctionDeclaration(
            name="calculate_emi",
            description=(
                "Calculate EMI (Equated Monthly Installment), total interest paid, "
                "and total repayment amount for any loan. Call this whenever the user "
                "asks about loan payments, monthly installments, or total loan cost."
            ),
            parameters=S(
                type=T.OBJECT,
                properties={
                    "principal":   S(type=T.NUMBER,  description="Loan principal amount in Indian rupees"),
                    "annual_rate": S(type=T.NUMBER,  description="Annual interest rate as a percentage, e.g. 12 for 12%"),
                    "months":      S(type=T.INTEGER, description="Loan tenure in months"),
                    "is_flat":     S(type=T.BOOLEAN, description="True if flat/simple interest rate, False for reducing balance"),
                },
                required=["principal", "annual_rate", "months"],
            ),
        ),

        genai.protos.FunctionDeclaration(
            name="calculate_loan_safety_score",
            description=(
                "Calculate a RISK score (0–100) for a loan offer. "
                "0 = safest, 100 = critical danger. Scale: 0-20 Safe | 21-40 Low | "
                "41-60 Medium | 61-80 High | 81-100 Critical. "
                "Call this when evaluating whether a loan is risky or dangerous."
            ),
            parameters=S(
                type=T.OBJECT,
                properties={
                    "annual_rate":             S(type=T.NUMBER,  description="Annual interest rate %"),
                    "is_flat_rate":            S(type=T.BOOLEAN, description="True if flat rate (not reducing balance) — adds risk"),
                    "has_prepayment_penalty":  S(type=T.BOOLEAN, description="True if loan has prepayment penalty clause"),
                    "has_balloon_payment":     S(type=T.BOOLEAN, description="True if there is a large balloon final payment"),
                    "has_cross_default":       S(type=T.BOOLEAN, description="True if cross-default clause present"),
                    "has_acceleration_clause": S(type=T.BOOLEAN, description="True if entire loan becomes due on missed EMI"),
                    "has_unlimited_liability": S(type=T.BOOLEAN, description="True if unlimited liability clause present"),
                    "has_privacy_clause":      S(type=T.BOOLEAN, description="True if SMS/contact/device data access required"),
                    "has_arbitration_clause":  S(type=T.BOOLEAN, description="True if arbitration-only dispute resolution clause"),
                    "has_subscription_fee":    S(type=T.BOOLEAN, description="True if recurring platform or subscription fee"),
                },
                required=["annual_rate"],
            ),
        ),

        genai.protos.FunctionDeclaration(
            name="compare_loans",
            description=(
                "Compare two loan offers side-by-side and recommend the better one. "
                "Call this when the user provides details of two different loans."
            ),
            parameters=S(
                type=T.OBJECT,
                properties={
                    "loan1_principal":   S(type=T.NUMBER, description="Loan 1 principal"),
                    "loan1_rate":        S(type=T.NUMBER, description="Loan 1 annual rate %"),
                    "loan1_months":      S(type=T.INTEGER, description="Loan 1 tenure in months"),
                    "loan2_principal":   S(type=T.NUMBER, description="Loan 2 principal"),
                    "loan2_rate":        S(type=T.NUMBER, description="Loan 2 annual rate %"),
                    "loan2_months":      S(type=T.INTEGER, description="Loan 2 tenure in months"),
                },
                required=["loan1_principal", "loan1_rate", "loan1_months",
                          "loan2_principal", "loan2_rate", "loan2_months"],
            ),
        ),

    ])]


def _execute_tool(name: str, args: dict) -> dict:
    """Execute a financial tool and return structured results."""
    import sys, os as _os
    _sys_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _sys_root not in sys.path:
        sys.path.insert(0, _sys_root)
    from services.calculator_service import calculate_emi as _emi

    if name == "calculate_emi":
        p = float(args.get("principal", 0))
        r = float(args.get("annual_rate", 0))
        m = int(args.get("months", 12))
        flat = bool(args.get("is_flat", False))

        if flat:
            total_interest = p * (r / 100) * (m / 12)
            emi = (p + total_interest) / m
            total = p + total_interest
        else:
            res = _emi(p, r, m)
            emi, total_interest, total = res["emi"], res["total_interest"], res["total_payment"]

        rate_label = "flat" if flat else "reducing balance"
        return {
            "monthly_emi":    round(emi, 2),
            "total_interest": round(total_interest, 2),
            "total_payment":  round(total, 2),
            "principal":      p,
            "extra_pct":      round((total - p) / p * 100, 1) if p else 0,
            "summary": (
                f"Loan ₹{p:,.0f} @ {r}% p.a. ({rate_label}) for {m} months → "
                f"EMI ₹{emi:,.2f}/month | Total interest ₹{total_interest:,.2f} | "
                f"Total repayment ₹{total:,.2f} ({round((total-p)/p*100,1)}% more than borrowed)"
            ),
        }

    if name == "calculate_loan_safety_score":
        r = float(args.get("annual_rate", 0))
        # Risk score: 0 = safest, 100 = critical (higher = more dangerous)
        risk = 0
        if r > 28: risk += 25
        elif r > 24: risk += 18
        elif r > 18: risk += 10
        elif r > 14: risk += 4
        if args.get("is_flat_rate"):            risk += 10
        if args.get("has_prepayment_penalty"):  risk += 10
        if args.get("has_balloon_payment"):     risk += 15
        if args.get("has_cross_default"):       risk += 20
        if args.get("has_acceleration_clause"): risk += 15
        if args.get("has_unlimited_liability"): risk += 25
        if args.get("has_privacy_clause"):      risk += 15
        if args.get("has_arbitration_clause"):  risk += 10
        if args.get("has_subscription_fee"):    risk += 10
        risk = max(0, min(100, risk))
        verdict = (
            "🟢 SAFE"                                              if risk <= 20 else
            "🟡 LOW RISK — Review key clauses carefully"           if risk <= 40 else
            "🟠 MEDIUM RISK — Negotiate terms before signing"      if risk <= 60 else
            "🔴 HIGH RISK — Get independent advice before signing" if risk <= 80 else
            "🆘 CRITICAL RISK — Do NOT sign without legal review"
        )
        return {
            "risk_score": risk,
            "verdict": verdict,
            "scale": "0=Safe, 100=Critical Risk",
        }

    if name == "compare_loans":
        res1 = _execute_tool("calculate_emi", {
            "principal": args["loan1_principal"],
            "annual_rate": args["loan1_rate"],
            "months": args["loan1_months"],
        })
        res2 = _execute_tool("calculate_emi", {
            "principal": args["loan2_principal"],
            "annual_rate": args["loan2_rate"],
            "months": args["loan2_months"],
        })
        better = 1 if res1["total_payment"] <= res2["total_payment"] else 2
        saving = abs(res1["total_payment"] - res2["total_payment"])
        return {
            "loan1": res1, "loan2": res2,
            "better_loan": better,
            "savings": round(saving, 2),
            "summary": (
                f"Loan {better} is cheaper — saves ₹{saving:,.2f} total. "
                f"Loan 1: ₹{res1['monthly_emi']:,.0f}/month ({res1['extra_pct']}% extra) | "
                f"Loan 2: ₹{res2['monthly_emi']:,.0f}/month ({res2['extra_pct']}% extra)"
            ),
        }

    return {"error": f"Unknown tool: {name}"}


def _offline_tool_dispatch(prompt: str, language: str = "English") -> dict:
    """Detect calculation intent from text and run tool without Gemma (offline fallback)."""
    import re
    p = prompt.lower()
    tool_calls, tool_results = [], {}

    nums = re.findall(r"([\d,]+(?:\.\d+)?)", p)
    rates = re.findall(r"(\d+(?:\.\d+)?)\s*%", p)
    tenure_m = re.search(r"(\d+)\s*month", p)
    tenure_y = re.search(r"(\d+)\s*year", p)

    if any(k in p for k in ("emi", "monthly payment", "loan payment", "installment")) and nums and rates:
        try:
            principal = float(nums[0].replace(",", ""))
            rate = float(rates[0])
            months = int(tenure_m.group(1)) if tenure_m else (int(tenure_y.group(1)) * 12 if tenure_y else 12)
            result = _execute_tool("calculate_emi", {"principal": principal, "annual_rate": rate, "months": months})
            tool_calls.append({"name": "calculate_emi", "args": {"principal": principal, "annual_rate": rate, "months": months}})
            tool_results["calculate_emi"] = result
        except Exception:
            pass

    return {
        "response":     generate(prompt, language=language),
        "tool_calls":   tool_calls,
        "tool_results": tool_results,
    }


# ── Online backend ─────────────────────────────────────────────────────────────

def _generate_online(prompt: str, system_prompt: str = "", api_key: str = "") -> str:
    import google.generativeai as genai
    if not api_key:
        api_key = os.getenv("GOOGLE_API_KEY", GOOGLE_API_KEY)
    genai.configure(api_key=api_key)
    sys_instr = system_prompt or _default_system_prompt()
    last_error = None
    for model_name in [MODEL_ONLINE, "gemma-2-2b-it", "gemma-3-2b-it"]:
        try:
            model = genai.GenerativeModel(model_name, system_instruction=sys_instr)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            last_error = e
            continue
    raise Exception(f"All Gemma models failed. Last: {last_error}")


# ── Ollama backend ─────────────────────────────────────────────────────────────

def _generate_ollama(prompt: str, system_prompt: str = "") -> str:
    """
    Ollama local inference — gemma3:2b is ~1.5 GB and runs on 4 GB RAM.
    Setup: install ollama.ai → run `ollama pull gemma3:2b`
    """
    sys_instr = system_prompt or _default_system_prompt()
    payload = {
        "model":   OLLAMA_MODEL,
        "prompt":  f"{sys_instr}\n\n{prompt}",
        "stream":  False,
        "options": {"temperature": 0.7, "num_predict": 600},
    }
    resp = _requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=120)
    if resp.status_code == 200:
        return resp.json().get("response", "")
    return ""


# ── HuggingFace local backend (legacy) ────────────────────────────────────────

def _get_hf_pipeline():
    global _hf_pipe
    if _hf_pipe is not None:
        return _hf_pipe
    from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
    import torch
    print(f"[AI] Loading local Gemma 4 E2B model from {HF_CACHE_DIR}…")
    snap = _snapshot_path()
    if not snap:
        raise RuntimeError("Model snapshot not found. Run python setup_model.py first.")
    tokenizer = AutoTokenizer.from_pretrained(snap, local_files_only=True)

    # Try 4-bit quantization (NF4) — reduces RAM from ~4.8 GB to ~1.2 GB
    # Requires: pip install bitsandbytes  (Linux/CUDA; falls back to bfloat16 on CPU)
    try:
        from transformers import BitsAndBytesConfig
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        model = AutoModelForCausalLM.from_pretrained(
            snap,
            quantization_config=bnb_config,
            device_map="auto",
            low_cpu_mem_usage=True,
            local_files_only=True,
        )
        print("[AI] Gemma 4 E2B loaded with 4-bit NF4 quantization (~1.2 GB RAM).")
    except Exception as _bnb_err:
        # bitsandbytes unavailable (Windows CPU) — fall back to bfloat16
        print(f"[AI] 4-bit quant unavailable ({_bnb_err}), falling back to bfloat16.")
        model = AutoModelForCausalLM.from_pretrained(
            snap, torch_dtype=torch.bfloat16, device_map="auto",
            low_cpu_mem_usage=True, local_files_only=True,
        )
        print("[AI] Gemma 4 E2B loaded in bfloat16.")

    _hf_pipe = pipeline("text-generation", model=model, tokenizer=tokenizer)
    return _hf_pipe


def _generate_local_hf(prompt: str, system_prompt: str = "") -> str:
    try:
        pipe = _get_hf_pipeline()
        sys_instr = system_prompt or _default_system_prompt()
        messages = [{"role": "user", "content": f"{sys_instr}\n\n{prompt}"}]
        output = pipe(messages, max_new_tokens=512, do_sample=True, temperature=0.7,
                      pad_token_id=pipe.tokenizer.eos_token_id)
        generated = output[0]["generated_text"]
        if isinstance(generated, list):
            return generated[-1].get("content", str(generated))
        return str(generated)
    except Exception as e:
        return f"❌ Local Gemma 4 error: {e}"


# ── System prompt ──────────────────────────────────────────────────────────────

def _default_system_prompt() -> str:
    return (
        "You are RuralFinance AI — a trusted, friendly financial assistant for "
        "rural and underserved communities. Your mission:\n"
        "1. Explain banking and finance in simple, plain language — no jargon.\n"
        "2. Give India-specific examples with rupee amounts.\n"
        "3. Warn clearly about financial risks and scam signs.\n"
        "4. Be encouraging, patient, and non-judgmental.\n"
        "5. End with 1-2 practical next steps.\n"
        "Use short sentences. Prefer bullet points over long paragraphs."
    )
