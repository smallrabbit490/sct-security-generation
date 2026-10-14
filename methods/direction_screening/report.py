"""训练开发报告：配对对照、复用草稿成本与失败信号；不消费隐藏测试或修改源库。"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
from methods.direction_screening.protocol import summarize

ROOT=Path(__file__).resolve().parents[2]


def build(out,phase,include_phases=(),output_name=None):
    """报告阶段读取已落盘结果；未齐的组仅报告已完成条数，不宣布初筛完成。"""
    directory=out/(output_name or phase)
    directory.mkdir(exist_ok=True)
    rows=[json.loads(l) for name in [phase,*include_phases]
          for l in (out/name/'rows.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    keys=[(str(r['task_id']),r['arm']) for r in rows]
    if len(keys)!=len(set(keys)):
        raise ValueError('combined_report_duplicate_key')
    summary=summarize(rows)
    base={str(r['task_id']):r for r in rows if r['arm']=='direct'}
    def total_pairs(arm,control):
        reference={str(r['task_id']):r for r in rows if r['arm']==control}
        pairs=[(reference[str(r['task_id'])]['final'],r['final']) for r in rows
               if r['arm']==arm and str(r['task_id']) in reference]
        return {'pairs':len(pairs),'wins':sum(not a['joint'] and b['joint'] for a,b in pairs),
                'losses':sum(a['joint'] and not b['joint'] for a,b in pairs),
                'functional_harms':sum(a['functional'] and not b['functional'] for a,b in pairs)}
    summary['paired_total_denominator']={arm:total_pairs(arm,'direct') for arm in summary['arms'] if arm!='direct'}
    contrasts={}
    for arm,control in [('slice','rule'),('draft_memory','draft_plain'),('staged_memory','staged_empty'),
                        ('role_budget','review'),('verification','verification_plain'),('skill','slice'),
                        ('contract_direct','direct'),('contract_slice','slice'),('contract_skill','skill'),
                        ('contract_slice','contract_direct'),('contract_skill','contract_slice')]:
        comparison=summarize(rows,control)['paired'].get(arm)
        if comparison:
            comparison['total_denominator']=total_pairs(arm,control)
            contrasts[arm+'_vs_'+control]=comparison
    summary['component_contrasts']=contrasts
    errors=Counter()
    for row in rows:
        if row.get('error_type'):
            errors[(row['arm'],row['error_type'],row.get('error_reason',''))]+=1
    summary['errors_by_type']=[{'arm':a,'type':t,'reason':r,'n':n} for (a,t,r),n in errors.items()]
    for arm,stats in summary['arms'].items():
        stats['joint_percent']=100*stats['joint']/stats['n'] if stats['n'] else 0
        items=[r for r in rows if r['arm']==arm]
        reused=[base[str(r['task_id'])] for r in items if (r.get('shared_draft_from') or r.get('equivalent_to_empty_memory')) and str(r['task_id']) in base]
        stats['deployment_total_tokens']=stats['total_tokens']+sum(r['usage']['total_tokens'] for r in reused)
        stats['deployment_calls']=stats['calls']+sum(r['usage']['calls'] for r in reused)
        stats['workflow_parse_degraded']=sum(any(s.get('status')=='degraded' for s in r.get('workflow_stages',[])) for r in items)
        stats['fallbacks']=sum(bool(r.get('fallback_to_draft')) for r in items)
        stats['source_memory_used']=sum(bool(r.get('verification_memory_used')) for r in items) if arm=='verification' else None
        stats['syntax_failures']=sum(r['final']['evidence']['syntax_or_compile']['status']=='fail' for r in items)
        stats['generation_or_workflow_failures']=sum(not bool(r['final']['code'].strip()) for r in items)
    branch=[r for r in rows if r['arm']=='branch']
    summary['branch_selector']={'n':len(branch),'actual_joint':sum(r['final']['joint'] for r in branch),
                               'oracle_any_joint':sum(r.get('oracle_any_joint',False) for r in branch),
                               'missed_available_success':sum(r.get('oracle_any_joint',False) and not r['final']['joint'] for r in branch)}
    controller=[r for r in rows if r['arm']=='controller']
    summary['controller']={'n':len(controller),'repairs':sum(len(r['attempts'])>1 for r in controller),
                           'stopped_without_patch':sum(r.get('controller_actions')==['review','stop'] for r in controller)}
    (directory/'analysis.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# '+phase+' 训练开发结果','',f'已完成 {len(rows)} 条任务×方法记录。PLT 官方测试评分仅作训练开发证据。',
           '', '| 方法 | n | F | S | Joint | 完整测量 | 执行时调用（含共用草稿） | Token（含共用草稿） | 工作流错误 |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for arm,stats in summary['arms'].items():
        lines.append('| '+arm+' | '+' | '.join(str(stats[k]) for k in ('n','functional','security','joint','measured','deployment_calls','deployment_total_tokens','errors'))+' |')
    lines+=['','完整 F/S 测量配对差（语法失效候选在此缺测；总分母救回/伤害另列，不能把它当环境事故）：','',
            '| 组件对照 | 完整测量配对 | 救回 | 伤害 | 原始 p |','|---|---:|---:|---:|---:|']
    for label,c in contrasts.items():
        lines.append(f"| {label} | {c['measured_pairs']} | {c['wins']} | {c['losses']} | {c['p_exact']:.4g} |")
    lines+=['','这些组件比较是探索性，未对所有组件对照校正；相对 direct 的 Holm 校正见 analysis.json。',
            '大改只验证有界原型。route 用官方训练状态，其他选择器只看公开证据。',
            '审查模型结论、字符串 API 扫描、生成测试均不能代替 PLT 动态安全测试。',
            '', '分支实际 Joint / oracle 任一成功：'+str(summary['branch_selector'])]
    lines+=['','总分母组件差（包括候选语法失效/生成失败，环境事故仍须单独调查）：','',
            '| 组件对照 | 配对数 | 救回 | 伤害 |','|---|---:|---:|---:|']
    for label,c in contrasts.items():
        v=c['total_denominator']
        lines.append(f"| {label} | {v['pairs']} | {v['wins']} | {v['losses']} |")
    (directory/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'phase':phase,'rows':len(rows),'arms':{a:(s['n'],s['joint'],s['errors']) for a,s in summary['arms'].items()},
                      'component_contrasts':contrasts},ensure_ascii=False))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=ROOT/'translation_work/diagnostics/20261009/memory_architecture_screening')
    parser.add_argument('--phase',default='screen')
    parser.add_argument('--include-phase',action='append',default=[])
    parser.add_argument('--output-name')
    args=parser.parse_args()
    build(args.out,args.phase,args.include_phase,args.output_name)
