"""Check that this machine is ready to run Sahayak on Snapdragon.

Run:  python scripts/check_env.py
"""
import importlib
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sahayak.config import Settings  # noqa: E402
from sahayak.llm import LLMError, build_llm  # noqa: E402

ok = True
print(f"Python {platform.python_version()} | machine={platform.machine()} | {platform.platform()}")
if platform.system() == "Windows" and platform.machine().upper() != "ARM64":
    print("  WARN: not ARM64 Python. On Snapdragon, install the ARM64 build from python.org "
          "for native speed (x64 Python runs under emulation).")

for mod, why in [("pypdf", "PDF text"), ("rapidocr_onnxruntime", "image OCR"),
                 ("onnxruntime", "OCR runtime"), ("pyttsx3", "read aloud (optional)")]:
    try:
        m = importlib.import_module(mod)
        print(f"  OK   {mod} {getattr(m, '__version__', '')} ({why})")
    except ImportError:
        print(f"  MISS {mod} ({why})")
        ok = ok and mod == "pyttsx3"

try:
    import onnxruntime as ort
    print("  ONNX Runtime providers:", ort.get_available_providers())
except ImportError:
    pass

try:
    llm = build_llm(Settings())
    models = llm.list_models()
    print(f"  LLM endpoint: {llm.base_url}")
    print(f"  Models served: {models or '(could not list)'}")
    print(f"  Selected: {llm.model_id}")
    if not any(k in llm.model_id.lower() for k in ("npu", "qnn")):
        print("  NOTE: selected model id does not mention NPU/QNN. Check 'foundry model list' "
              "for an NPU variant and confirm NPU activity in Task Manager.")
    reply, secs = llm.chat([{"role": "user", "content": "Reply with the single word: ready"}],
                           max_tokens=5)
    print(f"  Test reply: {reply!r} in {secs:.2f}s")
except LLMError as e:
    ok = False
    print("  FAIL LLM:", e)

print("\nRESULT:", "READY" if ok else "NOT READY - see messages above")
sys.exit(0 if ok else 1)
