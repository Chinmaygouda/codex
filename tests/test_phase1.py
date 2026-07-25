import os
import unittest
from unittest.mock import patch

from codecourt.agents import AgentLayer, MissingProviderKeyError
from codecourt.grounding import accepted_reviewer_findings, analyze_python
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


if __name__ == "__main__":
    unittest.main()
