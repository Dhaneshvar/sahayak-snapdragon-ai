"""Load a form from a PDF, image or text file into plain text."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from . import ocr

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
TEXT_EXT = {".txt", ".md"}


class DocumentError(RuntimeError):
    pass


@dataclass
class LoadedDocument:
    text: str
    source_name: str
    method: str          # "pdf-text" | "ocr" | "text"
    seconds: float
    truncated: bool = False


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise DocumentError("pypdf not installed: pip install pypdf") from e
    try:
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception as e:  # pypdf raises many exception types for malformed files
        raise DocumentError(f"Could not read PDF: {e}") from e


def load_document(path: str | Path, max_chars: int = 12000,
                  max_file_mb: int = 20) -> LoadedDocument:
    path = Path(path)
    if not path.is_file():
        raise DocumentError(f"File not found: {path.name}")
    if path.stat().st_size > max_file_mb * 1024 * 1024:
        raise DocumentError(f"File is larger than {max_file_mb} MB")

    ext = path.suffix.lower()
    start = time.perf_counter()
    if ext == ".pdf":
        text, method = _pdf_text(path), "pdf-text"
        if not text:
            raise DocumentError("This PDF has no text layer (it is a scan). "
                                "Save the page as an image (PNG/JPG) and open that instead.")
    elif ext in IMAGE_EXT:
        text, _ = ocr.ocr_image(path)
        method = "ocr"
    elif ext in TEXT_EXT:
        text, method = path.read_text(encoding="utf-8", errors="replace"), "text"
    else:
        raise DocumentError(f"Unsupported file type: {ext or '(none)'}")
    elapsed = time.perf_counter() - start

    text = text.strip()
    if not text:
        raise DocumentError("No readable text found. Try a clearer, well-lit photo.")
    truncated = len(text) > max_chars
    return LoadedDocument(text[:max_chars], path.name, method, elapsed, truncated)
