# CodeCourt MVP Plan

## Summary

Build a local-first Python MVP using FastAPI, SQLite, Jinja templates, Bandit,
and the OpenAI Python SDK. The core demo evaluates a seeded Python XXE
vulnerability through a grounded Generator/Reviewer debate.

## Phase 0 — Plan

- Commit this planning artifact before implementation begins.

## Phase 1 — Single-round core loop

- Implement Generator and Reviewer API wrappers with the Section 6 system
  prompts stored verbatim.
- Run one debate round against a hardcoded vulnerable Python XML parser; log
  prompts, responses, and transcript.
- Demonstrate locally, self-review, and commit.

## Phase 2 — Grounding

- Run Bandit against the candidate code and normalize findings.
- Add Python API-existence checks using AST reference extraction plus
  installed-package/runtime introspection.
- Supply tool evidence to the Reviewer; only persist Reviewer findings that
  cite a matching evidence reference.
- Demonstrate, self-review, and commit.

## Phase 3 — Rounds and deterministic scoring

- Add the prescribed round loop, adaptive budget, critical-finding escalation,
  and convergence checks.
- Implement a side-effect-free scorer that consumes structured findings and
  policy to produce a risk score, gate result, and escalation reason.
- Demonstrate, self-review, and commit.

## Phase 4 — Evidence and dashboard

- Add append-only SQLite tables for runs, rounds, raw agent calls, evidence,
  findings, and metrics.
- Build a minimal read-only FastAPI dashboard for a run transcript, evidence
  links, and risk score.
- Demonstrate, self-review, and commit.

## Phase 5 — End-to-end self-review

- Audit every persisted Reviewer finding for real supporting tool evidence;
  fix any gap.
- Record checks and fixes in `NOTES.md`, then commit.

## MVP boundaries

- Included: one Python XXE scenario, Generator/Reviewer roles, Bandit evidence,
  API-existence evidence, deterministic scoring, capped rounds, SQLite
  persistence, and a local dashboard.
- Stretch after MVP: additional reviewer personas, blast-radius weighting,
  sandbox containers, regression-trend charts, GitHub Check Runs, deployment,
  and additional vulnerability samples.

## Key interfaces

- `Finding`: normalized `{rule_id, severity, file, line, message, source,
  evidence_ref, resolved}`.
- `Evidence`: immutable tool execution record containing command/tool,
  timestamp, output, and run/round linkage.
- `score(findings, policy)`: pure function returning risk score,
  pass/fail/neutral decision, and escalation state.
- Reviewer output is advisory only; structured tool findings and the scorer
  determine the gate.

## Test plan

- Bandit detects the seeded XXE issue and the evidence is visible to the
  Reviewer.
- A deliberately invented Python API is detected by the API checker.
- Unsupported Reviewer claims are rejected from scored findings.
- Scorer output is identical for identical structured inputs.
- Critical findings escalate immediately; unresolved critical findings also
  escalate by round four; normal unresolved findings stop at the budget cap.
- Dashboard displays the saved transcript, tool evidence, and final risk score.

## Assumptions

- OpenAI credentials are provided through environment variables when live agent
  calls are demonstrated.
- The MVP runs locally; no CI, deployment, or GitHub integration is added
  before the core loop is complete.
- Each phase ends with a focused commit and documented self-review.
