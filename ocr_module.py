from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Dict

import cv2
import numpy as np
import pytesseract
from PIL import Image
from PyPDF2 import PdfReader


def _preprocess_image(image: Image.Image) -> np.ndarray:
    rgb = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def _ocr_pil_image(image: Image.Image) -> str:
    processed = _preprocess_image(image)
    try:
        return pytesseract.image_to_string(processed)
    except pytesseract.pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract executable was not found. Install Tesseract OCR and add it to PATH."
        ) from exc


def _extract_pdf_text_with_reader(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            text_parts.append(page_text)
    return "\n".join(text_parts)


def _extract_pdf_text_with_ocr(pdf_bytes: bytes) -> str:
    try:
        from pdf2image import convert_from_bytes
    except Exception:
        return ""

    text_parts = []
    for page_image in convert_from_bytes(pdf_bytes, first_page=1, last_page=1):
        text_parts.append(_ocr_pil_image(page_image))
    return "\n".join(text_parts)


def extract_text(file_path: str) -> Dict[str, object]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    raw_bytes = path.read_bytes()
    text = ""
    source = "unknown"

    if suffix == ".pdf":
        text = _extract_pdf_text_with_reader(raw_bytes)
        source = "pdf_text_layer"
        if len(text.strip()) < 20:
            text = _extract_pdf_text_with_ocr(raw_bytes)
            source = "pdf_ocr"
    else:
        with Image.open(path) as image:
            text = _ocr_pil_image(image)
            source = "image_ocr"

    cleaned_text = text.strip()
    return {
        "text": cleaned_text,
        "char_count": len(cleaned_text),
        "ocr_success": len(cleaned_text) > 20,
        "source": source,
    }
