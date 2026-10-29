"""仅回放已交付的S1原生行；未完成格不补请求，失败复析保持原样。"""
import json
import importlib.util
import shutil
import sqlite3
import sys
from pathlib import Path


def main():
    root=Path(__file__).resolve().parents[2]
    run=root/'translation_work/diagnostics/20261025/cle_v41_migration_S1'
    bundle=run/'source_bundle'
    parts=[run]+([Path(p) for p in json.loads((run/'recovery_segments.json').read_text())]
                 if (run/'recovery_segments.json').exists() else [])
    sys.path.insert(0,str(bundle));sys.path.insert(0,str(bundle/'src'))
    from methods.cle_ablation import runner
    from methods.sct_trajectory import run_closed_loop as native
    from methods.sct_trajectory.replay_journal import RequestJournal, ReplayStop, write_json
    from methods.sct_trajectory.context_pipeline import analysis_prompt
    from methods.sct_trajectory.agent_pipeline import _extract_json, _content
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    from configs.cle_v41_migration_20261025.run import empty_provider, MODEL
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    paths=[p for base in parts for p in sorted((base/'task_rows').glob('*.json'))]
    assert len({p.stem for p in paths})==len(paths)
    out=run/'replay_results'/f'completed_{len(paths)}'
    out.mkdir(parents=True,exist_ok=False)
    def denied(*a,**k):raise ReplayStop('zero_API_replay_network_and_credentials_denied')
    native.load_key=denied
    import urllib.request
    urllib.request.urlopen=denied
    # 复制已保存的真实向量，不给原缓存写入，也不因回放缺失而补embedding。
    with sqlite3.connect(f'file:{(parts[-1]/"embeddings.sqlite3").as_posix()}?mode=ro',uri=True) as src:
        with sqlite3.connect(out/'embeddings.sqlite3') as dst:src.backup(dst)
    EmbeddingClient._request=denied
    embedding=EmbeddingClient(cache_path=out/'embeddings.sqlite3',key_loader=denied)
    nodes=runner.load_memory(run/'inputs/memory.jsonl')
    tasks={str(t['index']):t for t in read(run/'inputs/tasks.json')}
    settings={'model':MODEL,'max_tokens':4096,'thinking':'disabled','temperature':0,'roles':['user'],'stream':True}
    spec=importlib.util.spec_from_file_location('migration_prefix_replay_tools',root/'configs/cle_v41_migration_20261025/resume.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    def request(identity):
        j=helper.make_prefix_journal(RequestJournal,out/'journals'/identity/'requests',
                                    [base/'journals'/identity/'requests' for base in parts])
        j.mode='replay'
        return j.wrap(lambda:denied,settings)
    def semantic(value):
        # selector真实耗时自然无法重演；只排除该时钟字段，其余原生行逐字段比较。
        if isinstance(value,dict):return {k:semantic(v) for k,v in value.items() if k!='elapsed_seconds'}
        if isinstance(value,list):return [semantic(v) for v in value]
        return value
    differences=[]
    for path in paths:
        old=read(path);tid=old['task_id'];arm=old['migration_arm'];pair_id=f"{tid}_r{old['repeat']}"
        initial=_extract_json(_content(request('shared_'+pair_id)(analysis_prompt(runner.plt_contract(tasks[tid])))))
        row=runner.run_one('PLT',tasks[tid],'P7',request(old['cell_id']),{'full':nodes},embedding,
            initial_analysis=initial,max_experiences=3,retrieval_mode='semantic_llm',candidate_order=None,
            delta=None,retrieval_provider=empty_provider if arm=='E0' else None)
        row.update({k:old[k] for k in ('migration_arm','repeat','family_id','cell_id','protocol','Q_updates')})
        write_json(out/'task_rows'/path.name,row)
        if semantic(row)!=semantic(old):differences.append(old['cell_id'])
    result={'status':'passed' if not differences else 'differences','rows':len(paths),
        'different_cells':differences,'API_calls':0,'credentials_reads':0,
        'comparison':'all native fields except selector elapsed_seconds; saved embedding cache reused',
        'partial_cells_not_executed':True}
    write_json(out/'summary.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
