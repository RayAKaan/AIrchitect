from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domains.model import ArchitecturalModel, Building, Level, Point3D, Site, Space
from app.domains.regulatory.canonical import CanonicalRegulatoryRequest, build_canonical_regulatory_package
from app.domains.regulatory.evidence import EvidenceRecord
from app.domains.regulatory.rulepacks import RuleApplicability, RuleDefinition, RulePack


SOURCE = "https://authority.example/building-code/section-1"


def _model() -> ArchitecturalModel:
    return ArchitecturalModel(
        project_id="project-1",
        revision=3,
        site=Site(id="site-1", width_m=30, depth_m=20),
        buildings=(Building(id="building-1", name="Main", site_id="site-1"),),
        levels=(Level(id="level-1", building_id="building-1", name="Ground", elevation_m=0, height_m=3),),
        spaces=(Space(
            id="room-1", level_id="level-1", name="Room",
            boundary=(
                Point3D(x=0, y=0, z=0), Point3D(x=10, y=0, z=0),
                Point3D(x=10, y=8, z=0), Point3D(x=0, y=8, z=0),
            ),
        ),),
    )


def _pack() -> RulePack:
    return RulePack(
        pack_id="saudi-custom-test-pack",
        profile_id="saudi-arabia",
        version="1.0",
        status="executable",
        source_refs=(SOURCE,),
        rules=(RuleDefinition(
            rule_id="site-width-min",
            title="Minimum site width",
            subject="site.width_m",
            check_type="numeric_min",
            expected=20,
            unit="m",
            applicability=RuleApplicability(),
            source_refs=(SOURCE,),
        ),),
    )


def _evidence() -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="evidence-1",
        source_ref=SOURCE,
        title="Authority code extract",
        edition="2026",
        locator="Section 1",
        verification_status="verified",
        reviewer_ref="reviewer-1",
        content_digest="a" * 64,
    )


def test_canonical_regulatory_package_binds_current_facts_to_verified_evidence():
    request = CanonicalRegulatoryRequest(pack=_pack(), evidence_records=(_evidence(),))
    result = build_canonical_regulatory_package(_model(), "version-1", request)

    assert result["source_model_hash"]
    assert result["package_hash"]
    assert result["facts"]["site.width_m"]["value"] == 30
    assert result["evaluation"]["findings"][0]["status"] == "pass"
    assert result["evidence"]["verified_count"] == 1
    assert result["verification"]["status"] == "verified"


def test_canonical_regulatory_package_blocks_unverified_or_missing_evidence():
    request = CanonicalRegulatoryRequest(pack=_pack())
    result = build_canonical_regulatory_package(_model(), "version-1", request)

    assert result["evidence"]["finding_count"] == 1
    assert result["evidence"]["verified_count"] == 0
    assert result["verification"]["status"] == "blocked"


def test_catalog_only_jurisdiction_pack_cannot_be_executed():
    pack = _pack().model_copy(update={"status": "catalog_only"})
    with pytest.raises(ValidationError, match="Catalog-only rule packs cannot be executed"):
        CanonicalRegulatoryRequest(pack=pack)


def test_verified_evidence_requires_reviewer_and_content_digest():
    with pytest.raises(ValidationError, match="Verified evidence requires reviewer_ref and content_digest"):
        CanonicalRegulatoryRequest(
            pack=_pack(),
            evidence_records=(EvidenceRecord(
                evidence_id="evidence-1",
                source_ref=SOURCE,
                title="Unverified extract",
                verification_status="verified",
            ),),
        )


def test_canonical_regulatory_routes_are_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/projects/{project_id}/regulatory-evidence/generate" in paths
    assert "/api/v1/projects/{project_id}/regulatory-evidence" in paths
