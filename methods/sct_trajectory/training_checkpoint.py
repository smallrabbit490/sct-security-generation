"""训练恢复的阶段完整性检查；只读上游，不把最大轨迹轮号当完整门控轮数。"""
import hashlib
import json
from pathlib import Path


def phase1_resume_source(path, expected_ids):
    """新方法只接受完整 Phase1 快照；混有 Phase2 或源清单不完整立即失败，不写库。"""
    path = Path(path)
    trajectories = path / 'trajectories.jsonl'
    if trajectories.exists() and trajectories.read_text(encoding='utf-8').strip():
        raise ValueError('global_gate_resume_requires_phase1_only')
    results = [json.loads(line) for line in (path / 'phase1_results.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    ids = [str(row['task_id']) for row in results]
    if len(ids) != len(set(ids)) or set(ids) != {str(i) for i in expected_ids}:
        raise ValueError('phase1_task_manifest_mismatch')
    pool_path = path / 'experience_pool.jsonl'
    pool = [json.loads(line) for line in pool_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    expected = {str(i) for i in expected_ids}
    if not pool or any((r.get('source') or {}).get('stage') != 'phase1' or
                       str((r.get('source') or {}).get('task_id')) not in expected for r in pool):
        raise ValueError('global_gate_resume_requires_phase1_only')
    card_ids = [str(row.get('invariant_id') or '') for row in pool]
    if not all(card_ids) or len(set(card_ids)) != len(card_ids):
        raise ValueError('phase1_memory_identity_mismatch')
    return {'path': str(path.resolve()), 'phase1_results': len(results),
            'memory_sha256': hashlib.sha256(pool_path.read_bytes()).hexdigest(), 'memory_count': len(pool)}


def phase2_resume_source(path, expected_ids, completed_rounds, max_rounds):
    """校验含有 Phase2 部分轨迹的检查点，供 global gate 续跑使用。"""
    path = Path(path)
    if completed_rounds < 0 or completed_rounds > max_rounds:
        raise ValueError('invalid_completed_round_count')
    phase1_path = path / 'phase1_results.jsonl'
    pool_path = path / 'experience_pool.jsonl'
    traj_path = path / 'trajectories.jsonl'
    if not phase1_path.is_file() or not pool_path.is_file() or not traj_path.is_file():
        raise ValueError('phase2_resume_missing_checkpoint')
    results = [json.loads(line) for line in phase1_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    ids = [str(row.get('task_id')) for row in results]
    if len(ids) != len(set(ids)) or set(ids) != {str(i) for i in expected_ids}:
        raise ValueError('phase2_resume_phase1_manifest_mismatch')
    pool = [json.loads(line) for line in pool_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    card_ids = [str(row.get('invariant_id') or '') for row in pool]
    if not pool or not all(card_ids) or len(card_ids) != len(set(card_ids)):
        raise ValueError('phase2_resume_memory_identity_mismatch')
    return {'path': str(path.resolve()), 'mode': 'phase2_partial',
            'phase1_results': len(results), 'completed_rounds': completed_rounds,
            'memory_sha256': hashlib.sha256(pool_path.read_bytes()).hexdigest(),
            'memory_count': len(pool),
            'trajectory_count': sum(1 for line in traj_path.read_text(encoding='utf-8').splitlines() if line.strip())}
