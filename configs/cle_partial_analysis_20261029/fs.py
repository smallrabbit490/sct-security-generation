"""FFS停止后已落盘单元的描述性配对汇总；不重跑或补齐全量。"""
from collections import Counter, defaultdict
import json
from pathlib import Path

from methods.sct_trajectory.replay_journal import write_json

RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
OUT = RUN / 'FFS/analysis/paused_prefix_20261029'
ARMS = ['B0', 'BM', 'BF', 'BS', 'BFS']


def main():
    if (OUT/'summary.json').exists():
        raise RuntimeError('snapshot_already_saved')
    sources = [Path(p) for p in json.loads((RUN/'FFS/execution_index.json').read_text())['segments']]
    paths = {}
    for source in reversed(sources):
        for p in (source/'task_rows').glob('*.json'):
            paths.setdefault(p.stem, p)
    rows, groups = {}, defaultdict(dict)
    for identity,p in paths.items():
        r = json.loads(p.read_text(encoding='utf-8'))
        assert r['cell_id'] == identity
        v = {k:r[k] for k in ('cell_id','task_id','condition','repeat','family_id')}
        v['first'] = {k:r['attempts'][0].get(k) for k in ('functional','security','joint','measured')}
        v['final'] = {k:r['final'].get(k) for k in ('functional','security','joint','measured')}
        v['evidence_path'] = str(p)
        rows[identity] = v
        groups[str(r['task_id']),r['repeat']][r['condition']] = v
    shared = [g for g in groups.values() if set(g)==set(ARMS)]
    complete_measured = [g for g in shared if all(g[a]['final']['measured'] for a in ARMS)]
    counts = {}
    for a in ARMS:
        found = [v for v in rows.values() if v['condition']==a]
        counts[a] = {'saved':len(found),'measured':sum(bool(v['final']['measured']) for v in found),
            'F':sum(bool(v['final']['functional']) for v in found),
            'S':sum(bool(v['final']['security']) for v in found),
            'Joint':sum(bool(v['final']['joint']) for v in found),
            'common_measured_Joint':sum(bool(g[a]['final']['joint']) for g in complete_measured)}
    comparisons = {}
    for a in ('B0','BF','BS','BFS'):
        paired = [g for g in groups.values() if a in g and 'BM' in g
                  and g[a]['final']['measured'] and g['BM']['final']['measured']]
        gains = [g for g in paired if g[a]['final']['joint'] and not g['BM']['final']['joint']]
        losses = [g for g in paired if not g[a]['final']['joint'] and g['BM']['final']['joint']]
        s_loss = [g for g in paired if g['BM']['final']['security'] and not g[a]['final']['security']]
        comparisons[a+'-BM'] = {'measured_pairs':len(paired),'rescue':len(gains),'loss':len(losses),
            'net':len(gains)-len(losses),'new_security_failures':len(s_loss),
            'rescue_cells':[g[a]['cell_id'] for g in gains],'loss_cells':[g[a]['cell_id'] for g in losses]}
    checkpoint = json.loads((sources[-1]/'summary.json').read_text())
    result = {'status':'partial_saved_prefix_analyzed','formal_plan':2980,'saved_units':len(rows),
        'last_checkpoint_completed':checkpoint['completed'],
        'saved_beyond_last_checkpoint':len(rows)-checkpoint['completed'],
        'distinct_tasks':len({r['task_id'] for r in rows.values()}),'complete_five_arm_groups':len(shared),
        'complete_five_arm_measured_groups':len(complete_measured),'arms':counts,'paired':comparisons,
        'all_planned_units_complete':False,'new_experiment_HTTP':0}
    write_json(OUT/'per_cell.json',list(rows.values()))
    write_json(OUT/'summary.json',result)
    text='# 功能安全对照：已保存部分结果\n\n仅汇总停止后的实际保存代码，不补跑全量、不形成298题完整主结论。\n\n'
    text+=f"原计划2980次，最后汇总检查点{checkpoint['completed']}次，独立逐题文件实际{len(rows)}次。后者多出的{len(rows)-checkpoint['completed']}次已返回落盘，但全局汇总尚未刷新；全部单列复用，后续不能重发。\n\n"
    text+='| 条件 | 已保存 | 完整测量 | 功能 | 安全 | Joint |\n|---|---:|---:|---:|---:|---:|\n'
    for a,v in counts.items():text+=f"|{a}|{v['saved']}|{v['measured']}|{v['F']}|{v['S']}|{v['Joint']}|\n"
    text+='\nB0无卡；BM原混合卡；BF仅功能；BS仅安全；BFS分栏呈现两类。不同条件未完成数量不同，主要看同题同重复配对。\n\n'
    v=comparisons['BFS-BM']
    text+=f"BFS相对BM，在{v['measured_pairs']}组可测配对中救回{v['rescue']}次、损失{v['loss']}次，净变化{v['net']}次，另有{v['new_security_failures']}次安全从通过转为失败。\n\n"
    text+='这批结果描述已经运行的前缀，不把缺测计成已测失败，也不按未完成的重复估计完整实验收益。局部代码复验已另行保存，不能直接外推为本批全部损失的原因。\n'
    (OUT/'report.md').write_text(text,encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('arms','paired')},ensure_ascii=False))
    print(json.dumps(comparisons['BFS-BM'],ensure_ascii=False))


if __name__=='__main__':
    main()
