from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ReleasePublication:
    """Immutable evidence that one verified release manifest was published."""

    publication_id: str
    project_version_id: str
    manifest_hash: str
    publisher_id: str
    published_at: datetime

    @classmethod
    def create(
        cls,
        *,
        project_version_id: str,
        manifest_hash: str,
        publisher_id: str,
        published_at: datetime,
    ) -> ReleasePublication:
        for name, value in (
            ("project_version_id", project_version_id),
            ("manifest_hash", manifest_hash),
            ("publisher_id", publisher_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")
        payload = {
            "project_version_id": project_version_id,
            "manifest_hash": manifest_hash,
            "publisher_id": publisher_id,
            "published_at": published_at.isoformat(),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        publication_id = hashlib.sha256(encoded).hexdigest()
        return cls(publication_id, project_version_id, manifest_hash, publisher_id, published_at)

    def as_dict(self) -> dict[str, Any]:
        return {
            "publication_id": self.publication_id,
            "project_version_id": self.project_version_id,
            "manifest_hash": self.manifest_hash,
            "publisher_id": self.publisher_id,
            "published_at": self.published_at.isoformat(),
        }


def verify_publication(
    publication: ReleasePublication,
    *,
    expected_project_version_id: str,
    expected_manifest_hash: str,
) -> bool:
    return (
        publication.project_version_id == expected_project_version_id
        and publication.manifest_hash == expected_manifest_hash
        and publication.publication_id
        == ReleasePublication.create(
            project_version_id=publication.project_version_id,
            manifest_hash=publication.manifest_hash,
            publisher_id=publication.publisher_id,
            published_at=publication.published_at,
        ).publication_id
    )
