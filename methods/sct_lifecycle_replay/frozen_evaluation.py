"""冻结后的 Base/Plus 评测计划与反馈隔离检查。"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

LANGUAGE_FILES = {"python": ("Python_Base.json", "Python_Plus.json"), "go": ("Go_Base.json", "Go_Plus.json"), "cpp": ("Cpp_Base.json", "Cpp_Plus.json")}

def check_frozen_run(run_dir: str | Path) -> dict:
    """校验 M*、冻结标记和反馈通道，生成各语言的评测计划。"""
    root = Path(run_dir)
    metadata = json.loads((root / "frozen/freeze_metadata.json").read_text(encoding="utf-8"))
    memory_path = root / "frozen/m_star.jsonl"
    digest = hashlib.sha256(memory_path.read_bytes()).hexdigest()
    if metadata.get("memory_sha256") != digest:
        raise ValueError("freeze_memory_hash_mismatch")
    if metadata.get("feedback_channel") != "disabled":
        raise ValueError("freeze_feedback_enabled")
    dataset_root = root.parents[2] / "data/SecEvoBasePlus"
    plan = []
    for language, files in LANGUAGE_FILES.items():
        for subset, name in zip(("Base", "Plus"), files):
            path = dataset_root / subset / name
            plan.append({"language": language, "subset": subset, "dataset": str(path), "exists": path.exists(), "feedback_channel": "disabled"})
    return {"frozen": True, "memory_sha256": digest, "feedback_channel": "disabled", "plan": plan}
