"""以本轮原生结果生成中文终稿和精简归档；不调用API，不改变协议。"""
import ast
from collections import Counter
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.cle_ablation import run_memory_q_equal_k as s
from methods.sct_trajectory.retrieval_hit_study import read_rows


def table(headers,records):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join('---' for _ in headers)+'|']+
        ['| '+' | '.join(str(v) for v in record)+' |' for record in records])


def main():
    s.verify(s.OUT)
    summary=s.read(s.CURATED/'summary.json')
    analysis=s.read(s.CURATED/'analysis.json')
    validation=s.read(s.CURATED/'case_validation.json')
    rows=read_rows(s.OUT/'rows.jsonl')
    assert len(rows)==48 and validation['new_API_calls']==0
    specs=s.read(s.OUT/'reused_inputs.json')
    nodes=s.load_memory(s.OLD/'observe/frozen/m_star_q.jsonl')
    by_id={n.invariant_id:n for n in nodes}
    pair_map={(v['task_id'],v['card_id']):v['pair_id'] for v in s.read(s.OUT/'pair_mapping.json')}
    model={v['pair_id']:v['label'] for v in read_rows(s.OUT/'model_labels.jsonl')}
    score={(v['task_id'],v['arm'],v['repeat']):v for v in rows}
    workflow=[{'task_id':r['task_id'],'arm':r['arm'],'repeat':r['repeat'],
        'attempt':a['attempt'],'error':a['generation']['error_type']}
        for r in rows for a in r['attempts'] if a['generation'].get('error_type')]
    with (s.CURATED/'mechanisms.csv').open(encoding='utf-8-sig') as f:
        mechanisms=list(csv.DictReader(f))
    mechanism_summary={a:{
        'first_members_changed_runs':sum(v['first_members_changed']=='True' for v in mechanisms if v['arm']==a),
        'first_new_members_declared_adopted_runs':sum(bool(ast.literal_eval(v['new_first_adopted_ids'])) for v in mechanisms if v['arm']==a),
        'first_new_members_declared_adopted_tasks':len({v['task_id'] for v in mechanisms if v['arm']==a and ast.literal_eval(v['new_first_adopted_ids'])}),
        'rescues_vs_Q1':sum(v['rescue']=='True' for v in mechanisms if v['arm']==a),
        'losses_vs_Q1':sum(v['loss']=='True' for v in mechanisms if v['arm']==a)} for a in ('Q2','Q3')}
    changed=[]
    first_coverage={}
    for spec in specs:
        old=set(s.choose(spec['first_trace']['scores'],nodes,spec['K'],'Q1')[1])
        new=set(s.choose(spec['first_trace']['scores'],nodes,spec['K'],'Q2')[1])
        for identifier in sorted(new-old):
            n=by_id[identifier]
            changed.append({'task_id':spec['task_id'],'card_id':identifier,'Q':n.q_value,'visits':n.q_visits,
                'AI_label':model[pair_map[spec['task_id'],identifier]],
                'principle':n.positive_principle,'guardrail':n.negative_guardrail})
    for arm in ('Q1','Q2'):
        selected=[i for spec in specs for i in s.choose(spec['first_trace']['scores'],nodes,spec['K'],arm)[1]]
        first_coverage[arm]={'selected':len(selected),'learned':sum(by_id[i].q_visits>0 for i in selected)}
    status={'status':'STOP_INCONCLUSIVE','generation':'COMPLETE_48_OF_48',
        'formal_retrieval_metrics':'WAIT_HUMAN' if not summary['human_confirmed'] else 'AVAILABLE',
        'positive_signal_gate_passed':False,'reason':'Q2 Joint below both controls; no new-card-mediated rescue established',
        'Q_training_added':False,'automatic_confirmation_or_full_test':False,
        'human_confirmed':summary['human_confirmed'],'label_pairs':summary['candidate_pairs']}
    s.write(s.CURATED/'decision.json',status)
    s.write(s.CURATED/'mechanism_summary.json',{'summary':mechanism_summary,
        'first_selection_Q_coverage':first_coverage,'Q2_added_first_cards':changed,'workflow_errors':workflow})
    s.write(s.OUT/'decision.json',status)
    meta=s.read(s.OUT/'run_metadata.json')
    raw=str(s.OUT)
    curated=str(s.CURATED)
    label_counts=Counter(model.values())
    def j(identifier,arm,repeat):return int(score[identifier,arm,repeat]['final']['joint'])
    main_table=table(['组别','F 功能','S 安全','Joint 联合','完整测量','流程异常运行'],[
        [arm,f"{a['functional']}/16",f"{a['security']}/16",f"{a['joint']}/16（{a['joint_rate']:.2%}）",
         f"{a['measured']}/16",a['workflow_error_runs']] for arm,a in analysis['aggregate'].items()])
    repeat_table=table(['重复','Q1 相似度','Q2 学习Q','Q3 打乱Q'],[
        [b,*[str(summary['repeats'][str(b)]['arms'][a]['joint'])+'/8' for a in s.ARMS]] for b in (1,2)])
    task_table=table(['题目','函数','K','Q1 两次Joint','Q2 两次Joint','Q3 两次Joint'],[
        [v['task_id'],score[v['task_id'],'Q1',1]['attempts'][0]['generation']['task'].get('function_name','')
         if 'task' in score[v['task_id'],'Q1',1]['attempts'][0]['generation'] else
         {'1256':'extract_email_domain','1306':'parse_json_request','1317':'convert_to_object','1341':'generate_xml_response',
          '1000':'format_blog_entry','1013':'see_user_profile','1055':'update_item_details','1259':'validate_password'}[v['task_id']],
         v['K'],*[str(j(v['task_id'],a,1))+' / '+str(j(v['task_id'],a,2)) for a in s.ARMS]] for v in specs])
    metrics_table=table(['组别','准确率','精确率','召回率','F1','选入冲突率'],[
        [arm,*[f"{m[k]:.2%}" for k in ('accuracy','precision','recall','f1')],f"{m['counts']['conflicts']}/47（{m['conflict_rate']:.2%}）"]
        for arm,m in summary['label_metrics']['model_estimate'].items()])
    stats_table=table(['主要比较','Joint均值差','95%题族配对区间','双侧精确p','Holm校正p'],[
        ['Q2−'+arm,f"{c['mean_joint_difference']:.2%}",f"[{c['ci95'][0]:.2%}, {c['ci95'][1]:.2%}]",
         c['p_exact_sign_flip'],c['p_holm']] for arm,c in analysis['primary'].items()])
    costs_table=table(['新增项目','模型','逻辑请求','回执Token'],[
        *[[a,'deepseek-v3.2',summary['cost_by_arm'][a]['calls'],f"{summary['cost_by_arm'][a]['total_tokens']:,}"] for a in s.ARMS],
        ['AI初标','gpt-4o',summary['judge_cost']['calls'],f"{summary['judge_cost']['total_tokens']:,}"],
        ['修复轮向量','text-embedding-3-large',summary['cost_by_arm']['embedding']['calls'],
         f"{summary['cost_by_arm']['embedding']['total_tokens']:,}"]])
    adoption_table=table(['组别','尝试数','选入卡次','声明采用卡次','选入超过3张的尝试','采用超过3张的尝试'],[
        [arm,*[v[k] for k in ('attempts','selected','declared_adopted','above_three_selected','above_three_adopted')]]
        for arm,v in analysis['adoption'].items()])
    errors_table=table(['题目','组别','重复','尝试（0首次/1修复）','原生错误'],[
        [v[k] for k in ('task_id','arm','repeat','attempt','error')] for v in workflow])
    text=f'''# CLE Q 等量选卡与接口约束实验：结果、逐题分析与停止报告

执行日期：2026-10-19。协议：`{s.PROTOCOL}`。分支：`{meta['branch']}`；基线提交：`{meta['commit']}`，运行中的实际源码以运行区 `source_snapshot/` 与 `run_metadata.json` 为准，包含本地未提交改动。

## 1. 结论与终态

本轮推荐的小实验已执行完毕：**8道既有D_gate开发题 × 3组 × 2次独立生成，共48/48次原P7运行**。48次均有完整F/S测量。学习Q的Joint为9/16，两个对照均为10/16，未通过“学习Q高于两个对照”的开发信号门。结论为 **STOP_INCONCLUSIVE（当前证据不足，停止追加投入）**；这不等于证明Q在所有条件下都无效。

Q确实改变了7/8题的首次入选成员，且4题出现新增成员的声明采用；但本轮没有建立由新增卡带来的额外通过路径。现有结果不支持启动全量测试、追加学习轮次或自动开启确认集。原始失败不重跑、不删题、不重写历史分数。

AI初标222/222完成，人工确认{summary['human_confirmed']}/222。下文检索指标全部是**首次候选池内的模型辅助估计**；正式人工指标状态为WAIT_HUMAN（等待真人复核）。生成比较已经完成，两项状态分别报告。

## 2. 这次实际做了什么

Q（经验卡的历史效用分数）保持冻结，使用上一轮完整273道D_grow（积累训练反馈的任务池）得到的1939卡库，未新增训练。原库466/1939张有Q反馈，覆盖率24.03%；本轮不会扩大该比例。

三组为Q1纯相似度、Q2原相似度/Q融合、Q3同CWE（漏洞类型）内打乱(Q,visits)后用同公式融合。每题固定K（给模型的卡数），取既有48题名单前8题，K来自旧Q1首次选卡数量，范围3–12，名单未依本轮成绩或标签调整。取消LLM（大语言模型）二次挑卡；排序直接决定成员，入选卡再统一按余弦相似度顺序呈现。因此Q不能只改变列表位置却被后续选卡器绕过。

所有组共用一条公开接口约束：保留题目已有变量、模板、配置与函数签名。它是生成提示，不是自动修复器。首次初析（模型对题目的初步分析）、查询、候选与余弦分数复用旧记录并核验一致；修复轮根据各自代码和原P7允许的反馈重新检索。原始数据与隐藏测试不改，诊断发现的隐藏要求没有传给生成模型或AI盲标。

生成模型`deepseek-v3.2`，thinking disabled，temperature=0，max_tokens=4096；embedding（把文本编码成向量）为`text-embedding-3-large`；δ=-1、λ=0.5；同CWE置换种子20261015。沿用原P7：首次代码Joint通过即停止，否则最多一次修复，交付末次代码。前两题第一重复的6次探针包含在48预算内；未新增额外真实探针。

本轮属于训练侧冻结开发诊断，不是完整CLE四阶段重跑，也不是Base/Plus独立测试。8题均已有开发暴露；两次重复仍只有8个family（题族，同源相似题的分组）统计单位。

## 3. 实际成绩与逐题结果

F（功能通过）：正常输入输出符合测试；S（安全通过）：通过原安全用例；Joint：同一份代码F和S同时通过。

{main_table}

流程异常指原JSON解析、规划或采用字段缺失，仍可能产出可执行代码。5次运行的7个尝试有此类异常，全部保留在上表16次分母内。48次F/S都测完，不存在把缺测当通过的情况。

{repeat_table}

下表1为Joint通过、0为未通过，“1 / 0”表示第一次通过、第二次未通过。

{task_table}

首次Joint、末次Joint和“任一候选曾通过”的数量在本轮均为Q1=10、Q2=9、Q3=10；19次修复未产生新增Joint救回。共67个代码尝试，29次首次通过早停，19次进入一次修复。尝试数不是独立题数。

Q1有2题两次结果不一致，Q2有1题，Q3没有。temperature=0也未产生逐字固定的远程模型输出；本轮直接观察到了重复波动。不能将单次翻转自动归因为Q。

## 4. Q是否真正介入

Q2首次成员相对Q1变化7/8题，两次共14/16次；新增首次成员在4题、7/16次运行中被声明采用。Q3变化也为7/8题，其新增首次成员在2题、4/16次中被声明采用。仅1317的Q1/Q2首次成员相同。原生修复轮成员与首次可以不同，首次机制统计不冒充全部修复采用统计。

Q1首次47个选入卡次中16个有学习反馈；Q2为20/47。可见Q把更多有学习记录的卡带入了上下文，但“有历史分数”仍没有转化为更高的当前任务成绩。

{adoption_table}

这里“选入”指交给经验复析的卡，“声明采用”指模型返回了采用ID；还需检查最终代码是否实现了建议。三组均确实出现超过3张的选入与采用，取消上限已经生效。

相对Q1，Q2跨两次重复救回1次、损失2次。唯一救回是1341第二次，但它首次声明采用的仍是与Q1共有的`cand-77-1719531174312373036`，没有采用该题新增首次成员；这条救回不能建立新增高Q卡的完整作用链。两组在该题两次生成中各通过一次，题族平均差为0。

## 5. 检索四指标：目前只是AI估计

共同评价池为222个“题目—卡片”对（某卡对某题是否适用），仅覆盖首次已召回候选，三组使用同一个分母。原匿名五类标签初标计数：{dict(label_counts)}。direct（直接适用）为正类，其余已裁决类别为负类。本次无insufficient（信息不足待裁决），但AI仍可能误标，尤其对额外前提和负向卡的解释。

{metrics_table}

三组均TP=9、FP=38、FN=14、TN=161。TP是选入且直接适用，FP是选入但不直接适用，FN是候选池中直接适用却未选入，TN是不适用且未选入。准确率=(TP+TN)/222，精确率=TP/47，召回率=TP/23，F1=2TP/(2TP+FP+FN)。任务命中率均3/8，即至少选入一张direct卡的题目比例。

**76.58%的准确率不能解读为选卡很好**：199/222个候选对被初标为负类，大量正确未选入增加了TN。更直观的选卡精确率仅19.15%，Q2没有提高它，AI估计的冲突率还从6/47增加到9/47。只有1256、1055、1259的候选池中存在AI标注的direct正例；另外5题的“池内无直接适用卡”尚需真人确认，不能称全库没有适用经验。

这里召回率39.13%表示**从本次已召回池里选中了多少适用卡**。没有标注候选外卡，因此候选召回阶段Recall及全库Recall均为null/未测量，不能说最初召回率为0或100%。两次生成共享同一次首次检索，不把222个对重复记为444个标签样本。

## 6. 逐题解释：瓶颈落在哪里

### 1256：新增高Q卡真正被采用，但原来就能做对

Q2新增`hint-1333-7952593739990058655`，Q=0.51、visits=2，建议匹配前限制邮件长度。两次均声明采用，代码均出现`len(email) > 254`，Joint也均通过。Q1两次同样通过。因此这是“改选—采纳—代码落实”的实例，却没有新增正确题；重复已有有效建议也不会自然增加得分。AI判它direct仍需核查题面是否保证这一长度边界。

### 1306：六次代码均卡在同一条功能要求

原验证器重放表明三组两次均只在capability第1号用例失败，错误为ValueError；安全2/2通过。该用例要求接受`application/vnd.custom+json`，模型仅接受`application/json`，因而拒绝了测试认为合法的输入。公开题面只写“检查content type、校验JSON”，未明确`+json`范围。这是公开契约未说清与模型实现不匹配的问题，不能仅凭该题判定Q排序没有用。Q2新增卡在第二次被采用，仍未改变该功能行为。

### 1317：公开契约与测试夹具间存在缺口，还混入实现错误

六次均在首个功能用例出现TypeError：夹具省略`format_type`，原参考签名默认`format_type="json"`；公开arguments列出参数却没有说明默认值，生成代码均把它写为必填。第一重复三组还把XML解析成Element对象，而测试期望字典，均发生output_mismatch。公开题面仅说“转回Python对象”，没有明确XML映射。原夹具已有`allowed_formats`，公开context却未给具体变量名。

第二重复Q1修正了XML输出仍因缺默认参数失败；Q2使用未定义的`ALLOWED_FORMATS`，功能XML和安全用例均出现NameError，是额外实现错误。这也说明仅核对参数名称的AST（代码语法树）检查不能发现默认参数缺失；不能把通过参考实现预检等同于公开契约完备。

### 1341：接口提示未能阻止模型把已有模板改成新参数

公开要求函数只接收`user_content`，已有全局`xml_template`。Q1第一次、Q2第二次保留单参数并通过；Q1第二次、Q2第一次、Q3两次均改为双参数，原验证器四个用例全部TypeError。没有一次重定义模板变量，仍有4/6次最终代码违反调用接口。共用提示缓解到什么程度不能由新旧不同协议分数推断；本轮直接说明它不是强制保证。

Q2新增三张有正Q的负向卡，AI全标conflict。其中部分是“不要过度转义”“不要改模板”等来源题经验，可能有适用边界。1341的新增卡未在首次被声明采用；不能把接口错误简单说成它们造成。Q1/Q2两次首次采用同一张共有卡，结果却交换通过，也显示输出波动。

### 1000：有分数差，但没有稳定的Q救回证据

Q2新增`hint-79-895508645598659977`，Q=0.657、visits=3，卡中原修法要求把另一个任务的模板改成函数参数；这是“历史高Q不等于当前可直接使用”的具体警示，不能照搬。该卡没有被声明采用，不能说它直接造成失败。

第一次Q2功能通过、安全失败：代码在HTML转义后额外用正则替换了已转义的结束script标记，改变了测试期望的输出。原安全夹具是精确输出比对，故S失败不等同于已证明存在可执行XSS漏洞。第二次Q2用`.format(title=..., body=...)`匹配题目模板，而实际模板用headline/content，产生ValueError；公开context没有写清占位符名称。两次最终采用的卡ID相同，不能用“采用了卡”替代“正确适配”。

Q3两次通过，但两次都没有声明采用ID；第一次还发生经验复析JSON解析降级。因此通过不能构成打乱Q卡被采用并实现的获益链，也不能证明它完全未受上下文影响。Q1第二次正确转义并替换占位符通过，第一次未完整适配。

### 1013、1055、1259：都通过，存在成绩上限

三题三组两次全部通过，无法提供额外救回空间。1055每次固定K=12，证实能给模型超过3张卡；Q2新增`guard-915-1851254758089417513`却两次都没被声明采用。第二次Q2缺采用ID但直接按`PERMITTED_FIELDS`更新对象仍通过。1259第二次Q2也有复析/采用解析降级，保留通过成绩但不视为完整机制链。

## 7. 配对统计与结论边界

{stats_table}

统计以8个题族为单位，先对每题两次Joint取平均，再计算Q2−对照的差；区间用10000次按题配对重采样，p值用2^8种双侧精确符号翻转，两项比较作Holm（控制同时比较的误报概率）校正。这里是开发诊断，不把16次运行当16个独立任务。未显著只表示证据不足，不能写成等效。

尚未排除公开契约缺口、模型输出波动、流程降级和AI标签误差。已排除“Q只改候选位置却被LLM二次筛回”“三组首次卡数不同”“本轮偷改Q”“三张截断未解除”等执行解释。没有删除1306/1317后再宣称提分；所有8题保留主分母。

## 8. 成本与原生错误

{costs_table}

新生成合计220次LLM逻辑请求、1,134,120 Token；初标222次、311,705 Token；合计442次LLM请求、1,445,825 Token。另有19次新增embedding、25,894 Token。回执无usage缺失或API计数错误；解析/规划错误另见下表。未查询当前账单，实付金额未测量；不能将Token相加换成未经核实的费用。

首次初析/首次候选向量复用既有记录，没有计成新增调用；19次修复轮embedding为本轮新增。重复运行入口跳过已保存身份，未用重跑覆盖失败。24次重点代码原验证器重放为零API诊断，不增加生成样本。

{errors_table}

## 9. 验证、归档与下一步

本轮及相关实现的89项离线测试通过；6次预算内探针完成工程核验，随后完成固定48。终稿复算核验：共同首次查询/候选/余弦一致，K固定且无LLM二次选卡，呈现顺序统一，冻结Q未变，同CWE打乱正确，Q事件为空，P7尝试和末次交付规则一致。24份重点代码原生验证重放全部与保存成绩吻合。已明确名称的模板/配置未发现重定义，但4份最终代码多了必填参数，仍属模型输出错误。

原生运行：[rows.jsonl]({raw}/rows.jsonl)，其中保留attempts（各次尝试）、generation（模型产物）、validation（验证）与retrieval_trace（检索轨迹）。关键结果：[逐题对照]({curated}/task_pairs.csv)、[67次尝试]({curated}/attempts.csv)、[采用机制]({curated}/mechanisms.csv)、[原验证器案例重放]({curated}/case_validation.json)、[执行核验]({curated}/verification.json)、[停止决定]({curated}/decision.json)。历史690条实验保持原样，不与本轮拼成提升曲线。

当前合理动作是复核222个AI标签，并整理公开契约缺口；尚无投入全量或新增Q学习的正向依据。若重新实验，应先单独锁定完整公开接口（包括默认参数、允许content type、XML返回形态及模板占位符），重新预检后另起协议，不能拿本轮失败后补写的约定重算本轮成绩。Q高分来源题的适用边界是另一个待检验瓶颈；不在本轮同时修改奖励、卡片或模型。

人工表：[human_review.csv]({raw}/human_review.csv)。按[人工复核指南]({ROOT}/docs/CLE_Q等量选卡人工复核指南_20261019.md)另存副本，真实填写标签、依据、理由、reviewer和confirmed_at。AI初标原件保留。此处依据`cle-retrieval-q`技能的“人工未完成时只报告模型估计，Agent不代填人名/确认时间或把AI输出转成人工金标准”，未代签或伪造人工完成。

## 10. 复现与结果文件刷新

在仓库根目录使用现有环境执行。已保存的生成记录会被跳过；prepare只用于新输出目录，不覆盖当前原件。

```powershell
python -X utf8 -m methods.cle_ablation.run_memory_q_equal_k prepare
python -X utf8 -m methods.cle_ablation.run_memory_q_equal_k label
python -X utf8 -m methods.cle_ablation.run_memory_q_equal_k run --tasks 2 --repeats 1
python -X utf8 -m methods.cle_ablation.run_memory_q_equal_k run
python -X utf8 configs/cle_memory_q_equal_k_20261019/analyze.py
python -X utf8 configs/cle_memory_q_equal_k_20261019/diagnose_cases.py
python -X utf8 configs/cle_memory_q_equal_k_20261019/finalize.py
```

analyze复算原生指标；diagnose只重放已保存重点代码，不调用模型；finalize生成本终稿。单独运行原生report命令会得到基础表格版报告，应最后运行finalize恢复完整分析。真人复核后使用`import-review --labels <真实填写的CSV>`导入，再按以上三个零API命令刷新；代码生成不因标签变更重跑。
'''
    for p in (s.OUT/'report.md',ROOT/'docs/CLE_Q等量选卡与接口约束实验结果_20261019.md'):
        p.write_text(text,encoding='utf-8')
    (s.CURATED/'README.md').write_text('''# 2026-10-19 等量选卡冻结Q实验

完整报告：../../../docs/CLE_Q等量选卡与接口约束实验结果_20261019.md。
协议：cle-q-equal-k-contract-v1；固定8题、3组、2重复，48/48已完成，统计单位8题族。
Joint：Q1 10/16，Q2 9/16，Q3 10/16；STOP_INCONCLUSIVE；AI初标222/222，人工0/222待复核。

- summary.json：原生分重复成绩、配对统计、成本及标签状态。
- analysis.json：总成绩、重复波动与选入/声明采用计数。
- task_pairs.csv / scores.csv：同题两重复与48条得分。
- attempts.csv：67次尝试、接口诊断与错误。
- mechanisms.csv / mechanism_summary.json：首次成员变化、采用ID、新卡正文与Q、流程异常。
- case_validation.json：24份代码用原验证器零API重放，保留逐组失败位置。
- verification.json / decision.json：执行核验与停止决定。

原生大文件与真人待审表保留在translation_work/diagnostics/20261019/cle_memory_q/equal_k_v1/；未复制历史690条大文件。运行configs/cle_memory_q_equal_k_20261019/analyze.py、diagnose_cases.py、finalize.py可零API刷新归档。
''',encoding='utf-8')
    print(json.dumps({'status':status,'mechanism':mechanism_summary,'report_written':True},ensure_ascii=False))


if __name__=='__main__':
    main()
