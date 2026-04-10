"""
Optional PaddleOCR helpers for scanned PDF pages and table-like OCR text.
Imported lazily so the app runs without paddlepaddle/paddleocr installed.

Supports PaddleOCR 2.x (legacy ``ocr()`` output) and 3.x (``predict()`` + OCRResult).
"""
from __future__ import annotations

import os
import re
from typing import Any, List, Optional, Tuple

_OCR_ENGINE: Any = None


def paddleocr_available() -> bool:
    try:
        import paddleocr  # noqa: F401

        return True
    except Exception:
        return False


def use_paddle_ocr_enabled() -> bool:
    return os.getenv("USE_PADDLE_OCR", "1").strip().lower() not in ("0", "false", "no")


def get_paddle_ocr():
    """Lazy singleton PaddleOCR instance per process."""
    global _OCR_ENGINE
    if _OCR_ENGINE is not None:
        return _OCR_ENGINE
    if not paddleocr_available() or not use_paddle_ocr_enabled():
        return None
    from paddleocr import PaddleOCR

    # PaddleOCR 3.x: no use_gpu / show_log; optional doc preprocessors off for lighter runs.
    try:
        _OCR_ENGINE = PaddleOCR(
            lang="en",
            use_textline_orientation=True,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
        )
        return _OCR_ENGINE
    except (TypeError, ValueError):
        pass
    try:
        _OCR_ENGINE = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        return _OCR_ENGINE
    except Exception:
        try:
            _OCR_ENGINE = PaddleOCR(lang="en")
            return _OCR_ENGINE
        except Exception:
            return None


def pixmap_to_rgb_numpy(pix) -> Any:
    """Convert PyMuPDF Pixmap to HxWx3 uint8 RGB (numpy)."""
    import numpy as np

    h, w, n = pix.height, pix.width, pix.n
    arr = np.frombuffer(memoryview(pix.samples), dtype=np.uint8).reshape(h, w, n)
    if n == 4:
        arr = arr[:, :, :3]
    elif n == 1:
        arr = np.repeat(arr, 3, axis=2)
    return arr


def _text_from_rec_item(tx: Any) -> str:
    if tx is None:
        return ""
    if isinstance(tx, (list, tuple)) and len(tx) >= 1:
        return str(tx[0]).strip()
    return str(tx).strip()


def _read_paddlex_rec(first: Any) -> Tuple[Optional[List], Optional[List]]:
    """Read rec_texts / rec_polys from PaddleX OCRResult or dict."""
    rec_texts = None
    rec_polys = None
    try:
        if isinstance(first, dict):
            rec_texts = first.get("rec_texts")
            rec_polys = first.get("rec_polys") or first.get("dt_polys")
        elif hasattr(first, "get"):
            rec_texts = first.get("rec_texts")
            rec_polys = first.get("rec_polys") or first.get("dt_polys")
        elif hasattr(first, "__getitem__"):
            try:
                rec_texts = first["rec_texts"]
            except (KeyError, TypeError):
                rec_texts = None
            if rec_texts is not None:
                try:
                    rec_polys = first["rec_polys"]
                except (KeyError, TypeError):
                    try:
                        rec_polys = first["dt_polys"]
                    except (KeyError, TypeError):
                        rec_polys = None
    except Exception:
        return None, None
    return rec_texts, rec_polys


def normalize_ocr_output(result: Any) -> List[str]:
    """
    Turn PaddleOCR ``predict`` / ``ocr`` output into ordered text lines.
    """
    if not result:
        return []
    first = result[0] if isinstance(result, (list, tuple)) and result else result

    rec_texts, rec_polys = _read_paddlex_rec(first)
    if rec_texts:
        import numpy as np

        if rec_polys is not None and len(rec_polys) == len(rec_texts):
            scored: List[Tuple[float, float, str]] = []
            for poly, tx in zip(rec_polys, rec_texts):
                t = _text_from_rec_item(tx)
                if not t:
                    continue
                try:
                    arr = np.asarray(poly, dtype=float)
                    cy = float(np.mean(arr[:, 1]))
                    cx = float(np.mean(arr[:, 0]))
                except Exception:
                    cy, cx = 0.0, 0.0
                scored.append((cy, cx, t))
            scored.sort(key=lambda x: (round(x[0], 1), x[1]))
            return [x[2] for x in scored]
        return [_text_from_rec_item(t) for t in rec_texts if _text_from_rec_item(t)]

    return _sort_ocr_lines_legacy(result)


def _sort_ocr_lines_legacy(result: Any) -> List[str]:
    if not result:
        return []
    block = result[0] if isinstance(result, list) and result else result
    if not block:
        return []
    scored: List[Tuple[float, float, str]] = []
    for line in block:
        if not line or len(line) < 2:
            continue
        box, tx = line[0], line[1]
        if not tx:
            continue
        text = (tx[0] if isinstance(tx, (list, tuple)) else tx) or ""
        text = str(text).strip()
        if not text:
            continue
        try:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            cy = sum(ys) / len(ys)
            cx = sum(xs) / len(xs)
        except Exception:
            cy, cx = 0.0, 0.0
        scored.append((cy, cx, text))
    scored.sort(key=lambda t: (round(t[0], 1), t[1]))
    return [t[2] for t in scored]


def ocr_numpy_rgb(img_rgb: Any) -> Tuple[str, str]:
    """
    Run OCR on RGB numpy image. Returns (combined_text, content_type).
    content_type is 'table' or 'image_ocr' based on simple heuristics.
    """
    ocr = get_paddle_ocr()
    if ocr is None:
        return "", "image_ocr"
    result = None
    try:
        if hasattr(ocr, "predict"):
            result = ocr.predict(img_rgb)
    except Exception:
        result = None
    if result is None:
        try:
            result = ocr.ocr(img_rgb, cls=True)
        except TypeError:
            try:
                result = ocr.ocr(img_rgb)
            except Exception:
                return "", "image_ocr"
        except Exception:
            return "", "image_ocr"
    lines = normalize_ocr_output(result)
    text = "\n".join(lines).strip()
    ct = classify_ocr_text(text)
    return text, ct


def classify_ocr_text(text: str) -> str:
    """
    Heuristic: mark OCR output as table-like vs plain image text.
    """
    if not text.strip():
        return "image_ocr"
    raw_lines = [ln.rstrip() for ln in text.splitlines()]
    lines = [ln for ln in raw_lines if ln.strip()]
    if len(lines) < 2:
        return "image_ocr"
    joined = "\n".join(lines)
    if re.search(r"[\t]{2,}", joined):
        return "table"
    pipe_lines = sum(1 for ln in lines if "|" in ln)
    if pipe_lines >= 2 and len(lines) >= 3:
        return "table"
    digitish = sum(1 for ln in lines if re.search(r"\d", ln))
    short_rows = sum(1 for ln in lines if len(ln.split()) <= 8)
    if len(lines) >= 5 and digitish >= 3 and short_rows >= len(lines) * 0.5:
        return "table"
    return "image_ocr"


def ocr_page_fitz(page, dpi_scale: float = 2.0) -> Tuple[str, str]:
    """Render page to pixmap and OCR. dpi_scale increases resolution."""
    import fitz

    mat = fitz.Matrix(dpi_scale, dpi_scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    try:
        rgb = pixmap_to_rgb_numpy(pix)
        return ocr_numpy_rgb(rgb)
    finally:
        pix = None
