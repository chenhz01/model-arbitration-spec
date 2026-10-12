# model-arbitration-spec

A formal, machine-readable spec for arbitrating between multiple LLM answers — majority vote, confidence weighting, or structured disagreement escalation — plus a deterministic referee that replays golden cases against any implementation of the spec. Teams running N models (or N samples of one model) and needing a *defensible, reproducible* tie-break rule should use this; if you just eyeball disagreements in a chat UI, you do not need it. Confidence: [High ≥80%] on the strategy definitions and referee determinism; [Medium] that confidence scores from real models are calibrated enough for weighted voting to beat plain majority. As of 2026-10-11.

## Problem

When three models answer and two disagree, someone (or some ad-hoc script) picks a winner — differently each time. The arbitration rule ends up implicit, unversioned, and untestable: a tie silently resolves by dict ordering, confidences are compared across incompatible scales, and escalations to a stronger model happen only when a developer remembers to add them. What is missing is a small formal contract: what counts as a group, who wins, when to escalate, and a way to verify an implementation actually follows it.

## How it works

1. **Normalization** — answers are trimmed, lowercased, and whitespace-collapsed before grouping, so "Paris", "paris ", and "PARIS" are one group.
2. **Strategies** (all pure functions of the vote list):
   - `majority`: a group wins only with strictly more than half of all votes; otherwise escalate. Optional `tie_break=lexicographic` makes ties deterministic instead of escalating.
   - `confidence_weighted`: highest summed confidence (each in [0,1]) wins; escalates when the winner's weight share falls below `spread_threshold` (default 0.5).
   - `disagreement_report`: never picks; always returns a structured escalation with the full group table.
   - `quorum` (v0.1.1): below a minimum vote count, every strategy escalates before running.
3. **Decision records** — every arbitration returns a JSON record: `spec_version`, `strategy`, `inputs`, `verdict`, `answer`, `groups`, `reason`. The record is the audit artifact.
4. **Referee** — a golden case suite (`referee` command) that pins the expected verdict of each strategy on canonical inputs; any conforming implementation must reproduce it.

## Quickstart (~2 min total)

```bash
# 1. Arbitrate a vote file (instant)
python model_arbitration_spec.py arbitrate --input votes.json --strategy majority

# 2. Weighted with a quorum (instant)
python model_arbitration_spec.py arbitrate --input votes.json --strategy confidence_weighted --quorum 3

# 3. Run the referee suite (~1 s)
python model_arbitration_spec.py referee
```

Self-test suite: `python self_test.py` — 68 cases, ~12 s [Measured, repro: `python self_test.py`].

## How this differs

| Alternative | What it does | How this differs |
|---|---|---|
| [ethz-coss/LLM_voting](https://github.com/ethz-coss/LLM_voting) (9★) | Research code + data for the "LLM Voting: Human Choices" paper | Studies how LLM voting mirrors human preferences; ships no executable arbitration contract, tie-break spec, or referee suite |
| [aaron10l/consensus-ai](https://github.com/aaron10l/consensus-ai) (0★) | A web application that implements LLM voting for the best response | UI-first product; the voting rule is embedded in the app, not a spec you can test against |
| [DUO-1337/llm-vote-game](https://github.com/DUO-1337/llm-vote-game) (0★) | LLM vote game | Entertainment framing; no decision records, quorum semantics, or conformance testing |

## Minimal Fallback (PLAN B)

No code at all? Write the rule down as a one-line contract in your PR template and enforce it in review:

> "Arbitration = majority with normalization; ties escalate to model M; escalations are logged with all N answers."

That is ~60% of this repo's value: an explicit, reviewable rule. What it cannot give you is the referee — automated proof that the implementation honors the rule.

## Design Trade-offs

Priority order when rules conflict: **determinism > auditability > simplicity > statistical sophistication**. Concretely: (1) every strategy is a pure function — same votes, same record, always; (2) escalation is a first-class verdict, not an error, so callers can branch on it; (3) the spec deliberately excludes re-asking models, debate rounds, or judge-models — those change the input distribution and break reproducibility; (4) confidence weighting assumes comparable scales and does not attempt calibration.

## Limits & Second-order Effects

- With 2 groups, a weighted winner always holds ≥50% share, so the default threshold never escalates two-way splits — use a 3+ group setup or raise the threshold above 0.5.
- Confidence scores are self-reported by models and poorly calibrated across vendors; weighted results inherit that bias.
- Second-order effects: normalization can **merge semantically different answers** ("3.14" vs "3.14159") into false consensus; lexicographic tie-breaks make outcomes deterministic but **arbitrary**, which can quietly favor answers that sort first; and a quorum rule creates an incentive to **pad vote counts** with cheap samples rather than good ones.

## FAQ

**Why is `disagreement_report` a strategy when it never decides?** Because explicit escalation is a decision — routing to a stronger model or a human is often the correct output, and it deserves a structured record.

**Can I use it for non-LLM votes?** Yes; any {answer, confidence} vote list works. The spec is domain-agnostic.

**Does the referee replace unit tests?** No — it pins cross-implementation conformance; your edge cases still need their own tests.

**When NOT to use this tool?**
1. Single-model, single-sample pipelines — nothing to arbitrate.
2. You need semantic similarity grouping ("Paris" ≈ "capital of France") — grouping here is exact-match normalized only.
3. You want model-as-judge scoring — that changes the voter set and is out of scope.
4. Latency-critical paths where an extra arbiter round-trip is unacceptable — arbitration here is local and instant, but the escalation path may not be.

## Core Assumptions

1. **Exact-match normalized grouping** is sufficient for factual/short-answer workloads; long-form answers need semantic grouping this spec does not provide. [Medium]
2. **Self-reported confidences are comparable enough** within a fixed voter set to make weighted voting meaningful. [Low — treat weighted results as advisory unless calibrated]
3. **Deterministic escalation beats probabilistic winners** for auditability, even at some accuracy cost. [High ≥80%]
4. **Decision records will be stored** by callers; the spec defines the record, not the storage. [High ≥80%]

## Contact

Issues and feedback: hcac4735@agent.qq.com

---

Part of the [zhengming-toolbox](https://github.com/chenhz01/zhengming-toolbox) — 55 purpose-built AI-engineering tools across neglected niches.

Related tools: [embedding-drift-watch](https://github.com/chenhz01/embedding-drift-watch) · [vector-meta-schema](https://github.com/chenhz01/vector-meta-schema) · [llm-gateway-spec](https://github.com/chenhz01/llm-gateway-spec)
