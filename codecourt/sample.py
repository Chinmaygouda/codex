"""Seeded input for the Phase 1 local demo."""

VULNERABLE_XXE_SAMPLE = '''from lxml import etree


def parse_profile(xml_payload: bytes) -> str:
    """Return the display name from an uploaded XML profile."""
    parser = etree.XMLParser(resolve_entities=True, load_dtd=True, no_network=False)
    profile = etree.fromstring(xml_payload, parser)
    return profile.findtext("display_name", default="anonymous")
'''

GENERATOR_TASK = """Review and defend the following existing Python function. It parses an XML
profile submitted by an application user. Explain any non-trivial choices and
provide a corrected implementation and regression test if you identify a problem."""
