"""落实2026-10-25网页6 Pro整批复审：只更新计划和索引，不派发模型请求。"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'translation_work/diagnostics/20261025/cle_v41_migration_S1'
REVIEW = RUN / 'pro_review_20261025'
DOCS = ROOT / 'docs/cle_memory_mechanisms_20261023'
CFG = ROOT / 'configs/cle_v41_migration_20261025'
CURATED = ROOT / 'results/curated/cle_v41_migration_20261025'
STAMP = '2026-10-25'
REPORT = '25_v41迁移复审与任务清单更新.md'
RAW_REPORT = '26_6Pro迁移综合审阅原文.md'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def csv_read(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def csv_write(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


# 原任务ID不改名、不把S1两臂冒充B02五臂；每项只列一个当前动作。
# 顺序为：当前状态、下一动作、对应证据、当前停止/继续门。
TASKS = {
    'A01': ('待原件', '仅登记Notion原件缺失，不重新生成配对', '原A01；Notion原生5817对仍未取得', '原件不可得则不报告Notion复现；不阻塞明确绑定诊断'),
    'A02': ('名单和参考预检完成；1348语义待裁决', '保留96题与版本；单独记录1348未决政策', '原96/96参考预检；S1固定12题原生记录', '含1348的完整先导须先裁决；参考通过不等于契约充分'),
    'A03': ('914对AI标签；人工0，待人工', '等待真实人工导入已导出的复核表', '既有914对盲审表；S1事后诊断不计入人审', '无人审不发布人工金标准四指标；不以AI代签'),
    'A04': ('本轮有限复盘完成归档', '关联新S1逐题诊断，不扩大旧案例扫描', '历史53例及303行索引；新48格/12题诊断', '250道旧同成绩未知保持未知；不为训练门控补标签'),
    'B01': ('视图工程部分完成；暂停批量制作', '保留已审核分区及原卡，等待独立表达问题', '339草稿、少量已审；S1的51采用卡事后核对', '草稿不当已审；分区效果未测，不自动批量改卡'),
    'B02': ('暂停原120次五臂；旧技术故障归档', '先消费B03最小绑定诊断，不恢复五臂', '旧B02无合格配对；新S1不是五臂实验', '需独立表达假设、新模型材料及授权；无依据则本轮不开展'),
    'B03': ('当前优先改为16次机制方案；未执行', '完成规定阶段提示接线后，提交独立付费授权', 'S1中1322/1409；删除空绑定8/8本地Joint；reviewed plan v2', 'C-A与D-B各净增至少2/4；C/D各在两族有保绑定Joint通过，无新S退化；过门不自动扩样'),
    'B04': ('有限回放完成；Notion余项待原件', '冻结已有足迹诊断，不启用复杂门控', 'v3、303对及9+6参照；原件缺失', '须胜无记忆与简单契约规则才考虑部署；当前不扩展'),
    'B05': ('暂停；未执行', '保留24次候选，待绑定实验后独立说明必要性', '原共享起点反事实诊断设计', '不能并入原P7成绩；不与B03并行付费'),
    'C01': ('渲染和来源索引部分完成；冻结材料', '保留合法L0-L4素材并列明15卡L4缺项', '五档入口、546个非空来源代码位置', '无合法来源则不可用；不以目标参考答案补造'),
    'C02a': ('暂停付费；真实粒度结果0', '消费者明确后再审先导必要性', '20/120/480格入口；S1不属于粒度实验', '无冻结消费者、合法材料及独立预算不启动；缺测不写科学失败'),
    'C02b': ('条件保留；未执行', '只在C02a原C1门通过后讨论480格', '原C1与分阶段执行入口', '至少4族稳定差异、两档各2族双向优势、上界差至少10pp；未过不扩展'),
    'C03': ('当前不训练；无真实标签', '保留分类器设计，等待合法真实档位结果', 'C02真实0；模型和训练标签未完成', '无生成前可预测的稳定档位差异则用固定档，不造伪标签'),
    'C04a': ('条件保留；未执行', '合法分类器存在后比较最佳固定档与公开简单规则', '原C2判定规格', '相对两基线均至少5pp、重复方向及去单族稳定；未过停止'),
    'C04b': ('暂停；未执行', 'C04a通过后另行申请24题三策略确认', '原144次规格', '无独立授权不执行；无显著证据不自动增样'),
    'D01': ('当前信用复盘完成', '归档403尝试/902更新和跨族信用证据', '既有Q信用报告；S1不更新Q', '不回写旧Q；无新政策差异不扩大审计'),
    'D02': ('整体消费者对照暂停；工程可用、效果未测', '保留P7_public_contract_v1为独立整体方案', '21d21c0；S0模型参数已修；原192次未跑', '反馈与交付不同须报整体包；B03失败不自动启动D02'),
    'D03a': ('冻结规格保留；新Q比较后置', '先要求稳定带卡增量或明确Q能解决的选择问题', '972旧反馈卡；旧466快照298四臂负结果', '新模型限三张须先验证集合变化超过波动；不新建学习器'),
    'D03b': ('停止当前轮启动；未执行', '本轮归档为未执行，不购买192次新Q确认', '原Q门未过；新S1未启用Q', '无D03a独立依据不开；S1不能证明新模型Q无效'),
    'D04': ('既有记录恢复和回放工程完成；新方案接线待做', '只完成B03规定阶段的零API接线检查', 'P3全298与S1全48回放；新静态预检', '模型、时段、预算、隐藏反馈、阶段边界不合格不派发'),
    'D05': ('本轮复审和清单收尾完成', '交付原文、决策差异、最新任务表与停止边界', '本报告、26原文、review_manifest和精简JSON', '结果与边界完整即收尾；不以提分为验收'),
    'H01': ('暂停；非必经', '保留在线D_grow23/273前缀', '最新在线Joint11/23；余250未执行', '无独立依据与新授权不续跑或加轮次'),
    'H02': ('暂停；非必经', '保留最新972快照；不重跑298题Q四臂', '旧466四臂97/104/102/100；新快照未测', '不把旧快照成绩冒充最新，也不为完整性购买新全量'),
    'H03': ('暂缓三张上限消融', '当前所有候选继续最多三卡', '本轮S1原P7与B03规格', '卡数与绑定/表达变量分开，不同时改'),
    'H04': ('新实验范围外；Base/Plus缺原镜像', '保留环境缺项，不启动其他模型/完整CLE/MASE', '新P3仅PLT完成；原验证镜像和父镜像缺失', '不替换验证器；未执行不记0分；须独立授权和原环境'),
    'H05': ('待人审；未校准', 'A03真实标签齐全后按原检索协议复算', '914对AI标签、人工0；高δ与Q路线分开', '候选池F1加5pp且命中不降冲突不增；不报全库召回'),
}

STAGES = {
    'S0': {'scope': '迁移接线、同P7空卡、预算/记录/回放', 'status': 'completed', 'next': '归档；仅真实改动时做对应检查'},
    'S1': {'scope': '12题两臂两重复热迁移', 'status': 'completed_gain_gate_failed', 'next': '关闭直接24题扩展；保留缺测和成本'},
    'S2': {'scope': '一次只研究一个有证据的消费者改进', 'status': 'binding_plan_reviewed_not_executable', 'next': 'B03的16格公开绑定提示诊断；接线与授权待完成'},
    'S3': {'scope': '原编号：粒度/分类器与Q后置研究', 'status': 'paused_conditional', 'next': '原C1/C2及新模型Q机制门未满足，不启动'},
    'S4': {'scope': '原编号：24族迁移验证，之后才讨论扩大', 'status': 'not_triggered', 'next': '本轮S1门未过；未来新方案须另定门与授权；Base/Plus另等原环境'},
}


def update_plan():
    plan_path = CFG / 'public_binding_next_plan.json'
    plan = read(plan_path)
    plan.update(protocol='cle-v41-public-binding-diagnostic-plan-v2', status='reviewed_design_execution_not_ready',
                paid_execution_enabled=False, execution_ready=False, reviewer_decision='modified_GO_design_only',
                review_source=f'docs/cle_memory_mechanisms_20261023/{RAW_REPORT}',
                original_plan='pro_review_20261025/03_current_reports_and_next_plan.txt contains unchanged v1',
                canonical_task='B03', migration_stage='S2', automatic_expansion=False,
                generalization_claim=False, code_generation_executed=0)
    plan['engineering_gate'] = '16 native records, no unresolved infrastructure, frozen inputs and native validator unchanged, within caps; model degradation retained, not retried to improve score'
    plan['binding_gate'] = 'C-A and D-B each paired Joint net gain >=2/4; C and D each have >=1 binding-preserved Joint pass in both families; no new paired S pass-to-fail regression; rescues require a complete measured mechanism path'
    plan['absolute_3_of_4_required'] = False
    plan['primary_comparisons'] = ['C-A: prompt effect without memory', 'D-B: prompt effect with memory', 'D-C: memory increment under protected bindings']
    plan['missing_measurement_rule'] = 'Keep all 16 planned cells in end-to-end denominator; separately report jointly measured pairs and code truncation. Missing controls cannot be counted as measured F/S rescues; an incomplete measurement chain cannot establish the mechanism gate.'
    plan['consumer_separation'] = {'runner': 'native run_one(P7)', 'public_repair_policy_enabled': False,
        'public_suite_feedback_enabled': False, 'new_static_checker_affects_generation_or_delivery': False,
        'checker_use': 'offline preparation and posthoc diagnosis only; no code auto-edit',
        'c0_c1_delivery': 'original first Joint early stop, otherwise final attempt; do not activate contract consumer'}
    plan['constraint_scope'] = 'Append only to experience reanalysis, planning and generation, on c0 and c1. Shared original c0 initial analysis, c1 initial analysis and original retrieval input remain without the new constraint payload.'
    plan['implementation_status'] = 'not_ready: generic implementation_constraints enters the entire task contract, including repair initial analysis; strict stage-scoped hook and frozen first-selection sharing are not yet implemented for this new protocol'
    plan['sharing_rule'] = 'New v4.1 first analysis per task/repeat; B/D share exact first selected card IDs and order; A/C empty. Repairs follow own original P7 code/feedback/retrieval. No old S1 scores or v3.2 dynamic responses spliced into new paired trials.'
    plan['interpretation'] = {
        'both_prompt_comparisons_pass': 'positive signal on two posthoc known faults only; if D does not improve over C, retain simpler empty+binding candidate; no stable memory benefit claim',
        'only_D_B_improves': 'possible memory-prompt complementarity, not confirmed interaction; no automatic new matrix',
        'only_C_A_improves_or_D_regresses': 'inspect concrete adopted card/source assumptions; expression study requires independent rationale and authorization',
        'both_prompt_comparisons_fail': 'stop this prompt-only version; no extra repeats, Q learning or sample expansion to rescue it',
        'technical_or_measurement_failure': 'inconclusive mechanism result; preserve missingness and paid evidence, no score-driven reruns',
    }
    plan['last_conditions_before_paid'] = ['explicit user authorization for this 16-cell protocol',
        'strict three-stage prompt hook implemented and checked with saved prompts, c0/c1 initial and query unchanged',
        'B/D exact c0 candidate/selection sharing and native c1 repair behavior verified offline',
        'public-name-only payload; native model/validator/schedule/budget frozen; zero unresolved requests']
    write(plan_path, plan)
    return plan


def static_preflight():
    # 仅读取公开字段；不执行模型、参考、fixture或生成代码。
    tasks = read(RUN / 'inputs/tasks.json')
    tasks = list(tasks.values()) if isinstance(tasks, dict) else tasks
    byid = {str(t.get('index', t.get('task_id'))): t for t in tasks}
    evidence = []
    for tid, name in [('1322', 'ALLOWED_DOMAINS'), ('1409', 'VALID_SIGNATURES')]:
        public = byid[tid]['task_description']
        relevant = {k: v for k, v in public.items() if k in ('description', 'context', 'arguments', 'entry_point', 'return', 'raise')}
        named = any(name in str(v) for v in relevant.values())
        assert named
        evidence.append({'task_id': tid, 'name': name, 'named_in_original_public_task': named,
                         'payload': {'binding_name': name, 'instruction': 'Use the runtime-provided binding; do not redefine, clear, replace or populate it.'},
                         'actual_binding_values_in_payload': False})
    findings = {'operation': 'zero_API_source_and_public_payload_preflight', 'API_calls': 0,
        'code_generations': 0, 'public_payload_checks': evidence,
        'source_observation': [
            'runner.run_one accepts implementation_constraints and inserts it into the common contract before generate',
            'context_pipeline.analysis_prompt serializes the full task for initial and experience analysis',
            'runner only reuses initial_analysis on attempt0; repair initial analysis would see the common constraints',
            'therefore generic contract injection does not meet the reviewed strict three-stage-only protocol'],
        'source_files': ['methods/cle_ablation/runner.py:141', 'methods/sct_trajectory/context_pipeline.py:59',
                         'methods/sct_trajectory/context_pipeline.py:150'],
        'stage_specific_hook_implemented': False, 'new_first_selection_sharing_implemented': False,
        'execution_ready': False, 'paid_execution_enabled': False,
        'next': 'Implement and verify a scoped prompt hook only if the user requests implementation; do not invoke current run/resume launchers for the proposed protocol'}
    write(REVIEW / '07_planning_static_preflight.json', findings)
    return findings


def update_tasks():
    path = DOCS / 'tasks.csv'
    rows = csv_read(path)
    assert set(TASKS) == {r['id'] for r in rows}
    for row in rows:
        status, action, evidence, gate = TASKS[row['id']]
        row.update(status=status, next_action=action, current_evidence=evidence, current_gate=gate,
                   current_plan='configs/cle_v41_migration_20261025/public_binding_next_plan.json' if row['id'] == 'B03' else '',
                   updated_at=STAMP)
    csv_write(path, rows)
    return rows


def update_validation():
    status = {
        'V01': 'S0完成；实际请求/metadata与返回模型已核对；非所有未来消费者效果已测',
        'V02': 'S1新P7链路已通过；原失败和未知用量保留',
        'V03': 'S1实际周日派发与共享并发已核对；时段规则沿用',
        'V04': 'P3完整298及S1原15+续33保留；未知用量不归零',
        'V05': 'S1冻结1939卡/972旧反馈；Q不参与且未更新',
        'V06': '原48参考通过；新12题语义缺项已事后分列，不称公开契约完整',
        'V07': 'S1固定12族完成；24族不启用；16次B03是事后诊断两题',
        'V08': '1348语义仍未裁决；不阻塞当前两题绑定方案',
        'V09': 'S1合法向量缓存与48格回放已验证；新查询重新计算',
        'V10': 'S1新模型共享初析与动态链完成；新B03共享接线待实现',
        'V11': 'S1完成：E0同P7空卡，所有轮为空，保留复析',
        'V12': 'S1完成：E1原LLM终选0-3，无Q/新卡；实际采用已记录',
        'V13': '首2题8次技术通过；计入48；v1后续严格门失败另存，v2恢复完成',
        'V14': 'S1执行完成但收益门失败；7/24对8/24，共同可测均7/23；不扩展',
        'V15': 'S1已知2063129 Token；391物理尝试/15未知；无新型号实付单价',
        'V16': '唯一优先B03：16次公开绑定机制方案；设计复审完成、接线待做、付费关闭',
        'V17': '少量分区保留，暂停批量制作；S1后验卡审阅不算表达效果',
        'V18': '原B02五臂未执行；不从S1两臂或绑定诊断继承门通过',
        'V19': 'S0模型参数已修；完整公开消费者未实测；B03不启用其反馈/交付策略',
        'V20': 'L0-L4工程部分完成，15卡L4缺项；真实粒度对照0，后置',
        'V21': 'C1未评估；无真实标签，不训练分类器',
        'V22': '只有旧不限量160次；新模型限三卡未测，后置非当前工作',
        'V23': '既有置换实现可复用；新模型四臂未执行，保持冻结',
        'V24': '关闭；不续旧250题、不新增学习、不混模型反馈',
        'V25': '914 AI/人工0；正式候选池四指标待人工，全库召回未测',
        'V26': '24族迁移验证未触发；S1门未过；未来另经方案门和授权',
        'V27': '全Dgate非默认，当前不启动',
        'V28': 'Base/Plus仍缺原镜像和父镜像；新模型未执行',
        'V29': 'P3全298与S1全48零API回放一致；不是第二次模型重复',
        'V30': '本轮报告及复审清单已更新；热迁移收益未建立，不等于Q普遍无效',
    }
    path = CFG / 'validation_checklist.csv'
    rows = csv_read(path)
    assert {r['id'] for r in rows} == set(status)
    for row in rows:
        row['status'] = status[row['id']]
        row['current_review'] = f'docs/cle_memory_mechanisms_20261023/{REPORT}'
        if row['id'] == 'V04':
            row['pass_condition'] = row['pass_condition'].replace('原290题', '原完整298题')
    csv_write(path, rows)


def update_assets():
    path = CFG / 'assets.csv'
    rows = csv_read(path)
    updates = {
        'A04': {'evidence_status': 'S1冻结消费完成48格；Q未参与；热迁移收益门未过', 'priority': '冻结归档'},
        'A06': {'evidence_status': 'S1新模型实际召回/LLM终选完成；48格回放一致', 'priority': '工程复用'},
        'A13': {'evidence_status': '历史53例有限复核及新12题48格诊断完成', 'migration': '优先公开绑定机制；人工副本成绩不加回模型成绩', 'priority': 'B03依据'},
        'A16': {'priority': '暂停；需独立表达依据'},
        'A18': {'migration': 'S0模型参数已修；保留整体消费者包，真实效果未测，不混入B03', 'priority': 'D02暂停'},
        'A21': {'evidence_status': 'P3全298与S1全48回放已完成；各批未知用量分列', 'priority': '已完成工程复用'},
    }
    for row in rows:
        row.update(updates.get(row['id'], {}))
    csv_write(path, rows)


def documents(rows, preflight):
    part1 = (REVIEW / '05_pro_review_part1_raw.md').read_text(encoding='utf-8')
    part2 = (REVIEW / '06_pro_review_part2_raw.md').read_text(encoding='utf-8')
    assert len(part1) > 7000 and len(part2) > 7000 and part1.rstrip().endswith('模型降')
    raw = ('# 网页6 Pro：v4.1迁移综合审阅原文\n\n'
           '接收：2026-10-25；[原会话](https://chatgpt.com/c/6ad626a2-c670-83ea-9191-8e17f218ae59)。'
           '四附件整批提交，首次被失效深度研究应用截断；改为普通6 Pro文本后获得正文。'
           '正文第一篇末尾截断，续篇从该处继续，两篇原文分别保留。模型审阅不等于本地执行或付费授权。\n\n'
           '**本地核对说明：**续篇误把S3改称独立确认、S4改称三集最终评测；执行清单保留原编号'
           '“S3粒度/分类器/Q后置、S4迁移验证与扩大”。采用的门及额外测量规则见25更新报告，不在原文内改写。\n\n'
           '## 第一篇（原样，末尾截断）\n\n' + part1 + '\n\n## 续篇（原样）\n\n' + part2 + '\n')
    (DOCS / RAW_REPORT).write_text(raw, encoding='utf-8')
    lines = ['# v4.1迁移：6 Pro综合复审与当前任务清单', '',
        '更新：2026-10-25。本轮完成材料整批交接、网页6 Pro审阅和本地核对；新增项目模型API调用0次、生成代码0份。付费保持暂停。', '',
        '**结论：换模后的P3及P7工程链可运行；旧1939卡在新模型上的稳定Joint增量未建立。唯一优先候选为B03的16次公开绑定机制诊断，目前仅方案冻结，规定阶段接线尚未实现，未执行。**', '',
        f'- [6 Pro完整原文]({RAW_REPORT})；[原网页会话](https://chatgpt.com/c/6ad626a2-c670-83ea-9191-8e17f218ae59)。',
        '- [当前26项任务表](tasks.csv)；[30项迁移验收清单](../../configs/cle_v41_migration_20261025/validation_checklist.csv)。',
        '- [B03修订协议v2](../../configs/cle_v41_migration_20261025/public_binding_next_plan.json)。原v1方案、旧清单和源码完整保留在本次审阅附件02/03中。', '',
        '## 1. 当前事实与各分母', '',
        '| 已执行 | 结果 | 结论 |', '|---|---|---|',
        '| v4.1 P3全PLT | 298交付，297可测；F111/S232/Joint96，32.21%；1125截断 | 新基准已完成，不能再写290/298；不是新完整CLE训练 |',
        '| v3.2→v4.1 P3 | 52→96/298，+14.77pp | 模型、JSON格式提示、并发/传输存在差异，不作纯模型因果归因 |',
        '| S1同P7空卡E0/1939卡E1 | 12族×2重复×2臂=48；F7/8、S18/20、Joint7/24与8/24 | 执行完成，原收益门失败；共同可测23配对均7/23 |',
        '| S1差异 | 唯一1343-r1，E0截断缺测、E1通过；r2两臂都过 | 有采用落实，但没有共同可测的稳定救回，也无带卡Joint损失 |',
        '| 采用 | 21/24有卡运行声明采用；72张次、51张不同采用卡、113选入张次 | 声明采用、实际代码落实、成绩作用分别判断 |',
        '| S1成本 | 已知2,063,129 Token；391次物理尝试，376有usage、15未知 | E1逻辑模型用量约E0的3.90倍；不填未知实付 |',
        '| P3成本 | 已知3,841,636 Token，30次历史HTTP未知 | 与S1分批列示；不能把未知费用填0 |',
        '| 回放 | P3全298、S1全48零API一致 | 证明保存记录能重放，不是新模型独立重复 |',
        '| 旧Q | 972/1939有visits；最新在线D_grow23/273 | 旧466快照298四臂97/104/102/100不能当最新Q或v4.1成绩 |',
        '| 未执行 | 新模型Q、五臂F/S、L0-L4、分类器、24族迁移验证及Base/Plus | 各自前置门仍有效；Base/Plus缺原镜像 |', '',
        '## 2. 本地对6 Pro建议的采纳与修正', '',
        '| 建议 | 本地决定 | 原因及边界 |', '|---|---|---|',
        '| 当前优先验证公开绑定 | 采纳 | 1322/1409两臂共8份失败代码，只删除空绑定定义便8/8 Joint通过；比继续刷Q更接近故障位置 |',
        '| 四臂16次改为相对门，不强求每臂3/4 | 采纳 | 比较C−A与D−B各净≥2/4；C/D各在两族有保绑定Joint通过且无新增配对S退化；只得已知两题上的信号 |',
        '| 复用完整契约消费者替代本次提示 | 不替代；保留D02 | 完整包改变公开反馈与交付选择，本次只变指定阶段的提示；检查器仅作离线/事后分析 |',
        '| 工程完成与效果成立分开 | 采纳并补缺测规则 | 16格原生记录可证明执行；缺测不冒充已测救回；没有完整可测作用链不能通过机制门 |',
        '| 续篇S3/S4重新命名 | 不采纳编号变化 | 保留原S3粒度/分类器/Q后置，S4为24族迁移验证及后续扩大，不重写阶段含义 |',
        '| 当前旧Q“停止” | 只停止本轮启动，保留成果 | S1未启用Q，不能据此证明Q普遍无效；将来需独立决策依据和授权 |',
        '| F/S与粒度后置 | 采纳当前优先级，不设永久禁令 | 其独立问题仍可研究，但不能把绑定结果直接算作分栏或分类器贡献 |', '',
        '主要瓶颈已分开：1322/1409/1341/1000是明确绑定或接口被覆盖；1266有注册表公开信息不足；335题面str与夹具bytes冲突；1306合法媒体类型边界不清；1317同时有默认/返回语义不足与错误XML API。不能都叫经验过度防御。', '',
        '1409空表返回0、1266空患者表先抛异常、335先拒绝bytes均可能恰好满足攻击用例；保留官方S，但不把它们当成预期防护逻辑已经可达。人工副本42次和参考8次诊断的恢复分不加回模型成绩。', '',
        '## 3. 原任务ID逐项对应', '',
        '原列保留历史任务、原始规模和验收；tasks.csv新增current_gate/current_plan/next_action/current_evidence解释当前版本，避免把旧48次和新16次相加运行。', '',
        '| ID | 当前状态 | 唯一下一动作 | 当前门与停止条件 |', '|---|---|---|---|']
    for row in rows:
        lines.append(f"| {row['id']} | {row['status']} | {row['next_action']} | {row['current_gate']} |")
    lines += ['', '## 4. 迁移阶段保持原编号', '', '| 阶段 | 原含义 | 当前状态/下一步 |', '|---|---|---|']
    for sid, stage in STAGES.items():
        lines.append(f"| {sid} | {stage['scope']} | {stage['status']}；{stage['next']} |")
    lines += ['', '## 5. B03/S2唯一候选：公开绑定提示，16格', '',
        '| 臂 | 卡片 | 新约束 |', '|---|---|---|', '| A | 空 | 无 |', '| B | 原1939，LLM至多3卡 | 无 |',
        '| C | 空 | 仅公开绑定保护 |', '| D | 同B的首次选卡，修复按本臂 | 同C保护 |', '',
        '1322与1409，各两次重复，共16次P7，最多32份代码。前8格为技术观察且包含在16内；题目按已经发现的失败事后选取，不是独立验证集。', '',
        '每题每重复新建共享v4.1首次初析；B/D首次查询、候选和终选卡号/顺序相同。A/C全程空卡。修复使用各臂真实代码与原P7反馈；原最多一次修复、首次Joint早停、否则交付末次不变。', '',
        '只向复析、规划、生成三阶段追加“使用公开已有的ALLOWED_DOMAINS或VALID_SIGNATURES，不重定义/清空/替换/填入新值，保持接口返回异常”。c0/c1初析与原检索输入不追加新约束；不传真实域名、签名、fixture、参考或预期输出。不启用public_repair_policy、公开suite反馈或新交付选择，不修改卡片。', '',
        '保留deepseek-v4.1-flash-1017、thinking disabled、temperature0、4096、单user、最多三卡及原验证器。沿用北京时间工作日09–12/14–18禁发，周末允许。硬上限200万模型Token、300总物理HTTP、60次Embedding HTTP；未知与在途按保守预留计入。预算为方案上限，不是授权或新账单。', '',
        '**门分两层：**工程门要求完整16格原生记录、无未决基础设施、冻结输入/原验证不变、预算合规。机制门要求C−A和D−B分别配对净增至少2/4；C、D每臂在两个题族均至少有一次正确保绑定且Joint通过，无新增配对S通过→失败。救回需完整可测作用链；缺测单列，不把未测对照计为已经测到的F/S救回。', '',
        '| 未来结果 | 可以说什么 | 后续 |', '|---|---|---|',
        '| C、D均改善 | 两道已知故障的公开绑定提示有机制信号 | D不优于C时优先简单空卡+绑定；另定泛化验证，不自动扩样 |',
        '| 只有D改善 | 可能存在经验/约束互补 | 只是两题假设，不作已证交互效应 |',
        '| C改善而D退化 | 具体记忆干扰值得定位 | 看采用卡与代码，不自动开五臂/分类器 |',
        '| 两者均未改善 | 当前提示版本未达门 | 停止本版，不追加轮数、换题或刷Q救结论 |',
        '| 技术失败/测量链缺失 | 机制结论不确定 | 留存失败、未知费用；不按成绩重跑 |', '',
        '## 6. 零API接线核对与真正剩余条件', '',
        '本轮已确认两个绑定名称存在于原公开题面，协议payload只含名称与保持指令，未填充实际数据值。静态核对还发现：现有run_one的implementation_constraints会写入共用task，analysis_prompt会整段序列化；修复轮不复用c0初析，因此直接使用该接点会把新约束带入c1初析。这不符合本次规定的三阶段范围。', '',
        '**当前execution_ready=false。** 尚需实现并零API验证专用阶段追加接点与B/D首次选卡共享，核对保存提示、c0/c1初析与查询均未额外注入。没有把“通用参数存在”写成新协议已经可运行。当前没有新launch入口、没有付费请求，也不借旧S1的run/resume启动器执行新方案。', '',
        '进入付费前最后条件为：该接线通过、16格名单/材料/预算与原验证冻结、未决请求处理完毕，以及用户明确授权此新16格协议。只有授权缺失时也仍不派发。本轮按用户要求完成的是综合复审及清单更新。', '',
        '## 7. 研究问题与结论边界', '',
        '- B：同源事实的功能/安全分栏是否改善适配；绑定保护属于生成约束，不能算分栏贡献。',
        '- D02：公开契约检查、合法反馈、保守交付整体包是否改善Joint；与提示单因素分开。',
        '- C：同一经验的表达档位是否存在可预测差异；没有真实L0-L4结果就没有分类器训练标签。',
        '- Q：在有效消费者及可归因的卡选择问题下，学习效用是否优于相似度与打乱Q；改变选卡不是Joint收益。',
        '- 当前可以交付可重复瓶颈和未建立收益的探索结果，不必为保留Q或保证三集提分扩大实验。', '',
        '本轮不修改用户手改Word、数据、参考、夹具、原卡、Q、S1/P3原生行或费用；没有提交/推送。原始审阅附件、失败现场、分段原文、静态核对和review_manifest位于S1运行根pro_review_20261025。']
    (DOCS / REPORT).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    overview = ['# 当前执行清单与阶段决策门', '', '更新：2026-10-25。此页为当前入口，历史执行报告保留原样。', '',
        '**现在：P3全298及S1全48已完成；S1收益门未过。原卡热迁移未建立稳定Joint收益。付费暂停；不恢复Q、粒度、分类器或Base/Plus。**', '',
        f'[完整复审与逐项任务表]({REPORT}) · [6 Pro原文]({RAW_REPORT}) · [tasks.csv](tasks.csv)', '',
        '## 最新结果', '',
        '- 新P3：Joint96/298，297可测；旧P3为52/298，存在格式/并发差异，不能全归因模型。',
        '- S1：同P7空卡7/24、带1939卡8/24；共同可测23对均7/23，唯一变化为对照端截断缺测。',
        '- S1已知2,063,129 Token，391物理尝试，15未知；带卡逻辑模型用量约空卡3.90倍。',
        '- 新逐题诊断区分公开绑定、类型/默认/返回契约、错误XML API、来源假设；人工副本分不计模型成绩。', '',
        '## 唯一下一候选', '',
        'B03/S2：1322和1409，空/带卡×无/有公开绑定保护×两重复，共16次。原48次绑定方案当前不另开。',
        '6 Pro修改后GO仅指设计：配对C−A、D−B各净≥2/4；C/D各在两族有保绑定Joint通过，无新增配对S退化；不强求绝对3/4。它是事后已知故障诊断，过门也不自动进入24题确认。',
        '协议paid_execution_enabled=false、execution_ready=false：现有通用约束参数会进入修复初析，三阶段专用接线与首次共享选卡尚需实现/验证。之后仍需该16格的明确执行授权。', '',
        '## 原任务如何处置', '',
        '| 包 | 当前决策 |', '|---|---|',
        '| A01/A03/H05 | 原件/人审待补；不当作绑定诊断的整体阻塞 |',
        '| A02/A04/D01 | 有限材料/复盘完成；1348单列，不无限追加旧案例 |',
        '| B03/D04 | 新16格设计完成；规定阶段接线待做，付费未开 |',
        '| B01/B02/B04/B05 | 保留部分成果；五臂/足迹门控/补丁生成暂停，不并行扩张 |',
        '| C01-C04b | 素材和工程部分完成；真实档位结果0，分类器不训练 |',
        '| D02/D03a/D03b | 完整消费者待单独比较；Q新比较/学习本轮不启动 |',
        '| H01-H04 | 旧在线250题、最新Q全D_gate、数量消融及范围外任务不恢复 |',
        '| D05 | 本轮复审、原文、清单和边界交付完成 |', '',
        '## 阶段编号保持原义', '',
        'S0接线已完成；S1热迁移已完成但收益门失败；S2只有B03单一机制候选；S3仍指粒度/分类器与Q后置；S4仍指24族迁移验证及后续扩大。Base/Plus必须等原镜像与独立授权。', '',
        '模型正常降级/截断保留原成绩，不为刷分补跑；未决HTTP、验证器故障、错模型、冻结输入变化或预算耗尽停止。所有旧失败、未知用量、手改Word和原卡/Q保留。']
    (DOCS / '07_当前执行清单与决策门.md').write_text('\n'.join(overview) + '\n', encoding='utf-8')


def navigation():
    readme = DOCS / 'README.md'
    text = readme.read_text(encoding='utf-8-sig')
    banner = f'**当前入口（2026-10-25）**：[v4.1迁移复审与清单更新]({REPORT})、[6 Pro完整原文]({RAW_REPORT})、[当前执行清单](07_当前执行清单与决策门.md)。P3全298、S1全48完成；热迁移收益门未过。新16格绑定方案未执行且接线未就绪；旧v3.2服务阻塞属于下文历史快照。付费保持暂停。\n\n下文保留原任务包背景与历次事实，当前状态以上述入口和tasks.csv为准。\n\n'
    if '**当前入口（2026-10-25）**' not in text:
        first, rest = text.split('\n', 1)
        readme.write_text(first + '\n\n' + banner + rest.lstrip('\n'), encoding='utf-8')
    master = ROOT / 'docs/CLE_v32成果汇总与v41Flash1017迁移验证方案_20261025.md'
    text = master.read_text(encoding='utf-8-sig')
    if '## 当前状态：6 Pro整批复审后' not in text:
        first, rest = text.split('\n', 1)
        top = f'''\n\n## 当前状态：6 Pro整批复审后\n\n2026-10-25更新。[完整决策](cle_memory_mechanisms_20261023/{REPORT})、[审阅原文](cle_memory_mechanisms_20261023/{RAW_REPORT})和[最新25项任务表](cle_memory_mechanisms_20261023/tasks.csv)为当前执行入口；下文保留原设计规格，不是尚待全部运行的矩阵。\n\n- S0接线及S1的48次P7已完成；空卡7/24、带卡8/24，共同可测均7/23；原收益门未过，24族扩展未触发。\n- 唯一优先候选为B03/S2两题四臂两重复16次公开绑定提示诊断。复审后改为配对相对门，取消绝对3/4门；不启用完整契约消费者的反馈和交付规则。\n- 方案已更新但三阶段限定接线尚未实现，execution_ready=false、paid_execution_enabled=false；本轮没有新增项目API。\n- S3仍为粒度/分类器/Q后置，S4仍为迁移验证及扩大；保留原编号，不采用审阅续篇的新命名。原192次整体消费者、120次五臂、480格粒度及Q四臂均不自动执行。\n\n'''
        text = first + top + rest.lstrip('\n')
    text = text.replace('日期：2026-10-25。执行对象：旧版CLE。性质：成果接收、迁移设计和验收清单；**本轮新增模型调用0次，不恢复付费实验**。',
                        '原设计日期：2026-10-25；已按顶部当前状态更新。执行对象：旧版CLE。性质：成果接收、迁移设计与验收清单；原设计时模型调用为0，后续S1真实48次另有原生报告；本次复审新增项目API仍为0。')
    text = text.replace('默认下一工作单元为S0接线与S1的2题技术部分；技术题计入12题，不额外加题。',
                        '原S0/S1已完成；当前下一工作单元为B03/S2规定阶段的零API接线，16次候选尚未执行。原技术题已计入12题，不额外加题。')
    text = text.replace('原1939库消费优先试跑 |', 'S1消费已48格完成，收益门未过 |')
    text = text.replace('**必须先修订的真实接点**：', '**原S0设计接点（当前模型参数及同P7空卡等已完成，参见顶部，不重复执行）**：')
    text = text.replace('`methods/cle_ablation/run_joint_contract.py`目前metadata和实际`_requester`均硬编码`deepseek-v3.2`，没有`--model`。先显式参数化并核对真实请求，不提供当前不存在的“加一个--model就能跑”的命令。',
                        '`methods/cle_ablation/run_joint_contract.py`原先硬编码v3.2；S0已增加实际`--model`并保持metadata一致，历史默认保留。完整契约消费者的v4.1付费效果仍未测，不把参数修好算方法收益。')
    text = text.replace('最新25项任务表', '最新26项任务表')
    master.write_text(text, encoding='utf-8')
    cfg_readme = CFG / 'README.md'
    text = cfg_readme.read_text(encoding='utf-8')
    note = f'\n## 6 Pro复审后的当前决策\n\n详见`docs/cle_memory_mechanisms_20261023/{REPORT}`及原文。`public_binding_next_plan.json`已修订为v2，原v1保存在审阅附件；仍paid=false且execution_ready=false。已有通用implementation_constraints会影响修复初析，不满足新的三阶段限定，不能直接拿旧run/resume执行。B03当前只保留16格方案，不另开旧48格；旧S1已完成，所有launch命令仅为历史入口，不应重跑。S3/S4沿原编号；Q/粒度/分类器/24题与Base/Plus未启动。\n'
    if '## 6 Pro复审后的当前决策' not in text:
        cfg_readme.write_text(text + note, encoding='utf-8')


def main():
    if read(CFG / 'public_binding_next_plan.json').get('status') == 'execution_completed_combined_gate_not_passed':
        raise RuntimeError('historical_review_update_superseded_by_completed_binding_study_do_not_roll_back')
    plan = update_plan()
    preflight = static_preflight()
    tasks = update_tasks()
    update_validation()
    update_assets()
    documents(tasks, preflight)
    navigation()
    manifest = read(REVIEW / 'review_manifest.json')
    manifest.update(status='completed_review_and_local_task_updates', reviewer_model_verified='gpt-6-pro / Pro selected in UI',
        response_parts=['05_pro_review_part1_raw.md', '06_pro_review_part2_raw.md'],
        first_application_failure_preserved='04_first_submission_app_failure.txt',
        new_project_API_calls=0, paid_experiments_resumed=False,
        local_correction='Preserve original S3 granularity/classifier/Q and S4 validation numbering; missing observations do not qualify as measured rescues',
        updated_report=f'docs/cle_memory_mechanisms_20261023/{REPORT}')
    write(REVIEW / 'review_manifest.json', manifest)
    summary = {'review': manifest, 'stages': STAGES, 'current_tasks': tasks,
               'next_protocol': plan, 'planning_preflight': preflight,
               'decision': 'one prompt-only binding diagnostic planned, execution not ready/authorized; keep all other paid studies paused',
               'new_model_experiments': 0}
    write(CURATED / 'pro_review_update.json', summary)
    assert not plan['paid_execution_enabled'] and not preflight['execution_ready']
    assert len(tasks) == 26 and len(csv_read(CFG / 'validation_checklist.csv')) == 30
    assert plan['P7_runs'] == 2 * 4 * 2 == 16
    assert plan['Q_updates'] is False and plan['card_generation'] is False
    print(json.dumps({'task_rows': len(tasks), 'validation_rows': 30, 'paid': False,
                      'execution_ready': False, 'report': str(DOCS / REPORT)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
