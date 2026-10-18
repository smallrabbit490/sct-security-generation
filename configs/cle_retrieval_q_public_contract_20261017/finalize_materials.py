"""基于落盘结果生成阶段报告和复核ZIP；不修改人工字段或发起模型请求。"""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.cle_ablation.retrieval_q_study import read,write
from methods.sct_trajectory.retrieval_hit_study import read_rows

CONFIG=Path(__file__).parent
OUT=ROOT/'translation_work/diagnostics/20261017/cle_retrieval_q/public_contract_v2'
CURATED=ROOT/'results/curated/cle_retrieval_q_public_contract_20261017'
meta=read(OUT/'run_metadata.json');manifest=read(OUT/'manifest.json')
pairs=read_rows(OUT/'pairs.jsonl');labels=read_rows(OUT/'model_labels.jsonl')
with (OUT/'human_review.csv').open(encoding='utf-8-sig',newline='') as stream:human=list(csv.DictReader(stream))
assert len(pairs)==len(labels)==len(human)==len({p['pair_id'] for p in pairs})
assert {p['pair_id'] for p in pairs}=={p['pair_id'] for p in labels}=={p['pair_id'] for p in human}
human_fields=('human_label','task_evidence','card_evidence','reason','reviewer','confirmed_at')
assert all(not row[k] for row in human for k in human_fields),'never ship auto-confirmed human fields'
data_path=ROOT/'data/external/secodeplt/secodeplt/data.json'
unchanged=hashlib.sha256(data_path.read_bytes()).hexdigest()==meta['original_dataset_sha256']
memory_unchanged=hashlib.sha256(Path(meta['memory_path']).read_bytes()).hexdigest()==meta['memory_sha256']
assert unchanged and memory_unchanged
audit=read(CONFIG/'public_contract_audit.json')
records=read_rows(OUT/'retrieval.jsonl');counts=Counter(x.get('label') or 'technical_error' for x in labels)
sources=Counter(x['source'] for x in labels)
cost=read(OUT/'retrieval_cost.json');judge_runs=read(OUT/'judge_cost.json')
judge={k:None if any(x.get(k) is None for x in judge_runs) else sum(x[k] for x in judge_runs)
       for k in ('calls','failed_calls','prompt_tokens','completion_tokens','total_tokens')}
checks={'protocol':meta['protocol'],'original_dataset_unchanged':unchanged,'memory_Q_unchanged':memory_unchanged,
    'original_context_rows_unchanged':[x['task_id'] for x in audit['changes']],
    'qualified':manifest['prepared'],'tasks':len(records),'pairs':len(pairs),'label_records':len(labels),
    'labels_by_source':dict(sources),'labels_by_class':dict(counts),
    'all_human_fields_blank':True,'human_confirmed':0,
    'P7_development_started':(OUT/'development/rows.jsonl').exists(),
    'confirmation_started':(OUT/'confirmation/rows.jsonl').exists(),
    'tests_passed':34,'tests_failed':0,'label_authority':'model_estimate_pending_human_review'}
write(OUT/'execution_checks.json',checks);shutil.copy2(OUT/'execution_checks.json',CURATED/'execution_checks.json')
bundle=OUT/'human_review_bundle.zip'
with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for name in ('人工复核说明.md','human_review.csv','review_task_index.csv','model_labels.jsonl','public_contract_overrides.json'):
        z.write(OUT/name,name)
    for p in sorted((OUT/'review_packets').glob('*.md')):z.write(p,p.relative_to(OUT))
metrics=read(OUT/'retrieval_metrics.json')
lines=['# CLE 公开契约补齐与 AI 初标报告','',
    f'日期：2026-10-17。协议：{meta["protocol"]}。旧协议的停止记录及原始数据均保留。','',
    f'本轮已补齐102、136的外部依赖说明，14道题通过原生参考F/S与有限上下文预检；'
    f'完成三种查询的共同候选池及全部{len(pairs)}对AI初标，并导出人工复核材料。'
    '目前停在等待人工确认阶段，未运行P7开发或预留确认。模型估计不能替代人工金标准。','',
    '## 102 和 136 原来缺什么','',
    '两题的本地记录与E盘完整归档相同。问题在于公开题面缺少运行依赖的名称和接口：'
    '参考代码可以在原夹具中运行，但生成器没有完整的公开上下文。','',
    '| 题目 | 原公开说明 | 原参考与夹具的依赖 | 本轮公开补充 |','|---|---|---|---|',
    '| 102 | 描述解码后校验JSON键名，但未命名外部校验器 | valid_key_pattern与unquote | 声明提供re、unquote及编译后的re.Pattern[str]校验器，按原键名规则使用外部绑定 |',
    '| 136 | 介绍Patient类和报告模板，没有说明如何按ID取患者 | patients映射 | 声明提供按字符串ID映射到既有Patient对象的patients，不自行重建记录 |','',
    '新协议通过public_contract_overrides.json在内存中追加task_description.context。'
    '原始data.json、参数/返回/异常字段、参考代码、测试和经验库均未改写。'
    '公开补充没有包含正则字面值、患者实例、测试输入、期望输出或参考修复实现。'
    '这是一次公开上下文修订，因此新旧协议结果分开报告。','',
    '## 重新预检的结果','',
    '| 校准题 | 原生参考状态 | 未公开依赖名检查 |','|---|---|---|']
for item in manifest['calibration_reference']:
    lines.append(f'| {item["task_id"]} | {item["F"]}/{item["S"]} | {"通过" if item["passed"] else "未通过"} |')
lines += ['',
    '8道开发题为1006、1017、1061、1065、1066、1067、1070、792，参考F/S均通过。'
    '名单和24道预留确认题没有替换。本检查仅覆盖原生参考可运行性和有限的依赖绑定，'
    '不保证整个PLT不存在其他语义或契约缺陷。开发题集中于字段更新、HTML和权限，不能代表全部CWE。','',
    '## 候选池和 AI 初标','',
    f'- 固定卡库1939张；每次查询1933张符合当前检索资格，6张因card_budget_exceeded（卡片正文超现有长度上限）排除。',
    f'- 14道题各生成一次共享初析；每题使用原题、纯初析、原题加初析三种查询。',
    f'- 共同评价池是三查询候选并集加每题16张随机未召回卡，共{len(pairs)}个不重复题卡对。',
    f'- AI新判断{sources["new_blind_model_estimate"]}对；完全一致的旧公开题卡标签复用{sources["reused_exact_public_pair_v3"]}对；技术失败{counts["technical_error"]}对。',
    '- 盲评不显示实验臂、排名、Q值或卡片来源题号；由gpt-4o判断，初析模型仍为deepseek-v3.2。','',
    '| AI标签 | 通俗含义 | 数量 |','|---|---|---|']
for key,text in [('direct','直接适用'),('conditional','需要额外前提或实质改写'),('irrelevant','无关'),('conflict','技术错误或契约冲突'),('insufficient','信息不足'),('technical_error','技术失败而非不适用')]:
    lines.append(f'| {key} | {text} | {counts[key]} |')
lines+=['','## 模型辅助四指标','',
    'TP为正确选入，FP为错误选入，FN为漏选，TN为正确未选。准确率=(TP+TN)/全部评价对；'
    '精确率=TP/(TP+FP)；召回率=TP/(TP+FN)；F1=2TP/(2TP+FP+FN)。'
    '这里只能计算候选池内的模型估计；全库召回率未测量。未标注、信息不足和零分母保留空值及原因。',
    '', '| 阶段 | 设置 | 准确率 | 精确率 | 候选池召回率 | F1 |','|---|---|---|---|---|---|']
for phase,settings in metrics['model'].items():
    for setting,item in settings.items():
        values=['未定义' if item[k] is None else f'{item[k]:.4f}' for k in ('accuracy','precision','recall','f1')]
        lines.append('| '+' | '.join([phase,setting,*values])+' |')
lines+=['',
    'R0沿用原题加初析和原δ门槛；R-query仅用原题，门槛相同。所有方法共享每题评价池。'
    '准确率会受大量TN影响，不能单独说明检索优秀；这些模型估计不用于锁定R*或推进P7。','',
    '校准集的2条insufficient尚待裁决，因此整组四指标留空，并非运行失败。开发集R-query没有任何卡通过原门槛，精确率因分母为0留空。','',
    '开发集的模型估计提示两个不同瓶颈：R0最终选入6张卡，直接适用为0；R-query在初始候选中覆盖54/60张池内直接适用卡，但最终选入0张。'
    '因此原题查询的候选召回较好，并不等于原门槛下能够交付合适卡。上述为待人工确认的诊断线索，不据此提前调门槛或判断Q有效性。','',
    '102题的R0最终空返回；AI在共同池标出7张直接适用卡，原题查询初始候选覆盖其中6张，但原门槛下仍空返回。'
    '136题的共同池没有AI判为direct的卡，R0最终选入3张、其中1张被判conflict。前者提示召回和门槛问题，后者提示覆盖与适用性问题；两题都应作为人工复核重点。','',
    '## 成本和冻结边界','',
    '| 用途 | 逻辑LLM调用 | 输入Token | 输出Token | 合计Token |','|---|---|---|---|---|']
for name,usage in [('共享初析',cost['initial_analysis']),('AI盲评',judge)]:
    lines.append('| '+' | '.join([name,*[str(usage[k]) for k in ('calls','prompt_tokens','completion_tokens','total_tokens')]])+' |')
lines += ['',f'Embedding另{cost["embedding"]["calls"]}次、{cost["embedding"]["total_tokens"]} Token；'
    '货币费用未核账单。复用旧标签未新增调用，逻辑请求数也不等同于包含底层重试的全部HTTP请求数。',
    '', '原始数据和冻结Q库文件在执行前后逐项核对保持不变。人工确认数为0，'
    '未产生selection.json（R*选择），未启动P7开发、预留确认、Q学习、完整CLE或Base/Plus。','',
    '## 人工复核材料怎么使用','',
    f'运行目录：`{OUT}`。','',
    '1. 打开human_review_bundle.zip中的人工复核说明.md。',
    '2. 逐题Markdown提供中文阅读提示、英文公开题目、完整卡片、AI标签、双方依据和理由。',
    '3. 在human_review.csv副本中填写human_label、task_evidence、card_evidence、reason、reviewer、confirmed_at；原始人工字段全部为空。',
    '4. 所有行确认并裁决insufficient后再导入。只有完成人工门，才可用6题校准选择单一改动。',
    '5. 本轮到人工材料交付为止；后续8题P7和最多24题确认仍按各自门槛执行。','',
    '## 验证与文件','',
    '34项针对性测试通过，其中新增覆盖context单字段覆盖、原始数据不被原地修改、原context漂移拒绝、'
    '公开输入不含患者或测试常量，以及102/136真实参考重新预检。没有提交或推送。',
    '', '源证据：public_contract_audit.json、public_contract_overrides.json、manifest.json、'
    'retrieval.jsonl、model_labels.jsonl、retrieval_metrics.json、execution_checks.json及用量文件。'
    '原始大材料留在忽略运行区，精简结果进入独立curated目录。']
text='\n'.join(lines)+'\n'
for p in (OUT/'report_zh.md',ROOT/'docs/CLE检索与Q公开契约补齐及初标报告_20261017.md',CURATED/'README.md'):
    p.write_text(text,encoding='utf-8')
summary=read(OUT/'summary.json');summary.update(checks)
write(OUT/'summary.json',summary);write(CURATED/'summary.json',summary)
print(json.dumps({'pairs':len(pairs),'model_sources':dict(sources),'bundle_bytes':bundle.stat().st_size,
                  'human_confirmed':0,'original_dataset_unchanged':unchanged},ensure_ascii=False))
