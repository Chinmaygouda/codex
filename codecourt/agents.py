"""Thin OpenAI Responses API wrapper for the Generator and Reviewer roles."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from openai import OpenAI

from .prompts import GENERATOR_SYSTEM_PROMPT, REVIEWER_SYSTEM_PROMPT

DEFAULT_MODEL = "gpt-5.6-sol"


class MissingOpenAIKeyError(RuntimeError):
    """Raised before a live debate when the required credential is absent."""


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

    def __init__(self, model: str = DEFAULT_MODEL, client: OpenAI | None = None) -> None:
        self._model = model
        self._client = client

    def generate(self, prompt: str) -> AgentCall:
        return self._call("generator", GENERATOR_SYSTEM_PROMPT, prompt)

    def review(self, prompt: str) -> AgentCall:
        return self._call("reviewer", REVIEWER_SYSTEM_PROMPT, prompt)

    def _call(self, role: str, system_prompt: str, prompt: str) -> AgentCall:
        client = self._client or self._live_client()
        response = client.responses.create(
            model=self._model,
            instructions=system_prompt,
            input=prompt,
            store=False,
        )
        raw_response = json.loads(response.model_dump_json())
        return AgentCall(
            role=role,
            system_prompt=system_prompt,
            input=prompt,
            output=response.output_text,
            raw_response=raw_response,
            created_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def _live_client() -> OpenAI:
        if not os.getenv("OPENAI_API_KEY"):
            raise MissingOpenAIKeyError(
                "OPENAI_API_KEY is required for a live CodeCourt debate. "
                "Set it in the environment and run the command again."
            )
        return OpenAI()
