"""Deterministic, side-effect-free risk scoring for CodeCourt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .grounding import Finding


@dataclass(frozen=True)
class ScoringPolicy:
    critical_weight: int = 100
    high_weight: int = 50
    medium_weight: int = 15
    low_weight: int = 5


@dataclass(frozen=True)
class ScoreOutcome:
    risk_score: int
    gate: str
    converged: bool
    escalate: bool
    escalation_reason: str | None
    unresolved_critical: int
    unresolved_high: int


DEFAULT_POLICY = ScoringPolicy()


def score(findings: Iterable[Finding], policy: ScoringPolicy = DEFAULT_POLICY) -> ScoreOutcome:
    """Return the same gate decision for the same structured findings and policy."""
    unresolved = tuple(finding for finding in findings if not finding.resolved)
    critical = sum(finding.severity.lower() == "critical" for finding in unresolved)
    high = sum(finding.severity.lower() == "high" for finding in unresolved)
    risk_score = sum(_weight(finding.severity, policy) for finding in unresolved)
    if critical:
        return ScoreOutcome(risk_score, "neutral", False, True, "critical finding", critical, high)
    if high:
        return ScoreOutcome(risk_score, "fail", False, False, None, critical, high)
    return ScoreOutcome(risk_score, "pass", True, False, None, critical, high)


def _weight(severity: str, policy: ScoringPolicy) -> int:
    return {
        "critical": policy.critical_weight,
        "high": policy.high_weight,
        "medium": policy.medium_weight,
        "low": policy.low_weight,
    }.get(severity.lower(), 0)
