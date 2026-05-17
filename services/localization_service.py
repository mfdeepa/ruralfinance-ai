"""Fast cached translation helper for UI/report strings.

Page rendering must be deterministic and quick. This module therefore returns
manual/cached translations during normal UI rendering and only calls AI when a
caller explicitly asks for live translation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from typing import Iterable

from services.ai_service import detect_mode, generate

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE_DIR = os.path.join(_ROOT, "data")
_CACHE_FILE = os.path.join(_CACHE_DIR, "translation_cache.json")
_BAD_SNIPPETS = (
    "AI not available",
    "Google AI API error",
    "Option A",
    "sorry",
    "cannot translate",
)

_FAIL_PREFIXES = ("⚠️", "❌", "**Option A", "Option A")


def _load_cache() -> dict:
    try:
        with open(_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _cache_key(language: str, text: str, context: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()
    ctx = hashlib.sha1(str(context or "").encode("utf-8", errors="ignore")).hexdigest()[:10]
    return f"v2:{language}:{ctx}:{digest}"


@lru_cache(maxsize=1)
def _translation_backend_available() -> bool:
    """Avoid repeated slow AI availability checks when translation is unavailable."""
    return detect_mode() != "limited"


def _looks_translatable(text: str) -> bool:
    clean = str(text or "").strip()
    if not clean:
        return False
    if len(clean) <= 1:
        return False
    if re.fullmatch(r"[\d\s,.\-+/%₹:()]+", clean):
        return False
    return True


def _looks_bad_translation(original: str, translated: str) -> bool:
    clean = str(translated or "").strip()
    if not clean:
        return True
    if clean.startswith(_FAIL_PREFIXES):
        return True
    lower = clean.lower()
    if any(snippet.lower() in lower for snippet in _BAD_SNIPPETS):
        return True
    original_clean = str(original or "").strip()
    if len(original_clean) < 120:
        if "\n" in clean or "\r" in clean:
            return True
        if "•" in clean or "<li" in lower:
            return True
        if "**" in clean and "**" not in original_clean:
            return True
        if len(clean) > max(160, len(original_clean) * 4):
            return True
    if len(original) > 500 and len(clean) < max(80, len(original) * 0.18):
        return True
    return False


def translate_text(
    text: str,
    language: str,
    *,
    context: str = "financial app UI",
    live: bool = False,
) -> str:
    """Translate one UI/report string into ``language`` with disk cache.

    By default this is cache-only. Live AI translation is intentionally opt-in
    because translating during Streamlit render makes pages slow and can change
    the structure of UI content.
    """
    original = "" if text is None else str(text)
    if not language or language.lower() == "english" or not _looks_translatable(original):
        return original

    if not _translation_backend_available():
        return original

    cache = _load_cache()
    key = _cache_key(language, original, context)
    cached = cache.get(key)
    if cached and not _looks_bad_translation(original, cached):
        return cached
    if cached:
        cache.pop(key, None)

    if not live:
        return original

    prompt = (
        f"Translate the following {context} text into {language}.\n"
        "Rules:\n"
        "- Return only the translated text.\n"
        "- Keep numbers, currency symbols, percentages, file extensions, and product names unchanged.\n"
        "- Keep markdown formatting such as **bold**, bullets, and line breaks.\n"
        "- Do not add explanations.\n\n"
        f"TEXT:\n{original}"
    )
    translated = generate(prompt, language=language).strip()
    if translated == original or _looks_bad_translation(original, translated):
        return original

    cache[key] = translated
    _save_cache(cache)
    return translated


def translate_many(
    items: Iterable[str],
    language: str,
    *,
    context: str = "financial app UI",
    live: bool = False,
) -> list[str]:
    return [translate_text(item, language, context=context, live=live) for item in items]
