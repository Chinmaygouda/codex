"""Phase 1: execute and record one live Generator/Reviewer debate round."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .agents import AgentCall, AgentLayer, MissingOpenAIKeyError
from .sample import GENERATOR_TASK, VULNERABLE_XXE_SAMPLE

ARTIFACT_PATH = Path("artifacts/phase1-transcript.json")


@dataclass(frozen=True)
class SingleRoundTranscript:
    round_number: int
    sample_name: str
    generator: AgentCall
    reviewer: AgentCall

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def run_single_round(agent_layer: AgentLayer | None = None) -> SingleRoundTranscript:
    """Run the Phase 1 debate; evidence gathering begins in Phase 2."""
    agents = agent_layer or AgentLayer()
    generator_input = f"{GENERATOR_TASK}\n\n```python\n{VULNERABLE_XXE_SAMPLE}```"
    generator = agents.generate(generator_input)
    reviewer_input = (
        "Review this Generator response against the original code. Phase 1 has no "
        "tool output yet, so do not represent any claim as tool-confirmed.\n\n"
        f"Original code:\n```python\n{VULNERABLE_XXE_SAMPLE}```\n\n"
        f"Generator response:\n{generator.output}"
    )
    reviewer = agents.review(reviewer_input)
    return SingleRoundTranscript(
        round_number=1,
        sample_name="xxe-vulnerable-xml-parser",
        generator=generator,
        reviewer=reviewer,
    )


def save_transcript(transcript: SingleRoundTranscript, path: Path = ARTIFACT_PATH) -> Path:
    """Persist the complete raw exchange for the local Phase 1 demonstration."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(transcript.as_dict(), indent=2), encoding="utf-8")
    return path


def main() -> None:
    try:
        transcript = run_single_round()
    except MissingOpenAIKeyError as error:
        print(error)
        raise SystemExit(2) from error
    path = save_transcript(transcript)
    print(f"Recorded live Phase 1 debate transcript: {path}")
    print("\nReviewer response:\n")
    print(transcript.reviewer.output)


if __name__ == "__main__":
    main()
