"""消融结果汇总、缺测隔离和配对比较。"""
from __future__ import annotations

from collections import defaultdict
import math


def _paired(old, new):
    common = sorted(set(old) & set(new))
    pairs = [(old[key], new[key]) for key in common]
    old_only = sum(a and not b for a, b in pairs)
    new_only = sum(b and not a for a, b in pairs)
    n = old_only + new_only
    p = 1.0 if not n else min(1.0, 2 * sum(math.comb(n, k) for k in range(min(old_only, new_only) + 1)) / (2 ** n))
    return {"pairs": len(pairs), "old_only": old_only, "new_only": new_only, "unpaired": len(set(old) ^ set(new)), "p_exact_two_sided": p}


def summarize_matrix(rows: list[dict], comparisons=()) -> dict:
    arms = defaultdict(lambda: defaultdict(list))
    for row in rows:
        arms[str(row.get("arm"))][str(row.get("dataset", "unknown"))].append(row)
    result = {"arms": {}, "datasets": {}}
    roles = {"Base": "final_external_test", "Plus": "final_external_test", "H_pass": "held_out_final_cle_evaluation", "D_gate": "training_diagnostic"}
    for dataset, role in roles.items():
        if any(dataset in groups for groups in arms.values()):
            result["datasets"][dataset] = {"evaluation_role": role, "feedback_channel": "disabled"}
    for arm, groups in arms.items():
        result["arms"][arm] = {}
        for dataset, items in groups.items():
            measured = [r for r in items if r.get("measured") is True]
            usage = [r.get("usage") or {} for r in items]
            token_values = [u.get("total_tokens") for u in usage]
            result["arms"][arm][dataset] = {
                "total": len(items), "measured": len(measured), "unmeasured": len(items) - len(measured),
                "functional": sum(bool(r.get("functional")) for r in measured), "security": sum(bool(r.get("security")) for r in measured), "joint": sum(bool(r.get("joint")) for r in measured),
                "calls": sum(int(u.get("calls", 0) or 0) for u in usage), "total_tokens": sum(token_values) if all(isinstance(v, (int, float)) for v in token_values) else None,
            }
    result["comparisons"] = {}
    for old_arm, new_arm in comparisons:
        for dataset in roles:
            old = {str(r.get("task_id")): bool(r.get("joint")) for r in arms.get(old_arm, {}).get(dataset, []) if r.get("measured")}
            new = {str(r.get("task_id")): bool(r.get("joint")) for r in arms.get(new_arm, {}).get(dataset, []) if r.get("measured")}
            if old or new:
                result["comparisons"][f"{old_arm}_vs_{new_arm}_{dataset}"] = _paired(old, new)
    return result
