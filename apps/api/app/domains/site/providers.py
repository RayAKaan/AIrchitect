from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ProviderCapability:
    provider_id: str
    capability: str
    dataset: str | None
    dataset_version: str | None
    terms_version: str


class GeocoderProvider(Protocol):
    capability: str
    async def search(self, query: str) -> list[dict[str, Any]]: ...


class BasemapProvider(Protocol):
    capability: str
    async def tile_source(self, *, style: str) -> dict[str, Any]: ...


class ContextProvider(Protocol):
    capability: str
    async def fetch(self, *, boundary: dict[str, Any]) -> dict[str, Any]: ...


class TermsRegistry:
    """Provider terms are explicit dependencies, never hidden inside adapters."""

    def __init__(self) -> None:
        self._terms: dict[tuple[str, str], dict[str, Any]] = {}

    def register(self, *, provider_id: str, capability: str, version: str, license: str | None,
                 attribution_required: bool, commercial_use: str, caching_allowed: bool,
                 source_url: str | None = None) -> None:
        self._terms[(provider_id, capability)] = {
            "version": version,
            "license": license,
            "attribution_required": attribution_required,
            "commercial_use": commercial_use,
            "caching_allowed": caching_allowed,
            "source_url": source_url,
        }

    def require(self, provider_id: str, capability: str) -> dict[str, Any]:
        terms = self._terms.get((provider_id, capability))
        if terms is None:
            raise LookupError(f"PROVIDER_TERMS_UNREGISTERED:{provider_id}:{capability}")
        return terms
