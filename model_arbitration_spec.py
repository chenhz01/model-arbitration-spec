#!/usr/bin/env python3
"""model-arbitration-spec: formal spec of multi-model arbitration strategies + deterministic referee.

Three strategies: majority (strict >n/2 vote), confidence_weighted (weight-sum
per normalized answer group), disagreement_report (always escalates with a
structured report). Pure stdlib. Exit codes: 0 decided/escalated as expected,
1 referee failure or violations, 2 input/usage error.
"""
import argparse
import json
import re
import sys

SPEC_VERSION = "1.0.0"

STRATEGIES = ("majority", "confidence_weighted", "disagreement_report")

SPEC = {
    "spec": "model-arbitration-spec",
    "version": SPEC_VERSION,
    "strategies": {
        "majority": {
            "pick_rule": "the answer group holding strictly more than half of all votes",
            "tie_rule": "escalate (configurable: lexicographic smallest group key)",
            "escalate_when": "no group holds > n/2 votes, or n == 0",
        },
        "confidence_weighted": {
            "pick_rule": "group with the highest sum of confidences; confidences must be in [0,1]",
            "tie_rule": "lexicographically smallest group key (deterministic)",
            "escalate_when": "winning weight share < spread_threshold (default 0.5), or n == 0",
        },
        "disagreement_report": {
            "pick_rule": "never picks; always escalates",
            "tie_rule": "n/a",
            "escalate_when": "always",
        },
    },
    "normalization": "answers are trimmed, lowercased, and internal whitespace collapsed before grouping",
    "decision_record": ["spec_version", "strategy", "inputs", "verdict", "answer", "groups", "reason"],
}


def normalize_answer(text):
    if not isinstance(text, str):
        raise TypeError("answer must be a string")
    return re.sub(r"\s+", " ", text.strip().lower())


def validate_votes(votes):
    """Raise ValueError on malformed vote lists. Returns (answers, weights)."""
    if not isinstance(votes, list):
        raise ValueError("votes must be a list")
    answers, weights = [], []
    for i, v in enumerate(votes):
        if not isinstance(v, dict) or "answer" not in v:
            raise ValueError("vote %d: must be an object with an 'answer' field" % i)
        ans = normalize_answer(v["answer"])
        if ans == "":
            raise ValueError("vote %d: answer is empty after normalization" % i)
        w = v.get("confidence", 1.0)
        if not isinstance(w, (int, float)) or isinstance(w, bool):
            raise ValueError("vote %d: confidence must be a number" % i)
        if not (0.0 <= float(w) <= 1.0):
            raise ValueError("vote %d: confidence out of range [0,1]" % i)
        answers.append(ans)
        weights.append(float(w))
    return answers, weights


def group_votes(answers, weights):
    groups = {}
    for ans, w in zip(answers, weights):
        g = groups.setdefault(ans, {"votes": 0, "weight": 0.0})
        g["votes"] += 1
        g["weight"] = round(g["weight"] + w, 10)
    return groups


def _finalize(strategy, votes, groups, winner, verdict, reason, tie_break):
    if verdict == "ESCALATE" and tie_break == "lexicographic" and groups:
        top = max(g["votes"] for g in groups.values())
        cands = sorted(k for k, v in groups.items() if v["votes"] == top)
        winner = cands[0]
        verdict = "ACCEPT"
    return {
        "spec_version": SPEC_VERSION,
        "strategy": strategy,
        "inputs": len(votes),
        "verdict": verdict,
        "answer": winner if verdict == "ACCEPT" else None,
        "groups": groups,
        "reason": reason,
    }


def arbitrate(votes, strategy, spread_threshold=0.5, tie_break="escalate", quorum=0):
    """Run one arbitration. Returns a decision record (dict).

    v0.1.1: quorum (int >= 0) — when the vote count is below quorum, the
    decision escalates with reason "quorum not met" before any strategy runs.
    """
    if strategy not in STRATEGIES:
        raise ValueError("unknown strategy: %s (expected one of %s)" % (strategy, ", ".join(STRATEGIES)))
    if not isinstance(quorum, int) or quorum < 0:
        raise ValueError("quorum must be a non-negative integer")
    answers, weights = validate_votes(votes)
    groups = group_votes(answers, weights)
    if quorum > 0 and len(votes) < quorum:
        return _finalize(strategy, votes, groups, None, "ESCALATE",
                         "quorum not met: %d < %d" % (len(votes), quorum), tie_break)

    if strategy == "disagreement_report" or not groups:
        return _finalize(strategy, votes, groups, None, "ESCALATE",
                         "disagreement_report always escalates" if strategy == "disagreement_report"
                         else "no votes", tie_break)

    if strategy == "majority":
        n = len(answers)
        top = max(g["votes"] for g in groups.values())
        if top * 2 > n:
            winners = [k for k, v in groups.items() if v["votes"] == top]
            winner = sorted(winners)[0] if len(winners) > 1 and tie_break == "lexicographic" else winners[0]
            verdict = "ESCALATE" if len(winners) > 1 and tie_break != "lexicographic" else "ACCEPT"
            return _finalize(strategy, votes, groups, winner, verdict,
                             "group holds strict majority" if verdict == "ACCEPT" else "majority tie",
                             tie_break)
        return _finalize(strategy, votes, groups, None, "ESCALATE",
                         "no group holds > n/2 votes", tie_break)

    # confidence_weighted
    total = sum(weights)
    if total <= 0:
        return _finalize(strategy, votes, groups, None, "ESCALATE", "total confidence is zero", tie_break)
    best_key = max(sorted(groups.keys()), key=lambda k: groups[k]["weight"])
    share = groups[best_key]["weight"] / total
    if share < spread_threshold:
        return _finalize(strategy, votes, groups, None, "ESCALATE",
                         "winning weight share %.4f < threshold %.4f" % (share, spread_threshold), tie_break)
    return _finalize(strategy, votes, groups, best_key, "ACCEPT",
                     "highest weight share %.4f" % share, tie_break)


# Golden referee cases: (votes, strategy, kwargs, expected_verdict, expected_answer)
GOLDEN_CASES = [
    ([{"answer": "Paris"}, {"answer": "paris "}, {"answer": "London"}], "majority", {}, "ACCEPT", "paris"),
    ([{"answer": "A"}, {"answer": "B"}], "majority", {}, "ESCALATE", None),
    ([{"answer": "A"}, {"answer": "A"}, {"answer": "B"}, {"answer": "B"}], "majority", {}, "ESCALATE", None),
    ([{"answer": "A"}, {"answer": "B"}], "majority", {"tie_break": "lexicographic"}, "ACCEPT", "a"),
    ([{"answer": "X", "confidence": 0.9}, {"answer": "Y", "confidence": 0.2}],
     "confidence_weighted", {}, "ACCEPT", "x"),
    ([{"answer": "A", "confidence": 0.4}, {"answer": "B", "confidence": 0.3},
      {"answer": "C", "confidence": 0.3}], "confidence_weighted", {}, "ESCALATE", None),
    ([{"answer": "X"}, {"answer": "Y"}], "disagreement_report", {}, "ESCALATE", None),
    ([], "majority", {}, "ESCALATE", None),
]


def referee():
    """Run golden cases; returns (passed, total, failures)."""
    failures = []
    for i, (votes, strategy, kw, want_verdict, want_answer) in enumerate(GOLDEN_CASES):
        rec = arbitrate(votes, strategy, **kw)
        if rec["verdict"] != want_verdict or rec["answer"] != want_answer:
            failures.append({"case": i, "got": rec["verdict"], "want": want_verdict,
                             "got_answer": rec["answer"], "want_answer": want_answer})
    return len(GOLDEN_CASES) - len(failures), len(GOLDEN_CASES), failures


def main(argv=None):
    ap = argparse.ArgumentParser(prog="model-arbitration-spec",
                                 description="Multi-model arbitration protocol: formal spec + deterministic referee")
    sub = ap.add_subparsers(dest="cmd")
    pa = sub.add_parser("arbitrate", help="arbitrate a votes JSON file")
    pa.add_argument("--input", required=True)
    pa.add_argument("--strategy", default="majority", choices=STRATEGIES)
    pa.add_argument("--spread-threshold", type=float, default=0.5)
    pa.add_argument("--tie-break", default="escalate", choices=("escalate", "lexicographic"))
    pa.add_argument("--quorum", type=int, default=0, help="v0.1.1: minimum votes, else escalate")
    sub.add_parser("referee", help="run the golden referee test suite")
    sub.add_parser("spec", help="print the formal strategy spec")

    args = ap.parse_args(argv)
    if args.cmd is None:
        ap.print_help(sys.stderr)
        return 2
    try:
        if args.cmd == "spec":
            print(json.dumps(SPEC, indent=2))
            return 0
        if args.cmd == "referee":
            passed, total, failures = referee()
            print("referee: %d/%d golden cases pass" % (passed, total))
            for f in failures:
                print("REF_FAIL", json.dumps(f))
            return 1 if failures else 0
        if args.cmd == "arbitrate":
            with open(args.input, "r", encoding="utf-8") as f:
                votes = json.load(f)
            rec = arbitrate(votes, args.strategy,
                            spread_threshold=args.spread_threshold, tie_break=args.tie_break,
                            quorum=args.quorum)
            print(json.dumps(rec, ensure_ascii=False, indent=2))
            return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
