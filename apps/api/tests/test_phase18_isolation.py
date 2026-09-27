"""Tests that enforce the process-isolation boundary of the Phase 18 pipeline.

Phase 18's central architectural claim is that the API never loads a CAD kernel:
OCCT and IfcOpenShell live in a separate virtualenv, and FreeCAD runs as a bounded
subprocess. That claim is only worth anything if it is tested, because the natural
temptation during integration is a single ``import ifcopenshell`` in a route handler
that would make the API process unbootable on any machine without the native stack.

These tests are mostly static analysis of the source, which is the point: they fail
at review time rather than at deploy time.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = API_ROOT / "app" / "cad_worker"
CAD_DOMAIN_DIR = API_ROOT / "app" / "domains" / "cad"

#: Native modules that must never be imported by the API process.
NATIVE_MODULES = ("OCP", "ifcopenshell", "FreeCAD", "Part")

#: The API is allowed to reference the worker only as a subprocess target.
API_ALLOWED_IMPORT_PREFIXES = ("app.cad_worker", "app.domains.cad")


def imported_modules(path: Path) -> set[str]:
    """Return every top-level module name imported by the file at *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # Relative imports (level > 0) belong to this package.
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def api_source_files() -> list[Path]:
    """Return every API source file that is not part of the worker package."""
    return [
        path
        for path in (API_ROOT / "app").rglob("*.py")
        if "cad_worker" not in path.parts
    ]


class TestApiNeverImportsANativeKernel:
    @pytest.mark.parametrize("module", NATIVE_MODULES)
    def test_no_api_module_imports_a_native_module(self, module):
        offenders = [
            str(path.relative_to(API_ROOT))
            for path in api_source_files()
            if module in imported_modules(path)
        ]
        assert not offenders, (
            f"{module} must not be imported by the API process; it belongs to the "
            f"worker virtualenv. Offending files: {offenders}"
        )

    def test_the_checked_in_worker_env_is_absent_from_api_dependencies(self):
        # A dependency declaration is how a native kernel sneaks into the API
        # image even when no import statement is present. The file is parsed
        # rather than grepped, because the mypy override section legitimately
        # names these packages when explaining why they are absent.
        import tomllib

        data = tomllib.loads((API_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = data.get("project", {})
        declared: list[str] = list(project.get("dependencies", []))
        for group in project.get("optional-dependencies", {}).values():
            declared.extend(group)
        for group in data.get("dependency-groups", {}).values():
            declared.extend(group)
        build = data.get("build-system", {}).get("requires", [])
        declared.extend(build)

        lowered = " ".join(declared).lower()
        for package in ("cadquery-ocp", "cadquery_ocp", "ifcopenshell", "freecad"):
            assert package not in lowered, f"{package} must not be an API dependency"

    def test_importing_the_cad_domain_does_not_load_a_kernel(self):
        script = (
            "import sys;"
            "import app.domains.cad.protocol, app.domains.cad.hashing,"
            " app.domains.cad.config, app.cad_worker.mesh, app.cad_worker.geometry;"
            "loaded=[m for m in sys.modules if m.split('.')[0] in "
            "('OCP','ifcopenshell','FreeCAD')];"
            "print(','.join(sorted(loaded)))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=str(API_ROOT),
            check=True,
        )
        assert result.stdout.strip() == "", (
            f"importing the CAD modules pulled in a native kernel: {result.stdout.strip()}"
        )


class TestFreeCadAdapterIsSelfContained:
    """The FreeCAD script runs inside FreeCAD's own interpreter.

    It therefore cannot rely on anything from the API package, and it must not use
    the IFC library FreeCAD happens to vendor.
    """

    @property
    def script(self) -> Path:
        return WORKER_DIR / "freecad_script.py"

    def test_script_exists(self):
        assert self.script.is_file()

    def test_never_imports_ifcopenshell(self):
        # FreeCAD 1.1.3 vendors ifcopenshell 0.8.4. Using it would mean two IFC
        # implementations with different behaviour behind one output format.
        assert "ifcopenshell" not in imported_modules(self.script)

    def test_only_imports_stdlib_and_freecad(self):
        allowed = set(sys.stdlib_module_names) | {"FreeCAD", "Part", "Import"}
        unexpected = imported_modules(self.script) - allowed
        assert not unexpected, (
            f"freecad_script.py must stay dependency-free; unexpected imports: {unexpected}"
        )

    def test_does_not_import_the_api_package(self):
        assert "app" not in imported_modules(self.script)

    def test_does_not_execute_user_supplied_python(self):
        text = self.script.read_text(encoding="utf-8")
        for danger in ("exec(", "eval(", "compile(", "__import__"):
            assert danger not in text, f"freecad_script.py must not use {danger}"

    def test_receives_its_request_by_environment_variable(self):
        # freecadcmd treats a trailing file argument as a document to import and
        # crashes on JSON, so the worker passes the path in the environment.
        text = self.script.read_text(encoding="utf-8")
        assert "AIRCHITECT_CAD_REQUEST" in text

    def test_runs_main_unconditionally(self):
        # FreeCAD imports the file as a module, so __name__ is never
        # "__main__"; guarding on it would silently do nothing.
        text = self.script.read_text(encoding="utf-8")
        assert '__name__ == "__main__"' not in text


class TestWorkerEntryPointInvokesFreeCadSafely:
    def test_freecad_is_invoked_with_an_argv_list_not_a_shell_string(self):
        text = (WORKER_DIR / "main.py").read_text(encoding="utf-8")
        assert "shell=True" not in text, "the worker must never use shell=True"

    def test_request_path_is_passed_by_environment_not_argv(self):
        text = (WORKER_DIR / "main.py").read_text(encoding="utf-8")
        assert "_FREECAD_REQUEST_ENV" in text

    def test_worker_never_imports_the_api_domain_package(self):
        # The worker owns geometry; the API owns policy. Sharing would drag the
        # API's dependency tree into the worker virtualenv.
        offenders = [
            str(path.relative_to(API_ROOT))
            for path in WORKER_DIR.glob("*.py")
            if path.name != "freecad_script.py"
            and "app.domains" in imported_modules(path)
        ]
        assert not offenders, f"worker modules must not import API domains: {offenders}"


class TestToolchainManifest:
    def test_manifest_is_valid_json_and_records_the_stack(self):
        import json

        manifest_path = CAD_DOMAIN_DIR / "toolchain_manifest.json"
        assert manifest_path.is_file(), "the toolchain manifest must be committed"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest
        text = json.dumps(manifest).lower()
        for expected in ("ocp", "ifcopenshell", "freecad", "lgpl"):
            assert expected in text, f"the manifest should record {expected}"

    def test_occt_exception_is_recorded(self):
        # cadquery-ocp's wrapper is Apache-2.0 but the bundled OCCT is LGPL with
        # an exception; conflating the two would misstate the obligations.
        import json

        manifest = json.loads(
            (CAD_DOMAIN_DIR / "toolchain_manifest.json").read_text(encoding="utf-8")
        )
        text = json.dumps(manifest).lower()
        assert "apache" in text
        assert "exception" in text
