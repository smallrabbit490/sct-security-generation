"""修复已观测的选择器180k字符预算故障，两组统一420k；保留旧失败并复用有效轨迹。"""
import argparse
import copy
import shutil
from pathlib import Path

from methods.cle_ablation import run_memory_q_dinit_card_cap as study
from methods.sct_trajectory import semantic_retrieval

ROOT = study.ROOT
ORIGINAL = ROOT / 'translation_work/diagnostics/20261020/cle_dinit_card_cap_v1'
CONFIG = ROOT / 'configs/cle_dinit_card_cap_20261020_v2'
OUT = ROOT / 'translation_work/diagnostics/20261020/cle_dinit_card_cap_v2'


def configure():
    study.CONFIG = CONFIG
    study.OUT = OUT
    study.CURATED = ROOT / 'results/curated/cle_dinit_card_cap_20261020_v2'
    study.PROTOCOL = 'cle-dinit-card-cap-v2-selector-budget420k'
    # 仅本显式实验进程改变长度许可；候选正文、提示词、生成预算及旧入口不变。
    semantic_retrieval.MAX_SELECTOR_CHARS = 420000


def bootstrap():
    configure()
    if (OUT / 'recovery.json').exists():
        return study.verify()
    old = study.read(ORIGINAL / 'run_metadata.json')
    assert old['status'] == 'technical_stop'
    for name, expected in old['identity'].items():
        assert study.core.digest(ROOT / name) == expected
    summary = study.read(ORIGINAL / 'summary.json')
    assert summary['fatal_issues'] == [{'arm':'L3','task_id':'1350','issue':'retrieval_infrastructure_or_budget'}]
    bad = study.read(ORIGINAL / 'task_rows/L3/1350.json')
    assert study.core.trace_of(bad['attempts'][1])['errors'] == ['selector_prompt_budget_exceeded']
    CONFIG.mkdir(parents=True, exist_ok=True)
    p = copy.deepcopy(study.read(ORIGINAL / 'protocol.json'))
    p.update(protocol=study.PROTOCOL, selector_prompt_max_chars=420000,
             recovery='preserve failed L3/1350; reuse15 valid complete P7 records; cumulative cost including v1')
    study.write(CONFIG / 'protocol.json', p)
    study.write(CONFIG / 'manifest.json', {**study.read(ORIGINAL / 'manifest.json'), 'protocol':study.PROTOCOL})
    study.prepare()
    for folder in ('requests','embedding_requests','initials','exposure_masks'):
        shutil.copytree(ORIGINAL / folder, OUT / folder, dirs_exist_ok=True)
    retained = []
    for arm in study.ARMS:
        for path in (ORIGINAL / 'task_rows' / arm).glob('*.json'):
            if arm == 'L3' and path.stem == '1350':
                continue
            row = study.read(path)
            assert not study.inspect(row)
            row.update(execution_protocol=row['protocol'], protocol=study.PROTOCOL,
                execution_source=str(path.relative_to(ROOT)), recovery_reused_record=True)
            study.write(OUT / 'task_rows' / arm / path.name, row)
            target = OUT / 'native_rows' / arm / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ORIGINAL / 'native_rows' / arm / path.name, target)
            retained.append((arm,path.stem))
    assert len(retained)==15
    # 已完成的正常请求提示与输出没有改变：长度门只拒绝旧失败的那次未发出的选择。
    recovery = {'reason':'observed_selector_prompt_budget_exceeded','old_limit_chars':180000,
        'new_limit_chars':420000,'retained_complete_records':retained,'discarded_primary_record':['L3','1350'],
        'old_record_preserved':True,'same_actual_prompts_for_retained_records':True,
        'cumulative_cost':True,'additional_physical_P7_due_technical_recovery':1}
    study.write(OUT / 'recovery.json',recovery)
    study.write(CONFIG / 'recovery.json',recovery)
    meta = study.read(OUT / 'run_metadata.json')
    path = Path(__file__).resolve()
    meta['identity'][str(path.relative_to(ROOT))] = study.core.digest(path)
    target = OUT / 'source_snapshot' / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path,target)
    meta.update(status='prepared',recovery=recovery)
    study.write(OUT / 'run_metadata.json',meta)
    return study.verify()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','smoke','pilot','full','report'])
    command=parser.parse_args().command
    bootstrap()
    result=study.report() if command=='report' else study.verify() if command=='prepare' else study.run(command)
    print({k:result[k] for k in ('status','P7_runs','arms') if k in result},flush=True)
