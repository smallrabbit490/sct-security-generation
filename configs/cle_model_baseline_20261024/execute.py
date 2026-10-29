"""v4.1 Flash 1017全CLE基准：新建经验、原生三阶段、独立测试和零API回放。"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from methods.sct_trajectory.replay_journal import RequestJournal, ReplayStop, write_json


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def install_recorders(run, mode, original_root):
    """沿用既有客户端及密钥加载器；替换只增加记录/回放，不改变模型可见正文。"""
    from methods.sct_trajectory import run_closed_loop as native
    from methods.sct_trajectory import semantic_retrieval as semantic
    from methods.sct_lifecycle_replay import chatanywhere_smoke as credentials
    original_factory = native._requester
    if mode != 'replay':
        # 从原项目调用原生加载器；函数内部才认证，不复制凭据到源码快照。
        spec = importlib.util.spec_from_file_location('cle_original_credential_loader',
            original_root / 'methods/sct_lifecycle_replay/chatanywhere_smoke.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        native.load_key = credentials.load_key = module.load_key
    else:
        def denied():
            raise ReplayStop('credentials_disabled_during_replay')
        native.load_key = credentials.load_key = denied
    llm = RequestJournal(run / 'requests', mode=mode)

    def factory(model, timeout, max_tokens=4096, max_inflight=0, **kwargs):
        kwargs.update(thinking='disabled', stream=True,
            endpoint='https://api.chatanywhere.org/v1/chat/completions',
            hard_timeout=300, gate_wait_timeout=600)
        return llm.wrap(lambda: original_factory(model, max(timeout, 180), max_tokens,
                    max_inflight, **kwargs),
                {'model': model, 'max_tokens': max_tokens, 'thinking': 'disabled',
                 'temperature': 0, 'roles': ['user'], 'stream': True})
    native._requester = factory
    embeddings = RequestJournal(run / 'embedding_requests', mode='replay' if mode == 'replay' else 'extend')
    original_embedding = semantic.EmbeddingClient._request

    def embed_request(client, texts):
        def live(_):
            before = client.usage
            vectors = original_embedding(client, texts)
            after = client.usage
            return {'vectors': vectors, 'usage': {k: after.get(k, 0)-before.get(k, 0)
                    for k in ('prompt_tokens', 'total_tokens')}}
        wrapped = embeddings.wrap(lambda: live, {'model': client.model, 'operation': 'embedding'})
        return wrapped(json.dumps(texts, ensure_ascii=False))['vectors']
    semantic.EmbeddingClient._request = embed_request
    return llm, embeddings


def arguments(protocol, stage, run, out):
    """使用原入口；只读本轮输入快照，绝不传入历史冻结库或Q学习开关。"""
    bundle = run / 'source_bundle'
    if stage == 'PLT':
        args = ['--out', str(out), '--tasks-file', str(bundle / 'inputs/plt_tasks.json')]
        for key, value in protocol['training_args'].items():
            flag = '--' + key.replace('_', '-')
            if value is True:
                args.append(flag)
            elif value is not False and value is not None:
                args.extend([flag, str(value)])
        args.extend(['--embedding-cache', str(run / 'embeddings.sqlite3')])
        return args
    return ['--out', str(out), '--memory', str(read(run / 'state.json')['new_memory']),
            '--data-root', str(bundle / 'data/SecEvoBasePlus'), '--subsets', stage,
            '--only-cle', '--context-pipeline', '--internal-checks',
            '--model', protocol['model'], '--max-tokens', '4096', '--workers', '4',
            '--retrieval-mode', 'semantic_llm', '--embedding-model', 'text-embedding-3-large',
            '--embedding-cache', str(run / 'embeddings.sqlite3')]


def record_validations(run, stage):
    """逐次封存实际代码、题目、测试和验证结果，供不生成新代码的完整事件回放。"""
    from methods.sct_trajectory import closed_loop, internal_checks, run_plus_frozen_comparison
    folder = run / 'validation_events' / stage
    folder.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    count = [len(list(folder.glob('*.json')))]

    def wrap(kind, original):
        def call(*args, **kwargs):
            with lock:
                count[0] += 1
                path = folder / f'{count[0]:07d}.json'
            event = {'kind':kind,'args':args,'kwargs':kwargs,
                     'started_utc':datetime.now(timezone.utc).isoformat()}
            write_json(path,event)
            result = original(*args,**kwargs)
            event.update(result=result,finished_utc=datetime.now(timezone.utc).isoformat())
            write_json(path,event)
            return result
        return call
    closed_loop.validate_and_state = wrap('PLT_official', closed_loop.validate_and_state)
    internal_checks.execute_checks = wrap('public_internal', internal_checks.execute_checks)
    run_plus_frozen_comparison.evaluate = wrap('BasePlus_official', run_plus_frozen_comparison.evaluate)


def stage_run(run, stage, *, mode='live'):
    """每段输出新目录；请求记录与精确输入共享，恢复时不会重付已完成前缀。"""
    protocol = read(run / 'protocol.json')
    journal_root = run / 'journals' / stage
    journals = install_recorders(journal_root, mode, Path(protocol['original_project_root']))
    if mode != 'replay':
        record_validations(run, stage)
    stage_root = ROOT / 'translation_work' / ('replay' if mode == 'replay' else 'baseline') / stage
    stage_root.mkdir(parents=True, exist_ok=True)
    attempt = len(list(stage_root.glob('segment_*'))) + 1
    out = stage_root / f'segment_{attempt:03d}'
    sys.argv = ['native_CLE', *arguments(protocol, stage, run, out)]
    from methods.sct_trajectory.wire_recording import WireRecording
    if mode == 'replay':
        # 所有未记录HTTP均禁止，包括意外绕开模型包装器的调用。
        import urllib.request
        def denied(*a, **k):
            raise ReplayStop('network_disabled_during_replay')
        urllib.request.urlopen = denied
    try:
        if stage == 'PLT':
            from methods.sct_trajectory.run_closed_loop import main
        else:
            from methods.sct_trajectory.run_plus_frozen_comparison import main
        if mode == 'replay':
            main()
        else:
            with WireRecording(run / 'wire' / stage):
                main()
    finally:
        write_json(run / ('replay_cost_' if mode == 'replay' else 'cost_') / (stage + '.json'),
                   {'LLM': journals[0].summary(), 'Embedding': journals[1].summary(),
                    'replay_does_not_add_paid_calls': True})
    if stage == 'PLT':
        p1 = [json.loads(x) for x in (out / 'phase1_results.jsonl').read_text(encoding='utf-8').splitlines()]
        final = [json.loads(x) for x in (out / 'final_eval.jsonl').read_text(encoding='utf-8').splitlines()]
        if len(p1) != 303 or len(final) != 298:
            raise ReplayStop('PLT_incomplete_native_outputs')
    else:
        rows = [json.loads(x) for x in (out / 'rows.jsonl').read_text(encoding='utf-8').splitlines()]
        expected = protocol['counts'][stage]
        if len(rows) != expected or len({r['task_id'] for r in rows}) != expected:
            raise ReplayStop('independent_evaluation_incomplete_or_duplicate')
    return out


def image_available():
    result = subprocess.run(['docker', 'image', 'inspect', 'safecoder-python-validator:local',
             '--format', '{{.Id}}'], capture_output=True, text=True, timeout=30)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--stage', choices=['PLT', 'Base', 'Plus'], required=True)
    parser.add_argument('--mode', choices=['live', 'resume', 'replay'], default='live')
    args = parser.parse_args()
    run = args.run_root.resolve()
    state = read(run / 'state.json')
    if args.mode != 'replay':
        control = read(Path(read(run / 'protocol.json')['control_summary']))
        if not (control.get('status') == 'passed' and control.get('reported_model') == state['model']):
            raise ReplayStop('minimal_new_model_control_not_passed')
        if args.stage != 'PLT' and not state.get('new_memory'):
            raise ReplayStop('new_training_memory_not_ready')
        if args.stage == 'Plus' and 'Base' not in state.get('completed', {}):
            raise ReplayStop('Base_must_finish_before_Plus')
        if args.stage != 'PLT' and not image_available():
            state.update(status='blocked_environment', blocked_reason='original_python_validator_image_missing')
            write_json(run / 'state.json', state)
            return
        state.update(status='running', stage=args.stage, pid=os.getpid())
        write_json(run / 'state.json', state)
    try:
        out = stage_run(run, args.stage, mode=args.mode)
    except BaseException as exc:
        if args.mode != 'replay':
            state.update(status='stopped_technical', stage=args.stage, error_type=type(exc).__name__, pid=None)
            write_json(run / 'state.json', state)
        raise
    if args.mode != 'replay':
        state.setdefault('completed', {})[args.stage] = str(out)
        if args.stage == 'PLT':
            state['new_memory'] = str(out / 'frozen/m_star.jsonl')
        state.update(status='completed' if len(state['completed']) == 3 else 'stage_completed', pid=None)
        write_json(run / 'state.json', state)
    else:
        write_json(run / 'replay_results' / (args.stage + '.json'), {'output': str(out), 'network_calls': 0})


if __name__ == '__main__':
    main()
