"""C3 冻结资格和审计清单。"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


class JsonlValidationError(ValueError):
    """JSONL 结构损坏；报告中保留首个坏行和是否为截断尾行。"""

    def __init__(self, path: Path, report: dict):
        self.path = path
        self.report = report
        super().__init__(f"invalid_jsonl:{path.name}:line={report.get('first_invalid_line')}:{report.get('error_type')}")


def validate_jsonl(path: Path, *, report_path: Path | None = None) -> tuple[list[dict], dict]:
    """校验经验库 JSONL，逐行返回合法记录并写审计报告；绝不静默丢弃坏行。"""
    rows: list[dict] = []
    invalid: list[dict] = []
    if not path.is_file():
        report = {"path": str(path), "valid_rows": 0, "invalid_rows": 0,
                  "first_invalid_line": None, "error_type": "missing_file", "valid": False}
    else:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_no, raw in enumerate(lines, 1):
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ValueError("row_not_object")
                rows.append(value)
            except (json.JSONDecodeError, ValueError) as exc:
                invalid.append({"line": line_no, "error_type": type(exc).__name__,
                                "message": str(exc)[:300], "truncated_tail": line_no == len(lines)})
        report = {"path": str(path), "valid_rows": len(rows), "invalid_rows": len(invalid),
                  "first_invalid_line": invalid[0]["line"] if invalid else None,
                  "invalid": invalid, "valid": not invalid}
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not report["valid"]:
        raise JsonlValidationError(path, report)
    return rows, report


class FreezeQualificationError(ValueError):
    pass


def audit_existing_freeze(pool_path: Path, frozen_dir: Path, *, policy: str,
                          expected_pool_sha256: str | None = None) -> dict:
    """审计底层 CLE 已导出的冻结快照，不重复按 active 状态重冻结。

    底层 ``CleRunner.freeze_tree`` 的契约是导出经验池全量快照，因此 C1/C2
    运行结束时快照可以包含 provisional 或 consolidated 节点。这里仍验证
    训练池哈希、候选 ID、快照非空和状态统计；真正的 C3 active/质量门控
    资格仍由 ``qualify_freeze`` 负责，不能用本函数绕过独立池资格检查。
    """
    raw = pool_path.read_bytes()
    actual_hash = hashlib.sha256(raw).hexdigest()
    if expected_pool_sha256 and expected_pool_sha256 != actual_hash:
        raise FreezeQualificationError("pool_hash_mismatch")
    rows, _ = validate_jsonl(pool_path, report_path=frozen_dir / "jsonl_validation.json")
    ids = [str(row.get("invariant_id") or "") for row in rows]
    if not rows or not all(ids) or len(set(ids)) != len(ids):
        raise FreezeQualificationError("invalid_pool_ids")
    mstar = frozen_dir / "m_star.jsonl"
    if not mstar.is_file():
        raise FreezeQualificationError("missing_existing_mstar")
    frozen_rows, _ = validate_jsonl(mstar, report_path=frozen_dir / "mstar_jsonl_validation.json")
    frozen_ids = [str(row.get("invariant_id") or "") for row in frozen_rows]
    if not frozen_rows or not all(frozen_ids) or len(set(frozen_ids)) != len(frozen_ids):
        raise FreezeQualificationError("invalid_frozen_ids")
    counts = dict(Counter(str(row.get("status") or "unknown") for row in rows))
    frozen_counts = dict(Counter(str(row.get("status") or "unknown") for row in frozen_rows))
    metadata = {
        "schema": "cle-ablation-freeze-v1", "policy": policy, "eligible": True,
        "source": "cle_runner_freeze_tree", "candidate_count": len(rows),
        "frozen_count": len(frozen_rows), "active_count": counts.get("active", 0),
        "status_counts": counts, "frozen_status_counts": frozen_counts,
        "pool_sha256": actual_hash, "m_star_sha256": hashlib.sha256(mstar.read_bytes()).hexdigest(),
        "feedback_channel": "disabled",
        "source_stages": sorted({str((r.get("source") or {}).get("stage", "unknown")) for r in rows}),
    }
    frozen_dir.mkdir(parents=True, exist_ok=True)
    (frozen_dir / "freeze_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def qualify_freeze(pool_path: Path, frozen_dir: Path, *, policy: str, expected_pool_sha256: str | None = None) -> dict:
    raw = pool_path.read_bytes()
    actual_hash = hashlib.sha256(raw).hexdigest()
    if expected_pool_sha256 and expected_pool_sha256 != actual_hash:
        raise FreezeQualificationError("pool_hash_mismatch")
    rows, _ = validate_jsonl(pool_path, report_path=frozen_dir / "jsonl_validation.json")
    ids = [str(row.get("invariant_id") or "") for row in rows]
    if not rows or not all(ids) or len(set(ids)) != len(ids):
        raise FreezeQualificationError("invalid_pool_ids")
    counts = dict(Counter(str(row.get("status") or "unknown") for row in rows))
    active = [row for row in rows if row.get("status") == "active"]
    if not active:
        raise FreezeQualificationError("no_active_nodes")
    rejected: list[dict] = []
    eligible = []
    for row in active:
        reasons = []
        # 这些字段由 CLE 门控记录写入；缺失时 C3-0 允许通过，后续门控明确拒绝，
        # 避免把“未测量”悄悄当作通过。
        if policy in {"C3-1", "C3-2", "C3-3"} and row.get("quality_score") is not None:
            try:
                if float(row["quality_score"]) < 0.6:
                    reasons.append("quality_below_threshold")
            except (TypeError, ValueError):
                reasons.append("invalid_quality_score")
        elif policy in {"C3-1", "C3-2", "C3-3"} and row.get("quality_score") is None:
            reasons.append("quality_unmeasured")
        if policy in {"C3-2", "C3-3"} and row.get("independent_validity") is not True:
            reasons.append("independent_validity_failed_or_unmeasured")
        if policy == "C3-3" and row.get("h_pass_regression") is not True:
            reasons.append("h_pass_regression_failed_or_unmeasured")
        if reasons:
            rejected.append({"invariant_id": row.get("invariant_id"), "reasons": reasons})
        else:
            eligible.append(row)
    active = eligible
    if not active:
        raise FreezeQualificationError("no_active_nodes_after_policy")
    frozen_dir.mkdir(parents=True, exist_ok=True)
    mstar = frozen_dir / "m_star.jsonl"
    mstar.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in active), encoding="utf-8")
    metadata = {
        "schema": "cle-ablation-freeze-v1", "policy": policy, "eligible": True,
        "candidate_count": len(rows), "frozen_count": len(active), "active_count": len(active),
        "status_counts": counts, "pool_sha256": actual_hash, "rejected_count": len(rejected),
        "rejections": rejected,
        "m_star_sha256": hashlib.sha256(mstar.read_bytes()).hexdigest(),
        "feedback_channel": "disabled", "source_stages": sorted({str((r.get("source") or {}).get("stage", "unknown")) for r in rows}),
    }
    (frozen_dir / "freeze_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata
