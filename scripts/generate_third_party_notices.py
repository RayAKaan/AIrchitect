#!/usr/bin/env python3
"""Generate THIRD-PARTY-NOTICES.md from the canonical compliance registry."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/legal/compliance-registry.json"
OUTPUT = ROOT / "docs/legal/THIRD-PARTY-NOTICES.md"


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    dependencies = registry.get("third_party_dependencies", [])
    reviews = registry.get("license_reviews", [])

    lines = [
        "# AIrchitect Third-Party Notices",
        "",
        "> Generated from `docs/legal/compliance-registry.json`. This inventory is an engineering compliance record, not legal advice.",
        "> Commercial redistribution remains subject to the explicit review status of each dependency and applicable legal review.",
        "",
        "## Reviewed dependencies",
        "",
        "| Component | Version | License | Classification | Runtime | Review due |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in dependencies:
        lines.append(
            f"| {item['name']} | {item['version']} | {item['license']} | {item['classification']} | "
            f"{item['runtime']} | {item['review_due']} |"
        )

    lines.extend([
        "",
        "## Redistribution controls",
        "",
        "- Preserve copyright and license notices required by every dependency.",
        "- Preserve source pointers or source offers required by copyleft licenses.",
        "- Do not treat an engineering review as legal clearance.",
        "- A dependency with a stale review is a release-preflight failure.",
        "- Data-source licenses are tracked separately from software licenses.",
        "",
        "## License reviews",
        "",
    ])
    for review in reviews:
        lines.extend([
            f"- **{review['scope']}** — {review['status']}; review due {review['review_due']}; commercial release cleared: `{str(review['commercial_release_cleared']).lower()}`.",
            f"  - {review['notes']}",
        ])

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"PASS: generated {OUTPUT.relative_to(ROOT)} from compliance registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
