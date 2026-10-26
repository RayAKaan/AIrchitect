import pytest

from app.domains.geometry.authority import GeometrySource
from app.domains.geometry.identity import canonical_geometry_identity


BASE = {
    "organization_id": "org-1",
    "project_id": "project-1",
    "project_version_id": "version-1",
    "world_model_revision_id": "wm-1",
    "world_model_hash": "wm-hash",
    "design_alternative_id": "alt-1",
    "design_hash": "design-hash",
    "source": GeometrySource.CAD_BREP,
    "geometry_hash": "geometry-hash",
}


def test_identity_hash_is_deterministic() -> None:
    first = canonical_geometry_identity(BASE)
    second = canonical_geometry_identity(dict(reversed(list(BASE.items()))))

    assert first.payload() == second.payload()
    assert first.identity_hash == second.identity_hash


def test_identity_hash_changes_when_canonical_input_changes() -> None:
    first = canonical_geometry_identity(BASE)
    changed = canonical_geometry_identity({**BASE, "design_hash": "new-design-hash"})

    assert first.identity_hash != changed.identity_hash


@pytest.mark.parametrize("field", ["organization_id", "project_id", "world_model_hash", "design_hash", "geometry_hash"])
def test_identity_rejects_missing_required_fields(field: str) -> None:
    values = dict(BASE)
    values[field] = ""

    with pytest.raises(ValueError, match="missing geometry identity fields"):
        canonical_geometry_identity(values)
