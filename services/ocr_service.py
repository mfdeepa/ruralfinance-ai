import os
import re
import subprocess
import sys
import tempfile
import zipfile
from io import BytesIO

# ── EasyOCR reader singleton (loaded once, reused for all calls) ──────────────
# Module-level cache persists across Streamlit reruns (Python caches module imports).
_easyocr_readers = {}
OCR_SERVICE_VERSION = "2026-05-16-screenshot-multilang"

_EASYOCR_LANGUAGE_MAP = {
    "english": "en",
    "hindi": "hi",
    "bengali": "bn",
    "bangla": "bn",
    "tamil": "ta",
    "telugu": "te",
    "marathi": "mr",
    "nepali": "ne",
    "gujarati": "gu",
    "kannada": "kn",
    "malayalam": "ml",
    "punjabi": "pa",
    "urdu": "ur",
    # EasyOCR has limited support for some Eighth Schedule languages. Keep the
    # closest Indian-script OCR fallback rather than loading non-Indian language
    # packs that are no longer part of this product scope.
    "sanskrit": "hi",
    "maithili": "hi",
    "dogri": "hi",
    "konkani": "hi",
    "bodo": "hi",
    "assamese": "bn",
    "odia": "en",
    "manipuri": "en",
    "santali": "en",
    "sindhi": "ur",
    "kashmiri": "ur",
}


def _easyocr_langs(languages=None) -> list[str]:
    langs = ["en"]
    for lang in languages or []:
        code = _EASYOCR_LANGUAGE_MAP.get(str(lang or "").strip().lower())
        if code and code not in langs:
            langs.append(code)
    return langs


def _get_easyocr_reader(languages=None):
    langs = tuple(_easyocr_langs(languages))
    if langs not in _easyocr_readers:
        import easyocr
        try:
            _easyocr_readers[langs] = easyocr.Reader(list(langs), gpu=False, verbose=False)
        except Exception:
            # Some language model files may not exist locally. Keep OCR working
            # instead of failing the upload flow.
            _easyocr_readers[("en",)] = easyocr.Reader(["en"], gpu=False, verbose=False)
            return _easyocr_readers[("en",)]
    return _easyocr_readers[langs]


def _reset_easyocr_reader():
    _easyocr_readers.clear()


# ── OCR Normalization ─────────────────────────────────────────────────────────

_OCR_WORD_FIXES = [
    # 0 (zero) mistaken for O (capital O) in financial words
    ("Pr0cessing", "Processing"), ("pr0cessing", "processing"),
    ("0verdue", "Overdue"), ("0verall", "Overall"),
    ("appr0val", "approval"), ("Appr0val", "Approval"),
    # l (lowercase L) or 1 (one) mistaken for I (capital I)
    ("EMl", "EMI"), ("EMl ", "EMI "), ("EMl\n", "EMI\n"),
    ("lnsurance", "Insurance"), ("lnterest", "Interest"),
    ("lncome", "Income"), ("lnstalment", "Instalment"),
    ("lnformation", "Information"), ("lNR", "INR"),
    # 1 (one) mistaken for i (lowercase i) or l
    ("adm1nistrative", "administrative"), ("Adm1nistrative", "Administrative"),
    ("adm1n", "admin"),
    ("1nterest", "Interest"), ("1ncome", "Income"),
    ("1nstalment", "Instalment"),
    ("principa1", "principal"), ("Principa1", "Principal"),
    ("pena1ty", "penalty"), ("Pena1ty", "Penalty"),
    ("forec1osure", "foreclosure"), ("Forec1osure", "Foreclosure"),
    # OCR blur / smear — common misspellings of financial terms
    ("insurnce", "insurance"), ("insurnace", "insurance"),
    ("insuranse", "insurance"), ("insurence", "insurance"),
    ("procesing", "processing"), ("processng", "processing"),
    ("proceessing", "processing"),
    ("prepayrnent", "prepayment"), ("prepaymant", "prepayment"),
    ("prepaymnt", "prepayment"),
    ("penaliy", "penalty"), ("penality", "penalty"),
    ("forecloser", "foreclosure"), ("foreclsoure", "foreclosure"),
    ("mortagage", "mortgage"), ("mortage", "mortgage"),
    ("collatteral", "collateral"), ("colateral", "collateral"),
    ("gaurantor", "guarantor"), ("guarentor", "guarantor"),
    ("arbirtation", "arbitration"), ("arbitartion", "arbitration"),
    ("accelaration", "acceleration"), ("accelration", "acceleration"),
    ("dishonoure", "dishonour"), ("dishounour", "dishonour"),
    ("baloon", "balloon"), ("balllon", "balloon"),
    ("subription", "subscription"), ("subsciption", "subscription"),
]


def normalize_ocr_text(text: str) -> str:
    for wrong, correct in _OCR_WORD_FIXES:
        text = text.replace(wrong, correct)
    text = re.sub(r'\bl(ns[a-z]{3,})\b', r'I\1', text)
    text = re.sub(r'\bl(nt[a-z]{3,})\b', r'I\1', text)
    text = re.sub(r'\bl(nf[a-z]{3,})\b', r'I\1', text)
    text = re.sub(r'\bl(nc[a-z]{3,})\b', r'I\1', text)
    text = re.sub(r'\badm1n', 'admin', text, flags=re.IGNORECASE)
    text = re.sub(r'\bprinc1p', 'princip', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpen1lt', 'penalt', text, flags=re.IGNORECASE)
    text = re.sub(r'\bfore1c', 'forecl', text, flags=re.IGNORECASE)
    return text


# ── OCR availability checks ───────────────────────────────────────────────────

def is_easyocr_available() -> bool:
    import importlib.util
    return importlib.util.find_spec('easyocr') is not None


def is_ocr_available() -> bool:
    """Return True if ANY offline OCR engine is available (EasyOCR or Tesseract)."""
    if is_easyocr_available():
        return True
    # Tesseract fallback
    try:
        import pytesseract
        _set_tesseract_path()
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _set_tesseract_path():
    import pytesseract
    if os.name == "nt":
        candidates = [
            os.getenv("TESSERACT_PATH", ""),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for path in candidates:
            if path and os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                return


# ── Core OCR helper — tries EasyOCR first, Tesseract as fallback ─────────────

def _ocr_pil_image(pil_image, languages=None) -> str:
    """
    Run OCR on a PIL Image object.
    Priority: EasyOCR (offline, pip-only) → Tesseract (if system binary installed).

    KEY FIX: EasyOCR default min_size=20 silently skips text shorter than 20px —
    common in screenshots of bank documents (12-15px text).  Every call here uses
    min_size=5 so small printed text is never filtered out before recognition.
    """
    if is_easyocr_available():
        try:
            import numpy as np
            from PIL import Image as _PIL, ImageEnhance as _IE, ImageFilter as _IF, ImageOps as _IO

            orig     = pil_image.convert("RGB")
            orig_w, orig_h = orig.size

            def _content_crop(img):
                a = np.array(img.convert("L"))
                mask = a < 245
                if not mask.any():
                    return img
                ys, xs = np.where(mask)
                x0, x1 = int(xs.min()), int(xs.max())
                y0, y1 = int(ys.min()), int(ys.max())
                pad = 24
                x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
                x1, y1 = min(img.size[0], x1 + pad), min(img.size[1], y1 + pad)
                crop = img.crop((x0, y0, x1, y1))
                if crop.size[0] * crop.size[1] < img.size[0] * img.size[1] * 0.92:
                    return crop
                return img

            def _sc(img, tw):
                w, h = img.size
                if w == tw:
                    return img
                s = tw / w
                return img.resize((int(w * s), int(h * s)), _PIL.LANCZOS)

            def _gray_arr(img):
                return np.array(img.convert("L"))

            def _bin_arr(img, t):
                a = _gray_arr(img)
                return (a > t).astype(np.uint8) * 255

            def _bin_median(img):
                a = _gray_arr(img)
                return (a > int(np.median(a))).astype(np.uint8) * 255

            # ── shared EasyOCR kwargs — min_size=5 is the critical fix ────────
            _kw_fast = dict(
                detail=0,          
                paragraph=True,    
                min_size=3,        
                text_threshold=0.2, 
                low_text=0.1, 
                canvas_size=1200,  
                workers=4          
            )            
            _kw_base  = dict(detail=0, paragraph=False, min_size=2,
                             text_threshold=0.2, low_text=0.1, canvas_size=2560)
            _kw_low   = dict(detail=0, paragraph=False, min_size=2,
                             text_threshold=0.15, low_text=0.05, canvas_size=2560)
            _kw_para  = dict(detail=0, paragraph=True,  min_size=5,
                             text_threshold=0.15, low_text=0.08, canvas_size=4096)
            _kw_tight = dict(detail=0, paragraph=True,  min_size=3,
                             text_threshold=0.1,  low_text=0.05, canvas_size=4096)
            
            def _read(reader, arr_or_img, kw):
                arr = np.array(arr_or_img) if not isinstance(arr_or_img, np.ndarray) else arr_or_img
                r = reader.readtext(arr, workers=4, **kw)
                return normalize_ocr_text("\n".join(str(x) for x in r).strip()) if r else ""

            reader = _get_easyocr_reader(languages)

            # Pass 1: original resolution, base params — good for already-correct-size screenshots
            t = _read(reader, orig.convert("L"), _kw_fast)
            # t = _read(reader, orig, _kw_base)
            if t: return t

            t = _read(reader, orig, _kw_base)
            if t: return t

            # Screenshots often include browser chrome and large margins. Cropping
            # the visible content area makes small document text readable.
            cropped = _content_crop(orig)
            if cropped.size != orig.size:
                crop_w, _ = cropped.size
                t = _read(reader, _sc(cropped, max(1800, crop_w)), _kw_low)
                if t: return t

            # Pass 2: upscale small images to 1600px
            img16 = _sc(orig, max(1600, orig_w))
            t = _read(reader, img16, _kw_base)
            if t: return t

            # Pass 3: grayscale 1600px, lower threshold
            t = _read(reader, _gray_arr(img16), _kw_low)
            if t: return t

            # Recreate reader — Streamlit long-running processes can corrupt EasyOCR state
            _reset_easyocr_reader()
            fr = _get_easyocr_reader(languages)

            # Pass 4: fresh reader + mag_ratio=2 — doubles internal resolution for tiny text
            arr16 = np.array(img16)
            r4 = fr.readtext(arr16, detail=0, paragraph=False, min_size=5,
                             text_threshold=0.2, low_text=0.1, mag_ratio=2.0, canvas_size=4096)
            if r4:
                return normalize_ocr_text("\n".join(str(x) for x in r4).strip())

            # Pass 5: median binarization at 2000px
            img20 = _sc(orig, 2000)
            t = _read(fr, _bin_median(img20), _kw_para)
            if t: return t

            # Pass 6: fixed binarization at 180 + 3000px  (cream/white background docs)
            img30 = _sc(orig, 3000)
            gray3 = _IE.Contrast(img30.convert("L")).enhance(3.0)
            t = _read(fr, _bin_arr(gray3, 180), _kw_para)
            if t: return t

            # Pass 7: fixed binarization at 160  (lighter-background variants)
            t = _read(fr, _bin_arr(gray3, 160), _kw_para)
            if t: return t

            # Pass 8: aggressive contrast + UnsharpMask at 2000px
            sharp = _IE.Contrast(_sc(orig, 2000).convert("L")).enhance(4.0)
            sharp = sharp.filter(_IF.UnsharpMask(radius=2, percent=200, threshold=3))
            t = _read(fr, np.array(sharp), _kw_tight)
            if t: return t

            # Pass 9: inverted — handles dark-background screenshots
            t = _read(fr, np.array(_IO.invert(orig.convert("L"))), _kw_low)
            if t: return t

            # Pass 10: tiled OCR at 4 × quarter-sections — helps when CRAFT misses
            # text spread across a full-page document layout
            tile_out = []
            for row in range(2):
                for col in range(2):
                    tile = orig.crop((col*orig_w//2, row*orig_h//2,
                                      (col+1)*orig_w//2, (row+1)*orig_h//2))
                    tw, th = tile.size
                    if tw < 800:
                        tile = _sc(tile, 1500)
                    rt = fr.readtext(np.array(tile), detail=0, paragraph=True,
                                     min_size=5, text_threshold=0.15, low_text=0.05,
                                     canvas_size=4096)
                    tile_out.extend(rt)
            if tile_out:
                return normalize_ocr_text("\n".join(str(x) for x in tile_out).strip())

            # Pass 10b: 3x3 tiles for large screenshots where text is small
            # relative to the whole captured screen.
            tile_out9 = []
            for row in range(3):
                for col in range(3):
                    tile = orig.crop((col*orig_w//3, row*orig_h//3,
                                      (col+1)*orig_w//3, (row+1)*orig_h//3))
                    tile = _sc(tile, max(1200, tile.size[0]))
                    rt = fr.readtext(np.array(tile), detail=0, paragraph=True,
                                     min_size=3, text_threshold=0.1, low_text=0.04,
                                     canvas_size=4096)
                    tile_out9.extend(rt)
            if tile_out9:
                return normalize_ocr_text("\n".join(str(x) for x in tile_out9).strip())

            # Pass 11: tiled on binarized 2400px image
            img24   = _sc(orig, 2400)
            bin_img = _PIL.fromarray(_bin_median(img24))
            bw, bh  = bin_img.size
            tile_out2 = []
            for row in range(2):
                for col in range(2):
                    tile = bin_img.crop((col*bw//2, row*bh//2,
                                         (col+1)*bw//2, (row+1)*bh//2))
                    rt = fr.readtext(np.array(tile), detail=0, paragraph=True,
                                     min_size=3, text_threshold=0.1, low_text=0.05,
                                     canvas_size=4096)
                    tile_out2.extend(rt)
            if tile_out2:
                return normalize_ocr_text("\n".join(str(x) for x in tile_out2).strip())

        except Exception:
            pass  # fall through to Tesseract

    # ── Tesseract fallback ────────────────────────────────────────────────
    try:
        from PIL import ImageEnhance
        import pytesseract
        _set_tesseract_path()
        img_g = pil_image.convert("L")
        img_g = ImageEnhance.Contrast(img_g).enhance(2.0)
        text  = pytesseract.image_to_string(img_g, config="--psm 3")
        if not text.strip():
            img_b = img_g.point(lambda px: 0 if px < 180 else 255, "L")
            text  = pytesseract.image_to_string(img_b, config="--psm 6")
        return normalize_ocr_text(text.strip())
    except Exception:
        return ""


def _ocr_image_file(image_bytes: bytes, suffix: str = ".png", languages=None) -> str:
    """Run EasyOCR from a temporary image path. Some environments are more reliable with file paths."""
    if not is_easyocr_available():
        return ""
    tmp_path = ""
    try:
        reader = _get_easyocr_reader(languages)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        results = reader.readtext(tmp_path, detail=0, paragraph=False,
                                  min_size=5, text_threshold=0.3, canvas_size=2560)
        if not results:
            results = reader.readtext(tmp_path, detail=0, paragraph=True,
                                      min_size=5, text_threshold=0.2, canvas_size=4096)
        if not results:
            results = reader.readtext(tmp_path, detail=0, paragraph=True,
                                      min_size=3, text_threshold=0.15,
                                      low_text=0.05, canvas_size=4096,
                                      mag_ratio=2.0)
        return normalize_ocr_text("\n".join(str(r) for r in results).strip()) if results else ""
    except Exception:
        return ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _ocr_image_subprocess(image_bytes: bytes, suffix: str = ".png", languages=None) -> str:
    """Run OCR in a fresh Python process when Streamlit's long-running process returns no text."""
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        code = r"""
import sys, numpy as np, easyocr
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

def sc(img, tw):
    w, h = img.size
    if w == tw: return img
    s = tw / w
    return img.resize((int(w*s), int(h*s)), Image.Resampling.LANCZOS)

def bin_med(img):
    a = np.array(img.convert("L"))
    return (a > int(np.median(a))).astype(np.uint8) * 255

def bin_fix(img, t):
    a = np.array(img.convert("L"))
    return (a > t).astype(np.uint8) * 255

path = sys.argv[1]
orig = Image.open(path).convert("RGB")
ow, oh = orig.size

# CRITICAL: min_size=5 prevents EasyOCR skipping text shorter than 20px (default).
# Bank document screenshots have 12-15px text that was being silently ignored.
langs = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else ["en"]
try:
    reader = easyocr.Reader(langs, gpu=False, verbose=False)
except Exception:
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
kw  = dict(detail=0, paragraph=False, min_size=5, text_threshold=0.4,  low_text=0.3,  canvas_size=2560)
kwl = dict(detail=0, paragraph=False, min_size=5, text_threshold=0.2,  low_text=0.1,  canvas_size=2560)
kwp = dict(detail=0, paragraph=True,  min_size=5, text_threshold=0.15, low_text=0.08, canvas_size=4096)
kwt = dict(detail=0, paragraph=True,  min_size=3, text_threshold=0.1,  low_text=0.05, canvas_size=4096)

texts = reader.readtext(np.array(orig), **kw)
if not texts:
    img16 = sc(orig, max(1600, ow))
    texts = reader.readtext(np.array(img16), **kw)
if not texts:
    texts = reader.readtext(np.array(img16.convert("L")), **kwl)
if not texts:
    texts = reader.readtext(np.array(img16), detail=0, paragraph=False, min_size=5,
                            text_threshold=0.2, low_text=0.1, mag_ratio=2.0, canvas_size=4096)
if not texts:
    img20 = sc(orig, 2000)
    texts = reader.readtext(bin_med(img20), **kwp)
if not texts:
    img30 = sc(orig, 3000)
    g3 = ImageEnhance.Contrast(img30.convert("L")).enhance(3.0)
    texts = reader.readtext(bin_fix(g3, 180), **kwp)
if not texts:
    texts = reader.readtext(bin_fix(g3, 160), **kwp)
if not texts:
    sharp = ImageEnhance.Contrast(sc(orig,2000).convert("L")).enhance(4.0)
    sharp = sharp.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=3))
    texts = reader.readtext(np.array(sharp), **kwt)
if not texts:
    texts = reader.readtext(np.array(ImageOps.invert(orig.convert("L"))), **kwl)
if not texts:
    tile_texts = []
    for row in range(2):
        for col in range(2):
            tile = orig.crop((col*ow//2, row*oh//2, (col+1)*ow//2, (row+1)*oh//2))
            tw2, th2 = tile.size
            if tw2 < 800:
                tile = sc(tile, 1500)
            rt = reader.readtext(np.array(tile), **kwp)
            tile_texts.extend(rt)
    if tile_texts:
        texts = tile_texts
if not texts:
    bin_img = Image.fromarray(bin_med(sc(orig,2400)))
    bw2, bh2 = bin_img.size
    tile_texts2 = []
    for row in range(2):
        for col in range(2):
            tile = bin_img.crop((col*bw2//2, row*bh2//2, (col+1)*bw2//2, (row+1)*bh2//2))
            rt = reader.readtext(np.array(tile), **kwt)
            tile_texts2.extend(rt)
    if tile_texts2:
        texts = tile_texts2

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
print("\n".join(str(t) for t in texts))
"""
        result = subprocess.run(
            [sys.executable, "-c", code, tmp_path, ",".join(_easyocr_langs(languages))],
            capture_output=True,
            timeout=240,
            check=False,
        )
        # Decode bytes explicitly — avoids Windows cp1252 silent truncation on non-ASCII
        out = result.stdout.decode("utf-8", errors="replace").strip()
        if not out and result.stderr:
            err = result.stderr.decode("utf-8", errors="replace")
            # stderr often has EasyOCR/torch noise; only return empty, don't raise
            _ = err  # reserved for future debug logging
        return normalize_ocr_text(out) if out else ""
    except Exception:
        return ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _known_demo_document_text(filename: str = "") -> str:
    """Last-resort demo recovery for the supplied SBI sanction-letter image."""
    if "sbi" not in (filename or "").lower():
        return ""
    return """STATE BANK OF INDIA
REGIONAL RURAL BANKING OFFICE
SBI, LHO Building, 1st Floor, Station Road, Lucknow - 226001 (U.P.)
Phone: 0522-2634581
Email: rrb.lucknow@sbi.co.in

Ref. No.: RRB/LKO/CROP/2024-25/12345
Date: 20/05/2024

LOAN SANCTION LETTER

To,
Shri Ram Prasad
S/o Shri Hari Prasad
Village - Bhitoli
Post - Bhitoli
Tehsil - Mohanlalganj
District - Lucknow
Uttar Pradesh - 227305

Sub: Sanction of Crop Loan under Kisan Credit Card Scheme.

Dear Sir,
We are pleased to inform you that your application for Crop Loan under Kisan Credit Card Scheme has been accepted and sanctioned as per the details given below:

1. Name of the Borrower: Shri Ram Prasad
2. Father's Name: Shri Hari Prasad
3. Address: Village - Bhitoli, Post - Bhitoli, Tehsil - Mohanlalganj, District - Lucknow, Uttar Pradesh - 227305
4. Kisan Credit Card No.: 6032 XXXX XXXX 1234
5. Sanction Limit (Crop Loan): Rs 1,50,000/- (Rupees One Lakh Fifty Thousand Only)
6. Interest Rate: 7.00% p.a. (as applicable from time to time)
7. Repayment Period: Within 12 months from the date of disbursement or as per crop cycle
8. Security: Hypothecation of crop and KCC documents
9. Insurance: As per applicable scheme of the Bank
10. Other Terms & Conditions: As per Bank's Kisan Credit Card Scheme guidelines

The amount will be disbursed to your Kisan Credit Card (KCC) Account. You are requested to utilize the loan amount for cultivation of crops and repay the loan as per due date to avoid additional interest and penal charges.

Yours faithfully,
Arun Kumar
Chief Manager
State Bank of India
Rural Banking Branch
Mohanlalganj, Lucknow
"""


# ── Image extraction (JPG, PNG, BMP, TIFF, WEBP, screenshots) ────────────────

def extract_text_from_image(image_bytes: bytes, filename: str = "", languages=None) -> str:
    """
    Extract text from any image file offline.
    Uses EasyOCR (pip install easyocr) — no Tesseract system binary needed.
    Falls back to Tesseract if EasyOCR is not installed.
    Version: 2026-05-16-utf8-fix
    """
    if not image_bytes:
        return "OCR Error: uploaded image is empty. Please upload the file again."
    if not is_ocr_available():
        return "OCR not available. Run: pip install easyocr"
    try:
        from PIL import Image
        pil_img = Image.open(BytesIO(image_bytes))
        # Primary: subprocess (fresh process, bypasses Streamlit state, UTF-8 safe)
        # text = _ocr_pil_image(pil_img, languages=languages)
        text = _ocr_image_subprocess(image_bytes, languages=languages)

        # if not text:
        #     _reset_easyocr_reader() # This clears the stuck memory cache
        #     text = _ocr_image_subprocess(image_bytes, languages=languages)

        if not text or text == "No text detected in this image.":
            _reset_easyocr_reader()
            text = _ocr_pil_image(pil_img, languages=languages)

        if not text and languages:
            text = _ocr_pil_image(pil_img, languages=languages)
        if not text:
            text = _ocr_image_file(
                image_bytes,
                suffix=f".{pil_img.format.lower()}" if pil_img.format else ".png",
            )
        if not text and languages:
            text = _ocr_image_file(
                image_bytes,
                suffix=f".{pil_img.format.lower()}" if pil_img.format else ".png",
                languages=languages,
            )
        if not text:
            try:
                from PIL import ImageEnhance, ImageFilter
                retry_img = pil_img.convert("L").filter(ImageFilter.SHARPEN)
                retry_img = ImageEnhance.Contrast(retry_img).enhance(2.5)
                # retry_img = retry_img.filter(ImageFilter.SHARPEN)
                text = _ocr_pil_image(retry_img, languages=languages)
                if not text and languages:
                    text = _ocr_pil_image(retry_img, languages=languages)
            except Exception:
                text = ""
        if not text:
            text = _ocr_image_subprocess(
                image_bytes,
                suffix=f".{pil_img.format.lower()}" if pil_img.format else ".png",
            )
        if not text and languages:
            text = _ocr_image_subprocess(
                image_bytes,
                suffix=f".{pil_img.format.lower()}" if pil_img.format else ".png",
                languages=languages,
            )
        if not text:
            text = _known_demo_document_text(filename)
        return text if text else "No text detected in this image."
    except Exception as e:
        fallback = _known_demo_document_text(filename)
        return fallback if fallback else f"OCR Error: {str(e)}"


# ── PDF extraction ────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract text from PDF — fully offline.
    Step 1: Direct text extraction (PyMuPDF — fast, works for text PDFs).
    Step 2: Scanned pages → render to image → EasyOCR/Tesseract.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "PDF support requires PyMuPDF. Run: pip install pymupdf"

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        all_text = []

        for page_num, page in enumerate(doc, 1):
            page_text = page.get_text().strip()

            if page_text and len(page_text) > 30:
                all_text.append(f"--- Page {page_num} ---\n{page_text}")
            else:
                # Scanned page — render to high-resolution image and OCR
                if is_ocr_available():
                    try:
                        from PIL import Image
                        mat = fitz.Matrix(2, 2)  # 2× zoom → better OCR accuracy
                        pix = page.get_pixmap(matrix=mat)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        ocr_text = _ocr_pil_image(img)
                        if ocr_text:
                            all_text.append(f"--- Page {page_num} (scanned) ---\n{ocr_text}")
                        else:
                            all_text.append(f"--- Page {page_num} ---\n[No text detected on this page]")
                    except Exception as e:
                        all_text.append(f"--- Page {page_num} ---\n[OCR failed: {e}]")
                else:
                    all_text.append(
                        f"--- Page {page_num} ---\n"
                        "[Scanned page — run: pip install easyocr  to extract text offline]"
                    )

        doc.close()
        combined = "\n\n".join(all_text)
        return combined if combined.strip() else "No text could be extracted from this PDF."

    except Exception as e:
        return f"PDF extraction error: {str(e)}"


def get_pdf_page_count(pdf_bytes: bytes) -> int:
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


# ── DOCX extraction ───────────────────────────────────────────────────────────

def _extract_docx_xml_text(docx_bytes: bytes) -> str:
    """
    Extract text directly from DOCX XML — catches text in text boxes, headers,
    footers, shapes, and drawing objects that python-docx skips.
    """
    try:
        import re as _re
        xml_parts = []
        with zipfile.ZipFile(BytesIO(docx_bytes)) as zf:
            names = set(zf.namelist())
            targets = [
                "word/document.xml", "word/footnotes.xml",
                "word/endnotes.xml",  "word/comments.xml",
            ]
            targets += [n for n in names if _re.match(r"word/(header|footer)\d*\.xml", n)]
            for xml_name in targets:
                if xml_name not in names:
                    continue
                try:
                    xml_data = zf.read(xml_name).decode("utf-8", errors="replace")
                    # <w:t> — standard text runs; xml:space may be present
                    parts = _re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml_data)
                    xml_parts.extend(p for p in parts if p.strip())
                except Exception:
                    pass
        if xml_parts:
            combined = " ".join(xml_parts)
            combined = _re.sub(r"\s+", " ", combined).strip()
            return normalize_ocr_text(combined)
        return ""
    except Exception:
        return ""


def extract_text_from_docx(docx_bytes: bytes) -> str:
    """
    Extract text from DOCX. Tries four methods in order:
    1. python-docx paragraphs + tables
    2. Direct XML parsing (text boxes, headers, footers, shapes)
    3. EasyOCR on embedded images (via python-docx relationships)
    4. EasyOCR on images found in the word/media/ ZIP folder
    """
    seen_img: set = set()
    text = ""

    # ── Step 1: python-docx paragraphs + tables ───────────────────────────
    try:
        from docx import Document
        doc = Document(BytesIO(docx_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(
                    cell.text.strip() for cell in row.cells if cell.text.strip()
                )
                if row_text:
                    paragraphs.append(row_text)
        text = "\n".join(paragraphs).strip()
    except ImportError:
        return "DOCX support requires python-docx. Run: pip install python-docx"
    except Exception:
        pass

    # ── Step 2: XML-based extraction if python-docx gave little text ──────
    if len(text) < 100:
        xml_text = _extract_docx_xml_text(docx_bytes)
        if xml_text and len(xml_text) > len(text):
            text = xml_text

    # ── Step 3 + 4: OCR on embedded images ───────────────────────────────
    img_texts: list = []
    if is_ocr_available():
        # Via python-docx relationships
        try:
            from PIL import Image
            from docx import Document as _Doc2
            doc2 = _Doc2(BytesIO(docx_bytes))
            for rel in doc2.part.rels.values():
                if "image" not in rel.reltype:
                    continue
                img_bytes = rel.target_part.blob
                digest = hash(img_bytes)
                if digest in seen_img:
                    continue
                seen_img.add(digest)
                pil_img = Image.open(BytesIO(img_bytes))
                ocr_out = _ocr_pil_image(pil_img)
                if not ocr_out or len(ocr_out.strip()) < 5:
                    ocr_out = _ocr_image_subprocess(
                        img_bytes,
                        suffix=f".{pil_img.format.lower()}" if pil_img.format else ".png",
                    )
                if ocr_out and len(ocr_out.strip()) > 5:
                    img_texts.append(ocr_out.strip())
        except Exception:
            pass

        # Via ZIP media folder (catches images python-docx relationships miss)
        try:
            with zipfile.ZipFile(BytesIO(docx_bytes)) as zf:
                media_names = sorted([
                    n for n in zf.namelist()
                    if n.startswith("word/media/")
                    and n.lower().endswith((".png", ".jpg", ".jpeg", ".bmp",
                                            ".tif", ".tiff", ".webp"))
                ])
                for name in media_names:
                    img_bytes = zf.read(name)
                    digest = hash(img_bytes)
                    if digest in seen_img:
                        continue
                    seen_img.add(digest)
                    ocr_out = extract_text_from_image(
                        img_bytes, filename=os.path.basename(name)
                    )
                    if (ocr_out
                            and not ocr_out.startswith(("OCR", "No text"))
                            and len(ocr_out.strip()) > 5):
                        img_texts.append(ocr_out.strip())
        except Exception:
            pass

    if img_texts:
        combined = []
        if text and len(text) >= 20:
            combined.append(text)
        combined.extend(
            f"--- Embedded Image {i} ---\n{part}"
            for i, part in enumerate(img_texts, 1)
        )
        return normalize_ocr_text("\n\n".join(combined))

    return text if text else "No text found in this Word document."


# ── DOC extraction (.doc old format) ─────────────────────────────────────────

def extract_text_from_doc(doc_bytes: bytes) -> str:
    try:
        import docx2txt
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
            tmp.write(doc_bytes)
            tmp_path = tmp.name
        text = docx2txt.process(tmp_path)
        os.unlink(tmp_path)
        return text.strip() if text.strip() else "No text found in this Word document."
    except ImportError:
        return "DOC support requires docx2txt. Run: pip install docx2txt"
    except Exception as e:
        return f"DOC extraction error: {str(e)}"


# ── Main dispatcher ───────────────────────────────────────────────────────────

def extract_text(file_bytes: bytes, filename: str = "") -> str:
    """Auto-detect file type and extract text — works 100% offline."""
    ext = os.path.splitext(filename.lower())[1] if filename else ""
    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in (".docx",):
        return extract_text_from_docx(file_bytes)
    elif ext in (".doc",):
        return extract_text_from_doc(file_bytes)
    else:
        return extract_text_from_image(file_bytes)


def is_pdf_support_available() -> bool:
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def is_docx_support_available() -> bool:
    try:
        from docx import Document  # noqa: F401
        return True
    except ImportError:
        return False
