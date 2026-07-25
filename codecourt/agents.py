"""Thin OpenAI Responses API wrapper for the Generator and Reviewer roles."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from .prompts import GENERATOR_SYSTEM_PROMPT, REVIEWER_SYSTEM_PROMPT

DEFAULT_OPENAI_MODEL = "gpt-5.6-sol"
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"


class MissingProviderKeyError(RuntimeError):
    """Raised before a live debate when the selected provider lacks a key."""


@dataclass(frozen=True)
class AgentCall:
    role: str
    system_prompt: str
    input: str
    output: str
    raw_response: dict[str, Any]
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentLayer:
    """Runs role-specific calls and retains the complete API response for audit."""

    def __init__(
        self,
        model: str | None = None,
        client: OpenAI | None = None,
        provider: str | None = None,
    ) -> None:
        load_dotenv()
        self._provider = provider or os.getenv("CODECOURT_PROVIDER") or self._default_provider()
        if self._provider not in {"openai", "gemini"}:
            raise ValueError("CODECOURT_PROVIDER must be 'openai' or 'gemini'.")
        self._model = model or self._default_model(self._provider)
        self._client = client

    def generate(self, prompt: str) -> AgentCall:
        return self._call("generator", GENERATOR_SYSTEM_PROMPT, prompt)

    def review(self, prompt: str) -> AgentCall:
        return self._call("reviewer", REVIEWER_SYSTEM_PROMPT, prompt)

    def _call(self, role: str, system_prompt: str, prompt: str) -> AgentCall:
        if self._provider == "gemini":
            output, raw_response = self._call_gemini(system_prompt, prompt)
        else:
            output, raw_response = self._call_openai(system_prompt, prompt)
        return AgentCall(
            role=role,
            system_prompt=system_prompt,
            input=prompt,
            output=output,
            raw_response=raw_response,
            created_at=datetime.now(UTC).isoformat(),
        )

    def _call_openai(self, system_prompt: str, prompt: str) -> tuple[str, dict[str, Any]]:
        client = self._client or self._openai_client()
        response = client.responses.create(
            model=self._model,
            instructions=system_prompt,
            input=prompt,
            store=False,
        )
        return response.output_text, json.loads(response.model_dump_json())

    def _call_gemini(self, system_prompt: str, prompt: str) -> tuple[str, dict[str, Any]]:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise MissingProviderKeyError("GEMINI_API_KEY is required for the Gemini provider.")
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
        raw_json = response.model_dump_json()
        return response.text or "", json.loads(raw_json)

    @staticmethod
    def _openai_client() -> OpenAI:
        if not os.getenv("OPENAI_API_KEY"):
            raise MissingProviderKeyError(
                "OPENAI_API_KEY is required for a live CodeCourt debate. "
                "Set it in the environment and run the command again."
            )
        return OpenAI()

    @staticmethod
    def _default_provider() -> str:
        return "gemini" if os.getenv("GEMINI_API_KEY") else "openai"

    @staticmethod
    def _default_model(provider: str) -> str:
        return DEFAULT_GEMINI_MODEL if provider == "gemini" else DEFAULT_OPENAI_MODEL
