from datetime import UTC, datetime

import pytest

from app.domains.lifecycle.release_publication import ReleasePublication, verify_publication


def test_publication_identity_is_deterministic() -> None:
    timestamp = datetime(2026, 10, 27, 1, 0, tzinfo=UTC)
    first = ReleasePublication.create(
        project_version_id="version-1",
        manifest_hash="abc123",
        publisher_id="user-1",
        published_at=timestamp,
    )
    second = ReleasePublication.create(
        project_version_id="version-1",
        manifest_hash="abc123",
        publisher_id="user-1",
        published_at=timestamp,
    )
    assert first == second


def test_publication_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ReleasePublication.create(
            project_version_id="version-1",
            manifest_hash="abc123",
            publisher_id="user-1",
            published_at=datetime(2026, 10, 27, 1, 0),
        )


def test_publication_verification_is_fail_closed() -> None:
    publication = ReleasePublication.create(
        project_version_id="version-1",
        manifest_hash="abc123",
        publisher_id="user-1",
        published_at=datetime(2026, 10, 27, 1, 0, tzinfo=UTC),
    )
    assert verify_publication(
        publication,
        expected_project_version_id="version-1",
        expected_manifest_hash="abc123",
    )
    assert not verify_publication(
        publication,
        expected_project_version_id="version-2",
        expected_manifest_hash="abc123",
    )
