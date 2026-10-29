"""原生回放比较：保留内容、顺序和门控结果，排除实测耗时。

原比较器把检索耗时连同派生全文摘要作正文比较，实测导致同响应回放误报。
原始文件保留；只在比较视图中移除 elapsed_seconds/duration_ms，并重算视图摘要。
"""
import hashlib
import json
from pathlib import Path
from configs.cle_weekly_build_20261027.completion import rows


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def stable(value):
    if isinstance(value, list):
        return [stable(v) for v in value]
    if not isinstance(value, dict):
        return value
    result = {k: stable(v) for k, v in value.items() if k not in ('elapsed_seconds', 'duration_ms')}
    if 'card' in value and 'sha256' in value:
        if digest(value['card']) != value['sha256']:
            raise ValueError('original_card_snapshot_digest_mismatch')
        result['sha256'] = digest(result['card'])
    return result


def compare(original, replay):
    differences, counts = [], {}
    specs = [
        ('phase1_results.jsonl', lambda r: str(r['task_id']),
         ('outcome', 'card_id', 'state_first', 'state_after_repair', 'generated_codes', 'distilled', 'agent_context')),
        ('trajectories.jsonl', lambda r: str(r['task_id']) + ':' + str(r['round']),
         ('states', 'generated_codes', 'retrieved_per_round', 'agent_context', 'transitions')),
        ('completed_rounds.jsonl', lambda r: str(r['round']),
         ('round', 'selected', 'schedule', 'gate_deferred', 'forced_replay', 'pass_rates')),
        ('final_eval.jsonl', lambda r: str(r['task_id']),
         ('phase', 'arm', 'cards', 'retrieval_snapshot', 'code', 'error_type', 'error_class', 'state', 'measured')),
        ('frozen/m_star.jsonl', lambda r: r['invariant_id'], None),
        ('gate_records.jsonl', lambda r: r['candidate_id'], None),
    ]
    for filename, key, fields in specs:
        pair = []
        for root in (original, replay):
            values = rows(Path(root) / filename)
            mapped = {key(v): stable(v) for v in values}
            if len(mapped) != len(values):
                raise ValueError('duplicate_native_result_identity:' + filename)
            pair.append(mapped)
        left, right = pair
        counts[filename] = {'original': len(left), 'replay': len(right)}
        for identity in sorted(left.keys() | right.keys()):
            if identity not in left or identity not in right:
                differences.append({'file': filename, 'identity': identity, 'field': 'presence'})
                continue
            for field in fields or sorted(left[identity].keys() | right[identity].keys()):
                if left[identity].get(field) != right[identity].get(field):
                    differences.append({'file': filename, 'identity': identity, 'field': field})
            if filename in ('phase1_results.jsonl', 'trajectories.jsonl', 'final_eval.jsonl'):
                a, b = left[identity], right[identity]
                for field in ('evidence_first', 'evidence_after_repair', 'evidence'):
                    if stable(a.get(field)) != stable(b.get(field)):
                        differences.append({'file': filename, 'identity': identity, 'field': field})
    return {'status': 'primary_outputs_match' if not differences else 'different',
            'counts': counts, 'differences': differences,
            'excluded_from_comparison': ['elapsed_seconds', 'duration_ms', 'derived snapshot digest recalculated in comparison view']}
