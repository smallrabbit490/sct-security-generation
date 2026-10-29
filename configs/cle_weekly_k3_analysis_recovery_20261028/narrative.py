"""依据已完成的K3原生分析准备两条研究叙事和原图文字；不派发实验。"""
import json
from pathlib import Path

from configs.cle_weekly_analysis_20261027.analysis import RUN, read, write
from configs.cle_weekly_full_20261027.prepare import ROOT


def main():
    out = RUN / 'analysis/K3'
    s = read(out / 'summary.json')
    assert s.get('analysis_completion_status') == 'completed'
    assert s['full_response_replay']['status'] == 'passed'
    p = s['first_final_paired']
    ci = s['family_intervals']['joint_divided_by_planned_ci95']
    evidence = ['analysis/K3/summary.json', 'analysis/K3/analysis.md',
                'analysis/K3/agent_case_review.json', 'FQ_LEARN/K3/zero_API_replay/replay_result.json',
                'analysis/K3/maintenance_20261028/frozen_Q_event_replay.json',
                'analysis/K3/maintenance_20261028/all_attempts_replay_comparison.json']
    results = (f'K3完整273/273，全部可测；首次Joint120/273，末次126/273（46.15%），任一候选上界126/273。'
               f'273配对救回6、损失0，217真实题族95%差值区间{p["ci95_family_bootstrap"]}，'
               f'family置换p={p["p_family_swap"]}；末次Joint整簇95%区间{ci}。'
               '单遍无法估计独立重复波动，两项Q主比较及Holm校正仍无冻结对照。'
               '273题原生响应和动态验证、全部426次尝试及1939卡Q/visits/正文重建一致。'
               '已知18270428 Token、2639次HTTP，83次未知保留，保守21998799/40950000 Token；本分析新增实验请求0。'
               '[完整统计与成本](E:/ResearchRuns/CLE/20261027_full_requirements/analysis/K3/summary.json)。')
    next_step = ('本项只交付K3。由工作台按最新规则自动接力C02的2题20格探针及分析，'
                 'C03的2题16格探针保留其自身依赖；不自动启动排队全量。'
                 '1416格同题回测与2384格迁移比较保留科学范围和真实依赖，暂缓不当完成。'
                 '不因低Joint重跑，不增预算；Q独立收益只能由匹配冻结对照回答。')
    card = ['增长题第3轮已完成', 'Joint126/273；原题回放一致。', '273题；代表10题已审阅']
    draft = {'task_id': 'Q.K3.analysis', 'evidence': evidence, 'sections': {
        'idea01': {
            'source_requirement': '给经验卡积累Q评分后，区分是否改变选卡、是否正确落实，以及是否多做对题。',
            'stage_reason': '旧Q改变选卡但没有稳定胜过相似度；固定1939卡正文，让当前v4.1逐题完成自身Q学习，排除旧模型评分直接迁移的解释。K3是最后一轮，不新增卡。',
            'results': results,
            'analysis': '10道实际代表题覆盖12队列项。1394线性正则、136白名单替换有落实和正信用；1289类型冲突、1298异常契约冲突影响负Q，后者另有覆盖外部字典的实现错误。1002覆盖外部模板，108未实现IDNA。110和1019分别由隐藏文件检查、删除空USERS覆盖救回；102和1344的空采用ID不能推出卡完全无影响。救回只说明题内修复，不能把本轮120→126或候选排序变化当Q相对基线收益。',
            'conclusion': '四阶段1122题次学习已完整，四套评分可供后续消费。K3技术回放和实际案例分析通过；尚无当前Q相对相似度与打乱Q的独立效果结论，两主比较及Holm不填虚值。K0原历史反馈回放证书与DNS动态分歧继续分别保留。',
            'next_step': next_step,
            'diagram': {
                'answer': 'K3全273题完成，Joint126/273；Q独立收益仍待对照。',
                'story': '选卡干预已知；四轮学习结束，接下来检验评分是否多做对题。',
                'cards': {'C01': card},
                'tasks': {
                    'q4': ['新模型四轮学习已完成', '1122题次；四套评分已保存。', '反馈769/1939卡；收益待对照。'],
                    'q5': ['先检查同题与迁移比较', 'C02先2题20次；C03先2题16次。', '探针及分析接力；排队全量暂缓。']}}},
        'idea02': {
            'source_requirement': '分轮积累做题反馈，检查固定经验卡的评分覆盖和同题效果；将Q更新与新增经验卡分开。',
            'stage_reason': 'K0/K1/K2覆盖445/610/702卡，K3继续同273题固定卡学习，保存第四套评分，为同一批题比较各轮Q提供实际资产。',
            'results': results + ' 本轮355卡获743次有效反馈，来自180题族；覆盖702→769/1939，新增67卡。232题奖励合格、41题仍完整执行而不授Q。',
            'analysis': '累计反馈445→610→702→769卡只证实覆盖增加；各轮在线Q不同，不能当独立重复或单调提分曲线。K3声明采用928个位置、涉及265题，不等于正确落实。实际案例中实现错误、公开契约冲突和工作流解析问题分别记录；110无奖励资格仍救回，1019删除外部数据覆盖后救回，不能统一归因追加评分有效。',
            'conclusion': '固定1939卡的分轮学习和K3冻结、回放、案例交付已完成；是否更多反馈能使同题更正确仍未回答。须保留K3对K0的同54题配对与最终K3对相似度的全273题对照及两次独立重复。',
            'next_step': next_step,
            'diagram': {
                'answer': '四轮反馈覆盖445→610→702→769卡；同题收益尚待比较。',
                'story': '评分资产已齐；在线分数不是收益曲线，用相同题目比较各轮。',
                'cards': {'C01': card},
                'tasks': {
                    'r4-q': ['四轮评分学习已完成', 'K3为273/273；末次Joint126。', '本轮新增67卡获得有效反馈。'],
                    'r5-q': ['先检查同题比较', '五条件两重复；先2题20次。', '探针计入1416次；全量暂缓。'],
                    'r6-q': ['比较评分是否更有用', '覆盖445→610→702→769卡。', '同题效果待测；按配对结果判断。']}}}
    }}
    stage = RUN / 'workbench_monitor/autonomy/deliveries/Q.K3.analysis'
    write(stage / 'delivery_draft.json', draft)
    story_path = ROOT / 'docs/research/CLE-STORY-20261028-nine-ideas.md'
    story = story_path.read_text(encoding='utf-8')
    (out / 'maintenance_20261028/narrative_before_K3.md').write_text(story, encoding='utf-8')
    story = story.replace('本次叙事采用10月28日15:31保存的状态。',
        '基础叙事采用10月28日15:31保存的状态；思路01、02已按K3完整273题回放及分析更新，其余思路保留原统计时点。', 1)
    start = story.index('<a id="idea01"></a>')
    stop = story.index('<a id="idea03"></a>')
    section = story[start:stop]
    replacements = {
        '前面三阶段已分别交付303、273、273题，反馈卡累计为445、610、702张；第三轮增长学习已完成7/273题，累计706张卡获得反馈。前三阶段最终Joint分别为148/301、133/272、124/273，分母是各阶段可测题数。':
        '四阶段已分别交付303、273、273、273题，共1122题次，反馈卡累计为445、610、702、769张。各阶段最终Joint按完整名单为148/303、133/273、124/273、126/273，可测题数分别301、272、273、273；缺测保留，不混换分母。',
        '下一步完成当前学习，按C02、C03顺序取得这一答案。':
        '学习已完成，下一步由工作台接力C02、C03就绪探针与分析，排队全量暂缓；完整主比较与真实依赖仍保留。',
        'K0、K1、K2后的反馈卡数依次为445、610、702张；K3在叙事统计时点完成7/273题。':
        'K0、K1、K2、K3后的反馈卡数依次为445、610、702、769张；四阶段1122题次完整保存，K3完成273/273题。',
        '当前确认的是反馈覆盖扩大。完成K3后，先回放和分析，再做C02；根据固定回测决定哪一轮反馈有帮助、追加轮次是否值得。':
        '当前确认的是反馈覆盖扩大。K3已完成原生回放和实际案例分析，由工作台接力C02探针及分析，排队全量暂缓；后续仍须根据固定回测决定哪一轮反馈有帮助、追加轮次是否值得。'
    }
    for old, new in replacements.items():
        assert old in section
        section = section.replace(old, new, 1)
    story = story[:start] + section + story[stop:]
    story_path.write_text(story, encoding='utf-8')
    write(out / 'maintenance_20261028/narrative_preparation.json', {
        'status': 'draft_ready_pending_publish', 'task_id': draft['task_id'],
        'draft': str(stage / 'delivery_draft.json'), 'sections': ['idea01', 'idea02'],
        'evidence': evidence, 'new_experiment_HTTP': 0})
    print(json.dumps({'draft': str(stage / 'delivery_draft.json'), 'status': 'ready'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
