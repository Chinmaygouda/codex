# Phase 5 self-review

## Checked

- Generator and Reviewer prompts remain the Section 6 text; later user prompts add
  grounding constraints without changing the system prompts.
- Static analyzer, XML configuration checker, and API-existence checker emit real,
  per-run evidence that is retained with the raw tool output.
- Scoring consumes only structured tool findings; it does not parse model prose for
  a pass/fail decision.
- SQLite persistence retains raw calls, evidence, findings, and only accepted Reviewer
  claims; dashboard routes are read-only.

## Fixed

- Reviewer claims now require an exact `(rule_id, severity, evidence_ref)` match to a
  real tool finding before acceptance or persistence. A matching evidence reference alone
  is no longer sufficient.
- Phase 1 now explicitly returns no findings when no tool evidence is available, rather
  than allowing ungrounded review assertions.
- Replaced a dynamic SQL query construction path with a fixed query map after Bandit
  identified it during the self-audit.
- Kept the subprocess-based Bandit adapter intentionally: it invokes a fixed executable
  argument list, uses no shell, writes only to a temporary directory, and has a timeout.
- Made the default SQLite path independent of the terminal working directory so an
  Antigravity-launched dashboard reads the same evidence store as the runner.
