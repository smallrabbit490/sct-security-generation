"""读取已完成四臂结果与逐题审阅，生成本次补充对照终稿；零API。"""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.cle_ablation import run_memory_q_gate_q0 as s


def table(headers,records):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join('---' for _ in headers)+'|']+
                     ['| '+' | '.join(str(v) for v in r)+' |' for r in records])


def main():
    s.verify(s.OUT)
    x=s.read(s.CURATED/'summary.json')
    diagnostics=s.read(s.CURATED/'diagnostics.json')
    decision=s.read(s.CURATED/'decision.json')
    assert x['completed'] and x['added_rows']==48
    scores=table(['组别','F 功能','S 安全','Joint 联合','Joint率','完整F/S测量','流程异常运行'],[
        [arm,*[str(x['arms'][arm][k])+'/48' for k in ('functional','security','joint')],
         f"{x['arms'][arm]['joint']/48:.2%}",str(x['arms'][arm]['measured'])+'/48',
         diagnostics['arms'][arm]['workflow_error_runs']] for arm in ('Q0','Q1','Q2','Q3')])
    pairs=table(['比较','救回','损失','Joint净差','95%配对区间','精确p','Holm校正p'],[
        [arm+'−Q0',r['wins'],r['losses'],f"{r['delta_joint']:.2%}",
         f"[{r['ci95_paired_tasks'][0]:.2%}, {r['ci95_paired_tasks'][1]:.2%}]",r['p_exact'],r['p_holm']]
        for arm,r in x['paired'].items()])
    adoption=table(['组别','代码尝试','选入卡次','声明采用卡次','选入超过3张的尝试','采用超过3张的尝试'],[
        [arm,*[v[k] for k in ('attempts','selected','declared_adopted','over_three_selected','over_three_adopted')]]
        for arm,v in x['adoption'].items()])
    oldcost=x['parent_cost']
    costs=table(['项目','执行来源','LLM逻辑调用','LLM Token'],[
        ['Q0','本次新增',x['new_cost']['Q0']['calls'],f"{x['new_cost']['Q0']['total_tokens']:,}"],
        *[[arm,'原D_gate复用',oldcost['llm']['by_arm'][arm]['calls'],f"{oldcost['llm']['by_arm'][arm]['total_tokens']:,}"]
          for arm in ('Q1','Q2','Q3')],
        ['共享首次初析','原48次，只计历史一次',oldcost['llm']['shared_initial']['calls'],
         f"{oldcost['llm']['shared_initial']['total_tokens']:,}"]])
    selected=s.read(s.CURATED/'case_reviews.json') if (s.CURATED/'case_reviews.json').exists() else []
    cases=table(['题目','Q0/Q1/Q2/Q3 Joint','逐题观察'],[
        [r['task_id'],' / '.join(str(int(r['Joint'][a])) for a in ('Q0','Q1','Q2','Q3')),r['interpretation']]
        for r in selected]) if selected else '逐题结果已保存于task_pairs.csv；尚无额外代码审阅结论。'
    result=x['paired']['Q2'];q0=x['arms']['Q0'];q2=x['arms']['Q2']
    direction='高于' if q2['joint']>q0['joint'] else '低于' if q2['joint']<q0['joint'] else '等于'
    statistical=('出现校正后正向统计信号，但追加对照与机制证据边界仍须保留。' if decision['statistical_positive_signal'] else
                 '未建立学习Q优于原CLE的统计证据；不等于证明两者等效或Q普遍无效。')
    meta=s.read(s.OUT/'run_metadata.json')
    source=s.PARENT.as_posix();out=s.OUT.as_posix();curated=s.CURATED.as_posix()
    text=f'''# CLE 不限三张Q：固定48题D_gate补充原CLE对照

执行日期：2026-10-19。协议：`{s.PROTOCOL}`。分支：`{meta['branch']}`；基线提交：`{meta['commit']}`；实际源码见本次run_metadata与快照。

## 1. 结论

**执行完成：新增48/48条Q0，复用原Q1/Q2/Q3共144条，形成同48题、四组192条D_gate记录。** 昨晚273题观察学习和273题冻结回测均未重跑，原690条记录保持原样。今天8题等K实验未混入本表。

原CLE不限三张Q0的Joint（同一份代码功能与安全同时通过）为**{q0['joint']}/48（{q0['joint']/48:.2%}）**。学习Q为{q2['joint']}/48，{direction}Q0；净差{q2['joint']-q0['joint']}题。{statistical}

这是补充开发对照：Q0追加执行，原三组来自此前运行。模型、输入和已记录源码身份一致，仍不能排除不同执行时段或远程模型服务的变化，不将其称为同期随机化试验或独立最终测试。未启动新Q学习、完整CLE或Base/Plus。

## 2. 四组到底比较什么

| 组别 | 候选呈现顺序 | 谁决定入选 | 数量上限 |
|---|---|---|---|
| Q0 原CLE不限三张 | 原向量Top24与词面Top8联集顺序 | 原LLM适用性筛选 | 无三张上限 |
| Q1 相似度顺序 | 对共同候选按相似度重排 | 同LLM筛选 | 无三张上限 |
| Q2 学习Q顺序 | 按相似度与学习Q融合重排 | 同LLM筛选 | 无三张上限 |
| Q3 打乱Q顺序 | 同CWE内打乱Q后融合重排 | 同LLM筛选 | 无三张上限 |

此处Q1不是直接取相似度前K张。Q0也使用原语义召回，因此不是“完全没有相似度”；它不做额外Q重排，也不把Q数值交给选卡模型。Q0传`candidate_order=None`、`max_experiences=None`，允许选0至全部候选，后续复析仍可不采用。

冻结相同1939卡正文、状态与Q（466卡有历史有效反馈，覆盖24.03%），复用父运行固定48题名单与首次初析。deepseek-v3.2、thinking disabled、temperature=0、max_tokens=4096；text-embedding-3-large；并发8，前2题探针并发2且包含在48预算内。

P7从父运行source_snapshot加载，已记录的其他依赖逐一核对一致。保留父公开契约覆盖与原检索白名单，不加入今天的新接口提示、默认值、模板占位符或return/raise修订。首次Joint早停，否则最多一次修复，交付末次代码；修复轮使用各自代码和原许可状态反馈。现存错误不重跑、不换题，旧文件不覆盖。

## 3. 完整生成成绩

{scores}

F为正常功能测试，S为原安全测试，Joint要求两者在同一份交付代码上通过。所有率保留48题计划分母，缺测及流程异常单列。流程异常可能仍生成可测代码，不能将其等同于未执行。

首次、任一尝试、最终Joint分别见diagnostics.json。8题等K研究与本研究的选卡方式、提示和重复规格不同，成绩不拼接成提分曲线。

## 4. 同题配对比较

{pairs}

Q2−Q0是本轮新增主要比较。三项相对Q0比较采用原项目双侧精确McNemar检验，并作Holm校正；区间按48个题族进行10000次配对重采样。救回/损失基于双方完整测量，净差和区间保留计划分母；若存在缺测，以逐题字段解释。原Q2−Q1/Q3的历史比较不因补Q0而重写。

本次Q2救回的题为1055、1361、1029、1067，损失题为1065。新增主要比较的原始p={result['p_exact']}，三项相对Q0比较校正p={result['p_holm']}；Joint净差{result['delta_joint']*100:.2f}个百分点，区间跨0。救回数量和净差不自动说明单张Q卡造成提升。

Q0与Q1比较候选原顺序和显式相似度顺序在LLM筛选后的整体差异；Q0与Q2比较原方法和Q排序方案。即使Joint出现差别，也需核对改选、采用、实现链，不能把所有生成变化归功于Q。

## 5. 不限三张与实际采用

{adoption}

“选入”是交给后续复析的卡，“声明采用”是模型返回的采用ID，均不自动证明最终代码正确实现。Q、卡正文和生命周期保持冻结，本次Q更新事件为空。

## 6. 逐题代码核对

{cases}

以上是Agent依据公开题目、卡片、代码与验证状态进行的事后审阅，不是人工适用性金标准。完整卡ID、代码片段和观察范围保存在case_reviews.json；全部48题四组成绩见task_pairs.csv。无采用ID的通过不能作为卡片被采用的完整收益链；相同采用卡下的不同结果不能自动归因于Q。

本次补充对照仍显示配置与模板落实是主要干扰项：1055和1029的差异包含重定义已有对象；1361首次采用同卡却结果不同；1065和1067甚至存在重定义配置后恰好通过原夹具的情况。保留原Joint分数，同时明确当前测试通过不等于公开契约完全遵守。

## 7. 成本

{costs}

本次新增Q0共{x['new_cost']['Q0']['calls']}次LLM逻辑请求、{x['new_cost']['Q0']['total_tokens']:,} Token；新增embedding为{x['new_cost']['embedding']['calls']}次、{x['new_cost']['embedding']['total_tokens']:,} Token。初析新调用为0，原共享48次初析的费用仅在历史成本中计一次。旧三组数据按路径复用，没有再生成或复制105MB原件。

本次用量缺失计数{x['new_cost']['Q0']['usage_missing']}，请求错误计数{x['new_cost']['Q0']['errors']}；原选择器格式重试若发生已计入回执和逻辑请求。逻辑请求不冒充HTTP重试次数。无当前账单，实际货币费用未测量。运行区metadata保存本次探针与续跑的分段墙钟耗时。

Q0首次Joint为{diagnostics['arms']['Q0']['first_joint']}/48，末次与任一候选Joint为{q0['joint']}/48；31题进入一次修复，新增救回1题。Q0有{diagnostics['arms']['Q0']['workflow_error_runs']}次运行、{diagnostics['arms']['Q0']['error_attempts']}个尝试出现规划、初析或采用协议异常；不是API调用失败或F/S缺测。包括继承的共享初析在1题不符合复用校验，原三臂也有同项记录，按原流程保留。

## 8. 验证与限制

新增3项离线测试通过，覆盖父P7入口加载、Q0无Q/不限三张参数、恢复不重跑已保存失败。零API预检核对父数据与三池、48题族、1939卡库、48份初析和144条原生记录。实际48条补跑完成后核对原P7早停/修复/末次交付、首次共同候选与余弦、冻结库未变及旧输入文件未修改。检索失败无法核对的尝试在verification/diagnostics中单列，不伪造通过。

保留原实验已知公开契约缺口与模型实现问题，避免只给新增Q0更完整的题目。本轮未新增适用性标注或全库召回测量，不能将Joint写成检索四指标；其他实验的AI标签也不直接拼入48题结论。

## 9. 产物与复现

- [新增Q0原生rows]({out}/rows.jsonl)：包含attempts、generation、validation、retrieval_trace与成本。
- [原三组144条，只读]({source}/gate/rows.jsonl)。
- [四组逐题表]({curated}/task_pairs.csv)、[完整得分表]({curated}/scores.csv)、[采用与配对变化]({curated}/paired_mechanisms.csv)。
- [执行核验]({curated}/verification.json)、[错误诊断]({curated}/diagnostics.json)、[决定与范围]({curated}/decision.json)。
- [执行规格]({ROOT.as_posix()}/docs/CLE_不限三张Q_Dgate补充Q0实验规格_20261019.md)。

```powershell
python -X utf8 -m methods.cle_ablation.run_memory_q_gate_q0 prepare
python -X utf8 -m methods.cle_ablation.run_memory_q_gate_q0 run --limit 2 --workers 2
python -X utf8 -m methods.cle_ablation.run_memory_q_gate_q0 run --workers 8
python -X utf8 configs/cle_memory_q_unlimited_gate_q0_20261019/analyze.py
python -X utf8 configs/cle_memory_q_unlimited_gate_q0_20261019/finalize.py
```

prepare只用于新目录，现有目录不覆盖。run跳过已保存身份（包括失败）。analyze与finalize为零API复算；单独运行原生report生成基础版，应最后运行finalize恢复本终稿。
'''
    for path in (s.REPORT,s.OUT/'report.md'):
        path.write_text(text,encoding='utf-8')
    (s.CURATED/'README.md').write_text(f'''# 48题D_gate补充原CLE不限三张Q0

新增48/48，复用原三臂144条，合计192条；Q0/Q1/Q2/Q3 Joint为{q0['joint']}/48、{x['arms']['Q1']['joint']}/48、{q2['joint']}/48、{x['arms']['Q3']['joint']}/48。
本研究各组均为LLM不限三张选卡，区别为候选呈现顺序；不混入8题直接选K研究。
完整报告：../../../docs/CLE_不限三张Q_Dgate补充Q0对照结果_20261019.md。

summary.json保存四组得分、统计和新旧成本；scores.csv为192条得分；task_pairs.csv为48题横向表；attempts.csv为所有代码尝试；paired_mechanisms.csv为相对Q0的改选、采用及得分变化；diagnostics.json保存原生错误；case_reviews.json为Agent逐题审阅；verification.json及decision.json保存核验和范围。

原始大文件只读引用，新Q0保存在translation_work/diagnostics/20261019/cle_memory_q/unlimited_gate_q0_v1/。未重训Q、未重跑273观察/回测、未启动Base/Plus。
''',encoding='utf-8')
    print(json.dumps({'report_written':str(s.REPORT),'Q0_Joint':q0['joint'],'Q2_minus_Q0':q2['joint']-q0['joint'],
        'new_rows':48,'reused_rows':144},ensure_ascii=False))


if __name__=='__main__':
    main()
