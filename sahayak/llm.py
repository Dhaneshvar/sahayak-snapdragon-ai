"""Minimal client for a *local* OpenAI-compatible chat endpoint.

Primary target: Microsoft Foundry Local, which selects the Qualcomm QNN (NPU)
variant of a model on Snapdragon X PCs when one exists. Also works with Ollama
for development. Standard library only, so no extra wheels are needed on
Windows ARM64.
"""
from __future__ import annotations

import ipaddress
import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


class LLMError(RuntimeError):
    pass


def is_loopback_url(url: str) -> bool:
    host = urllib.parse.urlparse(url).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def discover_foundry_endpoint(timeout_s: int = 20) -> str | None:
    """Ask the Foundry Local CLI where its service is listening."""
    try:
        proc = subprocess.run(["foundry", "service", "status"], capture_output=True,
                              text=True, timeout=timeout_s)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    match = re.search(r"https?://(?:127\.0\.0\.1|localhost):\d+", proc.stdout + proc.stderr)
    return match.group(0) if match else None


def pick_model(available: list[str], hint: str) -> str:
    """Choose the model id that best matches the hint, preferring NPU variants."""
    if not available or hint in available:
        return hint
    key = hint.lower()
    matches = [m for m in available if key in m.lower()] or available
    npu = [m for m in matches if "npu" in m.lower() or "qnn" in m.lower()]
    return (npu or matches)[0]


class LocalLLM:
    def __init__(self, base_url: str, model_hint: str, allow_remote: bool = False,
                 timeout_s: int = 180):
        base_url = base_url.strip().rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        if not base_url.startswith(("http://", "https://")):
            raise LLMError(f"Invalid endpoint URL: {base_url!r}")
        if not allow_remote and not is_loopback_url(base_url):
            raise LLMError("Refusing non-local LLM endpoint (privacy guard). "
                           "Set SAHAYAK_ALLOW_REMOTE=1 only for development.")
        self.base_url = base_url
        self.model_hint = model_hint
        self.timeout_s = timeout_s
        self._model_id: str | None = None

    def _call(self, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            self.base_url + path, data=data, method="POST" if data else "GET",
            headers={"Content-Type": "application/json", "Authorization": "Bearer local"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            raise LLMError(f"LLM endpoint returned HTTP {e.code}: {body}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise LLMError(f"Cannot reach local LLM at {self.base_url}: {e}") from e
        except json.JSONDecodeError as e:
            raise LLMError("LLM endpoint returned invalid JSON") from e

    def list_models(self) -> list[str]:
        try:
            return [m["id"] for m in self._call("/v1/models").get("data", []) if "id" in m]
        except LLMError:
            return []

    @property
    def model_id(self) -> str:
        if self._model_id is None:
            self._model_id = pick_model(self.list_models(), self.model_hint)
        return self._model_id

    def chat(self, messages: list[dict], temperature: float = 0.2,
             max_tokens: int = 700) -> tuple[str, float]:
        """Return (reply_text, seconds_elapsed)."""
        start = time.perf_counter()
        out = self._call("/v1/chat/completions", {
            "model": self.model_id, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens, "stream": False})
        elapsed = time.perf_counter() - start
        try:
            text = out["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError("Unexpected response shape from LLM endpoint") from e
        return text.strip(), elapsed


def build_llm(settings) -> LocalLLM:
    base = settings.llm_base_url or discover_foundry_endpoint()
    if not base:
        raise LLMError("No local LLM endpoint found. Start one with "
                       "'foundry model run phi-3.5-mini' or set SAHAYAK_LLM_BASE_URL.")
    return LocalLLM(base, settings.llm_model, settings.allow_remote, settings.llm_timeout_s)
