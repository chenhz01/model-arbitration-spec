#!/usr/bin/env python3
"""self_test for model-arbitration-spec. Tiers: [A] functional, [B] exception/CLI, [C] extreme edges."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import model_arbitration_spec as mas  # noqa: E402

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))


def run_cli(args):
    return subprocess.run([sys.executable, os.path.join(HERE, "model_arbitration_spec.py")] + args,
                          capture_output=True, text=True)


TMP = tempfile.mkdtemp(prefix="mas_selftest_")


def p(name):
    return os.path.join(TMP, name)


def votes_file(votes):
    path = p("v_%d.json" % len(RESULTS))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(votes, f)
    return path


def raises(exc_type, fn, *args, **kw):
    try:
        fn(*args, **kw)
        return False
    except exc_type:
        return True


V = lambda *answers: [{"answer": a} for a in answers]  # noqa: E731

# ---------------- [A] functional ----------------
check("A01 majority 2/3 accepts", mas.arbitrate(V("Paris", "paris ", "London"), "majority")["verdict"] == "ACCEPT")
check("A02 normalization groups paris/Paris", mas.arbitrate(V("Paris", "paris ", "London"), "majority")["answer"] == "paris")
check("A03 1-1 tie escalates", mas.arbitrate(V("A", "B"), "majority")["verdict"] == "ESCALATE")
check("A04 2-2 tie escalates", mas.arbitrate(V("A", "A", "B", "B"), "majority")["verdict"] == "ESCALATE")
check("A05 strict majority required (2/4 escalates)", mas.arbitrate(V("A", "A", "B", "C"), "majority")["verdict"] == "ESCALATE")
check("A06 lexicographic tie-break picks a", mas.arbitrate(V("B", "A"), "majority", tie_break="lexicographic")["answer"] == "a")
check("A07 confidence weighted picks higher weight", mas.arbitrate(
    [{"answer": "X", "confidence": 0.9}, {"answer": "Y", "confidence": 0.2}], "confidence_weighted")["answer"] == "x")
check("A08 confidence weighted groups votes", mas.arbitrate(
    [{"answer": "X", "confidence": 0.3}, {"answer": "x", "confidence": 0.4},
     {"answer": "Y", "confidence": 0.45}, {"answer": "Z", "confidence": 0.45}],
    "confidence_weighted")["verdict"] == "ESCALATE")
check("A09 spread threshold escalates weak winner", mas.arbitrate(
    [{"answer": "A", "confidence": 0.4}, {"answer": "B", "confidence": 0.3}, {"answer": "C", "confidence": 0.3}],
    "confidence_weighted")["verdict"] == "ESCALATE")
check("A10 disagreement report always escalates", mas.arbitrate(V("A", "A", "A"), "disagreement_report")["verdict"] == "ESCALATE")
check("A11 disagreement report includes groups", mas.arbitrate(V("A", "B"), "disagreement_report")["groups"] ==
      {"a": {"votes": 1, "weight": 1.0}, "b": {"votes": 1, "weight": 1.0}})
check("A12 decision record has all spec fields", set(mas.SPEC["decision_record"]) <= set(mas.arbitrate(V("A"), "majority").keys()))
check("A13 spec_version stamped", mas.arbitrate(V("A"), "majority")["spec_version"] == mas.SPEC_VERSION)
check("A14 inputs counted", mas.arbitrate(V("A", "B"), "majority")["inputs"] == 2)
check("A15 zero confidence total escalates", mas.arbitrate(
    [{"answer": "X", "confidence": 0.0}], "confidence_weighted")["verdict"] == "ESCALATE")
check("A16 empty votes escalate", mas.arbitrate([], "majority")["verdict"] == "ESCALATE")
check("A17 normalization collapses internal whitespace", mas.normalize_answer("  New\n  York \t City ") == "new york city")
check("A18 default confidence is 1.0", mas.arbitrate(V("A"), "majority")["groups"]["a"]["weight"] == 1.0)
check("A19 integer confidence accepted", mas.arbitrate(
    [{"answer": "A", "confidence": 1}], "confidence_weighted")["verdict"] == "ACCEPT")
check("A20 referee golden suite passes", mas.referee()[1] == 8 and mas.referee()[0] == 8)

# ---------------- [B] exception / CLI paths ----------------
check("B01 unknown strategy rejected", raises(ValueError, mas.arbitrate, V("A"), "coin_flip"))
check("B02 non-list votes rejected", raises(ValueError, mas.arbitrate, "A", "majority"))
check("B03 vote without answer rejected", raises(ValueError, mas.arbitrate, [{"confidence": 1}], "majority"))
check("B04 empty answer rejected", raises(ValueError, mas.arbitrate, [{"answer": "   "}], "majority"))
check("B05 non-numeric confidence rejected", raises(ValueError, mas.arbitrate,
                                                    [{"answer": "A", "confidence": "high"}], "majority"))
check("B06 bool confidence rejected", raises(ValueError, mas.arbitrate,
                                             [{"answer": "A", "confidence": True}], "majority"))
check("B07 confidence above 1 rejected", raises(ValueError, mas.arbitrate,
                                                [{"answer": "A", "confidence": 1.5}], "majority"))
check("B08 negative confidence rejected", raises(ValueError, mas.arbitrate,
                                                 [{"answer": "A", "confidence": -0.1}], "majority"))
check("B09 non-string answer rejected", raises(TypeError, mas.arbitrate, [{"answer": 42}], "majority"))
check("B10 CLI arbitrate clean exits 0", run_cli(["arbitrate", "--input", votes_file(V("A", "A", "B")),
                                                  "--strategy", "majority"]).returncode == 0)
check("B11 CLI missing file exits 2", run_cli(["arbitrate", "--input", p("missing.json")]).returncode == 2)
check("B12 CLI invalid strategy exits 2", run_cli(["arbitrate", "--input", votes_file(V("A")),
                                                   "--strategy", "bogus"]).returncode == 2)
check("B13 CLI referee exits 0", run_cli(["referee"]).returncode == 0)
check("B14 CLI spec prints strategies", all(s in run_cli(["spec"]).stdout for s in mas.STRATEGIES))
check("B15 CLI no subcommand exits 2", run_cli([]).returncode == 2)


def _corrupt():
    path = p("corrupt.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write("{bad json")
    return path


check("B16 CLI corrupt json exits 2", run_cli(
    ["arbitrate", "--input", _corrupt()]).returncode == 2)

# ---------------- [C] extreme edges ----------------
check("C01 single vote majority accepts", mas.arbitrate(V("Only"), "majority")["answer"] == "only")
check("C02 1000-vote majority splits 501-499", mas.arbitrate(
    V(*(["A"] * 501 + ["B"] * 499)), "majority")["answer"] == "a")
check("C03 1000-vote 500-500 tie escalates", mas.arbitrate(
    V(*(["A"] * 500 + ["B"] * 500)), "majority")["verdict"] == "ESCALATE")
check("C04 unicode answers group correctly", mas.arbitrate(V("巴黎", " 巴黎 ", "東京"), "majority")["answer"] == "巴黎")
check("C05 unicode tie-break deterministic", mas.arbitrate(V("乙", "甲"), "majority", tie_break="lexicographic")["answer"]
      in ("乙", "甲"))
check("C06 very long answer (100k chars) handled", mas.arbitrate(
    [{"answer": "x" * 100000}] * 3, "majority")["verdict"] == "ACCEPT")
check("C07 whitespace-only variants merge to one group", mas.arbitrate(
    [{"answer": "a b"}, {"answer": "a  b"}, {"answer": " a b "}], "majority")["groups"].keys() == {"a b"})
check("C08 mixed-case + tabs merge", mas.arbitrate(
    [{"answer": "YES"}, {"answer": " yes"}, {"answer": "\tYeS"}], "majority")["groups"].keys() == {"yes"})
check("C09 deep confidence precision stable", mas.arbitrate(
    [{"answer": "A", "confidence": 0.1}] * 10, "confidence_weighted", spread_threshold=0.99)["verdict"] == "ACCEPT")
check("C10 zero-confidence majority still counts votes", mas.arbitrate(
    [{"answer": "A", "confidence": 0.0}, {"answer": "A", "confidence": 0.0}, {"answer": "B", "confidence": 0.0}],
    "majority")["verdict"] == "ACCEPT")
check("C11 confidence threshold 1.0 requires unanimous", mas.arbitrate(
    [{"answer": "A", "confidence": 0.9}, {"answer": "B", "confidence": 0.1}],
    "confidence_weighted", spread_threshold=1.0)["verdict"] == "ESCALATE")
check("C12 20-way answer split escalates", mas.arbitrate(V(*("ans%d" % i for i in range(20))), "majority")["verdict"]
      == "ESCALATE")
check("C13 groups report counts exact", mas.arbitrate(V("A", "A", "B", "C"), "majority")["groups"]["a"]["votes"] == 2)
check("C14 weight sums rounded stably", mas.arbitrate(
    [{"answer": "A", "confidence": 0.1}] * 3, "confidence_weighted")["groups"]["a"]["weight"] == 0.3)
check("C15 newline-only answer rejected", raises(ValueError, mas.arbitrate, [{"answer": "\n\t"}], "majority"))
check("C16 emoji answer is a valid group", mas.arbitrate(V("🎯", "🎯", "🎲"), "majority")["answer"] == "🎯")
check("C17 nested vote structure rejected", raises(ValueError, mas.arbitrate, [[{"answer": "A"}]], "majority"))
check("C18 lexicographic tie-break on 3-way vote tie", mas.arbitrate(
    V("C", "A", "B"), "majority", tie_break="lexicographic")["answer"] == "a")
check("C19 spec json serializable", isinstance(json.dumps(mas.SPEC), str))
check("C20 arbitrate with spread 0 accepts any non-zero", mas.arbitrate(
    [{"answer": "A", "confidence": 0.01}, {"answer": "B", "confidence": 0.99}],
    "confidence_weighted", spread_threshold=0.0)["verdict"] == "ACCEPT")

# ---------------- [R2] round-2 block (v0.1.1: quorum gate) ----------------
check("R01 quorum unmet escalates", mas.arbitrate(V("A", "A"), "majority", quorum=3)["verdict"] == "ESCALATE")
check("R02 quorum met decides normally", mas.arbitrate(V("A", "A", "B"), "majority", quorum=3)["verdict"] == "ACCEPT")
check("R03 quorum 0 is no-op", mas.arbitrate(V("A"), "majority", quorum=0)["verdict"] == "ACCEPT")
check("R04 quorum reason mentions counts", "quorum not met: 1 < 2" in mas.arbitrate(V("A"), "majority", quorum=2)["reason"])
check("R05 quorum applies to confidence strategy", mas.arbitrate(
    [{"answer": "A", "confidence": 0.9}], "confidence_weighted", quorum=5)["verdict"] == "ESCALATE")
check("R06 quorum applies to disagreement_report", mas.arbitrate(
    V("A"), "disagreement_report", quorum=5)["reason"] == "quorum not met: 1 < 5")
check("R07 negative quorum rejected", raises(ValueError, mas.arbitrate, V("A"), "majority", quorum=-1))
check("R08 non-int quorum rejected", raises(ValueError, mas.arbitrate, V("A"), "majority", quorum=1.5))
check("R09 CLI --quorum escalates exit 0", run_cli(
    ["arbitrate", "--input", votes_file(V("A")), "--quorum", "3"]).returncode == 0
    and "quorum not met" in run_cli(["arbitrate", "--input", votes_file(V("A")), "--quorum", "3"]).stdout)
check("R10 quorum equal to votes passes", mas.arbitrate(V("A", "B", "C"), "majority", quorum=3)["inputs"] == 3)
check("R11 quorum does not break lexicographic tie-break", mas.arbitrate(
    V("B", "A"), "majority", tie_break="lexicographic", quorum=2)["answer"] == "a")
check("R12 quorum escalation still includes groups", mas.arbitrate(
    V("A", "B"), "majority", quorum=5)["groups"]["a"]["votes"] == 1)


def main():
    passed = sum(1 for _, ok in RESULTS if ok)
    total = len(RESULTS)
    for n, ok in RESULTS:
        if not ok:
            print("FAIL:", n)
    print("SUMMARY: PASS %d/%d" % (passed, total))
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
