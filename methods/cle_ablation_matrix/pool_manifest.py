"""固定四池清单：D_init/D_grow/D_gate 训练侧，H_pass 最终留出。"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

POOL_COUNTS = {"D_init": 270, "D_grow": 240, "D_gate": 64, "H_pass": 300}


def _families(rows):
    groups = defaultdict(list)
    for row in rows:
        family = str(row.get("family_id") or row.get("seed_family_id") or "")
        if not family:
            raise ValueError(f"missing family_id: {row.get('index')}")
        groups[family].append(row)
    return {key: sorted(value, key=lambda r: str(r.get("index"))) for key, value in sorted(groups.items())}


def _assign_families(rows):
    groups = _families(rows)
    remaining = list(groups.items())

    def take_exact(candidates, target):
        """选择按 family 原子的确定性子集；无精确解时拒绝分池。"""
        reachable = {0: []}
        for index, (_family, members) in enumerate(candidates):
            size = len(members)
            for total, chosen in list(reachable.items())[::-1]:
                nxt = total + size
                if nxt <= target and nxt not in reachable:
                    reachable[nxt] = chosen + [index]
        if target not in reachable:
            raise ValueError(f"family-atomic exact pool size is impossible: {target}")
        selected = set(reachable[target])
        return [item for index, item in enumerate(candidates) if index in selected], [item for index, item in enumerate(candidates) if index not in selected]

    result = {}
    # 固定顺序使相同 family manifest 产生相同四池；最后一池由剩余条目组成。
    for name in ("D_init", "D_grow", "D_gate"):
        chosen, remaining = take_exact(remaining, POOL_COUNTS[name])
        result[name] = [row for _family, members in chosen for row in members]
    result["H_pass"] = [row for _family, members in remaining for row in members]
    if len(result["H_pass"]) != POOL_COUNTS["H_pass"]:
        raise ValueError("family-atomic exact H_pass size is impossible")
    return result


def build_manifest(rows: Iterable[dict]) -> dict:
    rows = list(rows)
    if len(rows) != sum(POOL_COUNTS.values()):
        raise ValueError(f"expected {sum(POOL_COUNTS.values())} rows, got {len(rows)}")
    pools = _assign_families(rows)
    manifest = {
        "schema": "cle-ablation-pools-v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "counts": {key: len(value) for key, value in pools.items()},
        "pools": {key: [{"task_id": row.get("index"), "family_id": str(row.get("family_id") or row.get("seed_family_id")), "cwe": str(row.get("CWE_ID", ""))} for row in value] for key, value in pools.items()},
        "h_pass_role": "held_out_final_cle_evaluation",
    }
    manifest["sha256"] = hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return manifest


def validate_manifest(manifest: dict, rows: Iterable[dict]) -> dict:
    by_id = {str(row.get("index")): row for row in rows}
    entries_all = [entry for key in POOL_COUNTS for entry in manifest.get("pools", {}).get(key, [])]
    if len({str(entry.get("task_id")) for entry in entries_all}) != len(entries_all):
        raise ValueError("pool task overlap")
    if len(by_id) != len(entries_all):
        raise ValueError("manifest task count mismatch")
    family_sets = {}
    all_ids = []
    for name in POOL_COUNTS:
        entries = manifest.get("pools", {}).get(name, [])
        if len(entries) != POOL_COUNTS[name]:
            raise ValueError(f"pool count mismatch: {name}")
        family_sets[name] = set()
        for entry in entries:
            task_id = str(entry.get("task_id"))
            row = by_id.get(task_id)
            if row is None or str(row.get("family_id") or row.get("seed_family_id")) != str(entry.get("family_id")):
                raise ValueError(f"family manifest mismatch: {task_id}")
            family_sets[name].add(str(entry.get("family_id")))
            all_ids.append(task_id)
    if len(set(all_ids)) != len(all_ids):
        raise ValueError("pool task overlap")
    for left, right in (("D_init", "D_grow"), ("D_init", "D_gate"), ("D_init", "H_pass"), ("D_grow", "D_gate"), ("D_grow", "H_pass"), ("D_gate", "H_pass")):
        if family_sets[left] & family_sets[right]:
            raise ValueError(f"family overlap: {left}/{right}")
    return {"family_ids_pairwise_disjoint": True, "h_pass_isolated": True, "counts": {key: len(manifest["pools"][key]) for key in POOL_COUNTS}}


def select_pool_rows(rows: Iterable[dict], manifest: dict, pools: tuple[str, ...], *, purpose: str = "evaluation") -> list[dict]:
    if purpose == "training" and "H_pass" in pools:
        raise ValueError("H_pass is held out and cannot enter training")
    by_id = {str(row.get("index")): row for row in rows}
    return [by_id[str(entry["task_id"])] for name in pools for entry in manifest["pools"][name]]
