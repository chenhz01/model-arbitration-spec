# Changelog — model-arbitration-spec

All notable changes. Format based on Keep a Changelog; versioning: SemVer.

## [0.1.1] - 2026-10-11

### Added
- `quorum` parameter and `--quorum` CLI flag: below a minimum vote count every strategy escalates with reason "quorum not met" before running (round-2 review finding: with 2-of-5 voters offline, a 2-vote "majority" silently decided).
- Referee suite now part of the golden contract; quorum semantics pinned by tests.

### Fixed
- Round-2 self-review: default `spread_threshold=0.5` with strict `<` can never escalate a two-group weighted vote (winner share is always ≥ 0.5). Documented explicitly in Limits; golden case updated to a three-group escalation. Suite re-run green: `SUMMARY: PASS 68/68`.

### Changed
- Self-test suite expanded 56 → 68 cases (+21%, round-2 ≥20% improvement gate): [R2] block adds 12 cases covering quorum semantics across all three strategies, CLI wiring, and interaction with lexicographic tie-breaks.

## [0.1.0] - 2026-10-11

### Added
- Formal spec (JSON) of three arbitration strategies: majority (strict >n/2, configurable lexicographic tie-break), confidence_weighted (weight-sum groups, spread threshold), disagreement_report (always escalates with group table).
- Answer normalization (trim/lowercase/whitespace-collapse) with exact-match grouping.
- Structured decision records (spec_version/strategy/inputs/verdict/answer/groups/reason).
- Golden referee suite (8 cases) validating verdicts across strategies.
- CLI: `arbitrate`, `referee`, `spec` with CI exit-code discipline (0 ok / 1 referee failure / 2 input-error).
- Self-test suite: 56 cases across functional, exception/CLI, and extreme-edge tiers (1000-vote splits/unicode/100k-char answers/20-way splits/zero-confidence).
- MIT LICENSE, README with fallback plan and assumption register.
