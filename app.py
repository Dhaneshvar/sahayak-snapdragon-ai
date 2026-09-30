"""Sahayak desktop app (Tkinter - bundled with Python, no extra wheels needed).

Run:  python app.py
"""
from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from sahayak import tts
from sahayak.assistant import Assistant
from sahayak.config import Settings
from sahayak.documents import DocumentError, load_document
from sahayak.llm import LLMError, build_llm
from sahayak.ocr import OCRUnavailable

# Log events and timings only - never document text or answers.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sahayak")

FONT = ("Nirmala UI", 12)       # Windows font with Devanagari support
FONT_BOLD = ("Nirmala UI", 12, "bold")
FILETYPES = [("Forms", "*.pdf *.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff *.txt"),
             ("All files", "*.*")]


class SahayakApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sahayak - Private Offline Form Assistant")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.settings = Settings()
        self.assistant: Assistant | None = None
        self.results: queue.Queue = queue.Queue()
        self.busy = False
        self._build_ui()
        self.after(100, self._poll)
        self._run_bg(self._connect, "Connecting to on-device model...")

    # ---------- UI ----------
    def _build_ui(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="Open form...", command=self.open_form).pack(side="left")
        ttk.Label(top, text="  Language:").pack(side="left")
        self.lang = tk.StringVar(value="English")
        ttk.Combobox(top, textvariable=self.lang, values=["English", "Hindi"],
                     width=10, state="readonly").pack(side="left")
        ttk.Button(top, text="Explain", command=self.explain).pack(side="left", padx=4)
        ttk.Button(top, text="Field checklist", command=self.checklist).pack(side="left")
        self.speak_btn = ttk.Button(top, text="Read aloud", command=self.read_aloud,
                                    state="normal" if tts.available() else "disabled")
        self.speak_btn.pack(side="left", padx=4)
        ttk.Button(top, text="Wipe session", command=self.wipe).pack(side="right")

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=2)

        ttk.Label(left, text="Form text (you can correct OCR mistakes here)",
                  font=FONT_BOLD).pack(anchor="w")
        self.doc_box = tk.Text(left, wrap="word", font=FONT)
        self.doc_box.pack(fill="both", expand=True)

        ttk.Label(right, text="Sahayak", font=FONT_BOLD).pack(anchor="w")
        self.chat = tk.Text(right, wrap="word", font=FONT, state="disabled")
        self.chat.pack(fill="both", expand=True)
        ask = ttk.Frame(right)
        ask.pack(fill="x", pady=6)
        self.q = ttk.Entry(ask, font=FONT)
        self.q.pack(side="left", fill="x", expand=True)
        self.q.bind("<Return>", lambda _e: self.ask())
        ttk.Button(ask, text="Ask", command=self.ask).pack(side="left", padx=4)

        self.status = tk.StringVar(value="Starting...")
        ttk.Label(self, textvariable=self.status, anchor="w", padding=6,
                  relief="sunken").pack(fill="x", side="bottom")
        self.last_answer = ""

    def _say(self, who: str, text: str):
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{who}: {text}\n\n")
        self.chat.see("end")
        self.chat.configure(state="disabled")

    # ---------- background work ----------
    def _run_bg(self, fn, status: str):
        if self.busy:
            messagebox.showinfo("Sahayak", "Please wait - still working.")
            return
        self.busy = True
        self.status.set(status)

        def worker():
            try:
                self.results.put(("ok", fn()))
            except (LLMError, DocumentError, OCRUnavailable, ValueError, RuntimeError) as e:
                self.results.put(("err", str(e)))
            except Exception as e:  # last-resort guard so the UI never freezes
                log.exception("Unexpected error")
                self.results.put(("err", f"Unexpected error: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            kind, payload = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            if kind == "err":
                self.status.set("Error")
                messagebox.showerror("Sahayak", payload)
            elif callable(payload):
                payload()  # UI update closure, runs on the Tk thread
        self.after(100, self._poll)

    # ---------- actions ----------
    def _connect(self):
        llm = build_llm(self.settings)
        model = llm.model_id
        self.assistant = Assistant(llm)
        log.info("Connected to %s model=%s", llm.base_url, model)
        return lambda: self.status.set(f"Ready | model: {model} | endpoint: {llm.base_url}")

    def _require(self) -> bool:
        if not self.assistant:
            messagebox.showwarning("Sahayak", "The on-device model is not connected yet. "
                                   "Start it with 'foundry model run phi-3.5-mini'.")
            return False
        return True

    def _pane_text(self) -> str:
        """Read the (possibly user-corrected) form text. Call on the Tk thread only."""
        return self.doc_box.get("1.0", "end").strip()

    def _sync_doc(self, text: str):
        doc = self.assistant.session.document
        if not text or not doc:
            raise RuntimeError("Open a form first.")
        doc.text = text[: self.settings.max_document_chars]

    def open_form(self):
        path = filedialog.askopenfilename(title="Open form", filetypes=FILETYPES)
        if not path or not self._require():
            return

        def work():
            doc = load_document(path, self.settings.max_document_chars, self.settings.max_file_mb)
            log.info("Loaded document method=%s chars=%d secs=%.2f",
                     doc.method, len(doc.text), doc.seconds)

            def ui():
                self.assistant.load(doc)
                self.doc_box.delete("1.0", "end")
                self.doc_box.insert("1.0", doc.text)
                self.chat.configure(state="normal")
                self.chat.delete("1.0", "end")
                self.chat.configure(state="disabled")
                note = " (long document truncated)" if doc.truncated else ""
                self.status.set(f"Loaded {doc.source_name} via {doc.method} "
                                f"in {doc.seconds:.2f}s{note}")
            return ui
        self._run_bg(work, "Reading form on-device...")

    def explain(self):
        if not self._require():
            return
        lang, pane = self.lang.get(), self._pane_text()

        def work():
            self._sync_doc(pane)
            text, secs = self.assistant.explain(lang)
            log.info("explain secs=%.2f", secs)

            def ui():
                self.last_answer = text
                self._say("Sahayak", text)
                self.status.set(f"Explained in {secs:.2f}s")
            return ui
        self._run_bg(work, "Explaining...")

    def ask(self):
        if not self._require():
            return
        question, lang, pane = self.q.get().strip(), self.lang.get(), self._pane_text()
        if not question:
            return
        self.q.delete(0, "end")
        self._say("You", question)

        def work():
            self._sync_doc(pane)
            text, secs = self.assistant.ask(question, lang)
            log.info("ask secs=%.2f", secs)

            def ui():
                self.last_answer = text
                self._say("Sahayak", text)
                self.status.set(f"Answered in {secs:.2f}s")
            return ui
        self._run_bg(work, "Thinking...")

    def checklist(self):
        if not self._require():
            return
        pane = self._pane_text()

        def work():
            self._sync_doc(pane)
            data, secs = self.assistant.extract_fields()

            def ui():
                lines = []
                for f in data["fields"]:
                    if not isinstance(f, dict):
                        continue
                    mark = "*" if f.get("required") else " "
                    lines.append(f"[ ] {f.get('name', '?')}{mark} - {f.get('help', '')}")
                if data["documents_needed"]:
                    lines.append("\nKeep ready: " + ", ".join(map(str, data["documents_needed"])))
                self._say("Checklist (* = required)", "\n".join(lines) or "No fields found.")
                self.status.set(f"Checklist in {secs:.2f}s")
            return ui
        self._run_bg(work, "Building checklist...")

    def read_aloud(self):
        if self.last_answer:
            tts.speak_async(self.last_answer)

    def wipe(self):
        if self.assistant:
            self.assistant.session.wipe()
        self.doc_box.delete("1.0", "end")
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        self.last_answer = ""
        self.status.set("Session wiped - nothing kept in memory.")


if __name__ == "__main__":
    SahayakApp().mainloop()
