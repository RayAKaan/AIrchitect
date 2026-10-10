"""Format-level validation for persisted CAD/BIM exports.

This module deliberately uses only the Python standard library. The API must not
load FreeCAD, OCCT, or IfcOpenShell; native geometry work remains isolated in the
CAD worker. These checks verify artifact integrity and container/exchange-format
structure, not architectural correctness or full vendor interoperability.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import struct
import zipfile
from typing import Any

from app.domains.cad.protocol import ARTIFACT_CONTENT_TYPES

SUPPORTED_FORMATS = frozenset({"glb", "step", "ifc", "freecad_document", "brep"})


def _check(code: str, passed: bool, detail: str, *, actual: Any = None, expected: Any = None) -> dict[str, Any]:
    return {
        "code": code,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
        "actual": actual,
        "expected": expected,
    }


def _step_checks(data: bytes, *, ifc: bool) -> list[dict[str, Any]]:
    text = data.decode("latin-1", errors="replace").lstrip("\ufeff \t\r\n")
    label = "IFC" if ifc else "STEP"
    checks = [
        _check("EXCHANGE_HEADER", bool(re.match(r"^ISO-10303-21\s*;", text, re.IGNORECASE)),
               f"{label} exchange header is present"),
        _check("EXCHANGE_FOOTER", bool(re.search(r"END-ISO-10303-21\s*;\s*$", text, re.IGNORECASE)),
               f"{label} exchange footer is present"),
        _check("EXCHANGE_SECTIONS", bool(re.search(r"\bHEADER\s*;", text, re.IGNORECASE))
               and bool(re.search(r"\bDATA\s*;", text, re.IGNORECASE)),
               f"{label} HEADER and DATA sections are present"),
        _check("EXCHANGE_SCHEMA", bool(re.search(r"FILE_SCHEMA\s*\(", text, re.IGNORECASE)),
               f"{label} FILE_SCHEMA declaration is present"),
    ]
    if ifc:
        schema = re.search(r"FILE_SCHEMA\s*\(\s*\(?\s*'?(IFC(?:2X3|4X3|4))", text, re.IGNORECASE)
        checks.append(_check("IFC_SCHEMA", schema is not None,
                             "A recognized IFC2X3, IFC4, or IFC4X3 schema is declared",
                             actual=schema.group(1).upper() if schema else None,
                             expected=["IFC2X3", "IFC4", "IFC4X3"]))
    return checks


def _glb_checks(data: bytes) -> list[dict[str, Any]]:
    if len(data) < 12:
        return [_check("GLB_HEADER", False, "GLB is shorter than its 12-byte header")]
    magic, version, declared_length = struct.unpack_from("<4sII", data, 0)
    checks = [
        _check("GLB_MAGIC", magic == b"glTF", "GLB magic identifies a binary glTF file",
               actual=magic.decode("latin-1", errors="replace"), expected="glTF"),
        _check("GLB_VERSION", version == 2, "GLB version is supported", actual=version, expected=2),
        _check("GLB_LENGTH", declared_length == len(data), "GLB declared length matches the actual byte length",
               actual=declared_length, expected=len(data)),
    ]
    if magic != b"glTF" or declared_length != len(data):
        return checks

    offset = 12
    chunk_index = 0
    parsed_json: dict[str, Any] | None = None
    while offset < len(data):
        if offset + 8 > len(data):
            checks.append(_check("GLB_CHUNK_HEADER", False, "GLB contains a truncated chunk header"))
            return checks
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        end = offset + chunk_length
        if end > len(data):
            checks.append(_check("GLB_CHUNK_BOUNDS", False, "GLB chunk exceeds the declared file bounds",
                                 actual=end, expected=len(data)))
            return checks
        chunk = data[offset:end]
        if chunk_index == 0:
            is_json = chunk_type == 0x4E4F534A
            checks.append(_check("GLB_JSON_CHUNK", is_json, "The first GLB chunk is JSON"))
            if is_json:
                try:
                    decoded = chunk.decode("utf-8").rstrip(" \t\r\n\x00")
                    candidate = json.loads(decoded)
                    parsed_json = candidate if isinstance(candidate, dict) else None
                    checks.append(_check("GLB_JSON_VALID", parsed_json is not None,
                                         "The GLB JSON chunk is a JSON object"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    checks.append(_check("GLB_JSON_VALID", False, "The GLB JSON chunk is valid UTF-8 JSON"))
        offset = end
        chunk_index += 1
    checks.append(_check("GLB_CHUNKS", chunk_index > 0 and offset == len(data),
                         "GLB chunks exactly cover the file", actual=offset, expected=len(data)))
    asset = parsed_json.get("asset") if parsed_json else None
    asset_version = asset.get("version") if isinstance(asset, dict) else None
    checks.append(_check("GLTF_ASSET_VERSION", asset_version == "2.0",
                         "The glTF asset declares version 2.0", actual=asset_version, expected="2.0"))
    if parsed_json is not None and not parsed_json.get("meshes"):
        checks.append({
            "code": "GLB_MESHES",
            "status": "WARN",
            "detail": "No mesh objects were found; confirm that this is an intentional non-geometric scene.",
            "actual": 0,
            "expected": "one or more for a building massing export",
        })
    return checks


def _freecad_checks(data: bytes) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            has_document = "Document.xml" in names
            bad_member = archive.testzip()
        return [
            _check("FCSTD_ARCHIVE", True, "FreeCAD document is a readable ZIP container"),
            _check("FCSTD_DOCUMENT", has_document, "FreeCAD document contains Document.xml"),
            _check("FCSTD_MEMBERS", bad_member is None, "FreeCAD archive members pass CRC checks",
                   actual=bad_member, expected=None),
        ]
    except (zipfile.BadZipFile, OSError, ValueError):
        return [_check("FCSTD_ARCHIVE", False, "FreeCAD document is not a readable ZIP container")]


def validate_export(
    kind: str,
    data: bytes,
    *,
    declared_sha256: str,
    declared_size: int,
    declared_content_type: str | None = None,
) -> dict[str, Any]:
    """Validate byte integrity and a format-specific structural signature."""
    checks: list[dict[str, Any]] = []
    actual_sha256 = hashlib.sha256(data).hexdigest()
    checks.extend([
        _check("NON_EMPTY", bool(data), "Export is not empty", actual=len(data), expected="> 0 bytes"),
        _check("BYTE_SIZE", len(data) == declared_size, "Stored byte count matches artifact metadata",
               actual=len(data), expected=declared_size),
        _check("SHA256", actual_sha256 == declared_sha256, "Content SHA-256 matches artifact metadata",
               actual=actual_sha256, expected=declared_sha256),
    ])
    if kind not in SUPPORTED_FORMATS:
        checks.append(_check("SUPPORTED_FORMAT", False, "Artifact kind has no registered export validator",
                             actual=kind, expected=sorted(SUPPORTED_FORMATS)))
    elif data:
        if kind == "glb":
            checks.extend(_glb_checks(data))
        elif kind == "step":
            checks.extend(_step_checks(data, ifc=False))
        elif kind == "ifc":
            checks.extend(_step_checks(data, ifc=True))
        elif kind == "freecad_document":
            checks.extend(_freecad_checks(data))
        elif kind == "brep":
            checks.append({
                "code": "BREP_NATIVE_VALIDATION",
                "status": "WARN",
                "detail": "B-rep bytes and hash are verified, but native topology validation requires the isolated CAD worker.",
                "actual": None,
                "expected": "native-kernel validation",
            })
    expected_content_type = ARTIFACT_CONTENT_TYPES.get(kind)
    if expected_content_type and declared_content_type and declared_content_type != expected_content_type:
        checks.append({
            "code": "CONTENT_TYPE",
            "status": "WARN",
            "detail": "Stored media type differs from the API's registered type for this format.",
            "actual": declared_content_type,
            "expected": expected_content_type,
        })
    statuses = {check["status"] for check in checks}
    status = "FAIL" if "FAIL" in statuses else "REVIEW_REQUIRED" if "WARN" in statuses else "PASS"
    return {
        "schema_version": "1.0.0",
        "kind": kind,
        "status": status,
        "sha256": actual_sha256,
        "byte_size": len(data),
        "checks": checks,
        "limitations": [
            "Format checks do not prove full round-trip interoperability in every target CAD/BIM application.",
            "Passing export validation does not certify architectural design, structure, code compliance, or constructability.",
        ],
    }


__all__ = ["SUPPORTED_FORMATS", "validate_export"]
