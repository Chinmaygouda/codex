"""Phase 3 local runner for the deterministic scored round sequence."""

from __future__ import annotations

import json
from pathlib import Path

from .rounds import run_round_sequence

ARTIFACT_PATH = Path("artifacts/phase3-scored-debate.json")


def main() -> None:
    result = run_round_sequence()
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(result.as_dict(), indent=2), encoding="utf-8")
    print(f"Recorded Phase 3 debate: {ARTIFACT_PATH}")
    print(f"Rounds: {len(result.rounds)}")
    print(f"Gate: {result.final_score.gate}; risk score: {result.final_score.risk_score}")
    if result.escalation_reason:
        print(f"Escalation: {result.escalation_reason}")


if __name__ == "__main__":
    main()
