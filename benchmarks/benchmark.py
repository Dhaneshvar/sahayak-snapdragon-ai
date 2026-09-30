"""Measure Sahayak latency on this device and save the results.

Run:  python benchmarks/benchmark.py --runs 5
Writes benchmarks/results/<timestamp>.json and prints a Markdown table
to paste into docs/BENCHMARKS.md. Run once with the NPU model and once with a
CPU model (SAHAYAK_LLM_MODEL=...) to compare.
"""
import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sahayak.assistant import Assistant  # noqa: E402
from sahayak.config import Settings  # noqa: E402
from sahayak.documents import load_document  # noqa: E402
from sahayak.llm import build_llm  # noqa: E402
from sahayak.ocr import OCRUnavailable, ocr_image  # noqa: E402


def summarize(xs):
    xs = sorted(xs)
    return {"median_s": round(statistics.median(xs), 3), "min_s": round(xs[0], 3),
            "max_s": round(xs[-1], 3), "runs": len(xs)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--language", default="English", choices=["English", "Hindi"])
    args = ap.parse_args()

    settings = Settings()
    llm = build_llm(settings)
    assistant = Assistant(llm)
    assistant.load(load_document(ROOT / "samples" / "sample_kyc_form.txt"))

    results = {"device": {"machine": platform.machine(), "processor": platform.processor(),
                          "platform": platform.platform()},
               "model": llm.model_id, "endpoint": llm.base_url, "language": args.language}

    img = ROOT / "samples" / "sample_kyc_form.png"
    if img.exists():
        try:
            ocr_image(img)  # warm-up (model load)
            results["ocr"] = summarize([ocr_image(img)[1] for _ in range(args.runs)])
        except OCRUnavailable as e:
            results["ocr"] = {"skipped": str(e)}

    assistant.explain(args.language)  # warm-up
    results["explain"] = summarize([assistant.explain(args.language)[1] for _ in range(args.runs)])
    asks = []
    for _ in range(args.runs):
        assistant.session.history.clear()
        asks.append(assistant.ask("What is a nominee?", args.language)[1])
    results["ask"] = summarize(asks)

    out = ROOT / "benchmarks" / "results" / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(json.dumps(results, indent=2))
    print("\n| Stage | Median (s) | Min (s) | Max (s) | Runs |\n|---|---|---|---|---|")
    for stage in ("ocr", "explain", "ask"):
        r = results.get(stage, {})
        if "median_s" in r:
            print(f"| {stage} | {r['median_s']} | {r['min_s']} | {r['max_s']} | {r['runs']} |")
    print(f"\nModel: {results['model']}  |  saved to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
