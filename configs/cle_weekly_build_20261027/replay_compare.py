"""Compare saved and replayed native outcomes without treating timings as results."""
from pathlib import Path
from .completion import rows


def keyed(items, key):
    result = {}
    for item in items:
        identity = str(item[key])
        if identity in result:
            raise ValueError('duplicate_replay_identity:' + identity)
        result[identity] = item
    return result


def compare(original, replay):
    original, replay = Path(original), Path(replay)
    specifications = [
        ('phase1_results.jsonl', 'task_id',
         ('outcome', 'card_id', 'state_first', 'state_after_repair', 'generated_codes', 'distilled')),
        ('final_eval.jsonl', 'task_id',
         ('phase', 'arm', 'cards', 'retrieval_snapshot', 'code', 'error_type', 'error_class', 'state', 'measured')),
        ('frozen/m_star.jsonl', 'invariant_id', None),
    ]
    differences = []
    counts = {}
    for filename, key, fields in specifications:
        left, right = keyed(rows(original / filename), key), keyed(rows(replay / filename), key)
        counts[filename] = {'original': len(left), 'replay': len(right)}
        for identity in sorted(set(left) | set(right)):
            if identity not in left or identity not in right:
                differences.append({'file': filename, 'identity': identity, 'field': 'presence'})
                continue
            if fields is None:
                if left[identity] != right[identity]:
                    differences.append({'file': filename, 'identity': identity, 'field': 'card'})
            else:
                for field in fields:
                    if left[identity].get(field) != right[identity].get(field):
                        differences.append({'file': filename, 'identity': identity, 'field': field})
                if filename == 'final_eval.jsonl':
                    for group in ('functional', 'security'):
                        a = left[identity].get('evidence') or {}
                        b = right[identity].get('evidence') or {}
                        if (a.get(group) or {}).get('status') != (b.get(group) or {}).get('status'):
                            differences.append({'file': filename, 'identity': identity, 'field': group + '.status'})
    return {'status': 'primary_outputs_match' if not differences else 'different',
            'counts': counts, 'differences': differences,
            'scope': 'selected primary outputs; not every raw event or timing'}
