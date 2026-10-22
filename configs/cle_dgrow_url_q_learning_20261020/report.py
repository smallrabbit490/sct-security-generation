"""仅消费32题学习与D_gate固定查询回放，生成中文结果报告，不调用模型。"""
from collections import Counter
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'translation_work/diagnostics/20261020/cle_dgrow_url_q_learning_v1'
CURATED = ROOT / 'results/curated/cle_dgrow_url_q_learning_20261020'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def csv_rows(name):
    with (CURATED / name).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    learn = read(CURATED / 'learning_summary.json')
    replay = read(CURATED / 'Dgate_replay_summary.json')
    assert learn['executed'] == 32
    changes = csv_rows('changed_cards.csv')
    credit_events = [e for e in csv_rows('reward_events.csv') if e['invariant_id'] and e['reward'] not in ('', 'None')]
    task_map = {str(t['index']): t for t in read(OUT / 'tasks.json')}
    card_map = {c['invariant_id']: c for c in changes}
    source_counts = Counter((str(task_map[e['task_id']]['CWE_ID']), card_map[e['invariant_id']]['cwe'],
                             '正' if float(e['reward']) > 0 else '负') for e in credit_events)
    queries = [r for r in csv_rows('Dgate_fixed_queries.csv') if r['attempt'] == '0']
    exposure = []
    for change in changes:
        identifier = change['invariant_id']
        exposure.append({**change,
            'feedback_task_count': len({e['task_id'] for e in credit_events if e['invariant_id'] == identifier}),
            'feedback_family_count': len({e['family_id'] for e in credit_events if e['invariant_id'] == identifier}),
            'Dgate_first_candidate_queries': sum(identifier in r['new_full_order'].split('|') for r in queries),
            'Dgate_first_historical_selected': sum(identifier in r['historical_selected_ids'].split('|') for r in queries),
            'Dgate_first_historical_adopted': sum(identifier in r['historical_adopted_ids'].split('|') for r in queries)})
    with (CURATED / 'changed_cards_Dgate_exposure.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(exposure[0]))
        writer.writeheader(); writer.writerows(exposure)
    f = learn['final']; q = replay['first_queries']; allq = replay['all_historical_attempt_queries']
    usage = learn['total_llm_usage']
    effects = sorted(exposure, key=lambda r: (-r['Dgate_first_candidate_queries'], r['invariant_id']))
    lines = [
        '# 修订32题补充Q学习与D_gate历史选卡影响分析', '',
        '日期：2026-10-20。协议：`cle-repaired32-observer-cap3-screened-Q-v1`。**32题观察学习及零API历史回放已完成；没有重新运行D_gate选卡、代码生成或验证。**', '',
        '## 1. 做了什么与采用哪个起点', '',
        '32题均属于D_grow，CWE601为8题、CWE918为24题，共28个项目推断题族；与历史D_gate的217个题族交集为0。使用独立修订题集：恢复上游测试，24题补充公开context，1399恢复公开安全政策；原始数据、旧资格表、旧Q库和旧成绩均未覆盖。D_gate已在历史开发中暴露，不因题族不交叉就成为新的独立最终测试。', '',
        '新Q从资格屏蔽派生库开始，不从含已知不合格授信的原M1继续累积。原M1的466张有反馈卡先因资格修正降为416张；这不是本轮学习退步。两个变化分别报告，不将其混成一条提分曲线。', '',
        '原P7：初析、原候选顺序、LLM选择0–3张、复析与采用、规划、生成和原验证；首次Joint早停，否则最多修复一次，交付末次。deepseek-v3.2，thinking disabled，temperature=0，普通输出4096、选择器256；text-embedding-3-large，delta=-1，workers=2。', '',
        'Q只观察，不参与这32题选卡。每次c0/c1仅对完整流程、非空代码和完整测量下实际采用的卡授信，Joint +1、否则 -1，alpha=0.3。按原数字题ID及尝试顺序重放更新；并行完成先后不改变最终Q。未采用或流程不完整的卡不强行赋分。', '',
        '## 2. 32题实际执行与Q覆盖', '',
        '|指标|结果|', '|---|---:|',
        f'|计划/实际任务|32/{learn["executed"]}|',
        f'|代码尝试|{learn["attempts"]}|',
        f'|完整流程尝试|{learn["completed_workflow_attempts"]}|',
        f'|末次完整F/S测量|{f["measured"]}/32|',
        f'|末次功能通过|{f["functional"]}/32|',
        f'|末次安全通过|{f["security"]}/32|',
        f'|末次Joint|{f["joint"]}/32（{f["joint"]/32:.2%}）|',
        f'|首次Joint|{learn["first"]["joint"]}/32|',
        f'|原P7一次修复救回Joint|{learn["repair_joint_rescues"]}题|',
        f'|末次流程完整|{learn["complete_final_workflows"]}/32|',
        f'|末次Joint且流程完整|{learn["complete_final_joint"]}/32|',
        f'|产生有效奖励的题|{learn["tasks_with_valid_credit"]}/32|',
        f'|有效奖励卡次|{learn["valid_card_updates"]}（正{learn["positive_updates"]}、负{learn["negative_updates"]}）|',
        f'|Q或访问发生变化的卡|{learn["changed_cards"]}|',
        f'|其中首次得到反馈|{learn["new_cards_learned"]}|', '',
        '|库状态|有反馈卡数|全库覆盖率|', '|---|---:|---:|',
        '|旧M1，历史原授信|466/1939|24.03%|',
        '|本轮学习起点，资格屏蔽派生库|416/1939|21.45%|',
        f'|本轮32题之后|{learn["visited_after"]}/1939|{learn["coverage_after"]:.2%}|', '',
        '|卡片CWE|卡数|学习前有反馈|学习后有反馈|学习后正Q|学习后负Q|', '|---|---:|---:|---:|---:|---:|']
    for cwe in ('601', '918'):
        c = learn['by_card_CWE'][cwe]
        lines.append(f'|{cwe}|{c["cards"]}|{c["visited_before"]}|{c["visited_after"]}|{c["positive_Q_after"]}|{c["negative_Q_after"]}|')
    lines += ['', '本轮改变的20张卡全部此前未学习，原416张有反馈卡的数值未被本轮奖励改动。32题只有20题产生有效采用奖励，因此补做32题不会自动给252张本类卡或1939张全库卡逐一赋值。', '',
        '以上成绩是观察学习轨迹的成绩，模型当时没有读取新Q。不能将其写成Q参与后提高正确率；也不是与上一轮旧题面、旧反馈、不限量轨迹的干净配对。', '',
        f'流程/缺测问题共{len(learn["issues"])}条尝试，详见learning_summary.json。Joint按原测试口径统计，流程完整性另列；即使F/S通过，只要流程不完整也不授信。32题已逐一尝试不等于每题都产生奖励，更不等于1939张卡全被赋值。', '',
        '## 3. 对历史D_gate的影响：先区分两种变化', '',
        '将历史原M1、学习前资格屏蔽Q、新学32题后Q，分别放入相同历史查询、候选ID、余弦与原融合排序函数。只有评分变化，查询、题面、卡正文和余弦都不改。先复现保存的原Q2呈现顺序，再计算新增学习的增量。', '',
        f'- 首次298题，单纯资格屏蔽改变{replay["qualification_only_first_order_changed"]}题呈现。',
        f'- **在资格屏蔽起点上，新增32题学习改变{q["order_changed"]}/298题呈现，{q["top3_set_changed"]}/298题数值前三集合。**',
        f'- 原M1到最终新Q的累计变化是{replay["M1_to_after32_first_order_changed"]}/298题；不能用该数冒充新增32题的净影响。', '',
        '|新增32题的首次查询影响|题数或次数|', '|---|---:|',
        f'|候选中有Q值被本轮改变的卡|{q["with_changed_Q_candidates"]}/298题|',
        f'|历史实际选入卡中有本轮Q改变|{q["with_historical_selected_changed_Q"]}/298题|',
        f'|历史实际采用卡中有本轮Q改变|{q["with_historical_adopted_changed_Q"]}/298题|',
        f'|候选中有反馈卡出现次数：前→后|{q["candidate_visited_occurrences_before"]}→{q["candidate_visited_occurrences_after"]}|', '',
        f'含历史修复轮的{allq["queries"]}个可回放查询中，{allq["order_changed"]}个呈现改变。修复轮依赖当时旧代码与反馈，只是条件诊断，不是新增独立题，也不是新Q真实轨迹。无法恢复的查询单列{len(replay["skipped"])}条。', '',
        f'首次查询中有{len(replay["historical_first_queries_selector_not_completed"])}条历史选择器未完成但候选与呈现已保存，题号为{replay["historical_first_queries_selector_not_completed"]}。它们仅纳入排序回放，不当成成功选卡或新代码结果。', '',
        '历史选择已经发生，不会被追溯改写。这里的“历史实际采用卡有Q改变”，是旧采用ID和新评分的交叉核对，**不是新Q再次被LLM选入或采纳**。数值前三也不是LLM最后选择的三张。', '',
        '## 4. 哪些D_gate题类和卡片受影响', '',
        '|D_gate题目CWE|首次查询数|新增32题改序|数值前三集合变化|历史采用卡Q受影响的题|',
        '|---|---:|---:|---:|---:|']
    for cwe, item in replay['by_task_CWE_first'].items():
        if item['with_changed_Q_candidates'] or cwe in ('601', '918'):
            lines.append(f'|{cwe}|{item["queries"]}|{item["order_changed"]}|{item["top3_set_changed"]}|{item["with_historical_adopted_changed_Q"]}|')
    lines += ['',
        '|卡ID|CWE|Q前→后|反馈次数前→后|反馈题族数|历史首次候选题数|历史首次选入题数|历史首次采用题数|',
        '|---|---|---|---|---:|---:|---:|---:|']
    for c in effects[:8]:
        lines.append(f'|{c["invariant_id"]}|{c["cwe"]}|{float(c["Q_before"]):.4f}→{float(c["Q_after"]):.4f}|{c["visits_before"]}→{c["visits_after"]}|{c["feedback_family_count"]}|{c["Dgate_first_candidate_queries"]}|{c["Dgate_first_historical_selected"]}|{c["Dgate_first_historical_adopted"]}|')
    examples = sorted([r for r in queries if r['new32_top3_set_changed'] == 'True'], key=lambda r: int(r['task_id']))[:3]
    lines += ['', '按固定数字题ID顺序展示最多三个数值前三变化案例，不按旧Joint挑选：', '',
              '|D_gate题号|题目CWE|学习前数值前三|学习后数值前三|历史采用ID|', '|---|---|---|---|---|']
    for r in sorted(examples, key=lambda x: int(x['task_id'])):
        old_ids, new_ids, adopted = [r[k].replace('|', '；') for k in ('old_numeric_top3','new_numeric_top3','historical_adopted_ids')]
        lines.append(f'|{r["task_id"]}|{r["cwe"]}|{old_ids}|{new_ids}|{adopted}|')
    lines += ['', '该表展示潜在呈现机会改变，不为旧成功或失败重新分配原因。四臂实际选择/采用卡的前后真实反馈覆盖见Dgate_historical_selection_exposure.csv，其中Q3也按卡本身的真实学习史计数，不是原置换分配的visits，也没有重新生成新Q3策略。Q0/Q1本身不读取Q，因此本轮Q赋值不会改变其固定查询的排序规则。', '',
        '正奖励会把相关候选推前，负奖励会把它们推后；融合函数在每个候选集合内重新标准化，所以少量新增评分也可能改变整份列表。改序越多并不等于越好：奖励来自整份代码，可能同时反映题面补齐、模型实现和多张卡的共同影响，而非每张卡的独立贡献。实际效用仍需新策略前向验证。', '',
        '## 5. 本轮学习暴露了什么机制问题', '',
        '首次改序中，目标CWE601/918共35题，其余19题来自CWE179、74、1333。这源于原召回不按CWE硬截断，不是回放错误；19题的历史实际采用卡均没有被本轮改变Q，所以不能说它们已经被新Q影响了代码。', '',
        '一个具体旁路案例是D_gate的103题：公开任务是sanitize_email邮件校验，URL卡blind-918-5000078255013480260在新Q下升入数值首位。该卡适用条件明确针对可信URL域名、HTTP/HTTPS与内网访问，不应仅凭高Q就认定适用邮件题。过去此题未采用卡；本轮没有重新调用选择器，不能说新模型已经误用。它说明后续应检查适用性拒绝环节是否还能拦住这种跨类高Q卡。', '',
        '反馈次数也不是独立题族数：blind-918-5000078255013480260的5次正反馈来自5题族，Q到0.83193；hint-601-6672869002920924250的5次负反馈仅来自3题、2题族，Q到-0.83193。当前EMA不按题族去重，c0/c1及同族变体可反复影响同一卡；这就是为什么Q大小不能直接当跨题型可靠性。', '',
        '题目CWE与采用卡CWE也不总相同，实际有效奖励分布如下；跨CWE使用未必错误，但其通用性需要逐卡适用依据，不能用类别标签代替判断：', '',
        '|反馈题CWE|经验卡CWE|奖励符号|卡次|', '|---|---|---|---:|']
    for (task_cwe, card_cwe, sign), count in sorted(source_counts.items()):
        lines.append(f'|{task_cwe}|{card_cwe}|{sign}|{count}|')
    embedding_tokens = sum(e.get('total_tokens', 0) for e in learn['embedding_segments'])
    embedding_calls = sum(e.get('calls', 0) for e in learn['embedding_segments'])
    lines += ['',
        '## 6. 成本、保留和下一步边界', '',
        f'本轮学习LLM逻辑调用{usage["calls"]}次，输入{usage["prompt_tokens"]}、输出{usage["completion_tokens"]}，合计{usage["total_tokens"]} Token；错误调用{usage["errors"]}，缺usage记录{usage["usage_missing"]}。原生网络层可能重试，逻辑调用不能冒充精确物理HTTP数量。Embedding实际用量另列于summary的embedding_segments。没有账单，实付金额未测量；旧静态价格字段不作为实付。', '',
        f'新增Embedding调用{embedding_calls}次、输入{embedding_tokens} Token，原卡向量复用缓存；两道探针及其费用已包含在32题总数中，不重复相加。', '',
        'D_gate本轮API=0、新代码=0、新验证=0、新Joint=null。既有全D_gate Q0/Q1/Q2/Q3的97/104/102/100分仍是旧M1实验成绩，不能搬到新库。原本“收益未建立”的历史结论没有被排序回放推翻。', '',
        '本轮满足的是“补做32题有效反馈观察，并定位对历史决策的潜在触达”。若还要判断收益，须另立冻结新Q的同题配对小实验，共享初析和候选，对比相似度/新Q/同CWE打乱Q，并核查改选—采用—代码落实—Joint。当前不自动开启该实验、全量D_gate、完整CLE或Base/Plus。', '',
        '## 7. 复现与文件', '',
        '- 原生学习、事件、冻结新Q与元数据：`translation_work/diagnostics/20261020/cle_dgrow_url_q_learning_v1/`。',
        '- 输入、代码入口与参数：`configs/cle_dgrow_url_q_learning_20261020/`。',
        '- 精简逐题成绩、变动卡、D_gate查询和四臂历史曝光：`results/curated/cle_dgrow_url_q_learning_20261020/`。',
        '- 分支、基准提交、原生源码快照及报告用增量版本见run_metadata；旧数据与旧库保持独立保留。', '',
        '重新生成或追加学习不能覆盖本轮；复用run/learn时跳过已落盘任务并从不变起点重建，禁止重复授信。replay与report纯本地、不调用API。']
    target = ROOT / 'docs/CLE_修订32题补充Q学习与Dgate历史影响_20261020.md'
    target.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='')
    print(target)


if __name__ == '__main__':
    main()
