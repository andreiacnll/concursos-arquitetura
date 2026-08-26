from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProviderError(RuntimeError):
    """Erro técnico que deve ativar o fallback determinístico."""


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
