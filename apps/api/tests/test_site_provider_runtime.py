import pytest

from app.db.provider_models import Provider
from app.domains.site.provider_runtime import _bbox, _validated_endpoint, _validate_content_type, _validate_feature_collection


def test_context_bbox_is_deterministic() -> None:
    boundary = {"type": "Polygon", "coordinates": [[[77.61, 12.95], [77.59, 12.97], [77.60, 12.99], [77.61, 12.95]]]}
    assert _bbox(boundary) == (77.59, 12.95, 77.61, 12.99)


def test_provider_endpoint_requires_https() -> None:
    provider = Provider(provider_id="context", capability="context", coverage_json={"context_endpoint": "http://example.test"})
    with pytest.raises(ValueError, match="PROVIDER_CONTEXT_ENDPOINT_MUST_USE_HTTPS"):
        _validated_endpoint(provider)


def test_provider_endpoint_must_be_configured() -> None:
    provider = Provider(provider_id="context", capability="context", coverage_json={})
    with pytest.raises(ValueError, match="PROVIDER_CONTEXT_ENDPOINT_UNCONFIGURED"):
        _validated_endpoint(provider)


def test_content_type_requires_geojson_media_type() -> None:
    assert _validate_content_type("application/geo+json; charset=utf-8") == "application/geo+json"
    assert _validate_content_type("application/json") == "application/json"
    with pytest.raises(ValueError, match="PROVIDER_CONTEXT_RESPONSE_CONTENT_TYPE_INVALID"):
        _validate_content_type("text/html")


def test_context_payload_must_be_geojson_feature_collection() -> None:
    with pytest.raises(ValueError, match="PROVIDER_CONTEXT_RESPONSE_MUST_BE_FEATURE_COLLECTION"):
        _validate_feature_collection({"type": "Feature"})
    payload = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": None, "properties": {}}]}
    assert _validate_feature_collection(payload) == payload
