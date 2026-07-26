"""Round orchestration that combines agents, tools, and the pure scorer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Callable

from .agents import AgentCall, AgentLayer
from .grounding import Finding, ToolResult, accepted_reviewer_findings, analyze_python
from .phase2 import _first_python_block
from .sample import GENERATOR_TASK, VULNERABLE_XXE_SAMPLE
from .scoring import ScoreOutcome, score


def adaptive_round_budget(diff_lines: int, unresolved_critical_after_round_two: int = 0) -> int:
    """Allocate 2, 4, or 6 rounds from diff size; criticals receive the full cap."""
    if unresolved_critical_after_round_two:
        return 6
    if diff_lines <= 25:
        return 2
    if diff_lines <= 100:
        return 4
    return 6


@dataclass(frozen=True)
class RoundRecord:
    round_number: int
    generator: AgentCall
    reviewer: AgentCall
    tool_result: ToolResult
    score: ScoreOutcome
    accepted_reviewer_findings: list[dict[str, object]]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DebateResult:
    rounds: tuple[RoundRecord, ...]
    final_score: ScoreOutcome
    escalation_reason: str | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def run_round_sequence(
    agent_layer: AgentLayer | None = None,
    code: str = VULNERABLE_XXE_SAMPLE,
    analyzer: Callable[[str, str], ToolResult] = analyze_python,
) -> DebateResult:
    """Run generator → tools → reviewer → pure score until convergence or escalation."""
    agents = agent_layer or AgentLayer()
    current_code = code
    budget = adaptive_round_budget(len(code.splitlines()))
    records: list[RoundRecord] = []
    for round_number in range(1, budget + 1):
        generator = agents.generate(_generator_input(current_code, records))
        candidate_code = _first_python_block(generator.output) or current_code
        tool_result = analyzer(candidate_code, f"round_{round_number}_candidate.py")
        reviewer = agents.review(_reviewer_input(candidate_code, generator.output, tool_result))
        accepted = accepted_reviewer_findings(reviewer.output, tool_result.findings)
        outcome = score(tool_result.findings)
        record = RoundRecord(round_number, generator, reviewer, tool_result, outcome, accepted)
        records.append(record)
        if outcome.converged:
            return DebateResult(tuple(records), outcome, None)
        if outcome.escalate:
            return DebateResult(tuple(records), outcome, outcome.escalation_reason)
        if round_number == budget:
            capped = ScoreOutcome(
                risk_score=outcome.risk_score,
                gate="neutral",
                converged=False,
                escalate=True,
                escalation_reason="round budget exhausted",
                unresolved_critical=outcome.unresolved_critical,
                unresolved_high=outcome.unresolved_high,
            )
            records[-1] = RoundRecord(
                record.round_number,
                record.generator,
                record.reviewer,
                record.tool_result,
                capped,
                record.accepted_reviewer_findings,
            )
            return DebateResult(tuple(records), capped, capped.escalation_reason)
        current_code = candidate_code
    raise AssertionError("round budget must be positive")


def _generator_input(code: str, records: list[RoundRecord]) -> str:
    if not records:
        return f"{GENERATOR_TASK}\n\n```python\n{code}```"
    prior = records[-1]
    outstanding = [finding.as_dict() for finding in prior.tool_result.findings if not finding.resolved]
    return (
        "Patch the code below to resolve these tool-backed findings. Return a complete Python "
        "code block and a regression test.\n\n"
        f"Outstanding findings: {json.dumps(outstanding)}\n\n```python\n{code}```"
    )


def _reviewer_input(code: str, generator_output: str, tool_result: ToolResult) -> str:
    return """Review the Generator response using only this round's tool evidence.
Return JSON only:
{"findings":[{"rule_id":"...","severity":"high|medium|low","claim":"...","fix":"...","evidence_ref":"..."}]}
Every finding must exactly match a supplied tool finding's rule_id, severity, and evidence_ref.
Do not include judgment-only findings.

Candidate code:
```python
%s```

Generator response:
%s

Evidence:
%s""" % (code, generator_output, json.dumps([item.as_dict() for item in tool_result.evidence], indent=2))
