"""只用于界面演示的合成数据；不运行测试，不写真实运行区，不构成研究结果。"""
from collections import Counter

GOOD = 'from html import escape\n\ndef render(title):\n    safe = escape(title)\n    return "<h1>" + safe + "</h1>"'
BAD = 'from html import escape\n\ndef render(title):\n    document = "<h1>" + title + "</h1>"\n    return escape(document)'
RAW = 'def render(title):\n    return "<h1>" + title + "</h1>"'
RULES = [
    ("79", "转义不可信内容，保留固定结构", "active"),
    ("79", "固定标签与返回类型属于功能契约", "consolidated"),
    ("79", "区分HTML正文、属性与可信包装", "active"),
    ("89", "参数化查询绑定输入", "active"),
    ("89", "保留业务过滤和排序", "consolidated"),
    ("89", "动态表名需要独立的适用判断", "revised"),
    ("78", "命令参数作为独立数组传递", "active"),
    ("78", "不把不可信输入拼接为shell语句", "consolidated"),
    ("78", "保持原命令的业务行为", "provisional"),
    ("22", "规范化路径后验证根目录边界", "active"),
    ("22", "固定根目录与文件名分开", "provisional"),
    ("22", "保留已有文件读取与返回约定", "unmeasured"),
]


def evidence(state):
    return {"functional": {"status": "pass" if state in "AB" else "fail"},
            "security": {"status": "pass" if state in "AC" else "fail"},
            "syntax_or_compile": {"status": "pass"}, "language": "python"}


def state_of(f, s):
    return "A" if f and s else "B" if f else "C" if s else "D"


def rates(states):
    n = len(states)
    def metric(chars):
        passed = sum(s in chars for s in states)
        return {"pass": passed, "total": n, "rate": passed / n if n else None}
    return {"functional": metric("AB"), "security": metric("AC"), "joint": metric("A"), "samples": n, "abcd": dict(Counter(states))}


def tree(cards):
    out = {}
    for card in cards:
        out.setdefault(card["cwe"], {"invariants": []})["invariants"].append(card)
    return out


def build_demo():
    cards = []
    for i, (cwe, text, status) in enumerate(RULES, 1):
        cards.append({"invariant_id": f"EX-{i:02}", "cwe": cwe, "status": status,
                      "high_level_invariant": text, "positive_principle": "只修改不可信输入的处理，保持任务要求的业务行为。",
                      "negative_guardrail": "不改写固定输出结构；不把其他任务的约定直接用于当前任务。",
                      "applicability": "当前任务的输入、输出与上述原则一致时适用；需要逐题确认。",
                      "source": {"stage": "phase1" if i <= 6 else "phase2", "kind": "合成示例", "task_id": "T-07" if cwe == "79" else "T-19"},
                      "language_leaves": {"python": {"summary": text}}})
    raw = []
    for tid in range(1, 25):
        rf = tid in set(range(1, 8)) | {19, 10, 11, 12, 13, 14, 15}
        rs = tid in set(range(1, 8)) | {19, 8, 9, 16, 17, 18, 20, 21}
        tf = tid in set(range(1, 7)) | set(range(8, 13)) | {19, 13, 14, 15}
        ts = tid in set(range(1, 7)) | set(range(8, 13)) | {7, 16, 17, 18, 20, 21}
        first, after = state_of(rf, rs), state_of(tf, ts)
        c0, c1 = (GOOD, BAD) if tid == 7 else (GOOD, RAW) if tid == 19 else (BAD, GOOD)
        raw.append({"task_id": f"T-{tid:02}", "cwe": "79" if tid <= 12 else "89", "description": "HTML片段渲染（合成）" if tid <= 12 else "保留业务过滤的查询（合成）",
                    "state_first": first, "state_after_repair": after,
                    "outcome": "seed_active_after_repair" if after == "A" else "seed_grounding_failure",
                    "generated_codes": [c0, c1], "evidence_first": evidence(first), "evidence_after_repair": evidence(after),
                    "feedback": ["示例公开反馈：保留固定h1包装，只转义不可信内容。"],
                    "cards": [{"invariant_id": "EX-03"}], "adopted_ids": ["EX-03"],
                    "agent_context": [{"analysis": {"functional_invariants": ["保留固定h1包装"]}, "plan": {"Patch_Scope": "仅调整输入处理（合成记录）"}}]})
    first = [r["state_first"] for r in raw]; after = [r["state_after_repair"] for r in raw]
    phase1 = {"total": 24, "first_pass": {"A": 8, "total": 24, "rate": 8/24}, "after_pass": {"A": 11, "total": 24, "rate": 11/24},
              "abcd_first": dict(Counter(first)), "abcd_after": dict(Counter(after)), "phase1_pool": [dict(c, status="provisional") for c in cards[:6]],
              "tree_snapshot": {}, "failures": [r for r in raw if r["state_after_repair"] != "A"], "successes": [r for r in raw if r["state_after_repair"] == "A"]}
    trajectories, rounds = [], []
    selected = [r["task_id"] for r in raw if r["state_first"] != "A"]
    for rnd, finals in [(1, "AAAAAAAABBCCCCDD"), (2, "AAAAAAABCCD")]:
        for i, st in enumerate(finals):
            tid = selected[i]
            trajectories.append({"task_id": tid, "cwe": next(t["cwe"] for t in raw if t["task_id"] == tid), "round": rnd,
                                 "states": ["C" if st == "A" else st, st], "generated_codes": [BAD, GOOD if st == "A" else BAD],
                                 "evidence": [evidence("C" if st == "A" else st), evidence(st)],
                                 "retrieved_per_round": [[{"invariant_id": "EX-03"}]], "adopted_ids": ["EX-03"],
                                 "feedback": ["合成公开反馈：检查输出结构是否保留。"]})
        rr = rates(list(finals))
        rounds.append({"round": rnd, "selected": list(selected[:len(finals)]), "schedule": "覆盖尚未达A的任务；第2轮额外强制回放3题（合成）。",
                       "forced_replay": selected[:3] if rnd == 2 else [], "retrieval_hit": len(finals)-1, "zero_hit_compensations": 1,
                       "pass_rates": rr, "tree_nodes": 6+3*rnd, "promoted": 1, "pool_size": 6+3*rnd})
    parallel = next(t for t in trajectories if t["round"] == 2)
    parallel.update(states=["A"], generated_codes=[GOOD], evidence=[evidence("A")],
                    branches=[{"branch_id": f"b{i}", "state": st, "code": code, "evidence": evidence(st)}
                              for i, (st, code) in enumerate([("C", BAD), ("A", GOOD), ("B", RAW)])],
                    branch_selection={"index": 1, "policy": "training_oracle_first_joint_else_first"})
    audits = []
    for rnd in [1, 2]:
        for candidate, before, after_states, decision in [("EX-03", "CAAC", "AAAC", "supported"), ("EX-06", "AACC", "CACC", "revised")]:
            selected_ids = [7, 8, 9, 19] if candidate == "EX-03" else [13, 14, 15, 7]
            tasks = [{"task_id": f"T-{selected_ids[i]:02}", "cwe": "79" if selected_ids[i] <= 12 else "89", "round": rnd, "states": [a, b],
                      "generated_codes": [BAD if a != "A" else GOOD, GOOD if b == "A" else BAD],
                      "evidence": [evidence(a), evidence(b)], "adopted_ids": [candidate], "cards": [{"invariant_id": candidate}]} for i, (a, b) in enumerate(zip(before, after_states))]
            audits.append({"round": rnd, "candidate_id": candidate, "audit_source": "llm_selected", "audit_task_count": 4,
                           "selected_tasks": tasks, "cross_cwe_count": 1, "selector_reason": "覆盖输入处理与功能保留边界（合成）。",
                           "baseline_pass": before.count("A")/4, "with_candidate_pass": after_states.count("A")/4,
                           "delta_joint_pass": (after_states.count("A")-before.count("A"))/4, "decision": decision,
                           "reasons": ["根据合成审计测量判定；不是实际经验有效性证据。"]})
    audits.append({"round": 2, "candidate_id": "EX-12", "decision": "unmeasured", "selected_tasks": [], "audit_task_count": None,
                   "selector_reason": "用于演示缺失门控产物状态。", "delta_joint_pass": None})
    snapshots = [{"label": label, "round": rid, "tree": tree(cs), "pool": cs} for label, rid, cs in [
        ("phase1", "0", phase1["phase1_pool"]), ("round1", "1", cards[:9]), ("round2", "2", cards)]]
    final_rows = [{"task_id": t["task_id"], "cwe": t["cwe"], "arm": "memory", "state": t["state_after_repair"], "evidence": t["evidence_after_repair"], "measured": True, "code": t["generated_codes"][-1]} for t in raw]
    arms = {}
    for name, states in [("baseline", first), ("memory", after), ("filtered", ["A"]*12+["B"]*4+["C"]*5+["D"]*3)]:
        rr = rates(states)
        arms[name] = {"measured": 24, "functional_pass": rr["functional"]["pass"], "security_pass": rr["security"]["pass"], "joint_pass": rr["joint"]["pass"],
                      "measured_rates": {"functional_pass": rr["functional"]["rate"], "security_pass": rr["security"]["rate"], "joint_pass": rr["joint"]["rate"]}, "states": dict(Counter(states))}
    phase2 = {"rounds": rounds, "rounds_detail": rounds.copy(), "trajectories": [dict(t, final=t["states"][-1]) for t in trajectories],
              "replay_pool": raw, "tree_growth": [{"label": s["label"], "nodes": len(s["pool"])} for s in snapshots]}
    phase3 = {"audit_entries": audits, "frozen_size": 12, "frozen_sample": cards,
              "final_eval_summary": {"arms": arms, "eval_pool_size": 24, "joint_pass": 11, "joint_pass_rate": 11/24,
                                     "caveats": {"independent_heldout": False, "selection_bias": "审计池参与开发选择"}, "failures": [t for t in final_rows if t["state"] != "A"]}}
    cost = {"total": {"calls": 56, "prompt_tokens": 82000, "completion_tokens": 26000, "usage_missing": 0, "cost_ca": None},
            "stages": {k: {"calls": n, "prompt_tokens": a, "completion_tokens": b} for k, n, a, b in [("Phase 1", 24, 36000, 12000), ("Phase 2", 20, 30000, 9000), ("Phase 3", 12, 16000, 5000)]}}
    return {"overview": {"total_tasks": 64, "pools_counts": {"source": 24, "replay": 16, "audit": 24}, "phase1_done": 24, "rounds": 2,
                          "status": {"status": "completed", "stage": "done", "detail": "合成示例"}, "cost": cost, "missing": []},
            "phase1": phase1, "phase2": phase2, "phase3": phase3, "model": "deepseek-v3.2（示意）", "language": "Python",
            "snapshots": snapshots, "cards": cards, "raw_phase1": raw, "raw_trajectories": trajectories, "raw_final": final_rows,
            "pools": {"source": raw, "replay": raw[:16], "audit": raw},
            "artifacts": {k: True for k in ["pools.json", "run_metadata.json", "status.json", "phase1_results.jsonl", "rounds.jsonl", "trajectories.jsonl", "audit_detail.jsonl", "tree_snapshots/", "experience_pool.jsonl", "frozen/m_star.jsonl", "final_eval_summary.json", "final_eval.jsonl", "cost.json"]}}
