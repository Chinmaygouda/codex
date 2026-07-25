"""Phase 4 runner: execute a debate, persist it, then serve the dashboard."""

from __future__ import annotations

import uvicorn

from .dashboard import create_app
from .evidence_store import DEFAULT_DATABASE_PATH, EvidenceStore
from .rounds import run_round_sequence


def main() -> None:
    result = run_round_sequence()
    store = EvidenceStore(DEFAULT_DATABASE_PATH)
    try:
        run_id = store.record_debate(result)
    finally:
        store.close()
    print(f"Stored CodeCourt run: {run_id}")
    print("Dashboard: http://127.0.0.1:8000")
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
