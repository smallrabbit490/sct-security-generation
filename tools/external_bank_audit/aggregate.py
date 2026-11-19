"""按冻结题单聚合双判；缺测、分歧、token与未知用量独立列出。"""
import collections
import csv
import json
from pathlib import Path
from prepare import OUT, ROOT
from run import PROTOCOL
from schema import request_identity

BANK_ORDER=['CWEval','SecurityEval','LLMSecEval','SALLM','CodeGuard+','CyberSecEval','SecCodeBench-V2']
VERDICTS=['合格','有缺陷','无法判定']
DEFECTS=['接口契约','业务规则或数据','题面与测试冲突','环境依赖']
QUALITIES=['充分','安全组偏弱','Joint 可被绕过','输出格式过严','缺少正例','无法判定']
INTEGRITIES=['完整','不完整或语法错误','未提供','无法判定']


def render_classification_table(rows):
    """从已校验的逐题双判行生成面向阅读的按数据集汇总，不暴露逐题内容。"""
    summaries={}
    for bank in BANK_ORDER:
        sub=[r for r in rows if r['bank']==bank]
        verdicts=collections.Counter(); defects=collections.Counter()
        qualities=collections.Counter(); integrity=collections.Counter()
        valid=complete=agree=disagree=0
        for r in sub:
            labels=[]
            for suffix in ('s1','s2'):
                verdict=r[f'verdict_{suffix}']
                if verdict in VERDICTS:
                    valid+=1; verdicts[verdict]+=1; labels.append(verdict)
                    if verdict=='有缺陷' and r[f'defect_type_{suffix}']:
                        defects[r[f'defect_type_{suffix}']]+=1
            for suffix in ('s1',):
                quality=r[f'test_quality_{suffix}']
                if quality in QUALITIES: qualities[quality]+=1
                item_integrity=r[f'test_integrity_{suffix}']
                if item_integrity in INTEGRITIES: integrity[item_integrity]+=1
            if len(labels)==2:
                complete+=1
                if labels[0]==labels[1]: agree+=1
                else: disagree+=1
        summaries[bank]={'tasks':len(sub),'valid':valid,'complete':complete,'agree':agree,
                         'disagree':disagree,'verdicts':verdicts,'defects':defects,
                         'qualities':qualities,'integrity':integrity}

    def table(headers, body):
        return '\n'.join(['| '+' | '.join(headers)+' |',
                          '| '+' | '.join(['---']*len(headers))+' |']+
                         ['| '+' | '.join(str(v) for v in row)+' |' for row in body])

    lines=['# 七个函数级数据集审计分类汇总（当前部分结果）','',
           '按数据集汇总模型双判结果；不展示逐题明细。每次成功且通过本地校验的独立判断计一条 verdict/test_quality/test_integrity；缺陷类型只在 verdict=有缺陷时统计。',
           '双判一致率仅在两次判断都有效的题目上计算。SecCodeBench-V2 尚未派发；403 后停止，因此本表是部分结果。','',
           '## 覆盖与双判一致性','',
           table(['数据集','题数','有效判断 / 计划判断','完成双判','双判一致','双判分歧','一致率'],[
               [b,s['tasks'],f"{s['valid']} / {2*s['tasks']}",s['complete'],s['agree'],s['disagree'],
                f"{100*s['agree']/s['complete']:.1f}%" if s['complete'] else 'N/A']
               for b,s in summaries.items()]),'',
           '## Verdict 分布','',
           '分母为该数据集通过校验的独立判断数；缺测不进入百分比。','',
           table(['数据集','有效判断数']+[f'{v}（n / %）' for v in VERDICTS],[
               [b,s['valid']]+[f"{s['verdicts'][v]} / {100*s['verdicts'][v]/s['valid']:.1f}%" if s['valid'] else '0 / N/A' for v in VERDICTS]
               for b,s in summaries.items()]),'',
           '## 有缺陷类型','',
           '分母为该数据集被判为“有缺陷”的有效判断数；只有缺陷判断计入。','',
           table(['数据集','有缺陷判断数']+[f'{v}（n / %）' for v in DEFECTS],[
               [b,sum(s['defects'].values())]+[f"{s['defects'][v]} / {100*s['defects'][v]/sum(s['defects'].values()):.1f}%" if sum(s['defects'].values()) else '0 / N/A' for v in DEFECTS]
               for b,s in summaries.items()]),'',
           '## Test quality 分布','',
           '分母为该数据集有记录的第一判且给出合法 test_quality 的题数；第二判的 test_quality 未写入当前逐题聚合文件，因此不纳入。没有测试或测试不可判时按“无法判定”统计。','',
           table(['数据集','有效 test_quality 数']+[f'{v}（n / %）' for v in QUALITIES],[
               [b,sum(s['qualities'].values())]+[f"{s['qualities'][v]} / {100*s['qualities'][v]/sum(s['qualities'].values()):.1f}%" if sum(s['qualities'].values()) else '0 / N/A' for v in QUALITIES]
               for b,s in summaries.items()]),'',
           '## Test integrity 分布','',
           '分母为该数据集有记录的第一判且给出合法 test_integrity 的题数；第二判的 test_integrity 未写入当前逐题聚合文件，因此不纳入。','',
           table(['数据集','有效 integrity 数']+[f'{v}（n / %）' for v in INTEGRITIES],[
               [b,sum(s['integrity'].values())]+[f"{s['integrity'][v]} / {100*s['integrity'][v]/sum(s['integrity'].values()):.1f}%" if sum(s['integrity'].values()) else '0 / N/A' for v in INTEGRITIES]
               for b,s in summaries.items()]),'',
           '标签来自单模型两次独立判断，不等同人工复核。静态 oracle 数据集的 test_quality 为无法判定；本表也不代表全量动态测试已运行。','']
    return '\n'.join(lines)


def main():
    payloads=[json.loads(l) for l in (OUT/'payloads.jsonl').read_text(encoding='utf-8').splitlines()]
    rows=[]; totals=collections.defaultdict(collections.Counter)
    for p in payloads:
        records=[]
        for s in (1,2):
            f=OUT/'responses'/(request_identity(p,'gpt-6.1-sol',PROTOCOL,s)+'.json')
            records.append(json.loads(f.read_text(encoding='utf-8')) if f.exists() else None)
        labels=[r['parsed'] if r and r['status']=='ok' else None for r in records]
        a,b=labels
        row={'bank':p['bank'],'task_id':p['task_id'],'key':p['key'],'language':p['language'],
             'verdict_s1':a['verdict'] if a else '缺测','verdict_s2':b['verdict'] if b else '缺测',
            'agreement':(a['verdict']==b['verdict']) if a and b else None,
             'defect_type_s1':a.get('defect_type') if a else None,'defect_type_s2':b.get('defect_type') if b else None,
             'test_integrity_s1':a.get('test_integrity') if a else None,'test_quality_s1':a.get('test_quality') if a else None,
             'reason_s1':a.get('reason') if a else None,'reason_s2':b.get('reason') if b else None,
             'evidence_s1':a.get('evidence') if a else None,'evidence_s2':b.get('evidence') if b else None}
        rows.append(row);t=totals[p['bank']];t['tasks']+=1;t['completed_judgments']+=sum(x is not None for x in labels)
        t['complete_pairs']+=bool(a and b)
        t['tasks_with_any_valid']+=any(x is not None for x in labels)
        if row['agreement'] is not None:t['agree_verdict']+=row['agreement']
        t['s1_'+row['verdict_s1']]+=1
        if a:t['quality_s1_'+a['test_quality']]+=1
    attempts=[json.loads(f.read_text(encoding='utf-8')) for f in (OUT/'attempts').rglob('*.json')]
    dispatched=[a for a in attempts if a['status']=='dispatched']
    http_errors=collections.Counter(a.get('http_status') for a in attempts if a['status']=='http_error')
    usage=collections.Counter(); statuses=collections.Counter()
    for a in attempts:
        statuses[a['status']]+=1
        if a.get('usage'):
            for k,v in a['usage'].items():
                if isinstance(v,(int,float)):usage[k]+=v
    summary={'planned_tasks':2372,'planned_judgments':4744,
             'valid_judgments':sum(t['completed_judgments'] for t in totals.values()),
             'complete_pairs':sum(t['complete_pairs'] for t in totals.values()),
             'tasks_with_any_valid':sum(t['tasks_with_any_valid'] for t in totals.values()),
             'by_bank':dict(totals),'attempt_statuses':dict(statuses),
             'http_error_statuses':dict(http_errors),
             'in_flight_at_snapshot':[{'key':a['key'],'sample':a['sample'],'at':a.get('at')} for a in dispatched],
             'usage_all_attempts':dict(usage),'unknown_usage_attempts':sum(a.get('usage_unknown',True) for a in attempts),
             'currency_cost':'未测量：无核验单价及余额','limitations':['单模型双判不是人工一致性','绕过结论为静态审计，动态实测另记','同源基准不独立','无断言题不得强判隐藏契约缺陷']}
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'rows.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    with (OUT/'rows.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    report=ROOT/'docs/research/reports/CLE-ANL-20261118-external-bank-classification-summary.md'
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(render_classification_table(rows),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
