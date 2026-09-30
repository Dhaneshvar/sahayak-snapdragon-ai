"""Optional offline read-aloud via the Windows speech engine (pyttsx3 -> SAPI5).

Hindi voices are available only if a Hindi speech pack is installed in
Windows Settings > Time & language > Speech.
"""
import threading


def available() -> bool:
    try:
        import pyttsx3  # noqa: F401
        return True
    except ImportError:
        return False


def speak_async(text: str) -> None:
    def run():
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    threading.Thread(target=run, daemon=True).start()
