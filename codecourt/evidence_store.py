"""Append-only SQLite storage for CodeCourt runs and their grounding evidence."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from .rounds import DebateResult

DEFAULT_DATABASE_PATH = Path("data/codecourt.sqlite3")


class EvidenceStore:
    def __init__(self, database_path: Path = DEFAULT_DATABASE_PATH) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(database_path)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        self._connection.close()

    def record_debate(
        self,
        result: DebateResult,
        pr_id: str = "local-xxe-demo",
        model_version: str = "configured-provider",
        prompt_version: str = "section-6-verbatim-v1",
    ) -> str:
        run_id = str(uuid.uuid4())
        with self._connection:
            self._connection.execute(
                """INSERT INTO runs(run_id, pr_id, gate, risk_score, escalation_reason, model_version, prompt_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    pr_id,
                    result.final_score.gate,
                    result.final_score.risk_score,
                    result.escalation_reason,
                    model_version,
                    prompt_version,
                ),
            )
            for record in result.rounds:
                self._connection.execute(
                    """INSERT INTO rounds(run_id, round_number, gate, risk_score, escalation_reason)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        run_id,
                        record.round_number,
                        record.score.gate,
                        record.score.risk_score,
                        record.score.escalation_reason,
                    ),
                )
                for call in (record.generator, record.reviewer):
                    self._connection.execute(
                        """INSERT INTO agent_calls(run_id, round_number, actor, system_prompt, input, output, raw_response)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            run_id,
                            record.round_number,
                            call.role,
                            call.system_prompt,
                            call.input,
                            call.output,
                            json.dumps(call.raw_response),
                        ),
                    )
                for evidence in record.tool_result.evidence:
                    self._connection.execute(
                        """INSERT INTO evidence(run_id, round_number, evidence_ref, tool, command, output)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            run_id,
                            record.round_number,
                            evidence.evidence_ref,
                            evidence.tool,
                            json.dumps(evidence.command),
                            evidence.output,
                        ),
                    )
                for finding in record.tool_result.findings:
                    self._connection.execute(
                        """INSERT INTO findings(run_id, round_number, rule_id, severity, file, line, message,
                                                source, evidence_ref, resolved)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            run_id,
                            record.round_number,
                            finding.rule_id,
                            finding.severity,
                            finding.file,
                            finding.line,
                            finding.message,
                            finding.source,
                            finding.evidence_ref,
                            finding.resolved,
                        ),
                    )
                for claim in record.accepted_reviewer_findings:
                    self._connection.execute(
                        """INSERT INTO reviewer_claims(run_id, round_number, actor, claim, evidence_ref, resolved)
                           VALUES (?, ?, 'reviewer', ?, ?, 0)""",
                        (run_id, record.round_number, claim.get("claim", ""), claim["evidence_ref"]),
                    )
            self._connection.execute(
                """INSERT INTO metrics(run_id, pr_id, model_version, prompt_version, risk_score, gate)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (run_id, pr_id, model_version, prompt_version, result.final_score.risk_score, result.final_score.gate),
            )
        return run_id

    def list_runs(self) -> list[sqlite3.Row]:
        return self._connection.execute(
            "SELECT * FROM runs ORDER BY created_at DESC"
        ).fetchall()

    def get_run(self, run_id: str) -> sqlite3.Row | None:
        return self._connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()

    def run_details(self, run_id: str) -> dict[str, list[sqlite3.Row]]:
        queries = {
            "rounds": "SELECT * FROM rounds WHERE run_id = ? ORDER BY round_number, id",
            "agent_calls": "SELECT * FROM agent_calls WHERE run_id = ? ORDER BY round_number, id",
            "evidence": "SELECT * FROM evidence WHERE run_id = ? ORDER BY round_number, id",
            "findings": "SELECT * FROM findings WHERE run_id = ? ORDER BY round_number, id",
            "reviewer_claims": "SELECT * FROM reviewer_claims WHERE run_id = ? ORDER BY round_number, id",
        }
        return {
            table: self._connection.execute(query, (run_id,)).fetchall()
            for table, query in queries.items()
        }

    def _initialize(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY, pr_id TEXT NOT NULL, gate TEXT NOT NULL, risk_score INTEGER NOT NULL,
                escalation_reason TEXT, model_version TEXT NOT NULL, prompt_version TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS rounds (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, round_number INTEGER NOT NULL, gate TEXT NOT NULL,
                risk_score INTEGER NOT NULL, escalation_reason TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            CREATE TABLE IF NOT EXISTS agent_calls (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, round_number INTEGER NOT NULL, actor TEXT NOT NULL,
                system_prompt TEXT NOT NULL, input TEXT NOT NULL, output TEXT NOT NULL, raw_response TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, round_number INTEGER NOT NULL, evidence_ref TEXT NOT NULL,
                tool TEXT NOT NULL, command TEXT NOT NULL, output TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, round_number INTEGER NOT NULL, rule_id TEXT NOT NULL,
                severity TEXT NOT NULL, file TEXT NOT NULL, line INTEGER NOT NULL, message TEXT NOT NULL,
                source TEXT NOT NULL, evidence_ref TEXT NOT NULL, resolved INTEGER NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            CREATE TABLE IF NOT EXISTS reviewer_claims (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, round_number INTEGER NOT NULL, actor TEXT NOT NULL,
                claim TEXT NOT NULL, evidence_ref TEXT NOT NULL, resolved INTEGER NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, pr_id TEXT NOT NULL, model_version TEXT NOT NULL,
                prompt_version TEXT NOT NULL, risk_score INTEGER NOT NULL, gate TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            """
        )
        for table in ("runs", "rounds", "agent_calls", "evidence", "findings", "reviewer_claims", "metrics"):
            self._connection.executescript(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table}_immutable_update
                BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'append-only table'); END;
                CREATE TRIGGER IF NOT EXISTS {table}_immutable_delete
                BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'append-only table'); END;
                """
            )
