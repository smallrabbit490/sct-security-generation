"""Freeze native CLE build arguments; this command never dispatches requests."""
import json
from pathlib import Path

from .prepare_inputs import ROOT, RUN, read


def main():
    build = RUN / 'BUILD_C41'
    args_file = build / 'native_arguments.json'
    if args_file.exists():
        raise SystemExit('native_arguments_already_frozen')
    inputs = build / 'inputs/plt_tasks.json'
    tasks = read(inputs)
    manifest = read(build / 'inputs/manifest.json')
    if len(tasks) != 874 or manifest['starting_memory'] != 'empty' or manifest['Q_enabled']:
        raise SystemExit('unexpected_build_inputs')
    old = read(ROOT / 'translation_work/sct_runs/cle_full_v41flash1017_20261024/protocol.json')
    options = dict(old['training_args'])
    if options['model'] != 'deepseek-v4.1-flash-1017' or options['rounds'] != 3:
        raise SystemExit('unexpected_native_baseline')
    if options['retrieval_mode'] != 'semantic_llm' or options.get('q_learning', False):
        raise SystemExit('unexpected_retrieval_or_q')
    arguments = ['--out', str(build / 'native/segment_001'), '--tasks-file', str(inputs)]
    for key, value in options.items():
        flag = '--' + key.replace('_', '-')
        if value is True:
            arguments.append(flag)
        elif value is not False and value is not None:
            arguments.extend([flag, str(value)])
    arguments.extend(['--embedding-cache', str(build / 'embeddings.sqlite3')])
    args_file.write_text(json.dumps({'arguments': arguments, 'source': str(ROOT / 'translation_work/sct_runs/cle_full_v41flash1017_20261024/protocol.json'),
        'status': 'arguments_frozen_budget_and_execution_not_ready', 'API_calls': 0}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('native arguments frozen; no API calls; execution is not ready')


if __name__ == '__main__':
    main()
