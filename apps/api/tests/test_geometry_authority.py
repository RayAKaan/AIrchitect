import pytest

from app.domains.geometry.authority import (
    GeometryAuthorityError,
    GeometryAuthorityInput,
    GeometrySource,
    require_authoritative_geometry,
)


def _valid() -> GeometryAuthorityInput:
    return GeometryAuthorityInput(
        source=GeometrySource.CAD_BREP,
        current=True,
        world_model_hash_matches=True,
        design_hash_matches=True,
        cad_run_succeeded=True,
        validation_document_present=True,
    )


def test_valid_cad_geometry_is_authoritative() -> None:
    require_authoritative_geometry(_valid())


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("source", "CAD_REQUIRED"),
        ("current", "GEOMETRY_STALE"),
        ("world_model_hash_matches", "WORLD_MODEL_MISMATCH"),
        ("design_hash_matches", "DESIGN_MISMATCH"),
        ("cad_run_succeeded", "CAD_RUN_INVALID"),
        ("validation_document_present", "CAD_VALIDATION_REQUIRED"),
    ],
)
def test_authority_contract_fails_closed(field: str, code: str) -> None:
    values = _valid().__dict__
    values[field] = GeometrySource.LEGACY_IR if field == "source" else False

    with pytest.raises(GeometryAuthorityError, match=code):
        require_authoritative_geometry(GeometryAuthorityInput(**values))
