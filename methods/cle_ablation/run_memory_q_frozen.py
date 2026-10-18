"""Q6冻结消费：原P7前向、两次固定预算，Base/Plus隐藏反馈绝不回流。"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from time import perf_counter

from methods.cle_ablation.runner import load_memory, run_one
from methods.cle_ablation.run_memory_q import ROOT, POLICIES, record_result
from methods.direction_screening.protocol import summarize
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_branch_gate_study import file_digest


def load_frozen(memory, calibration):
    """消费固定库或完整训练冻结配置；核验Q/内容身份，不写经验或读取评分。"""
    nodes = load_memory(memory)
    config = json.loads(calibration.read_text(encoding='utf-8'))
    if config.get('frozen'):
        from methods.sct_lifecycle_replay.freeze_protocol import build_freeze_metadata
        digest = build_freeze_metadata([n.to_dict() for n in nodes], config['model'], config['retriever'], 'CLE')['memory_sha256']
    else:
        digest = file_digest(memory)
    if digest != config['memory_sha256']:
        raise ValueError('frozen_memory_mismatch')
    return nodes, config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--memory', type=Path, required=True)
    parser.add_argument('--calibration', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--dataset', choices=('Base','Plus'), required=True)
    parser.add_argument('--limit', type=int, default=1)
    parser.add_argument('--arms', nargs='+', choices=('Q0','Q1','Q2'), default=['Q1','Q2'])
    parser.add_argument('--calibration-only', action='store_true')
    args = parser.parse_args(argv)
    nodes, config = load_frozen(args.memory, args.calibration)
    if not args.out.resolve().is_relative_to((ROOT/'translation_work').resolve()) or args.limit < 1:
        parser.error('invalid output or limit')
    data_path = ROOT/f'data/SecEvoBasePlus/{args.dataset}/Python_{args.dataset}.json'
    tasks = json.loads(data_path.read_text(encoding='utf-8'))[:args.limit]
    before = [n.to_dict() for n in nodes]
    args.out.mkdir(parents=True, exist_ok=False)
    metadata = {'model': config['model'], 'embedding_model': config['embedding_model'],
                'dataset':args.dataset, 'task_ids':[t['ID'] for t in tasks], 'arms':args.arms,
                'feedback_channel':'disabled', 'attempts':2, 'final_selection':'last',
                'memory_sha256':file_digest(args.memory), 'dataset_sha256':file_digest(data_path),
                'backend':'persistent_docker', 'status':'calibration', 'Q_updates':False,
                'max_tokens':config['max_tokens'], 'thinking':config.get('thinking'),
                'delta':config['delta'], 'lambda_q':config['lambda_q'], 'workers':1,
                'output_schema':['run_metadata.json','calibration.json','rows.jsonl','summary.json','cost.json']}
    write(args.out/'run_metadata.json', metadata)
    from translation_pipeline.persistent_container import cleanup_stale_containers, close_implicit_pools
    from methods.sct_trajectory.run_plus_frozen_comparison import evaluate
    import os
    os.environ['SAFECODER_DOCKER_POOL_SIZE'] = '1'
    os.environ['SAFECODER_PYTHON_DOCKER_IMAGE'] = 'safecoder-python-validator:local'
    controls, rows = [], []
    try:
        cleanup_stale_containers()
        for task in tasks:
            result = evaluate(task, task['Secure Code'], 30)
            controls.append({'task_id':task['ID'], 'joint':result['joint'], 'environment_error':result['environment_error']})
        write(args.out/'calibration.json', controls)
        if not all(r['joint'] for r in controls):
            metadata['model_calls'] = 0
            raise RuntimeError('positive_control_failed_no_model_calls')
        if args.calibration_only:
            metadata['status'] = 'calibrated'
            return
        from methods.sct_trajectory.run_closed_loop import _requester, load_key
        from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
        thinking = config.get('thinking')
        request = _requester(config['model'], 60, max_tokens=config['max_tokens'], max_inflight=1,
                             thinking=None if thinking == 'provider_default' else thinking)
        embedding = EmbeddingClient(model=config['embedding_model'], key_loader=load_key,
            cache_path=ROOT/'translation_work/cache/embeddings/cle.sqlite3', timeout=120)
        with (args.out/'rows.jsonl').open('w',encoding='utf-8') as stream:
            for i, task in enumerate(tasks):
                for arm in args.arms[i % len(args.arms):] + args.arms[:i % len(args.arms)]:
                    started = perf_counter()
                    row = run_one(args.dataset, task, 'P7', request, {'full':nodes}, embedding,
                        retrieval_mode=POLICIES[arm], delta=config['delta'], lambda_q=config['lambda_q'])
                    identity = {'family_id':task['ID'], 'CWE_ID':task['ID'].split('_')[0].replace('CWE-','')}
                    record_result(row, identity, arm, args.dataset, perf_counter()-started)
                    stream.write(json.dumps(row,ensure_ascii=False)+'\n'); stream.flush()
                    rows.append(row)
        if [n.to_dict() for n in nodes] != before or file_digest(args.memory) != metadata['memory_sha256']:
            raise RuntimeError('frozen_memory_changed')
        summary = summarize(rows, 'Q1')
        summary['role'] = 'independent_frozen_probe; historical benchmark exposure disclosed'
        write(args.out/'summary.json', summary)
        write(args.out/'cost.json', {'embedding':embedding.usage, 'llm':{a:{k:sum(r['usage'][k] for r in rows if r['arm']==a)
                    for k in ('calls','failed_calls','prompt_tokens','completion_tokens','total_tokens')} for a in args.arms}})
        metadata.update(status='completed', memory_unchanged=True, rows=len(rows))
    except BaseException as exc:
        metadata.update(status='failed', error_type=type(exc).__name__)
        raise
    finally:
        write(args.out/'run_metadata.json', metadata)
        close_implicit_pools()


if __name__ == '__main__':
    main()
