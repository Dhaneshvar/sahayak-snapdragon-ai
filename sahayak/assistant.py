"""Conversation logic: explain, answer questions, extract a field checklist."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from . import prompts
from .documents import LoadedDocument

MAX_HISTORY_TURNS = 4  # keep context small for a 3-4B on-device model


@dataclass
class Session:
    document: LoadedDocument | None = None
    history: list = field(default_factory=list)
    fields: dict | None = None

    def wipe(self) -> None:
        """Clear everything in memory. Sahayak writes no document data to disk."""
        self.document = None
        self.history.clear()
        self.fields = None


def parse_json_object(text: str) -> dict:
    """Extract the first JSON object from model output (models sometimes add prose)."""
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object in model output")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("Unbalanced JSON in model output")


class Assistant:
    def __init__(self, llm):
        self.llm = llm
        self.session = Session()

    def load(self, document: LoadedDocument) -> None:
        self.session.wipe()
        self.session.document = document

    def _doc(self) -> str:
        if not self.session.document:
            raise RuntimeError("Open a form first.")
        return self.session.document.text

    def explain(self, language: str = "English") -> tuple[str, float]:
        msgs = [{"role": "system", "content": prompts.SYSTEM},
                {"role": "user", "content": prompts.explain(self._doc(), language)}]
        return self.llm.chat(msgs, max_tokens=500)

    def ask(self, user_question: str, language: str = "English") -> tuple[str, float]:
        if not user_question.strip():
            raise ValueError("Please type a question.")
        msgs = [{"role": "system", "content": prompts.SYSTEM}]
        msgs += self.session.history[-2 * MAX_HISTORY_TURNS:]
        msgs.append({"role": "user",
                     "content": prompts.question(self._doc(), user_question, language)})
        reply, secs = self.llm.chat(msgs, max_tokens=300)
        # Store only the short question, not the whole document, to keep context small.
        self.session.history += [{"role": "user", "content": user_question.strip()},
                                 {"role": "assistant", "content": reply}]
        return reply, secs

    def extract_fields(self) -> tuple[dict, float]:
        msgs = [{"role": "system", "content": prompts.SYSTEM},
                {"role": "user", "content": prompts.fields(self._doc())}]
        raw, secs = self.llm.chat(msgs, temperature=0.0, max_tokens=700)
        data = parse_json_object(raw)
        if not isinstance(data.get("fields", []), list):
            raise ValueError("Model returned 'fields' in an unexpected format")
        data.setdefault("fields", [])
        data.setdefault("documents_needed", [])
        self.session.fields = data
        return data, secs
