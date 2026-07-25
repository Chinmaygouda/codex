"""Phase 2: run a grounded Generator/Reviewer round against real tool evidence."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .agents import AgentCall, AgentLayer
from .grounding import ToolResult, accepted_reviewer_findings, analyze_python
from .sample import GENERATOR_TASK, VULNERABLE_XXE_SAMPLE

ARTIFACT_PATH = Path("artifacts/phase2-grounded-transcript.json")


@dataclass(frozen=True)
class GroundedRound:
    generator: AgentCall
    reviewer: AgentCall
    original_tools: ToolResult
    candidate_tools: ToolResult
    accepted_reviewer_findings: list[dict[str, object]]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def run_grounded_round(agent_layer: AgentLayer | None = None) -> GroundedRound:
    agents = agent_layer or AgentLayer()
    original_tools = analyze_python(VULNERABLE_XXE_SAMPLE, "original.py")
    generator = agents.generate(f"{GENERATOR_TASK}\n\n```python\n{VULNERABLE_XXE_SAMPLE}```")
    candidate_code = _first_python_block(generator.output) or VULNERABLE_XXE_SAMPLE
    candidate_tools = analyze_python(candidate_code, "generator_candidate.py")
    evidence = original_tools.evidence + candidate_tools.evidence
    reviewer_input = """Review the Generator response using only the evidence below.
Return JSON only with this shape:
{"findings":[{"severity":"high|medium|low","claim":"...","fix":"...","evidence_ref":"..."}]}
Every finding must cite exactly one evidence_ref from the supplied evidence. Do not include
judgment-only findings, and return an empty findings list if no evidence supports a claim.

Original code:
```python
%s```

Generator response:
%s

Evidence:
%s""" % (
        VULNERABLE_XXE_SAMPLE,
        generator.output,
        json.dumps([item.as_dict() for item in evidence], indent=2),
    )
    reviewer = agents.review(reviewer_input)
    accepted = accepted_reviewer_findings(reviewer.output, {item.evidence_ref for item in evidence})
    return GroundedRound(generator, reviewer, original_tools, candidate_tools, accepted)


def _first_python_block(text: str) -> str | None:
    match = re.search(r"```python\s*\n(.*?)```", text, flags=re.DOTALL)
    return match.group(1).strip() if match else None


def main() -> None:
    round_result = run_grounded_round()
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(round_result.as_dict(), indent=2), encoding="utf-8")
    print(f"Recorded grounded Phase 2 transcript: {ARTIFACT_PATH}")
    print(f"Accepted evidence-backed Reviewer findings: {len(round_result.accepted_reviewer_findings)}")


if __name__ == "__main__":
    main()
