"""把逐条科学审查落实到后续自主节点；不改已启动实验或预算。"""
import argparse
import copy
import json
from pathlib import Path
import tempfile

from configs.cle_weekly_reduced_20261028.scope import ROOT, RUN, read, write
from tools.build_cle_research_stage_map import status_snapshot
from tools.cle_live_workbench.autonomy import AutonomousPlan

CHECKLIST = 'docs/research/CLE-TODO-20261022-20261028-v06.md'
CONTROL = RUN/'scientific_review_20261028'
OMIT = {'path': 'scientific_review_20261028/scope_decision.json',
        'field': 'P3_external', 'values': ['deferred_from_current_mainline']}
REQUIREMENTS = {
    'Q.retest': 'C02：1416格与正式20格前缀不变；只在同54题比较各轮，K3/Q1全273另列，不用在线分数作收益。',
    'Q.retest.analysis': 'C02：原五项探索Holm保留；同54题列相邻轮/K3-K0，273题列K3-Q1。区分从未反馈、负反馈、正负抵消和多family反馈；共同候选、改选、采用、代码落实分别判定。',
    'Q.gate': 'C03：2384格不变。生成前按合法Q反馈来源固定同CWE异family集合及未覆盖CWE集合；均保留在298题中。',
    'Q.gate.analysis': 'C03：原全池Q2-Q1/Q3两项Holm不变；同CWE异family的两项作为预先指定迁移验证。若子集不是全池，另给四个不同对比共同Holm校正后的判断，禁止挑显著子集。按Q是否压低本题适用卡复核跨family负迁移，不能只看Q高低。',
    'FS.analysis': 'B02与思路9：保留原预定BFS-BM Joint主检验。补列F/S四象限、原安全通过但功能失败的救回、安全回退、AI/规则分区和首次/修复差异。结论是分栏表达，不是独立双库。复用全部主要损益案例，一题同时服务功能安全与代码改动解释，不重复生成。',
    'GR.labels': 'C04：820格与前20格不变；先区分正确性差异、重复翻转和纯成本差异。标签只是本次可接受档中的低输入成本选择，不是唯一真值。',
    'GR.labels.analysis': 'C04：调用新router.opportunity作训练侧诊断，报告跨重复同向差异、波动、完全同结果；保留accepted_levels。最低Token标签不同不直接说明题目正确性需求不同。',
    'GR.extra.analysis': 'C04E：合并互斥批次后重复相同机会分析，不重标旧题，不改变标签定义或重新购买旧格。',
    'GR.decide82': 'C04/C05：沿原工程扩大门，使用新Joint选模入口。开发结果只作预演，不用小样本收益取消既定全量。',
    'GR.decide164': 'C04E/C05：最多164题，沿原结束条件。不得继续补样追正收益。',
    'GR.train': 'C05：使用goal-aligned-router新方法；训练family三折按实际Joint选正则，平手输入Token再小C。只用原8特征/三参数/0.5阈值；开发21或41题复用结果预演，不能反向选模型。',
    'GR.gate': 'C06：1788逻辑格及正式36格前缀保留；精确同题同重复同档复用，跨重复独立，不把复用行成本相加。',
    'GR.gate.analysis': 'C06：分类器对训练选出的固定档/规则两项Holm。区分提高Joint与只省Token；报告实际生成格/1788逻辑格。两种收益均未过门就结束本轮，不追加复杂分类器。',
    'FR.run': 'C07：57题同一池标签回答三查询；额外选中卡仍按原预算纳入，不为完成机制链生成新代码。首次分析和卡库必须匹配才连接采用记录。',
    'FR.analysis': 'C07/C08：同一标签表分别算候选和最终选卡四指标，区分池内无正类、候选漏失、选择漏失和实现错误。三查询配对，待裁决不算负类；提供完整人审材料。',
    'FR.extra.analysis': 'C07E：同样比较57+57；不额外扫TopK或追加批。人工缺失保持AI估计，不据准确率高宣称召回好。',
    'BUILD.run': 'C09：原三轮和名单内前缀不变；先列原预算及前缀实测成本投影。卡数增长不是收益，D_gate用于全局门控，效果待C10/C11。',
    'BUILD.analysis': 'C09：完整建库与新库有用分开判定；新增/拒收/保留与来源family分轮记录。核实空库或与已有库相同的情况，不能为完全相同消费再购重复代码。',
    'CROSS.v41': 'C10：1788逻辑格，精确复用FFS1192格，新增最多596；正式12题前缀内新库最多24格。新库真实为空或完全相同，先验证同协议可复用性，不重复买相同消费。',
    'CROSS.analysis': 'C10：新库对无卡/旧库两项Holm、题族区间、两重复；同时胜才说新库更好。单列一次性建库成本和消费成本。D_gate用于门控，只作审计集比较，不能归因为生产模型能力。',
    'EXTERNAL.v41': 'C11：保留原环境下1530格和24格前缀，隐藏反馈边界不变；P3已暂缓，不连带启动。',
    'EXTERNAL.analysis': 'C11：Base/Plus各新库对无卡/旧库，四项主要外部比较统一Holm。分别报告效果和费用，不能只选好的集；仅一个集通过就只说该集有效。',
    'CLOSEOUT': '综合逐项回答九条思路：已证明什么、未过哪一道效果/成本门、对主线什么决定。P3暂缓写未执行，不写完成或0分；v3.2不可用不能拼出双模型交互。',
}


def update_plan(plan):
    result = copy.deepcopy(plan)
    by = {t['id']: t for t in result['tasks']}
    for identity, requirement in REQUIREMENTS.items():
        item = by[identity]
        item['research_review'] = {'source': CHECKLIST, 'required_analysis': requirement}
        marker = '\n目标与成本审查：'
        item['note'] = item.get('note', '').split(marker)[0] + marker + requirement + ' 开始前读v06对应段，按其中效果门、投入标准、成本口径写实际判断；这是新分析要求，不得改写历史成绩。'
        if item['kind'] == 'run':
            item['note'] += ' 正式前缀完成后用本包实测用量投影剩余工作，仍受原累计硬预算约束；不添加付费矩阵。'
    for identity in ('GR.decide82', 'GR.decide164', 'GR.train'):
        by[identity]['commands'] = [s.replace('configs.cle_weekly_reduced_20261028.adaptive',
                                            'configs.cle_scientific_review_20261028.adaptive')
                                    for s in by[identity]['commands']]
    check = {'path': 'FG_TRAIN/model.json', 'field': 'method_revision',
             'equals': 'cle-goal-aligned-router-20261028-v1'}
    if check not in by['GR.train']['accept']:
        by['GR.train']['accept'].append(check)
    for identity in ('P3.external', 'P3.analysis'):
        by[identity]['omit_when'] = copy.deepcopy(OMIT)
        by[identity]['title'] = '暂缓：' + by[identity]['title'].removeprefix('暂缓：')
    result.update(plan_id='cle-autonomy-20261028-goal-and-cost-v4', current_checklist=CHECKLIST,
                  scientific_review='configs/cle_scientific_review_20261028/README.md')
    return result


def install(preview=False):
    snapshot = status_snapshot()
    path = ROOT/'tools/cle_live_workbench/autonomy_plan.json'
    before = read(path)
    after = update_plan(before)
    old = {t['id']: t for t in before['tasks']}
    new = {t['id']: t for t in after['tasks']}
    changed = [k for k in old if old[k] != new[k]]
    states = {t['id']: t['status'] for t in snapshot['tasks']}
    protected = {k for k, v in states.items() if v in ('completed', 'running', 'waiting_window')}
    protected.update(('Q.run', 'FS.run'))
    if protected.intersection(changed):
        raise ValueError('cannot_edit_started_or_completed_nodes:' + ','.join(sorted(protected.intersection(changed))))
    for package in ('FG_LABELS', 'FG_GATE', 'P3_EXTERNAL'):
        actual = next(p for p in snapshot['packages'] if p['key'] == package)
        if actual.get('completed', 0):
            raise ValueError('cannot_change_started_scientific_design:' + package)
    with tempfile.TemporaryDirectory() as temp:
        AutonomousPlan(temp, after)
    result = {'changed_tasks': changed, 'protected_unchanged': sorted(protected),
              'additional_paid_units': 0, 'deferred_P3_units': 255,
              'model_calls_by_this_revision': 0, 'active_inputs_or_runner_changed': False}
    if preview:
        return result
    CONTROL.mkdir(parents=True, exist_ok=True)
    backup = CONTROL/'before_plan.json'
    if not backup.exists():
        write(backup, before)
        write(CONTROL/'before_snapshot.json', snapshot)
    write(CONTROL/'scope_decision.json', {'status': 'decided', 'P3_external': 'deferred_from_current_mainline',
          'reason': '当前归因使用同P7空卡；P3另属流程比较，255次暂缓，不记实验完成。',
          'source': CHECKLIST, 'experiment_executed': False})
    # 保护正在修复队列的独立CLI：若它已改过计划，先重新核对而不覆盖。
    if read(path) != before:
        raise ValueError('autonomy_plan_changed_during_review')
    write(path, after)
    write(CONTROL/'install_result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preview', 'install'])
    args = parser.parse_args()
    print(json.dumps(install(args.action == 'preview'), ensure_ascii=False))
