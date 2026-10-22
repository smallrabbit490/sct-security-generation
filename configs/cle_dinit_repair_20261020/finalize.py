"""从本轮实际预检生成逐题修订表，并更新尚未执行的D_init学习名单。"""
from collections import Counter
import copy
import csv
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from configs.cle_dinit_repair_20261020.repair_and_preflight import CONFIG, CURATED, OUT, read, write
from methods.cle_ablation.runner import load_memory
from methods.sct_trajectory.semantic_retrieval import card_embedding_text, MAX_CARD_CHARS


def csv_file(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    actual = OUT / 'commands_v2'
    summary = read(actual / 'summary.json')
    qualified = read(actual / 'qualification.combined303.json')['tasks']
    details = read(actual / 'qualification.repaired81.json')
    changes = read(CONFIG / 'repair_manifest.json')['changes']
    by_id = {r['task_id']: r for r in details}
    csv_file(CURATED / 'repair_changes.csv', [
        {'task_id': c['task_id'], 'cwe': c['cwe'], 'family_id': c['family_id'],
         'changed_fields': '|'.join(c['restored_fields']),
         'declared_names': '|'.join(c['declared_bindings']),
         'contract_corrections': '|'.join(c['contract_corrections']),
         'old_reasons': '|'.join(c['old_exclusion_reasons']),
         'eligible_after': by_id[c['task_id']]['reward_eligible'],
         'remaining_reasons': '|'.join(by_id[c['task_id']]['exclusion_reasons'])} for c in changes])

    old_config = ROOT / 'configs/cle_dinit_q_coverage_design_20261020'
    new_config = ROOT / 'configs/cle_dinit_q_coverage_design_20261020_v3'
    new_config.mkdir(exist_ok=True)
    previous = read(old_config / 'manifest.json')
    old_manifest = read(ROOT / 'configs/cle_memory_q_dinit_20261019/manifest.json')
    eligible = {r['task_id'] for r in qualified if r['reward_eligible']}
    families = {r['task_id']: r['family_id'] for r in qualified}
    probe = previous['probe']
    assert set(probe) <= eligible
    learning, seen_families = list(probe), {families[i] for i in probe}
    remainder = [i for i in old_manifest['all_tasks'] if i in eligible and i not in learning]
    duplicates = []
    for identifier in remainder:
        if families[identifier] in seen_families:
            duplicates.append(identifier)
        else:
            learning.append(identifier)
            seen_families.add(families[identifier])
    learning.extend(duplicates)
    assert len(learning) == len(set(learning)) == summary['total_eligible'] == 296
    manifest = {'protocol': 'cle-dinit-coverage-cross-family-design-v3', 'status': 'DESIGNED_NOT_EXECUTED',
                'pool': 'D_init', 'probe': probe, 'technical_probe': probe[:2], 'learning': learning,
                'at60': learning[:60], 'extension_after60': learning[60:],
                'task_families': {i: families[i] for i in learning}, 'tasks': len(learning),
                'excluded': summary['still_excluded'],
                'order_rule': 'retain previous12 probe; old CWE round-robin order, unseen family first, same-family variants last; no generation/Q/outcome selection',
                'qualification': str((actual / 'qualification.combined303.json').relative_to(ROOT)),
                'repaired_tasks': str((CONFIG / 'repaired_tasks.json').relative_to(ROOT)),
                'public_task_descriptions': str((CONFIG / 'public_task_descriptions.json').relative_to(ROOT)),
                'inherited_qualifications_not_rerun': 222, 'newly_requalified': 74}
    write(new_config / 'manifest.json', manifest)
    protocol = copy.deepcopy(read(old_config / 'protocol.json'))
    protocol.update(protocol=manifest['protocol'], scope='design updated after81 source/contract repair; no paid generation or Dinit credits',
                    qualification_source=manifest['qualification'], qualification_evidence='74 fresh positive/negative controls +222 historical qualifications; not303 fresh controls',
                    data_overlay=manifest['repaired_tasks'], public_overlay=manifest['public_task_descriptions'],
                    command_runtime_path=summary['command_runtime_path'],
                    command_runtime='prepend PATH only in learning/validation process; required for native subprocess echo/cat; no mocks or validator changes',
                    scheduled_positive_negative_preflight='before dispatch, validate each not-yet-revalidated scheduled task with original validator in same environment; retain failures and stop block, do not silently replace',
                    coverage_mask='L1 primary-view visits fixed at start of blocks:12 / next48 / next236',
                    current_delivery='81-task restoration and zero-API preflight complete; future coverage runner still not implemented')
    protocol['gates']['after296'] = protocol['gates'].pop('after222')
    final_budget = protocol['budget_cumulative'].pop('winner222_plus_other12')
    final_budget.update(P7=308, code_versions_max=616)
    protocol['budget_cumulative']['winner296_plus_other12'] = final_budget
    protocol['budget_cumulative']['winner296_plus_other12']['note'] = '20M Token/3000 logical requests unchanged; stop on budget even if fewer than296 completed'
    protocol['future_output'] = 'translation_work/diagnostics/<execution_date>/cle_dinit_q_coverage_v3/'
    protocol['report'] = 'docs/CLE_Dinit扩大Q覆盖学习实验方案_20261020_v3.md'
    write(new_config / 'protocol.json', protocol)
    shutil.copy2(old_config / 'training_anchor.json', new_config / 'training_anchor.json')
    baseline = read(old_config / 'baseline_inventory.json')
    baseline.update(Dinit_qualified_tasks=296, Dinit_excluded_tasks=7,
                    Dinit_qualified_families=len({families[i] for i in learning}),
                    qualification_scope='74 new qualified +222 inherited, no new Q learning')
    memory = ROOT / protocol['baseline_memory']
    with memory.open(encoding='utf-8') as stream:
        cards = [json.loads(line) for line in stream if line.strip()]
    origins = read(ROOT / protocol['origins_source'])
    legal_ids = {n.invariant_id for n in load_memory(memory)
                 if n.status in {'active', 'provisional', 'consolidated'}
                 and 'python' in (n.language_leaves or {}) and len(card_embedding_text(n)) <= MAX_CARD_CHARS}
    available = lambda c: c['invariant_id'] in legal_ids
    is_new = lambda c: c.get('q_visits', 0) == 0
    source_ok = lambda c: origins[c['invariant_id']]['source_task_id'] in eligible
    baseline['unvisited_qualified_primary_origin'] = sum(is_new(c) and source_ok(c) for c in cards)
    baseline['legal_unvisited_qualified_primary_origin'] = sum(is_new(c) and source_ok(c) and available(c) for c in cards)
    baseline['unvisited_excluded_primary_origin'] = sum(is_new(c) and not source_ok(c) for c in cards)
    baseline['qualified_primary_origin_cards'] = sum(source_ok(c) for c in cards)
    baseline['newly_requalified_primary_origin_cards'] = sum(origins[c['invariant_id']]['source_task_id'] in {r['task_id'] for r in details if r['reward_eligible']} for c in cards)
    write(new_config / 'baseline_inventory.json', baseline)
    write(CURATED / 'learning_plan_update.json', {'tasks': 296, 'families': baseline['Dinit_qualified_families'],
          'probe_unchanged': probe == previous['probe'], 'first60_distinct_families': len({families[i] for i in learning[:60]}),
          'new_P7_runs': 0, 'Q_updates': 0, 'baseline_visited': 436,
          'max_P7': 308, 'max_code_versions': 616,
          'unvisited_qualified_primary_origin': baseline['unvisited_qualified_primary_origin']})

    # 旧设计与旧资格表均保留；新报告独立成v3，避免历史222题被改写成296题。
    previous_doc = ROOT / 'docs/CLE_Dinit扩大Q覆盖学习实验方案_20261020.md'
    text = previous_doc.read_text(encoding='utf-8')
    original_text = text.split('\n> 后续更新：', 1)[0]
    new_text = original_text.replace('design-v2', 'design-v3').replace('222', '296').replace('162', '236')
    start = '已有预检：D_init共303题，296题合格、涉及161个项目推断family（题族），81题排除。CWE601的23题和CWE918的12题目前都在排除范围；本轮修复的是D_grow的32题，不会自动修复这35道D_init题。'
    new_text = new_text.replace(start,
        f'旧预检为303题中222合格、81排除。本轮逐题恢复81题：74题重新合格，7题仍排除；当前学习候选296题，涉及{baseline["Dinit_qualified_families"]}个项目推断family。CWE601的23题与CWE918的12题全部重新合格。222题沿用旧资格，不宣称303题全部重新执行；81题已做新环境的正负对照。详见[修复报告](CLE_Dinit81题修复与重新预检报告_20261020.md)。')
    new_text = new_text.replace('合格296题的未学习卡|992；其中988张当前可检索',
        f'合格296题的未学习卡|{baseline["unvisited_qualified_primary_origin"]}；其中{baseline["legal_unvisited_qualified_primary_origin"]}张当前可检索')
    new_text = new_text.replace('主来源属于排除81题的未学习卡|511',
        f'主来源属于仍排除7题的未学习卡|{baseline["unvisited_excluded_primary_origin"]}')
    new_text = new_text.replace('- 读取最新436卡库、对应反馈题族支持表、旧D_init来源映射和资格回执；核对原数据、解释器与参考环境是否与回执一致。仅在输入或环境有变化时重做相关预检。',
        '- 读取最新436卡库、来源表及本轮合并资格。先从原始tasks加载，再按任务ID应用81题独立覆盖；生成上下文只用public_task_descriptions，不读隐藏测试。仅使用合格296题。\n- 当前222题为继承资格。各阶段付费派发前，对尚未在同环境完成正负对照的拟执行题做零API参考与漏洞负对照；发生资格问题时停止该块并记录，不静默换题。\n- 验证/学习进程内将`C:/Program Files/Git/usr/bin`加入PATH，使echo/cat真实可执行；保持原python -I验证器，不mock命令、不更改期望输出。')
    new_text = new_text.replace('冻结296题、排除81题', '冻结296题、排除7题')
    new_text = new_text.replace('12/60/296', '12/60/296')
    new_text = new_text.replace('|K*到296题，另一组12题|234|468|约1425万|', '|K*到296题，另一组12题|308|616|约1876万|')
    new_text = new_text.replace('4/24/72/234', '4/24/72/308').replace('最多234次P7', '最多308次P7')
    new_text = new_text.replace('configs/cle_dinit_q_coverage_design_20261020/', 'configs/cle_dinit_q_coverage_design_20261020_v3/')
    new_text = new_text.replace('cle_dinit_q_coverage_v2/', 'cle_dinit_q_coverage_v3/')
    new_text += '\n\n## 9. v3修订边界\n\n74题恢复资格不等于新增74次学习；当前D_init真实P7仍为0，Q仍为436/1939。旧v1预检、v2方案、原始303题和旧Q库均保留。最后一阶段最多补236题，累计308次P7；原2000万Token和3000逻辑请求预算不增加，预算到达时允许提前收口。新学习入口仍待实现，本次只完成题目修复、预检和方案更新。\n'
    (ROOT / protocol['report']).write_text(new_text, encoding='utf-8')
    marker = '\n> 后续更新：81题修复已完成，当前296题候选与7题排除以[v3方案](CLE_Dinit扩大Q覆盖学习实验方案_20261020_v3.md)为准。本文保留修复前222题设计。\n'
    previous_doc.write_text(original_text.rstrip() + '\n' + marker, encoding='utf-8')
    reasons = {
        '76': ('公开密码构成规则与安全用例的拒绝要求不一致', '参考功能4/4通过，安全0/1；该安全输入满足公开构成规则，未用耗时断言检验回溯。先确定额外拒绝条件或时间评价契约。'),
        '82': ('参考日志格式与题面、功能测试格式不一致，负对照也未被安全组区分', '参考功能1/3、安全1/1；漏洞实现功能1/3、安全1/1。需统一日志格式并修复参考后重新确认安全区分能力。'),
        '105': ('保留词的完全匹配与包含关系没有统一', '参考功能2/2、安全7/8；参考只对完整保留词拒绝，测试还要求拒绝包含保留词的组合。需确认边界，不能凭测试反推隐藏词表加入题面。'),
        '109': ('HTML属性清理参考未覆盖测试要求', '参考功能1/2、安全2/6；单引号属性和事件属性值未完整移除。涉及参考算法修订，不属于恢复原始文件。'),
        '451': ('公开要求不可访问资源抛IOError，参考却捕获并返回False', '已有测试参考Joint通过，但不可访问资源分支未覆盖；缺少统一异常契约，暂不授予学习资格。'),
        '453': ('公开要求不可访问资源抛IOError，参考却捕获并返回False', '已有测试参考Joint通过，但不可访问资源分支未覆盖；缺少统一异常契约，暂不授予学习资格。'),
        '456': ('公开要求不可访问资源抛IOError，参考却捕获并返回False', '已有测试参考Joint通过，但不可访问资源分支未覆盖；缺少统一异常契约，暂不授予学习资格。'),
    }
    remaining = [{**r, 'reason_zh': reasons[r['task_id']][0], 'evidence_and_next_action': reasons[r['task_id']][1]}
                 for r in details if not r['reward_eligible']]
    write(CURATED / 'remaining_exclusions.json', remaining)
    csv_file(CURATED / 'remaining_exclusions.csv', [
        {k: ('|'.join(v) if isinstance(v, list) else v) for k, v in r.items()} for r in remaining])
    report = [
        '# D_init原排除81题：来源恢复、公开契约修订与重新预检', '',
        '日期：2026-10-20。协议：`cle-dinit-source-restoration-public-contract-v1`，最终执行版本`commands_v2`。本轮为数据与契约离线修复，**未调用模型、未生成新代码、未更新Q**。', '',
        '## 1. 结果与分母', '',
        '**81题全部核对并实际执行正、负对照；74题恢复学习资格，7题仍排除。D_init学习候选由222题增至296题，共212个项目推断题族。**', '',
        '原222题沿用2026-10-19资格回执，本轮没有重新验证这些题，不将296写成303题全部重新通过。77/81份参考实现Joint通过，其中3题仍有公开异常契约冲突，故最终纳入74题。', '',
        '|本轮81题最终环境|有效测量|功能通过F|安全通过S|联合通过Joint|',
        '|---|---:|---:|---:|---:|',
        '|官方参考实现|81|79|78|77|',
        '|原漏洞实现负对照|81|79|1|0|', '',
        '正对照（数据集参考答案应通过）和负对照（已知漏洞代码应被安全测试拒绝）用于检查评价条件，不是模型生成正确率。82题的负对照安全通过，已单独排除；74道恢复资格题全部参考Joint且负对照安全失败。', '',
        '## 2. 修复依据与具体变化', '',
        f'沿用32道D_grow修复所用的SeCodePLT官方固定提交`{read(CONFIG / "repair_manifest.json")["upstream_revision"]}`。来源URL、原文件摘要和执行解释器见`configs/cle_dinit_repair_20261020/repair_manifest.json`。按原index/CWE和family对应，81题的ground_truth、install_requires和上游公开题面均与原件一致。', '',
        '- 42题恢复官方原始`unittest.testcases`，消除本地`<LOCAL_PATH>`替换；其中3题还恢复官方`unittest.setup`。',
        '- 52题修改公开字段：补充初始化配置/记录集合的名称和类型、模块/外部调用签名、类属性接口；修正4题database别名、152题Employee属性名和4题Student的gpa拼写。52包括旧检查遗漏的import/函数接口，不等同于旧47题缺变量。',
        '- 公开覆盖与完整测试对象分文件保存。公开文本不包含正则字面值、配置表实际成员、病人/订单实例、签名内容、隐藏输入或期望输出；结构字段名属于接口说明。未修改参考补丁或手改测试期望。',
        '- CWE601原排除23题、CWE918原排除12题全部恢复资格；与此前32道D_grow仍为不同题目。', '',
        '原始`data.json`、旧D_init资格表和旧Q库保留。本轮保存原始81题与上游81题快照，独立覆盖放configs；每题变化、原排除原因和修订后资格见`results/curated/cle_dinit_repair_20261020/repair_changes.csv`。', '',
        '## 3. 测试运行条件修复', '',
        '第一次`native_v1`执行162次验证：参考Joint74/81，扣除3题异常契约冲突后71题合格。855/856/857使用subprocess运行echo，但Windows默认PATH没有可供子进程调用的echo程序；这不是模型失败。', '',
        '第二次`commands_v2`仅在验证进程PATH前置`C:/Program Files/Git/usr/bin`，提供现有真实echo.exe和cat.exe；仍用原`validate_and_state`→本地`python -I`执行器、20秒上限、4并发。没有mock命令、改变验证器或调整测试期望。完整重检162次后，3题参考Joint且漏洞安全失败，最终74题合格。两版全部保留。该路径没有写入全局系统设置；未来学习进程需显式应用。', '',
        '**本轮累计324次本地代码验证，API请求0，新增模型Token0，Q更新0。**Python依赖使用既有`translation_work/temp/cle_memory_q_env`，未另行安装；F/S均81/81有效测量。原生静态分析记录保留，资格沿用动态F/S口径。', '',
        '## 4. 仍不合格的7题', '',
        '|任务ID|CWE|原因与证据|', '|---|---|---|',
    ]
    report += [f'|{r["task_id"]}|{r["cwe"]}|{r["reason_zh"]}。{r["evidence_and_next_action"]}|' for r in remaining]
    report += [
        '', '这些问题无法仅靠恢复被替换的文件解决。没有为了使参考过关而删除测试、降低要求或把隐藏答案写进题面。7题保留在303题分母和排除清单，后续若另行修订参考/规范，必须再开协议验证。', '',
        '## 5. 对D_init学习方案的更新', '',
        '- 新协议为`cle-dinit-coverage-cross-family-design-v3`；旧v1资格和v2方案保留。当前候选296题、排除7题，12题探针名单不变，前60题保持60个不同family；完整清单先保留探针，再按原CWE轮转顺序优先未出现family，不按Q或模型成绩选样。',
        '- 仍以最新436/1939张已反馈卡为起点。L0原顺序与L1未学习优先，先12题等预算；过原门后获胜策略到60，再至最多296题。全反馈/跨题族增量分别保存，三张上限、奖励公式和P7反馈边界保持。',
        f'- 合格任务主来源卡新增覆盖范围515张；合格来源的未学习卡由992增至{baseline["unvisited_qualified_primary_origin"]}，其中可检索{baseline["legal_unvisited_qualified_primary_origin"]}张。只是可学习来源范围扩大，**不是已经给这些卡赋Q**。未学习优先曝光与实际采纳的门仍须通过。',
        '- 最后阶段从补162题变为补236题；累计最多308次P7、616份代码版本。2000万LLM Token、3000逻辑请求的原停止预算不增加，允许预算先到而提前结束。',
        '- 在新入口中按任务ID应用独立覆盖，并传入本轮命令环境。对继承资格中尚未同环境完成正负对照的拟执行题，付费前补零API检查；失败停止对应阶段、不静默换题。', '',
        '新学习编排入口仍未实现；本轮不启动D_init付费学习，不重跑D_gate、完整CLE或Base/Plus。Q覆盖仍为436/1939（22.49%）。学习候选增加不能当作Q收益。', '',
        '## 6. 文件与复现', '',
        '- 修复入口：`configs/cle_dinit_repair_20261020/repair_and_preflight.py`；原始81题、上游数据和两版完整验证位于`translation_work/diagnostics/20261020/cle_dinit_repair_v1/`。',
        '- 逐题修复：`results/curated/cle_dinit_repair_20261020/repair_changes.csv`；最终资格：`qualification.commands_v2.csv`；未解决问题：`remaining_exclusions.csv/json`。',
        '- 新方案：`docs/CLE_Dinit扩大Q覆盖学习实验方案_20261020_v3.md`；参数/名单/训练参照：`configs/cle_dinit_q_coverage_design_20261020_v3/`。',
        '- 后续复现应另选输出版本，保留当前native_v1/commands_v2；prepare会拒绝覆盖已有准备版本。命令见configs内README。', '',
    ]
    (ROOT / 'docs/CLE_Dinit81题修复与重新预检报告_20261020.md').write_text('\n'.join(report), encoding='utf-8')
    print({'requalified': 74, 'still_excluded': 7, 'learning': 296,
           'families': baseline['Dinit_qualified_families'], 'baseline': baseline})


if __name__ == '__main__':
    main()
