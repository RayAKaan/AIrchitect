from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.provider_models import Provider, ProviderFetchLog, ProviderTerms
from app.db.site_models import SiteEvidence, SiteLayerSnapshot, SiteRevision, SiteSource

MAX_CONTEXT_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ContextFetchResult:
    provider_id: str
    dataset_version: str | None
    feature_count: int
    source_id: str
    snapshot_id: str
    content_hash: str
    status: str


def _bbox(boundary: dict[str, Any]) -> tuple[float, float, float, float]:
    points = boundary["coordinates"][0]
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _validated_endpoint(provider: Provider) -> str:
    endpoint = provider.coverage_json.get("context_endpoint") if provider.coverage_json else None
    if not isinstance(endpoint, str) or not endpoint:
        raise ValueError("PROVIDER_CONTEXT_ENDPOINT_UNCONFIGURED")
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("PROVIDER_CONTEXT_ENDPOINT_MUST_USE_HTTPS")
    return endpoint


def _validate_feature_collection(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise ValueError("PROVIDER_CONTEXT_RESPONSE_MUST_BE_FEATURE_COLLECTION")
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("PROVIDER_CONTEXT_RESPONSE_FEATURES_INVALID")
    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError("PROVIDER_CONTEXT_RESPONSE_FEATURE_INVALID")
    return payload


async def fetch_context(
    session: AsyncSession,
    revision: SiteRevision,
    provider_id: str,
    *,
    timeout_seconds: float = 20.0,
) -> ContextFetchResult:
    provider = await session.scalar(
        select(Provider).where(Provider.provider_id == provider_id, Provider.capability == "context", Provider.enabled.is_(True))
    )
    if provider is None:
        raise ValueError("PROVIDER_CONTEXT_NOT_REGISTERED")
    terms = await session.scalar(
        select(ProviderTerms)
        .where(ProviderTerms.provider_id == provider_id, ProviderTerms.capability == "context")
        .order_by(ProviderTerms.effective_at.desc())
    )
    if terms is None:
        raise ValueError("PROVIDER_TERMS_UNREGISTERED")
    if terms.commercial_use == "UNKNOWN":
        raise ValueError("PROVIDER_COMMERCIAL_USE_UNKNOWN")
    if not terms.caching_allowed:
        raise ValueError("PROVIDER_CONTEXT_PERSISTENCE_NOT_PERMITTED")

    endpoint = _validated_endpoint(provider)
    min_lon, min_lat, max_lon, max_lat = _bbox(revision.boundary_geojson)
    request_params = {"bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}", "format": "geojson"}
    retrieved_at = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False) as client:
            response = await client.get(endpoint, params=request_params, headers={"Accept": "application/geo+json, application/json"})
            response.raise_for_status()
            raw = await response.aread()
    except httpx.HTTPError as exc:
        await session.rollback()
        raise ValueError("PROVIDER_CONTEXT_FETCH_FAILED") from exc
    if len(raw) > MAX_CONTEXT_BYTES:
        await session.rollback()
        raise ValueError("PROVIDER_CONTEXT_RESPONSE_TOO_LARGE")
    try:
        payload = _validate_feature_collection(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        await session.rollback()
        if isinstance(exc, ValueError) and str(exc).startswith("PROVIDER_CONTEXT_RESPONSE_"):
            raise
        raise ValueError("PROVIDER_CONTEXT_RESPONSE_INVALID_JSON") from exc

    canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    content_hash = hashlib.sha256(canonical_bytes).hexdigest()
    source = SiteSource(
        site_revision_id=revision.id,
        provider=provider_id,
        dataset=str(provider.coverage_json.get("dataset", provider_id)),
        dataset_version=str(provider.coverage_json.get("dataset_version", terms.version)),
        source_url=endpoint,
        retrieval_time=retrieved_at,
        attribution=str(provider.coverage_json.get("attribution", "")),
        license=terms.license,
        geographic_scope=str(provider.coverage_json.get("geographic_scope", "site_bbox")),
        raw_reference=content_hash,
    )
    session.add(source)
    await session.flush()
    snapshot = SiteLayerSnapshot(
        site_revision_id=revision.id,
        layer_type="CONTEXT",
        provider=provider_id,
        dataset_version=str(provider.coverage_json.get("dataset_version", terms.version)),
        payload_json=payload,
        status="SUPPORTED",
    )
    session.add(snapshot)
    evidence = SiteEvidence(
        site_revision_id=revision.id,
        source_id=source.id,
        claim_type="site_context_layer",
        value_json={"feature_count": len(payload["features"]), "content_hash": content_hash},
        confidence=1.0,
        status="SUPPORTED",
        method="provider_context_fetch",
    )
    session.add(evidence)
    session.add(ProviderFetchLog(
        provider_id=provider_id,
        capability="context",
        dataset=str(provider.coverage_json.get("dataset", provider_id)),
        dataset_version=str(provider.coverage_json.get("dataset_version", terms.version)),
        fetched_at=retrieved_at,
        source_url=endpoint,
        terms_version=terms.version,
        status="SUCCESS",
        raw_reference=content_hash,
        response_metadata_json={"feature_count": len(payload["features"]), "site_revision_id": revision.id},
    ))
    await session.commit()
    await session.refresh(source)
    await session.refresh(snapshot)
    return ContextFetchResult(provider_id, str(provider.coverage_json.get("dataset_version", terms.version)), len(payload["features"]), source.id, snapshot.id, content_hash, "SUPPORTED")
