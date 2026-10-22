"""将D_init v3原生逐题记录与真实阶段门整理为中文报告，不调用模型。"""
from collections import Counter
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from methods.cle_ablation import run_memory_q_dinit_coverage as study


def main():
    summary = study.report()
    out, curated = study.OUT, study.CURATED
    manifest, protocol = study.read(out / 'manifest.json'), study.read(out / 'protocol.json')
    gates = {name: study.read(out / name) for name in ('smoke_gate.json', 'probe_gate.json', 'gate60.json') if (out / name).exists()}
    findings = study.read(out / 'observed_contract_defects.json') if (out / 'observed_contract_defects.json').exists() else None
    screened = study.read(curated / 'contract_qualification_sensitivity.json') if (curated / 'contract_qualification_sensitivity.json').exists() else None
    closeout = study.read(curated / 'experiment_closeout.json') if (curated / 'experiment_closeout.json').exists() else None
    implementation = study.read(out / 'implementation_review.json') if (out / 'implementation_review.json').exists() else {}
    rows = study.records()
    mechanism = []
    for row in rows:
        for a in row.get('attempts', []):
            g, trace = a.get('generation', {}), study.trace_of(a)
            selected = [c['invariant_id'] for c in g.get('retrieved_cards', [])]
            adopted = [c['invariant_id'] for c in g.get('cards', [])]
            mechanism.append({'arm': row['arm'], 'task_id': row['task_id'], 'family_id': row['family_id'],
                'stage': row['stage'], 'attempt': a['attempt'], 'candidate_count': len(trace.get('candidate_ids', [])),
                'selected_ids': '|'.join(selected), 'adopted_ids': '|'.join(adopted),
                'workflow_completed': g.get('workflow_completed', False),
                **{k: a.get(k) for k in ('measured', 'functional', 'security', 'joint')},
                'generation_error': g.get('error_type'), 'retrieval_errors': '|'.join(trace.get('errors', [])),
                'shared_initial_error': row.get('shared_initial_error')})
    if mechanism:
        with (curated / 'attempt_mechanisms.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(mechanism[0]))
            writer.writeheader()
            writer.writerows(mechanism)
    study.write(curated / 'gates.json', gates)
    stopped = next((name for name, gate in gates.items() if not gate['passed']), None)
    if summary['status'].startswith('preflight_stop'):
        conclusion = '拟执行题的正负对照资格门未过，按协议停止该阶段。未执行的生成不计为模型失败。'
    elif summary['status'].startswith(('technical_stop', 'budget_stop')):
        conclusion = '运行遇到协议/技术或预算停止条件，已保存原件和已知用量，不自动重跑。'
    elif stopped:
        conclusion = f'已执行阶段的预设门未过（{stopped}），停止扩大；保留本轮获得的两种Q授信视图。'
    elif summary['status'] == 'completed_296':
        conclusion = '获胜策略一轮已按预设上限完成，冻结两种Q视图并停止，不追加第二轮或D_gate。'
    else:
        conclusion = '当前阶段已完成；下一阶段只在预设门满足后派发，详见阶段门表。'
    lines = [
        '# D_init Q覆盖学习：双臂执行、逐题机制与阶段门报告', '',
        f'日期：2026-10-20。协议：`{study.PROTOCOL}`。实际状态：`{summary["status"]}`。', '',
        '## 1. 结论与执行边界', '', conclusion, '',
        '本实验研究曝光策略（哪些卡先呈现给模型）能否增加实际采用后的有效反馈。L0为原候选顺序，L1为同候选中未学习卡优先；Q效用数值不参与这批解题。**训练内Joint通过率不等于Q参与选卡后的提分。**', '',
        f'当前已保存{summary["P7_runs"]}次P7，覆盖同一固定12题，共42份实际代码尝试；新增D_gate生成0次、Base/Plus0次。旧实验、原数据与436卡起点均保留。', '',
        '**L0与L1最终Joint均为3/12（25%），通过题相同：831、1350、1008。L0新增3张跨族卡、L1新增4张，均未达6张；L1多1张，未达多3张；新跨族卡实现并Joint的题族为0。按原门停止60/296题，不是因为API故障或预算不足。**原协议库和事后资格屏蔽库均单独保留，本轮未选择获胜策略、未提升任何一库为后续默认Q库；学习前436卡仍为明确基准。', '',
        '## 2. 执行规格与数据', '',
        'D_init候选296题/212个项目推断题族：74题为新修复正负对照合格，222题继承旧资格。拟执行但尚未在同环境完成对照的题先做零API检查，资格失败保留而不换题。生成只读取公开字段，修复后的完整测试对象用于原验证器。', '',
        '固定经验库1939卡，436卡已有有效反馈（22.49%）。卡正文、生命周期不变。L0/L1各自从同一起点授信；全反馈允许同源题族，跨题族增量拒绝同族或未还原的合并来源，只限制本轮新增事件，不追溯认证旧436卡。', '',
        '原P7：共享首次初析，同题首次查询/候选/余弦核对一致；LLM最多选3卡，复析决定实际采用；首次Joint早停，否则至多一次修复，交付末次。修复轮看各组自己的代码和原许可反馈。', '',
        '模型deepseek-v3.2、thinking disabled、temperature=0、普通输出4096、选择器256；text-embedding-3-large、delta=-1、alpha=0.3、并发2。原本地python -I验证器/20秒；进程PATH提供已有Git echo/cat，未mock测试。', '',
        '每个c0/c1仅对实际采用、流程完整、代码非空且F/S有效测量的卡更新：Q←Q+0.3×(r−Q)，Joint为+1，否则−1。选入、被召回或参考答案通过都不会直接赋Q。', '',
        '## 3. 实际生成结果', '',
        '|组|已执行题数|F/S有效测量|末次完整流程|F|S|Joint|不同选入卡|不同采用卡|采用卡次|',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for arm, s in summary['arms'].items():
        n = s['executed']
        lines.append(f'|{arm}|{n}|{s["measured"]}/{n}|{s["final_workflows"]}/{n}|{s["functional"]}/{n}|{s["security"]}/{n}|{s["joint"]}/{n}|{s["selected_unique"]}|{s["adopted_unique"]}|{s["adopted_occurrences"]}|')
    lines += ['', 'Joint（同一份最终代码的功能与安全均通过）按已执行任务报告，未执行阶段不填0%。采用卡次可能含同题c0/c1重复，不代表不同卡或不同题族。模型格式失败、技术失败保留在计划分母。', '',
        '## 4. Q覆盖与训练候选触达', '',
        '|组/授信视图|有反馈卡|覆盖率|新增卡|新增训练参照卡|触及参照题数|有效更新次数|核对实现且Joint的不同题族|',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for arm, s in summary['arms'].items():
        for policy, c in s['credit'].items():
            lines.append(f'|{arm}/{policy}|{c["learned_cards"]}/1939|{c["coverage"]:.2%}|{c["new_cards"]}|{c["new_anchor_cards"]}|{c["anchor_queries_touched"]}|{c["valid_updates"]}|{c["implementation_joint_families"]}|')
    if closeout:
        lines += ['', '新增反馈不等于新增成功经验：L0全反馈新5卡均只获负奖励；L1全反馈新11卡中1卡获正奖励、10卡获负奖励。严格跨族新增的3/4张卡全部只获负奖励，L1唯一新增正反馈卡属于同题族来源，不能拿来凑跨族成功。', '']
    lines += ['', '训练参照固定为228道D_grow的1167张历史候选卡；没有使用D_gate候选或成绩选学习题、曝光策略或扩展轮数。卡级奖励共享整份代码结果，不能解释为单卡因果贡献。', '',
        '## 5. 预设门与停止决定', '']
    if screened:
        lines += ['上述是原协议原始回放。发现契约问题后，另存事后资格屏蔽敏感性分析；不覆盖原分数、不重跑生成、不混用两个Q库。', '',
                  '|屏蔽后组/视图|保留任务|有反馈卡|新增卡|有效更新|', '|---|---:|---:|---:|---:|']
        for arm, data in screened['arms'].items():
            for policy, c in data['credit'].items():
                lines.append(f'|{arm}/{policy}|{data["retained_tasks"]}|{c["learned_cards"]}/1939|{c["new_cards"]}|{c["valid_updates"]}|')
        lines += ['', '屏蔽仅撤销这些题在本轮的新增授信，不重置或重认证继承的436张卡。由于该诊断是事后形成，不拿其子集通过率替代原12题主表。', '']
    for name, gate in gates.items():
        lines += [f'### {name}', '', '```json', json.dumps(gate, ensure_ascii=False, indent=2), '```', '']
    if not (out / 'gate60.json').exists():
        lines += ['60题与296题阶段未执行，不报告其Joint。', '']
    lines += ['原门保持：每组12题完整测量、至少10题完整流程、新增跨族卡≥6、参照内新增≥4、触及参照任务≥8，且至少两个题族存在新卡采用→代码落实→Joint证据。L1还须比L0多≥3张新增跨族卡、F/Joint不下降、分摊Token≤1.25倍。未达条件不扩大，不把工程门当统计显著性。', '',
        '## 6. 逐题机制与实现核对', '',
        f'首次共同候选已形成{len(summary["shared_candidates"])}对核验，查询/候选/余弦一致{sum(c["same_first_candidates"] for c in summary["shared_candidates"])}对。完整attempt、generation、validation、retrieval_trace及代码保留在运行区；精简逐次表见`attempt_mechanisms.csv`。', '',
        '|组|题目|尝试|选入数|采用数|流程完整|F/S/Joint|', '|---|---|---:|---:|---:|---|---|']
    for m in mechanism:
        count = lambda text: len(text.split('|')) if text else 0
        lines.append(f'|{m["arm"]}|{m["task_id"]}|c{m["attempt"]}|{count(m["selected_ids"])}|{count(m["adopted_ids"])}|{m["workflow_completed"]}|{m["functional"]}/{m["security"]}/{m["joint"]}|')
    lines += ['', '代码落实核对由Codex读取实际卡片建议与生成代码后记录在`implementation_review.json`，与模型声称采用分开。没有核对的条目不能用于通过实现门；该核对不冒称人工金标准。', '']
    if closeout:
        lines += [f'固定12题中，L0/L1首次选入成员集合变化{closeout["first_selected_set_changed"]}/12，首次声明采用集合变化{closeout["first_adopted_set_changed"]}/12；Joint救回{closeout["L1_joint_rescues"]}题、损失{closeout["L1_joint_losses"]}题。这是一次双臂观测，未通过重复选择实验排除模型自身波动，不能把所有成员变化都解释为纯顺序因果效应。', '']
    audited = implementation.get('joint_adoption_audit', [])
    if audited:
        lines += [f'已核对全部{len(audited)}份Joint成功尝试的实际采用ID、436卡起点访问标记及来源关系：符合“基线未学习且跨题族”的采用卡为{sum(a["new_cross_candidates"] for a in audited)}张。因此实现门的0有直接记录依据，不是漏填复核。L1题1008虽采用一张新增正反馈卡，但它来自同题族。', '']
    if findings:
        lines += ['### 本轮新增的公开契约问题', '', '以下缺口在固定题单执行期间被实际失败暴露。题面和提示未中途修改，未换题、未重跑；与原81题修复前的资格问题分开。', '']
        for f in findings['findings']:
            lines.append(f'- 题{f["task_id"]}（{f["classification"]}）：公开说明为“{f["public"]}”；参考/夹具为“{f["fixture_reference"]}”。证据：{f["evidence"]}。')
        lines += ['', '参考正对照和漏洞负对照通过只确认参考可执行，不能证明公开题面已经完整。未解决契约阻止扩大；原协议反馈保留为待资格审查结果，不能直接作为可信的新Q库投入后续测试。', '']
    lines += ['### 模型实现错误与Q机制的区别', '',
        '- 1299两组重定义已提供的签名映射为空字典；1303的L1把已有CSRF配置和数据库清空；1003的L1重定义已有模板。这些是实际代码对公开运行绑定的破坏，不能归因于Q值排序。',
        '- 1303两组还猜测嵌套字段和数据库形状，1319未保留未公开的默认参数，1258卡片建议在局部正则上被落实也未满足参考返回形状。即使声明采用，也可能在其他接口处失败。',
        '- 原P7修复反馈仅含许可的F/S状态和错误类别；未把隐藏输入或期望输出补给模型。因此它无法从状态反馈直接知道bytes/str、tags/tags_html等缺口，不能把c1未救回写成Q没有发挥排序作用。',
        '- 本轮未让Q效用数值参与排序，检验的是如何获得更多可信反馈。整份代码失败给采用卡共享−1，仍无法识别单卡是否导致失败；契约不清时更会把题目问题写进卡级分数。', '',
        '最小后续工作应先澄清并修订已暴露的公开类型、默认值、外部调用与模板字段，统一“使用已有运行绑定、不得重定义”的公开实现约束；另开协议后再做小对照。当前不追加学习轮数、不启动D_gate或全量测试。', '']
    for arm, stats in summary['arms'].items():
        for review in stats['credit']['cross_family']['implementation_reviews']:
            lines += [f'- {arm}题{review["task_id"]} c{review["attempt"]}，卡`{review["invariant_id"]}`：{review.get("rationale", "")}；代码行{review.get("code_lines", [])}。']
    cost = summary['cost']['LLM']
    embedding = summary['cost']['embedding']
    lines += ['', '## 7. 调用、Token与成本', '',
        '|项目|逻辑请求|Token|失败|缺usage|', '|---|---:|---:|---:|---:|',
        f'|LLM合计|{cost["calls"]}|{cost["total_tokens"]}|{cost["errors"]}|{cost["usage_missing"]}|',
        f'|其中共享初析|{summary["cost"]["shared_initial"]["calls"]}|{summary["cost"]["shared_initial"]["total_tokens"]}|{summary["cost"]["shared_initial"]["errors"]}|{summary["cost"]["shared_initial"]["usage_missing"]}|']
    for arm, stats in summary['arms'].items():
        c = stats['cost']
        lines.append(f'|{arm}其余P7调用|{c["calls"]}|{c["total_tokens"]}|{c["errors"]}|{c["usage_missing"]}|')
    lines += [f'|Embedding新增请求|{sum(e["calls"] for e in embedding)}|{sum(e["total_tokens"] for e in embedding)}|{sum(e["failures"] for e in embedding)}|{sum(e["usage_missing_calls"] for e in embedding)}|', '',
        '共享初析总账只计一次，12题比较时给每组分摊一半。逐次请求账保存数值usage与状态，不保存凭据或原始prompt。原请求器内部HTTP重试不完全可见，因此逻辑请求不当成精确物理请求数；实付金额未知，不沿用旧单价冒充账单。', '',
        '## 8. 证据边界与下一步', '',
        '若门未过，结论仅限当前起点、曝光策略、预算与题单未达到扩大条件；不证明Q普遍无用。若覆盖增加，仍需未来另获授权的冻结前向对照才能证明Q的生成收益。本轮不启动D_gate或Base/Plus。', '',
        '## 9. 产物与复现', '',
        '- 入口：`methods/cle_ablation/run_memory_q_dinit_coverage.py`，prepare/run --stage smoke/probe/60/296/report/gates。',
        '- 原件：`translation_work/diagnostics/20261020/cle_dinit_q_coverage_v3/`；含冻结配置、来源/源码身份、同题初析、请求用量、原生结果、两种Q事件和独立冻结库。',
        '- 精简统计：`results/curated/cle_dinit_q_coverage_20261020/`；配置与原门：`configs/cle_dinit_q_coverage_design_20261020_v3/`。',
        '- 新入口必要离线验证：29项通过，覆盖实际采用/跨族边界、共同候选、三卡限制、原生参数、门失败阻断付费与请求账。', '',
    ]
    if closeout:
        lines += [f'付费阶段墙钟合计{sum(v["seconds"] for v in closeout["segments"]):.1f}秒（不含入口开发和离线整理）；smoke约180.2秒、补足probe约926.7秒。198次LLM逻辑请求、1,660,321个LLM Token与30次Embedding/33,239 Token均在本阶段预算内。实际执行60题命令的门阻断检查已确认在任何新付费请求前拒绝，未执行60题本身。', '']
    path = ROOT / 'docs/CLE_Dinit双臂Q覆盖学习执行报告_20261020.md'
    path.write_text('\n'.join(lines), encoding='utf-8', newline='')
    print(json.dumps({'report': str(path.relative_to(ROOT)), 'P7': len(rows), 'status': summary['status']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
