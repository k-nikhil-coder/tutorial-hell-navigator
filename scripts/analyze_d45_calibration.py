import json
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "eval" / "injection_key_d45.json", "r", encoding="utf-8") as f:
    key_list = json.load(f)
key_map = {k["pair_id"]: k for k in key_list}

with open(PROJECT_ROOT / "eval" / "hand_grades_d45.json", "r", encoding="utf-8") as f:
    human_grades = json.load(f)

with open(PROJECT_ROOT / "eval" / "judge_day45_report.json", "r", encoding="utf-8") as f:
    judge_report = json.load(f)

evals = judge_report["detailed_evaluations"]

print("=" * 80)
print("=== DAY 45 BLIND LLM JUDGE BENCHMARK DETAILED BREAKDOWN ===")
print("=" * 80)

injected_evaluated = []
natural_evaluated = []

for e in evals:
    pid = e["pair_id"]
    k = key_map[pid]
    h = e["human_grade"]
    j = e["judge_grade"]
    h_v = h["verdict"]
    j_v = j["verdict"]
    is_inj = k["is_injected"]
    fam = k["defect_family"]
    has_rule = k["has_judge_rule"]
    agree = (h_v == j_v)

    record = {
        "pair_id": pid,
        "question_id": e["question_id"],
        "topic": e["topic"],
        "is_injected": is_inj,
        "defect_family": fam,
        "has_rule": has_rule,
        "human_verdict": h_v,
        "judge_verdict": j_v,
        "agreement": agree,
        "judge_reasons": {
            "flagged_claims": j.get("flagged_claims"),
            "hallucinated_code": j.get("hallucinated_code"),
            "ungrounded_steps": j.get("ungrounded_steps"),
            "feedback": j.get("reasoning"),
        }
    }

    if is_inj:
        injected_evaluated.append(record)
    else:
        natural_evaluated.append(record)

    agree_str = "MATCH" if agree else "DISAGREE"
    rule_str = f"Rule={has_rule}" if is_inj else "Natural"
    print(f"{pid:<7} | {e['question_id']:<9} | {('INJECTED' if is_inj else 'UNTOUCHED'):<9} | {rule_str:<12} | Human={h_v:<4} | Judge={j_v:<4} | {agree_str}")
    if not agree:
        print(f"   -> Reason: Flagged={j.get('flagged_claims')}, CodeErr={j.get('hallucinated_code')}, Steps={j.get('ungrounded_steps')}")

print("\n" + "=" * 80)
print("=== STATISTICAL METRICS SUMMARY ===")
print("=" * 80)

n_total = len(evals)
matches = sum(1 for e in evals if e["human_grade"]["verdict"] == e["judge_grade"]["verdict"])
obs_agreement = round(matches / n_total * 100, 2)

# Wilson interval for agreement
def wilson(k, n, z=1.96):
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return round(max(0.0, centre - margin) * 100, 2), round(min(1.0, centre + margin) * 100, 2)

w_low, w_high = wilson(matches, n_total)

cm = judge_report["confusion_matrix"]
tp = cm["true_positives"]
tn = cm["true_negatives"]
fp = cm["false_positives"]
fn = cm["false_negatives"]

print(f"Total Evaluated Pairs:         {n_total}")
print(f"Observed Agreement:            {matches}/{n_total} ({obs_agreement}%)")
print(f"95% Wilson Confidence Interval: [{w_low}%, {w_high}%]")
print(f"Cohen's Kappa (kappa):         {judge_report['cohens_kappa']} ({judge_report['kappa_interpretation']})")
print(f"Confusion Matrix (PASS=pos):   TP={tp}, TN={tn}, FP={fp}, FN={fn}")

# Recall on FAIL (FAIL is the negative class, but in diagnostic terms, detecting defects is the objective):
# Human FAIL count
human_fails = [e for e in evals if e["human_grade"]["verdict"] == "FAIL"]
judge_detected_fails = [e for e in human_fails if e["judge_grade"]["verdict"] == "FAIL"]
fail_recall_overall = round(len(judge_detected_fails) / len(human_fails) * 100, 2) if human_fails else 0.0

# Split FAIL recall by injected vs natural:
injected_fails = [r for r in injected_evaluated if r["human_verdict"] == "FAIL"]
injected_detected = [r for r in injected_fails if r["judge_verdict"] == "FAIL"]
injected_recall = round(len(injected_detected) / len(injected_fails) * 100, 2) if injected_fails else 0.0

# Injected split by whether judge has a rule vs no rule
with_rule_fails = [r for r in injected_fails if r["has_rule"] is True]
with_rule_detected = [r for r in with_rule_fails if r["judge_verdict"] == "FAIL"]
rule_recall = round(len(with_rule_detected) / len(with_rule_fails) * 100, 2) if with_rule_fails else 0.0

no_rule_fails = [r for r in injected_fails if r["has_rule"] is False]
no_rule_detected = [r for r in no_rule_fails if r["judge_verdict"] == "FAIL"]
no_rule_recall = round(len(no_rule_detected) / len(no_rule_fails) * 100, 2) if no_rule_fails else 0.0

natural_fails = [r for r in natural_evaluated if r["human_verdict"] == "FAIL"]
natural_detected = [r for r in natural_fails if r["judge_verdict"] == "FAIL"]
natural_recall = round(len(natural_detected) / len(natural_fails) * 100, 2) if natural_fails else 0.0

print("\n--- RECALL ON FAIL (Defect Catch Rate) ---")
print(f"Overall Recall on FAIL:        {len(judge_detected_fails)}/{len(human_fails)} ({fail_recall_overall}%)")
print(f"  -> Injected Defects Recall:     {len(injected_detected)}/{len(injected_fails)} ({injected_recall}%)")
print(f"     * Families Judge Has Rule For:   {len(with_rule_detected)}/{len(with_rule_fails)} ({rule_recall}%)")
print(f"     * Families Judge Has NO Rule For: {len(no_rule_detected)}/{len(no_rule_fails)} ({no_rule_recall}%)")
print(f"  -> Natural Failures Recall:     {len(natural_detected)}/{len(natural_fails)} (n={len(natural_fails)})")

# False positive analysis (Judge calling PASS pairs FAIL - i.e. False Negatives in CM)
false_alarms = [r for r in natural_evaluated if r["human_verdict"] == "PASS" and r["judge_verdict"] == "FAIL"]
print(f"\n--- NATURAL FALSE ALARMS (Human PASS, Judge FAIL) ---")
print(f"Count: {len(false_alarms)}/{len(natural_evaluated)} ({round(len(false_alarms)/len(natural_evaluated)*100, 2)}% false alarm rate on clean outputs)")
for fa in false_alarms:
    clean_fb = str(fa['judge_reasons']['feedback']).encode('ascii', 'replace').decode('ascii')
    print(f"  * {fa['pair_id']} ({fa['question_id']}): {clean_fb}")

# Human vs Injection Key Agreement
human_matches_key = sum(1 for e in evals if e["human_grade"]["verdict"] == key_map[e["pair_id"]]["expected_verdict"])
human_key_agreement = round(human_matches_key / n_total * 100, 2)
print(f"\n--- HUMAN VS INJECTION KEY AGREEMENT ---")
print(f"Agreement: {human_matches_key}/{n_total} ({human_key_agreement}%)")
print("=" * 80)
