# Phase 23 — Requirements Accuracy, Constraint Validation & Benchmarks
**Status:** In progress on \`feat/phase-23-requirements-accuracy\`. **Base:** \`main\` after Phase 22 PR #4 merged and CI run #100 passed.

## Objective
Make preliminary requirements extraction measurable and safer before it influences the canonical Building World Model. Distinguish exact facts, unsupported inequalities, ambiguous values, invalid quantities, contradictions, and cross-field inconsistencies without implying general language understanding.

## Repository-grounded findings
- Site-area extraction could scan across intervening quantities and attach a later GFA value to the site.
- Generic area fallback could reinterpret a site/plot area as GFA.
- Negated facts and comparative/range language could be misrepresented as exact requirements.
- Non-positive extracted values could reach canonical model construction; zero floors could trigger schema errors.
- Existing tests did not measure precision/recall on a versioned corpus.

## Work packages
1. **Context-safe extraction:** narrow site/plot patterns; allow generic GFA inference only for one unqualified area with no site/plot reference; skip negated facts and inequality/range values the exact-value schema cannot represent.
2. **Quality checks:** detect conflicting values, non-positive values, implausible magnitudes, ambiguous GFA inference, unsupported qualifiers, and explicit height/floor-height mismatch. Hard-invalid values block canonicalization; unusual values remain review warnings.
3. **Canonical integration:** persist validation in the brief structured payload, requirement provenance, and audit event; exclude hard-invalid/contradictory requirements from the World Model; reuse the existing commit contradiction gate; show warnings in the Foundation workspace.
4. **Benchmark gate:** version ten representative/adversarial briefs; calculate micro precision/recall/F1 and per-case exact match; enforce 0.95 thresholds in CI.

## Acceptance criteria
- [x] Site parsing cannot consume a later GFA value; site-only briefs never infer site area as GFA.
- [x] Negated facts and inequalities are not asserted as exact facts.
- [x] Invalid quantities are visible and cannot enter/commit into the canonical World Model.
- [x] Warnings are visible but do not silently become approvals.
- [x] Validation persists with brief/provenance/audit evidence.
- [x] All fixture fact sets match exactly; precision, recall, F1 >= 0.95.
- [x] Backend Ruff/pytest, PostgreSQL migration cycle, frontend lint/tests/build, Docker builds, Compose readiness/smoke, licence gate, and release preflight pass.

## Boundaries
No LLM as source of truth; no regulatory/structural certification. The benchmark is a regression corpus, not a universal accuracy claim.
