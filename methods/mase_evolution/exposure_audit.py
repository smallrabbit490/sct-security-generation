"""确认集准备阶段：保守统计历史真实运行与来源暴露；清单成员不等于已运行。

只读历史产物，不获取隐藏测试内容、不调用模型、不更新经验。未找到记录只能
说明本地审计未发现暴露，不能证明从未参与调参；不自动把它们当独立确认集。
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .artifacts import write_json


def scan(roots, tasks):
    """输入运行根与PLT任务映射→来源路径/暴露family/未知记录；损坏文件显式列出。"""
    by_id={str(t['index']):t['family_id'] for t in tasks}
    known=set(by_id.values())
    exposed=set()
    files=[]
    errors=[]
    candidates=set()
    for root in roots:
        root=Path(root)
        for pattern in ('*rows*.jsonl','trajectories.jsonl','*source*bank*.json'):
            candidates.update(root.rglob(pattern))
    for path in sorted(candidates):
        # 导入/缓存副本不增加独立证据；正式测试内容也不读取。
        if any(p in ('validation_runs','baseline_runs','mase_evolution','cache','temp') for p in path.parts):
            continue
        found=set()
        count=0
        try:
            if path.suffix=='.json':
                value=json.loads(path.read_text(encoding='utf-8'))
                records=value if isinstance(value,list) else []
            else:
                records=None
            with path.open(encoding='utf-8') as stream:
                for record in records if records is not None else stream:
                    if isinstance(record,str):
                        if not record.strip():
                            continue
                        record=json.loads(record)
                    if not isinstance(record,dict):
                        continue
                    # 只认逐题评分/轨迹或真实来源卡，不读pool_manifest成员。
                    if not any(k in record for k in ('final','generated_codes','source_id','functional','result','evidence')):
                        continue
                    count+=1
                    family=record.get('family_id')
                    ident=record.get('source_id',record.get('task_id',record.get('index')))
                    mapped=by_id.get(str(ident))
                    if family in known:
                        found.add(family)
                    elif mapped:
                        found.add(mapped)
        except (OSError,ValueError) as exc:
            errors.append({'path':str(path),'error_type':type(exc).__name__})
        if found or count:
            files.append({'path':str(path),'records':count,'families':sorted(found)})
        exposed.update(found)
    return {'exposed_families':sorted(exposed),'not_found_in_records':sorted(known-exposed),
            'files':files,'errors':errors,'proves_pristine':False,
            'interpretation':'未找到本地运行证据不能证明从未参与调参；独立确认仍需人工核查。'}


def main():
    """仅运行暴露审计；报告进入运行区，不选择确认集或更新方法。"""
    from .run import ROOT,DEFAULT_ROOT
    from methods.sct_trajectory.run_closed_loop import _load_tasks
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_ROOT/'exposure_audit.json')
    args=parser.parse_args()
    report=scan([ROOT/'translation_work/sct_runs',ROOT/'translation_work/diagnostics'],_load_tasks(0))
    write_json(args.output,report)
    print(json.dumps({'exposed_families':len(report['exposed_families']),
                      'not_found':len(report['not_found_in_records']),'errors':len(report['errors'])}))


if __name__=='__main__':
    main()
