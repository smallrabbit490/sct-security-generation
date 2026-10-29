"""将完成的K2分析补入对应两条叙事，沿用既有七阶段可编辑图。"""
from datetime import datetime, timezone
import json

from configs.cle_weekly_analysis_20261027.analysis import RUN, read, write
from configs.cle_weekly_full_20261027.prepare import ROOT
from tools import build_cle_horizontal_ideas as diagrams


def main():
    summary = read(RUN / 'analysis/K2/summary.json')
    assert summary['analysis_completion_status'] == 'completed'
    path = ROOT / 'docs/research/CLE-STORY-20261028-nine-ideas.md'
    text = path.read_text(encoding='utf-8')
    snapshot = diagrams.base.status_snapshot()
    write(RUN / 'analysis/K2/maintenance_20261028/narrative_snapshot.json', snapshot)
    sections = [
        ('**第六阶段：固定评分，分别回答同题收益与换题收益。**',
         '**K2阶段分析补充（10月28日）。** 完整273题首次Joint123、末次124，全部可测；273题保存响应与原动态验证回放一致，原信用函数重建的1939卡Q及反馈次数与冻结库一致。实际审阅9道题、覆盖11项案例队列：1289密码类型与1298异常契约/夹具冲突影响负信用解释；675、1301覆盖外部配置属于实际实现缺陷。唯一救回108来自IDNA实现修正，预先无奖励资格，不能作为Q收益证据。原成绩、资格和冻结库不改。[完整K2分析](E:/ResearchRuns/CLE/20261027_full_requirements/analysis/K2/analysis.md)。'),
        ('**第二阶段：用相同题目比较各轮评分。**',
         '**K2追加反馈的实际结果（10月28日）。** 本阶段340张卡得到611次有效反馈，来自171个题族；累计覆盖由610增至702/1939，新增92张。末次Joint124/273，217个真实题族整簇95%区间为38.11%—52.54%；首次—末次救回1、损失0、配对置换p=1。K2仅一遍，重复波动未测量，这些结果不识别追加Q的独立收益。累计已知18639471 Token、2616次HTTP，79次未知用量保留，未重置预算。同题比较仍保持1416次批准规模。[统计与逐题证据](E:/ResearchRuns/CLE/20261027_full_requirements/analysis/K2/summary.json)。')]
    for anchor, addition in sections:
        if addition not in text:
            assert anchor in text
            text = text.replace(anchor, addition + '\n\n' + anchor, 1)
    path.write_text(text, encoding='utf-8')
    original = diagrams.simplify

    def with_analysis(specs, items, source):
        display = original(specs, items, source)
        display['B01']['meaning'] = '结果：通过124/273题，反馈覆盖702张卡；273题回放一致，代表题复核完成。'
        return display

    diagrams.simplify = with_analysis
    snapshot_path = RUN / 'analysis/K2/maintenance_20261028/narrative_snapshot.json'
    diagrams.main(snapshot_path, only=[1, 2])
    write(RUN / 'analysis/K2/maintenance_20261028/narrative_update.json', {
        'status': 'completed', 'updated_utc': datetime.now(timezone.utc).isoformat(),
        'narrative': str(path), 'updated_ideas': [1, 2], 'snapshot': str(snapshot_path),
        'original_narrative_time_preserved': True, 'new_experiment_API': 0,
        'outputs': [str(ROOT / 'docs/research/diagrams/ideas_horizontal' / (stem + ext))
                    for stem in ('01_Q值选卡', '02_分轮积累') for ext in ('.svg', '.png')]})


if __name__ == '__main__':
    main()
