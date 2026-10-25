from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ArtifactVersion, Project, ProjectVersion, RequirementRecord, User, WorldModelRevision
from app.domains.foundation.service import error, resolve_project_version, resolve_world_model
from app.domains.lifecycle.service import canonical_hash, new_artifact

CATALOG = {
    "office": [("Reception", "public", .06), ("Open Work", "primary", .42), ("Meeting", "primary", .10), ("Focus", "secondary", .08), ("Pantry", "service", .04), ("Toilets", "service", .06), ("Circulation", "circulation", .14), ("Core", "service", .10)],
    "retail": [("Sales Floor", "public", .52), ("Entry", "public", .05), ("Stock", "service", .14), ("Staff", "service", .06), ("Toilets", "service", .05), ("Circulation", "circulation", .10), ("Core", "service", .08)],
    "restaurant": [("Dining", "public", .38), ("Entry", "public", .05), ("Kitchen", "service", .22), ("Storage", "service", .08), ("Toilets", "service", .07), ("Circulation", "circulation", .10), ("Core", "service", .10)],
    "residential": [("Living", "public", .25), ("Bedrooms", "private", .30), ("Kitchen", "private", .10), ("Bathrooms", "service", .10), ("Circulation", "circulation", .10), ("Core", "service", .15)],
}


def _use(requirements: list[RequirementRecord]) -> str:
    for row in reversed(requirements):
        if row.parameter == "building_use" and row.status in {"CONFIRMED", "ASSUMED"}:
            value = str(row.normalized_value_json).lower()
            for key in CATALOG:
                if key in value: return key
    return "office"


def build_program(requirements: list[RequirementRecord], world: WorldModelRevision) -> dict:
    confirmed = [r for r in requirements if r.status in {"CONFIRMED", "ASSUMED"}]
    gfa_row = next((r for r in reversed(confirmed) if r.parameter == "target_gfa"), None)
    floors_row = next((r for r in reversed(confirmed) if r.parameter == "floor_count"), None)
    gfa = float(gfa_row.normalized_value_json) if gfa_row else None
    floors = int(floors_row.normalized_value_json) if floors_row else None
    assumptions = []
    unknowns = []
    if gfa is None:
        site_area = world.model_json.get("site", {}).get("area")
        site_area = site_area.get("value") if isinstance(site_area, dict) else site_area
        if site_area and floors:
            gfa = float(site_area) * .65 * floors
            assumptions.append({"parameter": "target_gfa", "value": gfa, "unit": "m2", "reason": "Preliminary program target derived from canonical site area, 65% coverage and confirmed floor count."})
        else:
            unknowns.append("target_gfa")
    if floors is None: unknowns.append("floor_count")
    if gfa is None:
        raise error(409, "PROGRAM_INPUT_INCOMPLETE", "A target GFA or enough confirmed site/floor information is required to build a bounded program", unknowns=unknowns)
    use = _use(requirements)
    catalog = CATALOG[use]
    spaces=[]
    for index,(name,category,ratio) in enumerate(catalog,1):
        target = round(gfa * ratio, 2)
        spaces.append({"id": f"space-{index:02d}", "name": name, "space_type": name.lower().replace(" ", "_"),
            "category": category, "quantity": 1, "target_area_m2": target,
            "min_area_m2": round(target*.85,2), "max_area_m2": round(target*1.15,2),
            "source": "program_template_v1", "assumption": False})
    adj=[]
    ids={s["name"]:s["id"] for s in spaces}
    for a,b,kind in [("Entry","Sales Floor","direct"),("Entry","Dining","direct"),("Sales Floor","Stock","service"),("Dining","Kitchen","service"),("Reception","Open Work","direct"),("Open Work","Meeting","direct"),("Kitchen","Storage","service")]:
        if a in ids and b in ids: adj.append({"from":ids[a],"to":ids[b],"relationship":kind,"required":True})
    return {"schema_version":"s2-program-v1","use":use,"target_gfa_m2":round(gfa,2),"floor_count":floors,
        "spaces":spaces,"adjacencies":adj,"assumptions":assumptions,"unknowns":sorted(set(unknowns)),
        "provenance":{"requirement_ids":[r.id for r in confirmed],"world_model_hash":world.model_hash,"engine":"program_template_v1"}}

async def generate(session: AsyncSession, project_id: str, version_ref: str, user: User) -> dict:
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    world = await resolve_world_model(session, version.id)
    requirements = list((await session.scalars(select(RequirementRecord).where(RequirementRecord.project_version_id == version.id)
        .order_by(RequirementRecord.created_at, RequirementRecord.id))).all())
    if any(r.status == "CONTRADICTORY" for r in requirements):
        raise error(409, "CONTRADICTORY_REQUIREMENTS", "Resolve contradictory requirements before program generation")
    payload = build_program(requirements, world)
    digest = canonical_hash(payload)
    previous = await session.scalar(select(ArtifactVersion).where(ArtifactVersion.project_version_id == version.id,
        ArtifactVersion.artifact_type == "architectural_program").order_by(ArtifactVersion.version.desc()).limit(1))
    if previous and previous.output_hash == digest:
        return {"artifact_id": previous.id, "program": previous.payload_json, "program_hash": digest, "idempotent": True}
    artifact = await new_artifact(session, project=project, version=version, world=world, actor=user.id,
        artifact_type="architectural_program", payload=payload, status="current")
    artifact.output_hash = digest
    await session.commit()
    return {"artifact_id": artifact.id, "program": payload, "program_hash": digest, "idempotent": False}
