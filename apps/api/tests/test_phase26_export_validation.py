from __future__ import annotations

import hashlib
import io
import json
import struct
import zipfile

import pytest

from app.domains.cad.export_validation import validate_export


STEP = b"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('AIrchitect export'),'2;1');
FILE_NAME('building.step','2026-10-11T00:00:00',('AIrchitect'),('AIrchitect'),'','AIrchitect','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN_CC2'));
ENDSEC;
DATA;
ENDSEC;
END-ISO-10303-21;
"""

IFC = b"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [ReferenceView_V1.2]'),'2;1');
FILE_NAME('building.ifc','2026-10-11T00:00:00',('AIrchitect'),('AIrchitect'),'','AIrchitect','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
ENDSEC;
END-ISO-10303-21;
"""


def glb_bytes(*, meshes: bool = True) -> bytes:
    document = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
                "nodes": [{"mesh": 0}] if meshes else [{}],
                "meshes": [{"primitives": []}] if meshes else []}
    payload = json.dumps(document, separators=(",", ":")).encode()
    payload += b" " * ((4 - len(payload) % 4) % 4)
    chunk = struct.pack("<II", len(payload), 0x4E4F534A) + payload
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunk)) + chunk


def freecad_bytes() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Document.xml", "<Document/>")
        archive.writestr("GuiDocument.xml", "<GuiDocument/>")
    return stream.getvalue()


def validate(kind: str, data: bytes, content_type: str | None = None) -> dict:
    return validate_export(kind, data, declared_sha256=hashlib.sha256(data).hexdigest(),
                           declared_size=len(data), declared_content_type=content_type)


@pytest.mark.parametrize("kind,data,content_type", [
    ("step", STEP, "model/step"),
    ("ifc", IFC, "application/x-ifc"),
    ("glb", glb_bytes(), "model/gltf-binary"),
    ("freecad_document", freecad_bytes(), "application/vnd.freecad"),
])
def test_exchange_exports_pass_integrity_and_format_checks(kind: str, data: bytes, content_type: str):
    result = validate(kind, data, content_type)
    assert result["status"] == "PASS"
    assert all(check["status"] == "PASS" for check in result["checks"])


def test_step_export_with_missing_footer_fails():
    result = validate("step", STEP.replace(b"END-ISO-10303-21;", b""))
    assert result["status"] == "FAIL"
    assert "EXCHANGE_FOOTER" in {check["code"] for check in result["checks"] if check["status"] == "FAIL"}


def test_ifc_export_requires_recognized_ifc_schema():
    data = IFC.replace(b"IFC4", b"UNKNOWN_SCHEMA")
    result = validate("ifc", data)
    assert result["status"] == "FAIL"
    assert "IFC_SCHEMA" in {check["code"] for check in result["checks"] if check["status"] == "FAIL"}


def test_glb_declared_length_and_json_are_checked():
    data = glb_bytes()
    corrupt = data[:8] + struct.pack("<I", len(data) + 4) + data[12:]
    result = validate("glb", corrupt)
    assert result["status"] == "FAIL"
    assert "GLB_LENGTH" in {check["code"] for check in result["checks"] if check["status"] == "FAIL"}


def test_freecad_document_must_be_a_zip_with_document_xml():
    result = validate("freecad_document", b"not a FreeCAD archive")
    assert result["status"] == "FAIL"


def test_metadata_mismatch_fails_closed():
    result = validate_export("step", STEP, declared_sha256="0" * 64,
                             declared_size=len(STEP) + 1, declared_content_type="text/plain")
    assert result["status"] == "FAIL"
    failed = {check["code"] for check in result["checks"] if check["status"] == "FAIL"}
    assert {"SHA256", "BYTE_SIZE"} <= failed
    assert any(check["code"] == "CONTENT_TYPE" and check["status"] == "WARN" for check in result["checks"])


def test_brep_is_review_required_not_misrepresented_as_native_validated():
    data = b"native brep bytes"
    result = validate("brep", data)
    assert result["status"] == "REVIEW_REQUIRED"
    assert any(check["code"] == "BREP_NATIVE_VALIDATION" and check["status"] == "WARN"
               for check in result["checks"])


def test_empty_export_fails_even_when_empty_hash_matches():
    result = validate("glb", b"")
    assert result["status"] == "FAIL"
    assert "NON_EMPTY" in {check["code"] for check in result["checks"] if check["status"] == "FAIL"}
