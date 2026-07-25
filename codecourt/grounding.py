"""Tool-backed grounding for CodeCourt reviews."""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    file: str
    line: int
    message: str
    source: str
    evidence_ref: str
    resolved: bool = False

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ToolEvidence:
    evidence_ref: str
    tool: str
    command: tuple[str, ...]
    output: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ToolResult:
    findings: tuple[Finding, ...]
    evidence: tuple[ToolEvidence, ...]


def analyze_python(code: str, filename: str = "candidate.py") -> ToolResult:
    """Run real analyzer output plus deterministic source/API checks."""
    bandit_findings, bandit_evidence = _run_bandit(code, filename)
    xxe_findings, xxe_evidence = _check_xml_parser_configuration(code, filename)
    api_findings, api_evidence = _check_referenced_apis(code, filename)
    return ToolResult(
        findings=tuple(bandit_findings + xxe_findings + api_findings),
        evidence=tuple(bandit_evidence + xxe_evidence + api_evidence),
    )


def _run_bandit(code: str, filename: str) -> tuple[list[Finding], list[ToolEvidence]]:
    with tempfile.TemporaryDirectory(prefix="codecourt-bandit-") as directory:
        target = Path(directory) / filename
        target.write_text(code, encoding="utf-8")
        command = (sys.executable, "-m", "bandit", "-f", "json", "-q", str(target))
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    output = completed.stdout or completed.stderr
    evidence_ref = _evidence_ref("bandit", output)
    evidence = ToolEvidence(evidence_ref, "bandit", command, output)
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        payload = {"results": []}
    findings = [
        Finding(
            rule_id=item["test_id"],
            severity=item["issue_severity"].lower(),
            file=filename,
            line=item["line_number"],
            message=item["issue_text"],
            source="bandit",
            evidence_ref=evidence_ref,
        )
        for item in payload.get("results", [])
    ]
    return findings, [evidence]


def _check_xml_parser_configuration(code: str, filename: str) -> tuple[list[Finding], list[ToolEvidence]]:
    tree = ast.parse(code, filename=filename)
    unsafe_calls: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_xml_parser(node.func):
            continue
        keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
        unsafe = (
            _literal_bool(keywords.get("resolve_entities")) is True
            or _literal_bool(keywords.get("load_dtd")) is True
            or _literal_bool(keywords.get("no_network")) is False
        )
        if unsafe:
            unsafe_calls.append(node.lineno)
    output = json.dumps({"unsafe_xml_parser_lines": unsafe_calls}, sort_keys=True)
    evidence_ref = _evidence_ref("xml-parser-check", output)
    evidence = ToolEvidence(
        evidence_ref,
        "xml-parser-check",
        ("python-ast", "XMLParser keyword configuration"),
        output,
    )
    findings = [
        Finding(
            rule_id="CC-XXE-001",
            severity="high",
            file=filename,
            line=line,
            message=(
                "XMLParser enables external entities, DTD loading, or network access; "
                "untrusted XML may permit XXE or SSRF."
            ),
            source="xml-parser-check",
            evidence_ref=evidence_ref,
        )
        for line in unsafe_calls
    ]
    return findings, [evidence]


def _check_referenced_apis(code: str, filename: str) -> tuple[list[Finding], list[ToolEvidence]]:
    tree = ast.parse(code, filename=filename)
    imports = _import_bindings(tree)
    missing: list[tuple[str, int]] = []
    checked: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
            continue
        module_name = imports.get(node.value.id)
        if not module_name:
            continue
        qualified_name = f"{module_name}.{node.attr}"
        checked.append(qualified_name)
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            missing.append((qualified_name, node.lineno))
            continue
        if not hasattr(module, node.attr):
            missing.append((qualified_name, node.lineno))
    output = json.dumps({"checked": sorted(set(checked)), "missing": missing}, sort_keys=True)
    evidence_ref = _evidence_ref("api-existence-check", output)
    evidence = ToolEvidence(
        evidence_ref,
        "api-existence-check",
        ("python-importlib", "AST attribute references"),
        output,
    )
    findings = [
        Finding(
            rule_id="CC-API-404",
            severity="high",
            file=filename,
            line=line,
            message=f"Referenced API does not exist: {qualified_name}",
            source="api-existence-check",
            evidence_ref=evidence_ref,
        )
        for qualified_name, line in missing
    ]
    return findings, [evidence]


def _import_bindings(tree: ast.AST) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bindings[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                bindings[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return bindings


def _is_xml_parser(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "XMLParser"


def _literal_bool(node: ast.expr | None) -> bool | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, bool) else None


def _evidence_ref(tool: str, output: str) -> str:
    digest = hashlib.sha256(output.encode("utf-8")).hexdigest()[:12]
    return f"{tool}:{digest}"


def accepted_reviewer_findings(raw_review: str, evidence_refs: set[str]) -> list[dict[str, Any]]:
    """Keep only structured Reviewer claims that cite evidence from this run."""
    try:
        payload = json.loads(raw_review)
    except json.JSONDecodeError:
        match = re.search(r"```json\s*(.*?)```", raw_review, flags=re.DOTALL)
        if not match:
            return []
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []
    findings = payload.get("findings", []) if isinstance(payload, dict) else []
    return [
        finding
        for finding in findings
        if isinstance(finding, dict)
        and isinstance(finding.get("evidence_ref"), str)
        and finding["evidence_ref"] in evidence_refs
    ]
