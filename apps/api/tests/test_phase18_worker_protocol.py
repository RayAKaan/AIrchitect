"""Guards the request contract between the API and the CAD worker.

The API validates requests with pydantic; the worker reads the same document as a
plain ``dict``. Nothing makes the two agree, and both kinds of disagreement fail
silently rather than loudly:

* a key the worker reads but the API does not declare is defaulted by the worker,
  so a setting such as ``cad_freecad_timeout_seconds`` looks like it does
  something while the worker quietly ignores the configured value;
* a field the API declares but the worker never reads is accepted, validated, and
  then discarded, so a caller who sets it gets a successful job that did not
  honour it.

The first of those was a real bug: ``freecad_timeout_seconds`` was configured,
used as the outer subprocess limit, and never sent, so the worker's inner FreeCAD
timeout was permanently 180s. The checks below exist so that the next such gap is
a test failure rather than a production surprise.

The worker's key set is derived from its source rather than restated here, so a
key the worker starts reading is picked up automatically.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.domains.cad.protocol import CadJobRequest, Footprint, MassingElement

CAD_WORKER = Path(__file__).resolve().parents[1] / "app" / "cad_worker"

# Keys the API may legitimately send without the worker reading them.
#
# schema_version is a wire-format stamp that the worker never needs to act on, and
# the remaining fields are API-side provenance: they are recorded alongside the
# result so an artifact can be traced back to the alternative, world model
# revision, and site it came from. Silently ignoring them is the intended
# behaviour, not a defect.
API_ONLY_KEYS = frozenset({"schema_version", "alternative_ref", "site"})

# Worker entry points that receive a parsed request document.
WORKER_ENTRY_POINTS = ("main", "run_job", "_run_freecad", "_dispatch")


def _attribute_chain(node: ast.AST) -> str | None:
    """Return ``request["key"]`` / ``request.get("key")`` keys as a set holder.

    Returns the literal string key when *node* is a subscript or call on a name
    whose identifier suggests it is the request, otherwise ``None``.
    """
    if isinstance(node, ast.Subscript):
        base, _, key = node.value, None, node.slice
        if not isinstance(base, ast.Name) or not _is_request_name(base.id):
            return None
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            return key.value
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr != "get" or not node.args:
            return None
        base = node.func.value
        if not isinstance(base, ast.Name) or not _is_request_name(base.id):
            return None
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return None


def _is_request_name(name: str) -> bool:
    return "request" in name.lower()


def _keys_from_source(path: Path) -> set[str]:
    """Collect ``request["key"]`` and ``request.get("key")`` literals in *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Subscript, ast.Call)):
            key = _attribute_chain(node)
            if key is not None:
                found.add(key)
    return found


def worker_request_keys() -> set[str]:
    """Every request key the worker reads, across all worker modules."""
    keys: set[str] = set()
    for module in sorted(CAD_WORKER.glob("*.py")):
        keys |= _keys_from_source(module)
    return keys


def test_the_worker_source_is_actually_parsed() -> None:
    """Guard the guard: a regex/AST change must not silently find nothing."""
    keys = worker_request_keys()
    assert "elements" in keys, "extraction found no request keys; the AST walk is broken"
    assert "output_dir" in keys


def test_worker_reads_exactly_the_declared_request_fields() -> None:
    """The worker's read set and the API's field set must be the same set."""
    read = worker_request_keys()
    declared = set(CadJobRequest.model_fields)

    # A key the worker reads but the API does not send means the worker silently
    # substitutes its own default for a value the operator configured.
    unsent = read - declared
    assert not unsent, (
        "worker reads request keys the API never sends; they will be silently "
        f"defaulted: {sorted(unsent)}"
    )

    # A field the API sends but the worker never reads means a caller can set it
    # and get a successful job that ignored it.
    unread = declared - read - API_ONLY_KEYS
    assert not unread, (
        "CadJobRequest declares fields the worker never reads; they are validated "
        f"then discarded: {sorted(unread)}"
    )


def test_the_freecad_timeout_setting_reaches_the_request() -> None:
    """The configured FreeCAD timeout must actually be sent to the worker.

    This is the regression test for the bug described in the module docstring. The
    assertion is on the stamped document rather than on the value, because the
    failure mode was "the setting is never transmitted at all".
    """
    from app.domains.cad.config import CadConfig
    from app.domains.cad.runner import _prepare_request

    config = CadConfig(
        worker_venv_root="/nonexistent/venv",
        freecad_root="/nonexistent/freecad",
        artifact_root="/nonexistent/artifacts",
        freecad_timeout_seconds=642.5,
    )
    element = {
        "id": "m1",
        "kind": "building_mass",
        "name": "M1",
        "footprint": {"points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        "base_elevation_m": 0.0,
        "height_m": 12.0,
        "material_class": "conceptual_mass",
    }
    request = CadJobRequest.model_validate({"elements": [element]})

    import json
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        path = _prepare_request(request, config, out)
        document = json.loads(path.read_text(encoding="utf-8"))

    assert document["freecad_timeout_seconds"] == 642.5


def test_worker_tolerates_the_absence_of_optional_keys() -> None:
    """No ``request.get(key)`` may lack both a default and an ``or`` guard.

    ``elements`` is the only required key, so a request carrying only elements
    must stay valid. This codebase spells the fallback as
    ``request.get(key) or default`` rather than passing a second argument to
    ``get``, so both forms count as guarded; a bare ``request.get(key)`` would
    yield ``None`` and surface later as an unhelpful failure deep in the worker.
    """
    for module in sorted(CAD_WORKER.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        parents: dict[int, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[id(child)] = node

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "get"):
                continue
            base = func.value
            if not (isinstance(base, ast.Name) and _is_request_name(base.id)):
                continue
            if len(node.args) >= 2 or node.keywords:
                continue  # an explicit default was supplied

            parent = parents.get(id(node))
            guarded = (
                isinstance(parent, ast.BoolOp)
                and isinstance(parent.op, ast.Or)
                and any(child is node for child in parent.values)
            )
            assert guarded, (
                f"{module.name}:{node.lineno} calls request.get() with no default and "
                "no `or` fallback, so an omitted key would yield None"
            )


def test_no_lowercase_typos_in_worker_key_literals() -> None:
    """Catch a hand-edited key that differs from the API's field by case.

    Pydantic field names are snake_case; a worker literal in camelCase would read
    a key that is never present, defaulting silently.
    """
    camel = re.compile(r"[a-z][A-Z]")
    offenders = {k for k in worker_request_keys() if camel.search(k)}
    assert not offenders, f"request keys must be snake_case: {sorted(offenders)}"
