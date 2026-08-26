from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .provider import LLMProvider, LLMProviderError


class OllamaProvider(LLMProvider):
    def __init__(self) -> None:
        self.enabled = os.getenv("OLLAMA_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
        self.base_url = os.getenv("OLLAMA_BASE_URL", "").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "")
        timeout_value = os.getenv("OLLAMA_TIMEOUT_SECONDS", "")
        self.timeout = float(timeout_value) if timeout_value else 0.0

    def generate(self, payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise LLMProviderError("ollama_disabled")
        if not self.base_url or not self.model or self.timeout <= 0:
            raise LLMProviderError("ollama_configuration_incomplete")
        body = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "messages": [{"role": "system", "content": payload["system"]},
                          {"role": "user", "content": payload["user"]}],
            "options": {"temperature": 0},
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMProviderError(str(exc)) from exc
        # Never persist thinking or metrics: only message.content.
        if not isinstance(result, dict):
            raise LLMProviderError("ollama_response_not_object")
        content = ((result.get("message") or {}).get("content"))
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError("ollama_missing_message_content")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("ollama_invalid_content_json") from exc
        if not isinstance(parsed, dict):
            raise LLMProviderError("ollama_content_not_object")
        return parsed
    def generate_text(self, system: str, user: str) -> str:
        """Gera texto simples com a mesma configuracao opcional do provider."""
        if not self.enabled:
            raise LLMProviderError("ollama_disabled")
        if not self.base_url or not self.model or self.timeout <= 0:
            raise LLMProviderError("ollama_configuration_incomplete")
        body = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0},
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMProviderError(str(exc)) from exc
        if not isinstance(result, dict):
            raise LLMProviderError("ollama_response_not_object")
        content = ((result.get("message") or {}).get("content"))
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError("ollama_missing_message_content")
        return content.strip()
