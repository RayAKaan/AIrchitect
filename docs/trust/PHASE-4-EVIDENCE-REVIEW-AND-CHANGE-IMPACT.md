# Phase 4 trust model

## Evidence graph
Typed `EvidenceNode` records identify REQUIREMENT, WORLD_MODEL, ARTIFACT, AI_DECISION, WORKFLOW/SYSTEM, and HUMAN_REVIEW sources. Nodes include source/evidence hashes, labels, minimized payloads, provenance, project version, and workflow scope. `EvidenceLink` stores typed direction between nodes. APIs are tenant-scoped.

## Change impact
Changed canonical fields are compared across project versions. Artifact dependency/source status determines affected versus unaffected explanations. Transitive stale propagation remains deterministic. V1 artifacts are never edited; recomputation creates new versions. Unaffected artifacts remain valid only when stored dependency and source hashes support that conclusion.

## Grounded explanations
The context builder selects at most 20 recent scoped evidence nodes. The assistant is read-only and returns evidence IDs. Unsupported citations force `UNGROUNDED`; external-provider output that claims grounding remains `REVIEW_REQUIRED`. No-evidence answers are explicitly `UNGROUNDED`.

## Human review
The only dispositions are `ACCEPT_FOR_FEASIBILITY`, `REQUEST_CHANGES`, and `BLOCK`. Review records bind project/version/workflow, artifact versions, source hash, reviewer, rationale, comments, and timestamp. Stale artifact versions cannot be accepted. Acceptance means preliminary feasibility use only—not approval, certification, construction readiness, legal advice, tender pricing, or market assurance.
