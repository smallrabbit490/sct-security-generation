"""将九图审查接入未执行分析；保留活动实验，新增有界的本地R01。"""
import argparse
import copy
import json
import tempfile

from configs.cle_weekly_reduced_20261028.scope import ROOT, RUN, read, write
from tools.build_cle_research_stage_map import status_snapshot
from tools.cle_live_workbench.autonomy import AutonomousPlan

SOURCE = 'docs/research/CLE-TODO-20261022-20261028-v08.md'
NARRATIVE = 'docs/research/CLE-STORY-20261028-nine-ideas.md'
CONTROL = RUN / 'narrative_plan_20261028'
STORY_SECTIONS = {
    'Q.retest.analysis': ['idea02'], 'Q.gate.analysis': ['idea01','idea03'],
    'FS.analysis': ['idea04','idea09'], 'FS.single_edit': ['idea04','idea09'],
    'GR.labels.analysis': ['idea05'], 'GR.extra.analysis': ['idea05'],
    'GR.gate.analysis': ['idea05'], 'FR.analysis': ['idea06'],
    'FR.extra.analysis': ['idea06'], 'BUILD.analysis': ['idea02','idea08'],
    'CROSS.analysis': ['idea08'], 'EXTERNAL.analysis': ['idea08'],
    'CLOSEOUT': [f'idea{i:02d}' for i in range(1,10)],
}
NOTES = {
    'Q.retest.analysis': '图02：同54题比较K0至K3；最终Q/Q1全273另列。这是固定卡的Q反馈曲线，不能称每轮新增经验的收益曲线。',
    'Q.gate.analysis': '图01/03：首次Q1/Q2/Q3共同候选，Q0边界不同；修复查询可不同。按实际合法Q反馈的CWE/family集合报告迁移，旧卡来源暴露另列。改选、声明采用、代码落实和Joint分别判断。',
    'FS.analysis': '图04/09：A11/A19接口保护、A18固定代码编辑不是B02同一干预。原BFS-BM主检验不变。Joint与安全净变化、逐题安全退步同时列出；无净收益不等于必有取舍。完成代表差异题实际阅读后，由FS.single_edit接续R01本地单点复验，不能先把阅读印象写成验证过的原因。',
    'GR.labels.analysis': '图05：L3目标模板和L4来源示例是两种呈现，不是信息量单调递增。正确性异质性、重复翻转和纯Token差异分开；仍按原可训练/扩大条件执行。',
    'GR.gate.analysis': '图05：只用训练侧选择固定档与模型；分别报告对固定档和简单规则的配对Joint及完整流程成本。不要把首选标签预测准确率当正确率。',
    'FR.analysis': '图06：199题历史对照与另14题914对初标不是同一批。当前AI指标单列；完整人审池之后才是正式四指标；无匹配题面/查询/卡库的代码记录就不宣称已解释实现环节。',
    'FR.extra.analysis': '图06：追加不改原标签与选样规则；人工确认之后才合并正式指标。不要为补采用路径重新生成代码。',
    'BUILD.analysis': '图02/08：原CLE动态回放的各轮题目/记忆会变化，记录过程与卡库变化即可，不称为各轮同条件效果对照。最终新库的价值由C10/C11判断；本轮不增加432次逐轮卡库回测。',
    'CROSS.analysis': '图08：C10审计题参与原建库门控，只判断这套新库在该审计集的效果。v3.2不可用，不能把单模型三库写成完整模型交互。1192复用逐格核准，建库与消费成本分开。',
    'EXTERNAL.analysis': '图08：C11的两集外部结果独立于C10说明，每集对无卡/旧库的主要比较按v06。P3仍暂缓，不因镜像到位恢复。',
    'CLOSEOUT': '逐条回答v08九条叙事：来源、阶段理由、结果、分析、结论、下一步；先更新叙事再出图。R01只有局部单点作用结论。逐轮新卡、不可用双模型交叉和独立双库架构按真实未测状态写。',
}


def update_plan(plan):
    result = copy.deepcopy(plan)
    by = {t['id']: t for t in result['tasks']}
    marker = '\n九图审查：'
    for identity, note in NOTES.items():
        task = by[identity]
        task['note'] = task.get('note', '').split(marker)[0] + marker + note + ' 执行前读' + SOURCE + '，原实验和预算不改。'
        task['diagram_review'] = {'source': SOURCE, 'required_analysis': note}
    new = {
        'id': 'FS.single_edit', 'title': 'R01：最多6题单点代码复验（不调用实验API）',
        'kind': 'custom', 'package': 'FFS', 'depends': ['FS.analysis'], 'priority': 1,
        'note': '按' + SOURCE + '#r01执行。实际读主要BFS-BM差异，按预定顺序最多6道不同题；每题先写假设与单点改动，再在独立副本用同版本原验证器复验原代码及修改版，总计最多12次本地验证。不得改测试/契约/正式代码，不注入隐藏答案，不更新Q，不发生成或Embedding请求，不迭代修到通过。无单点可隔离例子也保存候选和原因，不能凑题。输出FFS/analysis/single_edit_review/cases.json和summary.md，包含选样、原证据路径、diff、两份验证结果、结果判断、耗时及实际分析用量；使用真实文件写custom完成收据。局部支持/否定/未隔离均保留，完成不代表正收益。',
        'diagram_review': {'source': SOURCE, 'experiment': 'R01', 'max_tasks': 6,
                           'max_local_validations': 12, 'model_api_calls': 0},
    }
    if new['id'] in by:
        result['tasks'][result['tasks'].index(by[new['id']])] = new
    else:
        result['tasks'].insert(next(i for i,t in enumerate(result['tasks']) if t['id']=='CLOSEOUT'), new)
    by = {t['id']:t for t in result['tasks']}
    for identity,sections in STORY_SECTIONS.items():
        task=by[identity]
        task['note']=task.get('note','').split('\n叙事与成图：')[0]+(
            '\n叙事与成图：使用 $cle-idea-narrative，实际完成本包分析后，将来源要求、阶段理由、比较与实测结果、结果分析、结论、下一步写全。'
            '回写'+NARRATIVE+'中的'+','.join(sections)+'，再按同一截止仅刷新对应图；运行/恢复统一显示正在运行。'
            '不要为补叙事新增模型请求、重跑已完成实验或改活动规则。')
        task['narrative']={'source':NARRATIVE,'sections':sections,'skill':'cle-idea-narrative'}
    closeout=by['CLOSEOUT']
    if 'FS.single_edit' not in closeout['depends']:
        closeout['depends'].append('FS.single_edit')
    result.update(plan_id='cle-autonomy-20261028-narrative-to-plan-v6',current_checklist=SOURCE)
    return result


def install(preview=False):
    snapshot = status_snapshot()
    path = ROOT / 'tools/cle_live_workbench/autonomy_plan.json'
    before = read(path)
    after = update_plan(before)
    old = {t['id']: t for t in before['tasks']}
    changed = [t['id'] for t in after['tasks'] if old.get(t['id']) != t]
    protected = {t['id'] for t in snapshot['tasks'] if t['status'] in ('completed','running','waiting_window')}
    protected.update(('Q.run','FS.run'))
    if protected.intersection(changed):
        raise ValueError('cannot_change_active_or_completed:' + ','.join(sorted(protected.intersection(changed))))
    with tempfile.TemporaryDirectory() as temp:
        AutonomousPlan(temp, after)
    result = {'changed_tasks': changed, 'additional_model_api_calls': 0,
              'max_added_local_validations': 12, 'protected_unchanged': sorted(protected)}
    if not preview:
        CONTROL.mkdir(parents=True, exist_ok=True)
        if not (CONTROL/'before_plan.json').exists():
            write(CONTROL/'before_plan.json', before)
            write(CONTROL/'before_snapshot.json', snapshot)
        if read(path) != before:
            raise ValueError('plan_changed_during_review')
        write(path, after)
        write(CONTROL/'install_result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preview','install'])
    print(json.dumps(install(parser.parse_args().action=='preview'), ensure_ascii=False))
