import os
import unittest
from unittest.mock import patch

from codecourt.agents import AgentLayer, MissingProviderKeyError
from codecourt.grounding import accepted_reviewer_findings, analyze_python
from codecourt.grounding import Finding
from codecourt.rounds import adaptive_round_budget
from codecourt.scoring import score
from codecourt.prompts import GENERATOR_SYSTEM_PROMPT, REVIEWER_SYSTEM_PROMPT
from codecourt.sample import VULNERABLE_XXE_SAMPLE


class PhaseOneTests(unittest.TestCase):
    def test_seeded_sample_is_an_xxe_candidate(self) -> None:
        self.assertIn("resolve_entities=True", VULNERABLE_XXE_SAMPLE)
        self.assertIn("load_dtd=True", VULNERABLE_XXE_SAMPLE)

    def test_prompts_preserve_required_grounding_language(self) -> None:
        self.assertIn("Never claim an API", GENERATOR_SYSTEM_PROMPT)
        self.assertIn("Do not invent vulnerabilities", REVIEWER_SYSTEM_PROMPT)
        self.assertIn("tool-confirmed", REVIEWER_SYSTEM_PROMPT)

    def test_selected_provider_requires_an_api_key(self) -> None:
        original_key = os.environ.pop("OPENAI_API_KEY", None)
        original_gemini_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            with patch("codecourt.agents.load_dotenv"):
                with self.assertRaises(MissingProviderKeyError):
                    AgentLayer(provider="openai").generate("test")
        finally:
            if original_key is not None:
                os.environ["OPENAI_API_KEY"] = original_key
            if original_gemini_key is not None:
                os.environ["GEMINI_API_KEY"] = original_gemini_key

    def test_tool_layer_detects_unsafe_xml_configuration(self) -> None:
        result = analyze_python(VULNERABLE_XXE_SAMPLE)
        self.assertTrue(any(finding.rule_id == "CC-XXE-001" for finding in result.findings))
        self.assertTrue(any(item.tool == "bandit" for item in result.evidence))

    def test_api_checker_flags_a_referenced_missing_api(self) -> None:
        result = analyze_python("from lxml import etree\netree.ImaginaryParser()\n")
        self.assertTrue(any(finding.rule_id == "CC-API-404" for finding in result.findings))

    def test_unsupported_reviewer_claim_is_not_accepted(self) -> None:
        raw = '{"findings":[{"claim":"unsupported","evidence_ref":"missing"}]}'
        self.assertEqual(accepted_reviewer_findings(raw, {"bandit:real"}), [])

    def test_supported_reviewer_claim_in_fenced_json_is_accepted(self) -> None:
        raw = '```json\n{"findings":[{"claim":"grounded","evidence_ref":"bandit:real"}]}\n```'
        self.assertEqual(
            accepted_reviewer_findings(raw, {"bandit:real"}),
            [{"claim":"grounded", "evidence_ref":"bandit:real"}],
        )

    def test_scoring_is_deterministic(self) -> None:
        finding = Finding("rule", "medium", "file.py", 1, "message", "tool", "evidence")
        self.assertEqual(score([finding]), score([finding]))
        self.assertEqual(score([finding]).gate, "pass")

    def test_critical_finding_escalates_immediately(self) -> None:
        finding = Finding("rule", "critical", "file.py", 1, "message", "tool", "evidence")
        outcome = score([finding])
        self.assertTrue(outcome.escalate)
        self.assertEqual(outcome.gate, "neutral")
        self.assertEqual(outcome.escalation_reason, "critical finding")

    def test_adaptive_round_budget_uses_documented_cap(self) -> None:
        self.assertEqual(adaptive_round_budget(10), 2)
        self.assertEqual(adaptive_round_budget(50), 4)
        self.assertEqual(adaptive_round_budget(101), 6)
        self.assertEqual(adaptive_round_budget(10, unresolved_critical_after_round_two=1), 6)


if __name__ == "__main__":
    unittest.main()
