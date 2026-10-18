"""只读CLE运行概况；不执行生成代码，不访问模型，不输出题面、夹具或凭据。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def inspect_run(run):
    """只归纳确有原生final字段的记录；未知schema保留为未归纳。"""
    run = Path(run).resolve(strict=True)
    names = ('run_metadata.json', 'status.json', 'summary.json', 'manifest.json', 'rows.jsonl',
             'gate_B.json', 'gate_D.json', 'selection.json', 'human_labels.json')
    result = {'run': str(run), 'files_present': [name for name in names if (run / name).is_file()],
              'operation': 'read_only_inventory', 'model_calls': 0, 'code_execution': False}
    if (run / 'run_metadata.json').is_file():
        metadata = load(run / 'run_metadata.json')
        keys = ('protocol', 'model', 'backend', 'feedback_channel', 'max_tokens', 'thinking',
                'embedding_model', 'Q_updates', 'dataset')
        result['metadata'] = {k: metadata[k] for k in keys if k in metadata}
        if isinstance(metadata.get('parameters'), dict):
            result['parameters'] = {k: metadata['parameters'][k] for k in keys if k in metadata['parameters']}
    if (run / 'status.json').is_file():
        status = load(run / 'status.json')
        result['stage'] = status.get('stage')
    if (run / 'summary.json').is_file():
        summary = load(run / 'summary.json')
        result['reported_summary'] = {k: summary[k] for k in (
            'protocol', 'role', 'stage', 'status', 'human_confirmed', 'candidate_pairs',
            'confirmation_run', 'confirmation_conclusion') if k in summary}
    for filename in ('gate_B.json', 'gate_D.json'):
        if (run / filename).is_file():
            gate = load(run / filename)
            result[filename] = {k: gate[k] for k in (
                'passed', 'complete', 'technical_gate', 'q_passed', 'retrieval_passed',
                'missing_human_pairs', 'reason', 'next') if k in gate}
    if (run / 'human_labels.json').is_file():
        result['human_label_records'] = len(load(run / 'human_labels.json'))
    if (run / 'rows.jsonl').is_file():
        totals, native, identities = Counter(), defaultdict(Counter), defaultdict(list)
        with (run / 'rows.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                totals['records'] += 1
                final = row.get('final')
                if not isinstance(final, dict) or not all(k in final for k in ('functional', 'security', 'joint', 'measured')):
                    totals['records_without_native_final'] += 1
                    continue
                arm = row.get('arm')
                native[arm]['records'] += 1
                identities[arm].append(str(row['task_id']) if 'task_id' in row else None)
                for key in ('functional', 'security', 'joint', 'measured'):
                    if final[key] is True:
                        native[arm][key + '_true'] += 1
                    elif final[key] is False:
                        native[arm][key + '_false'] += 1
                    else:
                        native[arm][key + '_unknown'] += 1
                if row.get('error_type'):
                    native[arm]['row_error_type_present'] += 1
        result['row_counts'] = dict(totals)
        result['native_final_counts'] = [
            {'arm': arm, **dict(counts), 'unique_nonmissing_task_ids': len({x for x in identities[arm] if x is not None})}
            for arm, counts in native.items()]
        result['row_scope'] = '原生final字段计数；不是完整格式审计、统计检验或作用链审查'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(inspect_run(args.run), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
