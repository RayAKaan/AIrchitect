"""Audit statically declared backend test skips and require explicit classification."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

CATEGORIES = (
    "POSTGRES_REQUIRED",
    "NATIVE_CAD_REQUIRED",
    "BROKEN",
    "OBSOLETE",
    "ENVIRONMENTAL",
    "INTENTIONAL",
    "UNCLASSIFIED",
)


def literal_reason(node: ast.Call) -> str:
    """Return a statically available skip reason when one exists."""
    reason = next((keyword.value for keyword in node.keywords if keyword.arg == "reason"), None)
    if isinstance(reason, ast.Constant) and isinstance(reason.value, str):
        return reason.value
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0].value
    return ""


def classify(reason: str) -> str:
    normalized = reason.lower()
    if any(term in normalized for term in ("postgres", "postgis", "postgresql")):
        return "POSTGRES_REQUIRED"
    if any(term in normalized for term in ("freecad", "ifcopenshell", "occt", "native cad", "native toolchain")):
        return "NATIVE_CAD_REQUIRED"
    if any(term in normalized for term in ("environment", "platform", "windows", "linux", "macos")):
        return "ENVIRONMENTAL"
    if any(term in normalized for term in ("obsolete", "deprecated test", "no longer valid")):
        return "OBSOLETE"
    if any(term in normalized for term in ("broken", "known failure", "fails because")):
        return "BROKEN"
    if any(term in normalized for term in ("intentional", "optional", "not applicable", "not implemented")):
        return "INTENTIONAL"
    return "UNCLASSIFIED"


def decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = decorator_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return decorator_name(node.func)
    return ""


def audit_file(path: Path) -> list[tuple[str, Path, int, str, str]]:
    """Return classified skip declarations in one test file."""
    source = path.read_text(encoding="utf-8-sig")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return [("BROKEN", path, 1, "SYNTAX_ERROR", "file could not be parsed")]

    findings: list[tuple[str, Path, int, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for decorator in node.decorator_list:
                name = decorator_name(decorator)
                if name in {"pytest.mark.skip", "pytest.mark.skipif", "unittest.skip", "unittest.skipIf"}:
                    call = decorator if isinstance(decorator, ast.Call) else None
                    reason = literal_reason(call) if call else ""
                    findings.append((classify(reason), path, node.lineno, "decorator", reason))
        elif isinstance(node, ast.Call):
            name = decorator_name(node.func)
            if name in {"pytest.skip", "pytest.importorskip", "unittest.skipTest"}:
                reason = literal_reason(node)
                findings.append((classify(reason), path, node.lineno, "skip", reason))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail when any skip is unclassified")
    args = parser.parse_args()

    root = Path("apps/api/tests")
    findings: list[tuple[str, Path, int, str, str]] = []
    for path in sorted(root.rglob("*.py")):
        findings.extend(audit_file(path))

    print("category,path,line,kind,reason")
    for category, path, line, kind, reason in sorted(
        findings, key=lambda item: (str(item[1]), item[2], item[3])
    ):
        print(f"{category},{path},{line},{kind},{reason}")
    print(f"\nStatic skip declarations: {len(findings)}")

    if args.strict and any(category == "UNCLASSIFIED" for category, *_ in findings):
        print("\nERROR: every static skip declaration must have an explicit classification.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
