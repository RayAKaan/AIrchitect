import pytest

from app.domains.site.providers import TermsRegistry


def test_terms_registry_requires_explicit_registration() -> None:
    registry = TermsRegistry()
    with pytest.raises(LookupError, match="PROVIDER_TERMS_UNREGISTERED"):
        registry.require("osm", "context")


def test_terms_registry_preserves_data_use_constraints() -> None:
    registry = TermsRegistry()
    registry.register(provider_id="osm", capability="context", version="2026-10", license="ODbL-1.0", attribution_required=True, commercial_use="ALLOWED_WITH_TERMS", caching_allowed=False)
    terms = registry.require("osm", "context")
    assert terms["license"] == "ODbL-1.0"
    assert terms["attribution_required"] is True
    assert terms["caching_allowed"] is False
