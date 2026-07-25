import os
import unittest
from unittest.mock import patch

from codecourt.agents import AgentLayer, MissingProviderKeyError
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


if __name__ == "__main__":
    unittest.main()
