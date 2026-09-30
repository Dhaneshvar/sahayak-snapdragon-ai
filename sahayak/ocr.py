"""On-device OCR using RapidOCR (ONNX models ship inside the wheel; no download)."""
from __future__ import annotations

import time
from pathlib import Path


class OCRUnavailable(RuntimeError):
    pass


_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as e:
            raise OCRUnavailable(
                "OCR engine not installed. Run: pip install rapidocr_onnxruntime "
                "(see README > Troubleshooting for Windows ARM64).") from e
        _engine = RapidOCR()
    return _engine


def group_lines(items: list, y_tolerance: float = 12.0) -> str:
    """Turn RapidOCR [box, text, score] items into reading-order lines."""
    boxes = []
    for box, text, _score in items:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        boxes.append(((min(ys) + max(ys)) / 2, min(xs), text))
    boxes.sort(key=lambda b: (b[0], b[1]))
    lines: list[list] = []
    for yc, x, text in boxes:
        if lines and abs(lines[-1][0] - yc) <= y_tolerance:
            lines[-1][1].append((x, text))
        else:
            lines.append([yc, [(x, text)]])
    return "\n".join(" ".join(t for _, t in sorted(parts)) for _, parts in lines)


def ocr_image(path: str | Path) -> tuple[str, float]:
    """Return (text, seconds). Raises OCRUnavailable if the engine is missing."""
    engine = _get_engine()
    start = time.perf_counter()
    result, _ = engine(str(path))
    elapsed = time.perf_counter() - start
    return (group_lines(result) if result else ""), elapsed
