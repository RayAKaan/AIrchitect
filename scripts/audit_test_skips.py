#!/usr/bin/env python3
"""Audit statically declared pytest/unittest skips in the backend test suite.

This is deliberately a source audit, not a replacement for pytest's runtime
``-rs`` report. It catches skip declarations that can otherwise disappear from
normal CI output and classifies them using their explicit reason text.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Skip:
    path: Path
    line: int
    kind: str
    reason: str
    category: str


def classify(reason: str) -> str:
    text = reason.lower()
    if any(term in text for term in ("postgres", "postgis", "postgresql")):
        return "POSTGRES_REQUIRED"
    if any(term in text for term in ("freecad", "ifcopenshell", "occt", "native cad", "native toolchain")):
        return "NATIVE_CAD_REQUIRED"
    if any(term in text for term in ("broken", "failing", "bug", "regression")):
        return "BROKEN"
    if any(term in text for term in ("obsolete", "superseded", "legacy")):
        return "OBSOLETE"
    if any(term in text for term in ("environment", "platform", "windows", "linux", "macos")):
        return "ENVIRONMENTAL"
    if any(term in text for term in ("intentional", "document", "slow", "manual", "release")):
        return "INTENTIONAL"
    return "UNCLASSIFIED"


def literal_reason(node: ast.Call) -> str:
    for keyword in node.keywords:
        if keyword.arg == "reason" and isinstance(keyword.value, ast.Constant):
            if isinstance(keyword.value.value, str):
                return keyword.value.value
    if node.args:
        value = node.args[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    return ""


def decorator_skip(decorator: ast.expr) -> tuple[str, str] | None:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Attribute):
        if target.value.attr == "mark" and target.attr in {"skip", "skipif"}:
            reason = literal_reason(decorator) if isinstance(decorator, ast.Call) else ""
            return target.attr, reason
    if isinstance(target, ast.Attribute) and target.attr in {"skip", "skipIf"}:
        reason = literal_reason(decorator) if isinstance(decorator, ast.Call) else ""
        return target.attr, reason
    return None


def audit(root: Path) -> list[Skip]:
    findings: list[Skip] = []
    paths = sorted(root.rglob("test_*.py")) + sorted(root.rglob("*_test.py"))
    for path in sorted(set(paths)):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            findings.append(Skip(path, 1, "SYNTAX_ERROR", "file could not be parsed", "BROKEN"))
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                for decorator in node.decorator_list:
                    found = decorator_skip(decorator)
                    if found:
                        kind, reason = found
                        findings.append(Skip(path, node.lineno, kind, reason, classify(reason)))
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr in {"skip", "importorskip", "skipTest"}:
                    reason = literal_reason(node)
                    findings.append(Skip(path, node.lineno, node.func.attr, reason, classify(reason)))
    return sorted(set(findings), key=lambda item: (str(item.path), item.line, item.kind))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("apps/api/tests"))
    parser.add_argument("--strict", action="store_true", help="fail when a skip is unclassified")
    args = parser.parse_args()

    findings = audit(args.root)
    print("category,path,line,kind,reason")
    for finding in findings:
        reason = finding.reason.replace("\n", " ").replace(",", ";")
        print(f"{finding.category},{finding.path},{finding.line},{finding.kind},{reason}")
    print(f"\nStatic skip declarations: {len(findings)}")
    if args.strict and any(item.category == "UNCLASSIFIED" for item in findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
