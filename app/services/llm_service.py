# services/llm_service.py
#
# Single access point for all LLM calls across every node.
#
# Responsibilities:
#   - Provider abstraction: swap Google / OpenAI / Anthropic via config.
#   - Retry with exponential back-off on transient errors.
#   - Per-call cost + latency tracking (emitted as structured log events).
#   - Fallback chain: primary model → fallback model → raises LLMUnavailable.
#   - Thread-safe singleton via module-level instance.

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LLMUnavailable(RuntimeError):
    """Raised when all models in the fallback chain fail."""


# ---------------------------------------------------------------------------
# Token cost table  (USD per 1 k tokens, input / output)
# Update whenever pricing changes.
# ---------------------------------------------------------------------------

_COST_TABLE: Dict[str, Dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.000_075, "output": 0.000_300},
    "gemini-2.5-flash-lite":   {"input": 0.001_250, "output": 0.005_000},
}

_DEFAULT_PRIMARY  = os.getenv("LLM_PRIMARY_MODEL",  "gemini-2.5-flash")
_DEFAULT_FALLBACK = os.getenv("LLM_FALLBACK_MODEL", "gemini-2.5-flash-lite")


# ---------------------------------------------------------------------------
# LLMService
# ---------------------------------------------------------------------------

class LLMService:
    """
    Usage
    -----
    from services.llm_service import llm_service

    response = llm_service.invoke(
        prompt="...",
        node_name="UserContextBuilder",
    )
    text = response.content
    """

    def __init__(
        self,
        primary_model: str = _DEFAULT_PRIMARY,
        fallback_model: str = _DEFAULT_FALLBACK,
        temperature: float = 0.0,
        max_retries: int = 3,
    ) -> None:
        self._primary_model_name  = primary_model
        self._fallback_model_name = fallback_model
        self._temperature  = temperature
        self._max_retries  = max_retries

        self._primary  = self._build_model(primary_model)
        self._fallback = self._build_model(fallback_model)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def invoke(
        self,
        prompt: str,
        node_name: str = "unknown",
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BaseMessage:
        """
        Invoke the primary model with automatic retry and fallback.
        Logs cost + latency as structured events.
        """
        try:
            return self._invoke_with_retry(
                self._primary, self._primary_model_name, prompt, node_name, user_id, metadata
            )
        except Exception as primary_err:
            log.warning(
                "llm.primary_failed",
                node=node_name,
                model=self._primary_model_name,
                error=str(primary_err),
            )
            try:
                return self._invoke_with_retry(
                    self._fallback, self._fallback_model_name, prompt, node_name, user_id, metadata
                )
            except Exception as fallback_err:
                log.error(
                    "llm.fallback_failed",
                    node=node_name,
                    model=self._fallback_model_name,
                    error=str(fallback_err),
                )
                raise LLMUnavailable(
                    f"All models failed for node '{node_name}'. "
                    f"Primary: {primary_err}. Fallback: {fallback_err}."
                ) from fallback_err

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _invoke_with_retry(
        self,
        model: BaseChatModel,
        model_name: str,
        prompt: str,
        node_name: str,
        user_id: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> BaseMessage:
        @retry(
            retry=retry_if_exception_type((TimeoutError, ConnectionError)),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            stop=stop_after_attempt(self._max_retries),
            reraise=True,
        )
        def _call() -> BaseMessage:
            t0 = time.perf_counter()
            response = model.invoke([HumanMessage(content=prompt)])
            latency_ms = (time.perf_counter() - t0) * 1000

            # Estimate token cost
            input_tokens  = len(prompt) // 4          # rough: 4 chars ≈ 1 token
            output_tokens = len(response.content) // 4
            cost = self._estimate_cost(model_name, input_tokens, output_tokens)

            log.info(
                "llm.call",
                node=node_name,
                model=model_name,
                user_id=user_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=round(latency_ms, 1),
                cost_usd=round(cost, 6),
                **(metadata or {}),
            )
            return response

        return _call()

    @staticmethod
    def _build_model(model_name: str) -> BaseChatModel:
        """Instantiate the right LangChain chat model from the model name."""
        if model_name.startswith("gemini"):
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model=model_name, temperature=0.0)
        elif model_name.startswith("gpt"):
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model_name, temperature=0.0)
        elif model_name.startswith("claude"):
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=model_name, temperature=0.0)
        else:
            raise ValueError(f"Unknown model prefix for '{model_name}'. "
                             "Add it to LLMService._build_model().")

    @staticmethod
    def _estimate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
        table = _COST_TABLE.get(model_name, {"input": 0.0, "output": 0.0})
        return (input_tokens * table["input"] + output_tokens * table["output"]) / 1000


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly in nodes
# ---------------------------------------------------------------------------

llm_service = LLMService()