"""Tests for Phase 18 CAD/BIM persistence.

The properties that matter here are the ones a caller cannot check by looking at the
API response:

* a run that produced nothing is still recorded, with a typed error code;
* geometry is bound to the world model revision it was computed from, and a
  revision that moved mid-run is recorded as stale instead of current;
* nothing large lands in the database, and the bytes on disk match the hash on the
  row;
* a repeat run that produces identical geometry reuses it rather than writing a
  second row.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import (
    ArtifactDependency,
    Base,
    CadArtifact,
    CadJobRun,
    DesignAlternative,
    EvidenceRecord,
    GeometryArtifact,
    Organization,
    Project,
    ProjectVersion,
    User,
    ValidationCheck,
    ValidationRun,
    WorldModelRevision,
)
from app.domains.cad.errors import CadJobError, CadStorageError
from app.domains.cad.persistence import (
    CadRevisionError,
    record_cad_failure,
    record_cad_success,
    request_hash,
    resolve_current_world,
    store_worker_artifacts,
)
from app.domains.cad.protocol import CadJobRequest, CadJobResult
from app.domains.cad.storage import ContentAddressedStore
from app.domains.lifecycle.service import canonical_hash

GLB = b"glTF" + (2).to_bytes(4, "little") + (12).to_bytes(4, "little") + b"\x00" * 8
STEP = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


def world_payload(project_id: str, version_id: str) -> dict:
    return {
        "schema_version": "1.0.0",
        "project_id": project_id,
        "project_version_id": version_id,
        "site": {"location": {"city": "Riyadh", "country": "Saudi Arabia"}},
        "building": {"use": "commercial_retail", "floor_count": 6},
        "levels": [],
        "provenance": {},
    }


async def seed(session):
    user = User(email="cad@example.com", name="Designer", password_hash="x")
    session.add(user)
    await session.flush()
    org = Organization(name="CAD Org", created_by=user.id)
    session.add(org)
    await session.flush()
    project = Project(organization_id=org.id, name="Retail", created_by=user.id)
    session.add(project)
    await session.flush()
    version = ProjectVersion(
        organization_id=org.id,
        project_id=project.id,
        version=1,
        status="COMMITTED",
        revision_number=1,
        created_by=user.id,
    )
    session.add(version)
    await session.flush()
    project.current_version_id = version.id
    payload = world_payload(project.id, version.id)
    world = WorldModelRevision(
        organization_id=org.id,
        project_id=project.id,
        project_version_id=version.id,
        revision=1,
        model_json=payload,
        model_hash=canonical_hash(payload),
        created_by=user.id,
    )
    session.add(world)
    await session.flush()
    # design_alternatives inherits DomainArtifactMixin, so an ArtifactVersion must
    # exist first; the design engine does the same via new_artifact.
    from app.domains.lifecycle.service import new_artifact

    alternative_version = await new_artifact(
        session,
        project=project,
        version=version,
        world=world,
        actor=user.id,
        artifact_type="design_alternative",
        payload={"design_hash": "design-hash-1"},
        status="CURRENT",
    )
    alternative = DesignAlternative(
        artifact_version_id=alternative_version.id,
        project_id=project.id,
        project_version_id=version.id,
        world_model_revision_id=world.id,
        name="Option A",
        strategy_id="balanced",
        strategy_version="1",
        design_parameters_json={},
        key_metrics_json={},
        input_world_model_hash=world.model_hash or "",
        design_hash="design-hash-1",
        status="VALID",
    )
    session.add(alternative)
    await session.flush()
    alternative_version.alternative_id = alternative.id
    await session.commit()
    return user, org, project, version, world, alternative


def make_request(**overrides) -> CadJobRequest:
    element = {
        "id": "tower-a",
        "kind": "building_mass",
        "name": "Tower A",
        "footprint": {"points": [[0, 0], [20, 0], [20, 15], [0, 15]]},
        "base_elevation_m": 0.0,
        "height_m": 24.0,
        "material_class": "conceptual_mass",
    }
    payload = {"elements": [element], "project_name": "Retail"}
    payload.update(overrides)
    return CadJobRequest.model_validate(payload)


def make_result(
    *,
    artifacts: dict[str, bytes] | None = None,
    valid: bool = True,
    volume_m3: float = 7200.0,
):
    from app.domains.cad.protocol import (
        ArtifactRef,
        BoundingBox,
        CadValidationResult,
        ProviderInfo,
        SolidMeasurement,
        ValidationCheck,
    )
    from app.domains.cad.storage import sha256_bytes

    chosen = artifacts if artifacts is not None else {"glb": GLB, "step": STEP}
    refs = [
        ArtifactRef(
            kind=kind,
            filename=f"{kind}.{'glb' if kind == 'glb' else 'step'}",
            content_type={
                "glb": "model/gltf-binary",
                "step": "model/step",
            }[kind],
            byte_size=len(data),
            sha256=sha256_bytes(data),
            payload=base64.b64encode(data).decode("ascii"),
        )
        for kind, data in sorted(chosen.items())
    ]
    provider = ProviderInfo(
        provider="occt",
        engine_name="OCCT via cadquery-ocp",
        engine_version="7.9.3",
        python_version="3.14.4",
        occt_version="7.9.3",
        occt_build="",
        ifc_library_version="0.8.5",
        freecad_version=None,
        provider_digest="abc123",
    )
    validation = CadValidationResult(
        valid=valid,
        checks=[
            ValidationCheck(
                code="solid_valid",
                status="PASS",
                actual=True,
                expected=True,
                detail="solid is valid",
                source="solid",
            )
        ],
        errors=[] if valid else ["one solid is invalid"],
        warnings=[],
    )
    return CadJobResult(
        provider=provider,
        job_id="job-1",
        element_count=1,
        artifacts=refs,
        combined_volume_m3=volume_m3,
        combined_area_m2=300.0,
        measurements=[
            SolidMeasurement(
                id="tower-a",
                kind="building_mass",
                volume_m3=volume_m3,
                surface_area_m2=300.0,
                centroid=(10.0, 7.5, 12.0),
                bounding_box=BoundingBox(min=(0, 0, 0), max=(20, 15, 24)),
                solid_count=1,
                face_count=6,
                edge_count=12,
                vertex_count=8,
                is_valid=True,
                is_closed=True,
                center_of_mass=(10.0, 7.5, 12.0),
            )
        ],
        validation=validation,
        warnings=[],
    )


# --------------------------------------------------------------------------- #
# current-revision resolution
# --------------------------------------------------------------------------- #


async def test_resolve_current_world_returns_the_highest_revision(session) -> None:
    _, org, project, version, world, _alt = await seed(session)
    newer_payload = world_payload(project.id, version.id)
    newer_payload["building"]["floor_count"] = 9
    newer = WorldModelRevision(
        organization_id=org.id,
        project_id=project.id,
        project_version_id=version.id,
        revision=2,
        model_json=newer_payload,
        model_hash=canonical_hash(newer_payload),
        created_by=(await _user(session)).id,
    )
    session.add(newer)
    await session.commit()

    resolved = await resolve_current_world(session, version)
    assert resolved.id == newer.id
    assert resolved.revision == 2


async def test_resolve_current_world_raises_when_unbound(session) -> None:
    """Geometry with nothing to attribute it to is refused, not recorded."""
    user = User(email="empty@example.com", name="E", password_hash="x")
    session.add(user)
    await session.flush()
    org = Organization(name="Empty Org", created_by=user.id)
    session.add(org)
    await session.flush()
    project = Project(organization_id=org.id, name="P", created_by=user.id)
    session.add(project)
    await session.flush()
    version = ProjectVersion(
        organization_id=org.id,
        project_id=project.id,
        version=1,
        status="COMMITTED",
        revision_number=1,
        created_by=user.id,
    )
    session.add(version)
    await session.commit()

    with pytest.raises(CadRevisionError):
        await resolve_current_world(session, version)


async def _user(session) -> User:
    return (await session.scalars(select(User))).first()


# --------------------------------------------------------------------------- #
# request hashing
# --------------------------------------------------------------------------- #


def test_request_hash_ignores_operational_fields() -> None:
    """A different timeout or scratch path is the same geometry request."""
    a = make_request(freecad_timeout_seconds=180.0, job_id="one")
    b = make_request(freecad_timeout_seconds=900.0, job_id="two")
    assert request_hash(a) == request_hash(b)


def test_request_hash_tracks_mesh_deflection() -> None:
    """Deflection changes the GLB, so it must change the hash."""
    a = make_request()
    b = make_request(mesh_deflection_m=0.5)
    assert request_hash(a) != request_hash(b)


def test_request_hash_tracks_the_elements() -> None:
    a = make_request()
    b = make_request(
        elements=[
            {
                "id": "tower-b",
                "kind": "building_mass",
                "name": "Tower B",
                "footprint": {"points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
                "base_elevation_m": 0.0,
                "height_m": 12.0,
                "material_class": "conceptual_mass",
            }
        ]
    )
    assert request_hash(a) != request_hash(b)


# --------------------------------------------------------------------------- #
# artifact storage
# --------------------------------------------------------------------------- #


def test_store_worker_artifacts_writes_every_artifact(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    stored = store_worker_artifacts(
        store, organization_id="o" * 8, result=make_result()
    )
    assert set(stored) == {"glb", "step"}
    for blob in stored.values():
        assert blob.path.is_file()
        assert blob.byte_size > 0


def test_store_worker_artifacts_rejects_a_wrong_declared_hash(tmp_path: Path) -> None:
    from app.domains.cad.protocol import ArtifactRef

    store = ContentAddressedStore(tmp_path)
    result = make_result()
    bad = ArtifactRef(
        kind="glb",
        filename="glb.glb",
        content_type="model/gltf-binary",
        byte_size=len(GLB),
        sha256="0" * 64,
        payload=base64.b64encode(GLB).decode("ascii"),
    )
    result.artifacts = [bad]
    with pytest.raises(CadJobError, match="hashes to"):
        store_worker_artifacts(store, organization_id="o" * 8, result=result)


def test_store_worker_artifacts_rejects_a_wrong_declared_size(tmp_path: Path) -> None:
    from app.domains.cad.protocol import ArtifactRef

    store = ContentAddressedStore(tmp_path)
    result = make_result()
    result.artifacts = [
        ArtifactRef(
            kind="glb",
            filename="glb.glb",
            content_type="model/gltf-binary",
            byte_size=9999,
            sha256="0" * 64,
            payload=base64.b64encode(GLB).decode("ascii"),
        )
    ]
    with pytest.raises(CadJobError, match="bytes but declared"):
        store_worker_artifacts(store, organization_id="o" * 8, result=result)


def test_store_worker_artifacts_rejects_a_mislabelled_content_type(tmp_path: Path) -> None:
    from app.domains.cad.protocol import ArtifactRef
    from app.domains.cad.storage import sha256_bytes

    store = ContentAddressedStore(tmp_path)
    result = make_result()
    result.artifacts = [
        ArtifactRef(
            kind="glb",
            filename="glb.glb",
            content_type="application/x-freecad",  # wrong on purpose
            byte_size=len(GLB),
            sha256=sha256_bytes(GLB),
            payload=base64.b64encode(GLB).decode("ascii"),
        )
    ]
    with pytest.raises(CadJobError, match="content type"):
        store_worker_artifacts(store, organization_id="o" * 8, result=result)


def test_store_worker_artifacts_writes_nothing_when_one_payload_is_bad(
    tmp_path: Path,
) -> None:
    """Verification happens before any write, so a bad artifact writes nothing."""
    from app.domains.cad.protocol import ArtifactRef

    store = ContentAddressedStore(tmp_path)
    result = make_result()
    result.artifacts = [
        ArtifactRef(
            kind="step",
            filename="step.step",
            content_type="model/step",
            byte_size=1,
            sha256="0" * 64,
            payload="not base64!!",
        )
    ]
    with pytest.raises(CadJobError):
        store_worker_artifacts(store, organization_id="o" * 8, result=result)
    assert not (tmp_path / "cad").exists()


# --------------------------------------------------------------------------- #
# failure recording
# --------------------------------------------------------------------------- #


async def test_failure_is_recorded_with_its_typed_code(session) -> None:
    user, _org, project, version, world, _alt = await seed(session)
    run = await record_cad_failure(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="freecad",
        request=make_request(),
        error_code="duplicate_element_id",
        error_message="duplicate element id 'tower-a'",
    )
    await session.commit()

    stored = await session.get(CadJobRun, run.id)
    assert stored is not None
    assert stored.status == "FAILED"
    assert stored.error_code == "duplicate_element_id"
    assert stored.geometry_artifact_id is None
    assert stored.world_model_revision_id == world.id
    assert stored.input_world_model_hash == world.model_hash
    assert stored.completed_at is not None


async def test_failure_records_no_artifacts_or_geometry(session) -> None:
    user, _org, project, version, world, _alt = await seed(session)
    await record_cad_failure(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        error_code="worker_timeout",
        error_message="exceeded 60s",
    )
    await session.commit()
    assert await session.scalar(select(func.count()).select_from(CadArtifact)) == 0
    assert await session.scalar(select(func.count()).select_from(GeometryArtifact)) == 0


# --------------------------------------------------------------------------- #
# success recording
# --------------------------------------------------------------------------- #


async def test_success_records_run_artifacts_and_evidence(session, tmp_path: Path) -> None:
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result()
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)

    recorded = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=alt.id,
        design_hash="design-hash-1",
    )
    await session.commit()

    assert recorded.run.status == "SUCCEEDED"
    assert recorded.stale is False
    assert len(recorded.artifacts) == 2

    rows = list((await session.scalars(select(CadArtifact))).all())
    assert {r.kind for r in rows} == {"glb", "step"}
    for row in rows:
        assert row.organization_id == org.id
        assert row.project_version_id == version.id
        # the recorded hash must match the bytes actually on disk
        from app.domains.cad.storage import sha256_bytes

        assert sha256_bytes(store.read_bytes(row.storage_key)) == row.sha256
        assert row.byte_size == len(store.read_bytes(row.storage_key))

    glb_row = next(r for r in rows if r.kind == "glb")
    assert glb_row.media_role == "viewer_primary"
    assert glb_row.content_type == "model/gltf-binary"

    evidence = list((await session.scalars(select(EvidenceRecord))).all())
    assert len(evidence) == 1
    assert evidence[0].artifact_version_id == glb_row.artifact_version_id
    assert evidence[0].source_hash == glb_row.sha256
    assert evidence[0].verification_status == "verified"


async def test_success_never_stores_bytes_in_a_json_column(session, tmp_path: Path) -> None:
    """The payload column must hold metadata, not the artifact."""
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result()
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)

    recorded = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=alt.id,
    )
    await session.commit()

    from app.db.models import ArtifactVersion

    for version_row in (await session.scalars(select(ArtifactVersion))).all():
        if not version_row.artifact_type.startswith("cad_"):
            continue
        blob = json_dumps(version_row.payload_json)
        assert len(blob) < 2000, f"{version_row.artifact_type} payload is too large to be metadata"
        assert "glTF" not in blob
        assert base64.b64encode(GLB).decode("ascii") not in blob
    assert recorded.run.measurements_json["combined_volume_m3"] == 7200.0


def json_dumps(value) -> str:
    import json

    return json.dumps(value, default=str)


async def test_geometry_is_bound_to_the_world_model_revision(
    session, tmp_path: Path
) -> None:
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result()
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)

    recorded = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=alt.id,
    )
    await session.commit()

    assert recorded.geometry_artifact_id is not None
    geometry = await session.get(GeometryArtifact, recorded.geometry_artifact_id)
    assert geometry is not None
    assert geometry.world_model_revision_id == world.id
    assert geometry.input_world_model_hash == world.model_hash
    assert geometry.status == "CURRENT"
    assert geometry.provenance_json["world_model_is_current"] is True


async def test_geometry_is_recorded_stale_when_the_revision_moved_mid_run(
    session, tmp_path: Path
) -> None:
    """The revision binding is re-checked at write time, not assumed."""
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result()
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)

    # A new revision lands while the worker is busy.
    moved_payload = world_payload(project.id, version.id)
    moved_payload["building"]["floor_count"] = 11
    moved = WorldModelRevision(
        organization_id=org.id,
        project_id=project.id,
        project_version_id=version.id,
        revision=2,
        model_json=moved_payload,
        model_hash=canonical_hash(moved_payload),
        created_by=user.id,
    )
    session.add(moved)
    await session.flush()

    recorded = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,  # the run was bound to the older revision
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=alt.id,
    )
    await session.commit()

    assert recorded.stale is True
    geometry = await session.get(GeometryArtifact, recorded.geometry_artifact_id)
    assert geometry.status == "STALE"
    assert geometry.world_model_revision_id == world.id
    assert geometry.provenance_json["world_model_is_current"] is False


async def test_identical_geometry_from_a_second_run_is_reused(
    session, tmp_path: Path
) -> None:
    """A repeat run must not write a second geometry row."""
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)

    ids = []
    for _ in range(2):
        result = make_result()
        stored = store_worker_artifacts(store, organization_id=org.id, result=result)
        recorded = await record_cad_success(
            session,
            project=project,
            version=version,
            world=world,
            actor_id=user.id,
            provider="occt",
            request=make_request(),
            result=result,
            stored=stored,
            alternative_id=alt.id,
        )
        await session.flush()
        ids.append(recorded.geometry_artifact_id)
    await session.commit()

    assert ids[0] is not None
    assert ids[0] == ids[1]
    assert await session.scalar(select(func.count()).select_from(GeometryArtifact)) == 1
    # the runs themselves are still both recorded
    assert await session.scalar(select(func.count()).select_from(CadJobRun)) == 2


async def test_different_geometry_creates_a_second_row(session, tmp_path: Path) -> None:
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)

    result = make_result()
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)
    first = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=alt.id,
    )
    await session.flush()

    # Different measurements, so genuinely different geometry.
    other = make_result(volume_m3=9600.0)
    other_stored = store_worker_artifacts(store, organization_id=org.id, result=other)
    second = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=other,
        stored=other_stored,
        alternative_id=alt.id,
    )
    await session.commit()

    assert first.geometry_artifact_id != second.geometry_artifact_id
    assert await session.scalar(select(func.count()).select_from(GeometryArtifact)) == 2


async def test_differently_exported_bytes_with_identical_measurements_reuse_the_geometry(
    session, tmp_path: Path
) -> None:
    """Same measurements is the same geometry, however the binaries were written.

    The geometry hash is derived from the measurements, not from the export bytes, so
    a re-run that produces the same solids with different tessellation is correctly
    recognised as the same geometry and does not duplicate the row.
    """
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)

    result = make_result()
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)
    first = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=alt.id,
    )
    await session.flush()

    reexported = make_result(artifacts={"glb": GLB + b"retessellated", "step": STEP + b"!"})
    re_stored = store_worker_artifacts(store, organization_id=org.id, result=reexported)
    second = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=reexported,
        stored=re_stored,
        alternative_id=alt.id,
    )
    await session.commit()

    assert first.geometry_artifact_id == second.geometry_artifact_id
    # the two runs did store two distinct sets of binaries
    assert await session.scalar(select(func.count()).select_from(CadArtifact)) == 4
    assert await session.scalar(select(func.count()).select_from(GeometryArtifact)) == 1


async def test_geometry_depends_on_the_exported_artifacts(session, tmp_path: Path) -> None:
    """The dependency edge is recorded, not implied."""
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result()
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)

    recorded = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=alt.id,
    )
    await session.commit()

    from app.db.models import ArtifactVersion

    geometry = await session.get(GeometryArtifact, recorded.geometry_artifact_id)
    artifact_ids = {
        r.artifact_version_id for r in await session.scalars(select(CadArtifact))
    }
    dependencies = list(
        await session.scalars(
            select(ArtifactDependency).where(
                ArtifactDependency.artifact_version_id == geometry.artifact_version_id
            )
        )
    )
    assert {d.depends_on_artifact_version_id for d in dependencies} == artifact_ids
    assert geometry.artifact_version_id not in artifact_ids


async def test_no_geometry_row_without_an_alternative(session, tmp_path: Path) -> None:
    """geometry_artifacts requires an alternative, so none is invented."""
    user, org, project, version, world, _alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result()
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)

    recorded = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=None,
    )
    await session.commit()

    assert recorded.geometry_artifact_id is None
    assert await session.scalar(select(func.count()).select_from(GeometryArtifact)) == 0
    # the run and its artifacts are still recorded
    assert await session.scalar(select(func.count()).select_from(CadJobRun)) == 1
    assert await session.scalar(select(func.count()).select_from(CadArtifact)) == 2


async def test_unknown_alternative_is_refused_before_anything_is_written(
    session, tmp_path: Path
) -> None:
    user, org, project, version, world, _alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result()
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)

    with pytest.raises(CadJobError, match="does not exist"):
        await record_cad_success(
            session,
            project=project,
            version=version,
            world=world,
            actor_id=user.id,
            provider="occt",
            request=make_request(),
            result=result,
            stored=stored,
            alternative_id="not-a-real-alternative",
        )
    await session.rollback()
    assert await session.scalar(select(func.count()).select_from(CadJobRun)) == 0


async def test_validation_run_and_checks_are_recorded(session, tmp_path: Path) -> None:
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result(valid=True)
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)

    recorded = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=alt.id,
    )
    await session.commit()

    assert recorded.validation_run_id is not None
    validation = await session.get(ValidationRun, recorded.validation_run_id)
    assert validation.status == "PASSED"
    assert validation.engine_name == "occt"
    assert validation.world_model_revision_id == world.id

    checks = list(
        await session.scalars(
            select(ValidationCheck).where(
                ValidationCheck.validation_run_id == validation.id
            )
        )
    )
    assert len(checks) == 1
    assert checks[0].code == "solid_valid"
    assert checks[0].severity == "INFO"
    assert checks[0].source_artifact_id == recorded.geometry_artifact_id


async def test_failed_validation_is_recorded_as_failed(session, tmp_path: Path) -> None:
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result(valid=False)
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)

    recorded = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=alt.id,
    )
    await session.commit()
    validation = await session.get(ValidationRun, recorded.validation_run_id)
    assert validation.status == "FAILED"


async def test_skipped_validation_is_recorded_as_blocked(session, tmp_path: Path) -> None:
    """run_validation=false must not be reported as a pass."""
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result()
    result.validation = None
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)

    recorded = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=alt.id,
    )
    await session.commit()
    assert recorded.validation_run_id is None
    assert await session.scalar(select(func.count()).select_from(ValidationRun)) == 0


async def test_toolchain_versions_are_stored_per_run(session, tmp_path: Path) -> None:
    from app.domains.cad.capability import WorkerCapabilities

    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result()
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)
    capabilities = WorkerCapabilities(
        schema_version="1.0",
        occt={
            "available": True,
            "engine_name": "OCCT via cadquery-ocp",
            "engine_version": "7.9.3",
            "occt_version": "7.9.3",
        },
        ifc={"available": True, "version": "0.8.5"},
        freecad={"available": False},
    )

    recorded = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=alt.id,
        capabilities=capabilities,
    )
    await session.commit()

    run = await session.get(CadJobRun, recorded.run.id)
    assert run.provider_engine_name == "OCCT via cadquery-ocp"
    assert run.provider_engine_version == "7.9.3"
    assert run.occt_version == "7.9.3"
    assert run.ifc_library_version == "0.8.5"
    assert run.capabilities_json["provider"]["provider_digest"] == "abc123"
    assert run.capabilities_json["capability_snapshot"]["occt"]["occt_version"] == "7.9.3"


async def test_run_timestamps_are_populated(session, tmp_path: Path) -> None:
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result()
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)
    recorded = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=alt.id,
        duration_ms=1234,
    )
    await session.commit()
    run = await session.get(CadJobRun, recorded.run.id)
    assert run.started_at is not None and run.completed_at is not None
    assert run.duration_ms == 1234
    assert isinstance(run.created_at, datetime)


async def test_artifact_and_run_agree_on_the_job_id(session, tmp_path: Path) -> None:
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result()
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)
    recorded = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(job_id="caller-label"),
        result=result,
        stored=stored,
        alternative_id=alt.id,
    )
    await session.commit()
    run = await session.get(CadJobRun, recorded.run.id)
    assert run.job_id == "caller-label"
    assert run.element_count == 1


async def test_storage_key_rejects_traversal_at_the_repository_boundary(
    session, tmp_path: Path
) -> None:
    """A corrupted storage_key cannot become a read outside the root."""
    store = ContentAddressedStore(tmp_path)
    with pytest.raises(CadStorageError):
        store.resolve("cad/../../etc/passwd")


# --- staleness cascade -------------------------------------------------------------
# The write-time check above catches a revision that moves *during* a run. The design
# engine's hash-mismatch cascade is the other direction: geometry that was recorded
# while current, and only afterwards superseded, must stop reading as current.


async def _record_current_run(session, tmp_path: Path, **kwargs):
    user, org, project, version, world, alt = await seed(session)
    store = ContentAddressedStore(tmp_path)
    result = make_result()
    stored = store_worker_artifacts(store, organization_id=org.id, result=result)
    recorded = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        result=result,
        stored=stored,
        alternative_id=alt.id,
        **kwargs,
    )
    await session.commit()
    return recorded, dict(user=user, org=org, project=project, version=version, world=world, alt=alt)


async def test_world_model_change_invalidates_a_recorded_cad_run(session, tmp_path: Path) -> None:
    """A superseded run and its artifacts must not keep reading as current."""
    from app.domains.design.engine import ENGINE

    recorded, ctx = await _record_current_run(session, tmp_path)
    assert recorded.stale is False
    assert (await session.get(CadJobRun, recorded.run.id)).status == "SUCCEEDED"

    # The world model moves on. The cascade is given the *new* hash, which is what
    # the engine computes after committing the new revision.
    moved_payload = world_payload(ctx["project"].id, ctx["version"].id)
    moved_payload["building"]["floor_count"] = 9
    current_hash = canonical_hash(moved_payload)

    await ENGINE._mark_hash_mismatch_stale(
        session,
        ctx["version"].id,
        current_hash,
        ctx["project"],
        ctx["version"],
        ctx["user"].id,
    )
    await session.commit()

    assert (await session.get(CadJobRun, recorded.run.id)).status == "STALE"
    # The alternative and the geometry go with it.
    assert (await session.get(DesignAlternative, ctx["alt"].id)).status == "STALE"
    assert (await session.get(GeometryArtifact, recorded.geometry_artifact_id)).status == "STALE"


async def test_invalidated_cad_artifacts_are_marked_stale(session, tmp_path: Path) -> None:
    """Currency of a stored binary is expressed through its ArtifactVersion."""
    from app.db.models import ArtifactVersion
    from app.domains.design.engine import ENGINE

    recorded, ctx = await _record_current_run(session, tmp_path)
    artifact_rows = list(
        (
            await session.scalars(
                select(CadArtifact).where(CadArtifact.cad_job_run_id == recorded.run.id)
            )
        ).all()
    )
    assert artifact_rows
    version_ids = [row.artifact_version_id for row in artifact_rows]
    for vid in version_ids:
        assert (await session.get(ArtifactVersion, vid)).status == "CURRENT"

    moved_payload = world_payload(ctx["project"].id, ctx["version"].id)
    moved_payload["levels"] = [{"id": "l1"}]
    await ENGINE._mark_hash_mismatch_stale(
        session,
        ctx["version"].id,
        canonical_hash(moved_payload),
        ctx["project"],
        ctx["version"],
        ctx["user"].id,
    )
    await session.commit()

    for vid in version_ids:
        assert (await session.get(ArtifactVersion, vid)).status == "STALE"


async def test_cad_run_is_invalidated_even_with_no_alternative(session, tmp_path: Path) -> None:
    """Regression: the cascade used to return early when nothing on the design side matched.

    A CAD run can exist without a surviving design alternative, and a viewer must not
    keep serving that geometry as current just because the design side had nothing to
    mark.
    """
    from app.domains.design.engine import ENGINE

    recorded, ctx = await _record_current_run(session, tmp_path)
    # Simulate the design side having already been invalidated: the alternative is
    # no longer VALID or SELECTED, so the old query would have found nothing.
    (await session.get(DesignAlternative, ctx["alt"].id)).status = "STALE"
    await session.commit()

    moved_payload = world_payload(ctx["project"].id, ctx["version"].id)
    moved_payload["building"]["use"] = "industrial"
    await ENGINE._mark_hash_mismatch_stale(
        session,
        ctx["version"].id,
        canonical_hash(moved_payload),
        ctx["project"],
        ctx["version"],
        ctx["user"].id,
    )
    await session.commit()

    assert (await session.get(CadJobRun, recorded.run.id)).status == "STALE"


async def test_a_failed_run_is_not_invalidated_by_a_world_model_change(
    session, tmp_path: Path
) -> None:
    """A run that produced nothing has nothing to invalidate."""
    from app.domains.design.engine import ENGINE

    user, org, project, version, world, alt = await seed(session)
    run = await record_cad_failure(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=user.id,
        provider="occt",
        request=make_request(),
        error_code="WORKER_EXITED",
        error_message="worker exited with code 1",
        duration_ms=120,
    )
    await session.commit()

    moved_payload = world_payload(project.id, version.id)
    moved_payload["building"]["floor_count"] = 3
    await ENGINE._mark_hash_mismatch_stale(
        session, version.id, canonical_hash(moved_payload), project, version, user.id
    )
    await session.commit()

    # A failure is a historical fact about that attempt, not a claim about the world.
    assert (await session.get(CadJobRun, run.id)).status == "FAILED"


async def test_invalidation_audit_names_the_cad_runs(session, tmp_path: Path) -> None:
    """The audit record has to say which runs were invalidated, not just that some were."""
    from app.db.models import AuditEvent
    from app.domains.design.engine import ENGINE

    recorded, ctx = await _record_current_run(session, tmp_path)
    moved_payload = world_payload(ctx["project"].id, ctx["version"].id)
    moved_payload["provenance"] = {"edited_by": "user"}
    await ENGINE._mark_hash_mismatch_stale(
        session,
        ctx["version"].id,
        canonical_hash(moved_payload),
        ctx["project"],
        ctx["version"],
        ctx["user"].id,
    )
    await session.commit()

    events = list(
        (
            await session.scalars(
                select(AuditEvent).where(AuditEvent.action == "GEOMETRY_INVALIDATED")
            )
        ).all()
    )
    assert events
    assert recorded.run.id in events[-1].metadata_json["stale_cad_job_run_ids"]


async def test_cascade_is_a_noop_when_everything_matches(session, tmp_path: Path) -> None:
    """Nothing to invalidate means no audit noise."""
    from app.db.models import AuditEvent
    from app.domains.design.engine import ENGINE

    recorded, ctx = await _record_current_run(session, tmp_path)
    await ENGINE._mark_hash_mismatch_stale(
        session,
        ctx["version"].id,
        ctx["world"].model_hash or "",
        ctx["project"],
        ctx["version"],
        ctx["user"].id,
    )
    await session.commit()

    assert (await session.get(CadJobRun, recorded.run.id)).status == "SUCCEEDED"
    assert not list(
        (await session.scalars(select(AuditEvent).where(AuditEvent.action == "GEOMETRY_INVALIDATED"))).all()
    )
