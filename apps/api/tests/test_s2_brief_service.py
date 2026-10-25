from app.domains.brief.service import canonical_text, content_hash


def test_brief_canonicalization_collapses_layout_whitespace():
    assert canonical_text("  café\n\n  plan   for  20  units ") == "café plan for 20 units"


def test_brief_hash_is_stable_for_equivalent_text():
    assert content_hash("A\nB", {}) == content_hash(" A  B ", {})


def test_brief_hash_includes_structured_content():
    assert content_hash("A", {"use": "office"}) != content_hash("A", {"use": "retail"})
