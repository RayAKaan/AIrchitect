"""HTTP-level tests for the CAD/BIM API.

These run the real router against the real ASGI app, with a real subprocess standing
in for the CAD worker (see ``phase18_fake_worker``). Nothing native is imported, and
nothing is mocked out of the API's own code -- the orchestrator, the persistence, the
store and the routes all run for real. What is faked is only the geometry kernel.

The behaviours worth protecting here, and why they are not obvious:

* A client's contribution to a job is a design alternative id. Everything geometric
  is derived server-side. If that ever inverts, a caller can build geometry the World
  Model and the audit trail have never seen.
* A failure that happened *after* the worker ran is a recorded outcome with a run
  row, not a 500. A toolchain that is simply absent is the opposite: a 503 with no
  row, because nothing was invoked.
* An id from another tenant is indistinguishable from an id that does not exist.
"""

from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest

from app.db.models import CadJobRun, DesignAlternative
from tests.phase18_fake_worker import SCENARIO_ENV, FAILING, SLOW, FakeWorker


async def _tenant(api: httpx.AsyncClient, suffix: str):
    email = f"p18-{suffix}-{uuid.uuid4().hex}@example.com"
    auth = await api.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "name": "Designer",
            "password": "phase-eighteen-secure-password",
            "organization_name": f"Org {suffix}",
        },
    )
    headers = {"Authorization": "Bearer " + auth.json()["access_token"]}
    org = (await api.get("/api/v1/organizations", headers=headers)).json()[0]
    return headers, org


async def _committed_project(api: httpx.AsyncClient, suffix: str = "a"):
    """A tenant, a project, a brief, and a committed world model."""
    headers, org = await _tenant(api, suffix)
    project = (
        await api.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "organization_id": org["id"],
                "name": "Retail Design",
                "description": "P18",
                "building_type": "commercial_retail",
                "location": "Riyadh",
            },
        )
    ).json()
    version = (
        await api.get(f"/api/v1/projects/{project['id']}/versions", headers=headers)
    ).json()["versions"][0]
    brief = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/brief",
        headers=headers,
        json={
            "text": (
                "Six-floor commercial retail building in Riyadh with 8,000 m2 GFA "
                "on a 2,000 m2 site and 40 parking spaces in basement parking."
            ),
            "expected_revision": 1,
        },
    )
    assert brief.status_code == 201, brief.text
    commit = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/world-model",
        headers=headers,
        json={"expected_revision": brief.json()["version_revision"], "commit": True},
    )
    assert commit.status_code == 200, commit.text
    return headers, org, project, commit.json()["version"]


async def _alternatives(
    api: httpx.AsyncClient, headers: dict, project: dict, version: dict
) -> list[dict]:
    generated = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/generate",
        headers=headers,
    )
    assert generated.status_code == 201, generated.text
    listing = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives",
        headers=headers,
    )
    return listing.json()["alternatives"]


async def _alternative(
    api: httpx.AsyncClient, headers: dict, project: dict, version: dict
) -> dict:
    return (await _alternatives(api, headers, project, version))[0]


def _cad_url(project: dict, version: dict, alternative: dict) -> str:
    return (
        f"/api/v1/projects/{project['id']}/versions/{version['id']}"
        f"/design/alternatives/{alternative['id']}/cad"
    )


def _job_url(project: dict, version: dict, run_id: str) -> str:
    return f"/api/v1/projects/{project['id']}/versions/{version['id']}/cad/jobs/{run_id}"


def _download_url(project: dict, version: dict, artifact_id: str) -> str:
    return (
        f"/api/v1/projects/{project['id']}/versions/{version['id']}"
        f"/cad/artifacts/{artifact_id}/download"
    )


async def _generate(api: httpx.AsyncClient, headers: dict, project: dict, version: dict, alt: dict):
    response = await api.post(_cad_url(project, version, alt), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_cad_generation_returns_a_recorded_run_with_real_artifacts(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)

    body = await _generate(api, headers, project, version, alternative)

    assert body["status"] == "SUCCEEDED"
    assert body["element_count"] == 1
    assert body["duration_ms"] is not None
    assert body["artifacts"], "a successful run must report its artifacts"
    assert "step" in {a["kind"] for a in body["artifacts"]}
    for artifact in body["artifacts"]:
        assert artifact["byte_size"] > 0
        assert len(artifact["sha256"]) == 64
        assert artifact["download_path"] == _download_url(project, version, artifact["id"])
        # The storage key is opaque and relative: never a server path.
        assert not artifact["storage_key"].startswith("/")
        assert "\\" not in artifact["storage_key"]

    # The worker really was launched, once, in a real subprocess.
    assert cad.worker.count == 1
    assert cad.worker.last.request["alternative_ref"] == alternative["id"]


async def test_cad_response_reports_measurements_and_provenance(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)

    body = await _generate(api, headers, project, version, alternative)

    # A geometric number is only reviewable with the tool that produced it.
    assert body["provider"]
    assert body["provider_engine_name"]
    assert body["occt_version"]
    assert body["world_model_revision_id"]
    assert body["request_hash"]

    measurements = body["measurements"]
    assert measurements["combined_volume_m3"] > 0
    assert measurements["combined_area_m2"] > 0
    assert measurements["combined_bounding_box"]
    elements = measurements["elements"]
    assert elements and elements[0]["volume_m3"] > 0
    assert elements[0]["surface_area_m2"] > 0
    assert len(elements[0]["centroid"]) == 3
    assert elements[0]["is_valid"] is True
    assert elements[0]["is_closed"] is True

    # Nothing the kernel does not measure may appear as though it did.
    for fabricated in (
        "gross_floor_area_m2",
        "roof_area_m2",
        "site_coverage_ratio",
        "open_site_area_m2",
    ):
        assert fabricated not in measurements, f"{fabricated} was never measured on the solid"
    assert "not a construction quantity" in body["notice"]


async def test_cad_job_status_and_artifact_listing_are_readable_afterwards(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)
    created = await _generate(api, headers, project, version, alternative)

    status = await api.get(_job_url(project, version, created["id"]), headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["id"] == created["id"]
    assert status.json()["status"] == "SUCCEEDED"
    assert status.json()["artifacts"]

    listing = await api.get(_job_url(project, version, created["id"]) + "/artifacts", headers=headers)
    assert listing.status_code == 200, listing.text
    payload = listing.json()
    assert payload["cad_job_run_id"] == created["id"]
    assert {a["id"] for a in payload["artifacts"]} == {a["id"] for a in created["artifacts"]}
    # Listing must not carry the bytes.
    assert all("payload" not in a for a in payload["artifacts"])


async def test_cad_artifact_download_streams_the_stored_bytes(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)
    created = await _generate(api, headers, project, version, alternative)
    artifact = next(a for a in created["artifacts"] if a["kind"] == "step")

    download = await api.get(_download_url(project, version, artifact["id"]), headers=headers)

    assert download.status_code == 200, download.text
    assert download.headers["content-type"].startswith("model/step")
    assert "attachment" in download.headers["content-disposition"]
    assert artifact["filename"] in download.headers["content-disposition"]
    assert download.headers["etag"].strip('"') == artifact["sha256"]
    assert download.headers["x-cad-artifact-sha256"] == artifact["sha256"]
    assert download.content == b"ISO-10303-21;FAKE"


async def test_cad_requested_outputs_narrow_the_artifact_set(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)

    response = await api.post(
        _cad_url(project, version, alternative), headers=headers, json={"requested_outputs": ["step"]}
    )

    assert response.status_code == 201, response.text
    assert {a["kind"] for a in response.json()["artifacts"]} == {"step"}
    options = cad.worker.last.request["options"]
    assert options["write_step"] is True
    for switched_off in ("write_glb", "write_ifc", "write_fcstd"):
        assert options[switched_off] is False, "narrowing must switch the others off"


async def test_cad_cannot_switch_on_an_output_the_deployment_disabled(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)
    cad.set(write_ifc=False)

    response = await api.post(
        _cad_url(project, version, alternative), headers=headers, json={"requested_outputs": ["ifc"]}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CAD_NO_OUTPUTS_ENABLED"


async def test_cad_rejects_an_unknown_requested_output(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)

    response = await api.post(
        _cad_url(project, version, alternative), headers=headers, json={"requested_outputs": ["dwg"]}
    )

    # A closed vocabulary: the schema rejects it before the route is reached.
    assert response.status_code == 422


async def test_cad_derives_geometry_from_the_alternative_and_ignores_a_client_supplied_one(
    api, cad
):
    headers, _, project, version = await _committed_project(api)
    alternative = (await _alternatives(api, headers, project, version))[0]
    parameters = alternative["parameters"]

    response = await api.post(
        _cad_url(project, version, alternative),
        headers=headers,
        # Everything here is an attempt to smuggle geometry past the design engine.
        json={
            "requested_outputs": ["step"],
            "footprint": {"points": [[0, 0], [999, 0], [999, 999], [0, 999]]},
            "elements": [{"height_m": 4000.0}],
            "organization_id": "someone-elses-org",
        },
    )

    assert response.status_code == 201, response.text
    element = cad.worker.last.request["elements"][0]
    points = element["footprint"]["points"]
    # The footprint came from the alternative's parameters, in metres, derived from
    # the design engine -- not from the request body.
    assert points[0] == [0.0, 0.0]
    assert points[1] == [pytest.approx(parameters["footprint_width_m"], rel=1e-6), 0.0]
    assert points[1][0] < 999, "the client's 999 m footprint must not have been used"
    assert element["height_m"] == pytest.approx(
        parameters["floor_count"] * parameters["floor_to_floor_height_m"], rel=1e-9
    )
    assert element["height_m"] < 1000.0, "the client's 4000 m height must not have been used"
    assert element["source_reference"] == f"design_alternative:{alternative['id']}"


async def test_cad_worker_failure_is_a_recorded_outcome_not_a_transport_error(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)
    cad.worker_with(FAILING)

    response = await api.post(_cad_url(project, version, alternative), headers=headers)

    # A job that ran and failed is a 201 with a row, so the failure is reviewable.
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["error"]["code"]
    assert body["error"]["message"]
    assert body["artifacts"] == []
    assert body["geometry_artifact_id"] is None

    # The run is durable, not merely echoed back.
    status = await api.get(_job_url(project, version, body["id"]), headers=headers)
    assert status.status_code == 200
    assert status.json()["status"] == "FAILED"
    assert status.json()["error"]["code"] == body["error"]["code"]
    assert (await api.get(_job_url(project, version, body["id"]) + "/artifacts", headers=headers)).json()[
        "artifacts"
    ] == []


async def test_cad_failure_message_does_not_leak_internal_paths(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)
    cad.worker_with(FAILING)

    body = (await api.post(_cad_url(project, version, alternative), headers=headers)).json()

    message = body["error"]["message"]
    assert "Traceback" not in message
    assert "\\" not in message, "the failure must not carry a filesystem path"
    assert "cad-job" not in message, "the failure must not carry the worker's scratch path"


async def test_cad_absent_toolchain_is_503_and_records_nothing(api, cad):
    cad.set(worker_python="H:/no/such/python.exe")
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)

    response = await api.post(_cad_url(project, version, alternative), headers=headers)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "CAD_DEPENDENCY_MISSING"
    # No worker ran, so there is no run to report.
    assert cad.worker.count == 0


async def test_cad_rejects_an_uncommitted_version_before_looking_for_the_alternative(
    api, cad
):
    """Geometry requires a committed World Model.

    The version is checked before the alternative, so a request naming an alternative
    that cannot exist on a draft is still refused for the reason that matters. The
    worker is not launched: nothing was invoked, so there is nothing to record.
    """
    headers, _, project, version = await _committed_project(api)
    created = await api.post(
        f"/api/v1/projects/{project['id']}/versions",
        headers={**headers, "Idempotency-Key": "p18-floor-change"},
        json={
            "expected_current_version_id": version["id"],
            "expected_revision": version["revision_number"],
            "change_summary": "6 to 8 floors",
            "changes": {"floor_count": 8},
        },
    )
    assert created.status_code == 201, created.text
    draft = created.json()["version"]
    assert draft["status"] != "COMMITTED"

    response = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{draft['id']}"
        f"/design/alternatives/{uuid.uuid4()}/cad",
        headers=headers,
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "WORLD_MODEL_INVALID"
    # The caller is told what state the version is actually in.
    assert body["context"]["version_status"] == draft["status"]
    assert cad.worker.count == 0


async def test_cad_rejects_an_unknown_alternative(api, cad):
    headers, _, project, version = await _committed_project(api)

    response = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}"
        f"/design/alternatives/{uuid.uuid4()}/cad",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ALTERNATIVE_NOT_FOUND"


async def test_cad_rejects_an_alternative_from_another_version(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)
    created = await api.post(
        f"/api/v1/projects/{project['id']}/versions",
        headers={**headers, "Idempotency-Key": "p18-alt-version"},
        json={
            "expected_current_version_id": version["id"],
            "expected_revision": version["revision_number"],
            "change_summary": "7 floors",
            "changes": {"floor_count": 7},
        },
    )
    other = created.json()["version"]
    commit = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{other['id']}/world-model",
        headers=headers,
        json={"expected_revision": other["revision_number"], "commit": True},
    )
    assert commit.status_code == 200, commit.text

    response = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{other['id']}"
        f"/design/alternatives/{alternative['id']}/cad",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ALTERNATIVE_NOT_FOUND"


async def test_cad_rejects_an_alternative_bound_to_a_superseded_world_model(api, cad, db):
    """A stale alternative must not reach the kernel.

    A committed version is immutable, so the World Model it was committed with cannot
    change underneath it and this state is not reachable through the public API. The
    guard is therefore defence-in-depth: it exists for the case where an alternative
    was recorded against a world model hash that is no longer the one in force, which
    is exactly what a bug in the design cascade or a future feature would produce.
    Sending it to CAD would produce a solid that provably describes a building the
    project no longer contains.
    """
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)
    async with db() as session:
        row = await session.get(DesignAlternative, alternative["id"])
        row.input_world_model_hash = "0" * 64
        await session.commit()

    response = await api.post(_cad_url(project, version, alternative), headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_ARTIFACT"


async def test_cad_runs_are_tenant_scoped_on_every_endpoint(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)
    created = await _generate(api, headers, project, version, alternative)
    artifact = created["artifacts"][0]

    other_headers, _, _, _ = await _committed_project(api, "b")

    for path in (
        _job_url(project, version, created["id"]),
        _job_url(project, version, created["id"]) + "/artifacts",
        _download_url(project, version, artifact["id"]),
    ):
        denied = await api.get(path, headers=other_headers)
        assert denied.status_code == 404, f"{path} leaked across tenants: {denied.status_code}"

    generated = await api.post(_cad_url(project, version, alternative), headers=other_headers)
    assert generated.status_code == 404


def _error(response: httpx.Response) -> dict:
    """The comparable part of an error body.

    The envelope carries a per-request ``request_id``, which differs by
    construction, so identity comparisons have to ignore it.
    """
    body = response.json()["error"]
    return {"code": body["code"], "message": body["message"], "context": body["context"]}


async def test_cad_unknown_run_and_artifact_ids_are_the_same_404(api, cad):
    headers, _, project, version = await _committed_project(api)

    unknown_job = await api.get(_job_url(project, version, uuid.uuid4()), headers=headers)
    unknown_artifacts = await api.get(
        _job_url(project, version, uuid.uuid4()) + "/artifacts", headers=headers
    )
    unknown_download = await api.get(_download_url(project, version, uuid.uuid4()), headers=headers)

    assert unknown_job.status_code == 404
    assert unknown_job.json()["error"]["code"] == "CAD_JOB_NOT_FOUND"
    # Both run endpoints report an unresolvable run identically.
    assert unknown_artifacts.status_code == unknown_job.status_code
    assert _error(unknown_artifacts) == _error(unknown_job)
    assert unknown_download.status_code == 404
    assert unknown_download.json()["error"]["code"] == "CAD_ARTIFACT_NOT_FOUND"


async def test_cad_download_404s_when_the_stored_bytes_are_pruned(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)
    created = await _generate(api, headers, project, version, alternative)
    artifact = next(a for a in created["artifacts"] if a["kind"] == "step")

    # The row survives a pruning of the content-addressed store.
    stored = cad.artifact_root / artifact["storage_key"]
    assert stored.is_file()
    stored.unlink()

    pruned = await api.get(_download_url(project, version, artifact["id"]), headers=headers)
    unknown = await api.get(_download_url(project, version, uuid.uuid4()), headers=headers)

    # A 404, not a 500, and indistinguishable from an id that never existed.
    assert pruned.status_code == 404
    assert _error(pruned) == _error(unknown)


async def test_cad_two_runs_of_one_alternative_are_separately_recorded(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)

    first = await _generate(api, headers, project, version, alternative)
    second = await _generate(api, headers, project, version, alternative)

    # Two invocations, two runs, two correlation ids -- and both stay addressable.
    assert first["id"] != second["id"]
    assert first["job_id"] != second["job_id"]
    for body in (first, second):
        assert (await api.get(_job_url(project, version, body["id"]), headers=headers)).status_code == 200


async def test_cad_identical_geometry_reuses_the_stored_artifact(api, cad):
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)

    first = await _generate(api, headers, project, version, alternative)
    second = await _generate(api, headers, project, version, alternative)

    # Same design parameters, same bytes, so the content-addressed store collapses
    # them. Reuse happens at the artifact level, which is why the run still happened.
    assert {a["sha256"] for a in first["artifacts"]} == {a["sha256"] for a in second["artifacts"]}
    assert first["request_hash"] == second["request_hash"]


async def test_cad_run_is_reported_stale_when_its_world_model_moved_on(api, cad, db):
    """A run whose recorded world model hash is no longer current must not read as
    current, even before the staleness cascade has rewritten its row.

    Reporting staleness from the recorded hash as well as the status is deliberate:
    between the World Model changing and the cascade running, a `SUCCEEDED` row whose
    input hash no longer matches is a superseded result being served as the answer.
    """
    headers, _, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)
    created = await _generate(api, headers, project, version, alternative)
    assert created["stale"] is False

    async with db() as session:
        row = await session.get(CadJobRun, created["id"])
        row.input_world_model_hash = "0" * 64
        await session.commit()

    status = await api.get(_job_url(project, version, created["id"]), headers=headers)

    assert status.status_code == 200
    # The run is still there -- it is evidence of what was computed -- but it no
    # longer describes the project, and says so.
    assert status.json()["stale"] is True
    assert status.json()["status"] == "STALE"
    assert status.json()["input_world_model_hash"] == "0" * 64


async def test_cad_does_not_block_the_event_loop_while_a_job_runs(api, cad):
    """A slow kernel must delay only its own request.

    This is why the orchestrator hands the blocking work to a worker thread. If the
    worker were awaited on the event loop, the concurrent request below could not
    complete until the job did.
    """
    headers, org, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)
    cad.worker_with(SLOW)
    # A short budget so the slow worker's 60 s sleep is cut short promptly.
    cad.set(job_timeout_seconds=1.0)

    job = asyncio.ensure_future(api.post(_cad_url(project, version, alternative), headers=headers))
    try:
        # Let the request reach the worker, then prove the loop is still free.
        await asyncio.sleep(0.3)
        assert not job.done(), "the CAD request finished before the slow worker could"
        concurrent = await api.get("/api/v1/organizations", headers=headers)
        assert concurrent.status_code == 200
        assert [o["id"] for o in concurrent.json()] == [org["id"]]
        response = await asyncio.wait_for(job, timeout=60)
    finally:
        if not job.done():  # pragma: no cover - only on an unexpected failure
            job.cancel()

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["error"]["code"] == "CAD_JOB_TIMEOUT"
