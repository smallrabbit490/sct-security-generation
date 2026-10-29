"""保存独立运行源码，保留活动包引用的原文件；本脚本不调用模型。"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
PREFIX='configs.cle_weekly_reduced_20261028'


def make(source, target, edits):
    text=(ROOT/source).read_text(encoding='utf-8-sig')
    for old,new in edits:
        if old not in text:
            raise ValueError('adapter_source_anchor_missing:'+target+':'+old[:80])
        text=text.replace(old,new)
    (HERE/target).write_text(text,encoding='utf-8')


def main():
    make('configs/cle_weekly_eval_20261027/retest.py','retest.py',[
        ('configs.cle_weekly_eval_20261027.retest',PREFIX+'.retest'),
        ("'configs/cle_weekly_eval_20261027',", "'configs/cle_weekly_eval_20261027', 'configs/cle_weekly_reduced_20261028',"),
        ("def prepare():", "def legacy_full_prepare_not_used():"),
        ("def dependencies():", "def prepare():\n    return read(package_root()/'inputs/protocol.json')\n\n\ndef dependencies():"),
        ("    return {'ready': not reasons, 'reasons': reasons}\n", "    from configs.cle_weekly_k0_saved_feedback_20261028.certificate import accepted\n    if accepted(RUN):\n        reasons = [r for r in reasons if r != 'K0_native_replay_pending']\n    return {'ready': not reasons, 'reasons': reasons}\n"),
        ('self.controlled_conditions)\n\n    def after_group', "tuple(r['condition'] for r in rows if r['condition'] in self.controlled_conditions))\n\n    def after_group"),
        ("    args = parser.parse_args()", "    parser.add_argument('--workers',type=int,choices=range(1,5),default=4)\n    args = parser.parse_args()\n    FrozenRetest.worker_limit=args.workers"),
        ("'run'], cwd=ROOT", "'run', '--workers', str(args.workers)], cwd=ROOT"),
        ("'planned': 2730, 'updated_utc'", "'planned': prepare()['planned_P7'], 'updated_utc'")])
    ret=HERE/'retest.py'
    ret.write_text(ret.read_text(encoding='utf-8').replace('json.dumps(r, ensure_ascii=False)', 'json.dumps(r, ensure_ascii=True)'),encoding='utf-8')
    make('configs/cle_weekly_granularity_20261027/evaluate.py','granularity.py',[
        ('from configs.cle_weekly_eval_20261027 import retest as base','from . import retest as base'),
        ('configs.cle_weekly_granularity_20261027.evaluate',PREFIX+'.granularity'),
        ('def prepare():','def legacy_full_prepare_not_used():'),
        ('def dependencies():', "def prepare():\n    return base.read(package_root()/'inputs/protocol.json')\n\n\ndef dependencies():"),
        ("base.read(copied) != base.read(task_source())", "base.read(copied) != {i:base.read(task_source())[i] for i in base.read(copied)}"),
        ("!= 2730:","!= prepare()['planned_P7']:"),
        ("'planned': 2730,\n                'updated_utc'", "'planned': prepare()['planned_P7'],\n                'updated_utc'")])
    make('configs/cle_weekly_gate_20261027/evaluate.py','qgate.py',[
        ('from configs.cle_weekly_eval_20261027 import retest','from . import retest'),
        ('configs.cle_weekly_gate_20261027.evaluate',PREFIX+'.qgate'),
        ('!= 2730:', '!= 1416:'),
        ("'completed_retest_required': 2730", "'completed_retest_required': 1416")])
    make('configs/cle_weekly_granularity_gate_20261027/evaluate.py','granularity_gate.py',[
        ('from configs.cle_weekly_eval_20261027 import retest as base','from . import retest as base'),
        ('from configs.cle_weekly_granularity_20261027 import evaluate as labels','from . import granularity as labels'),
        ('configs.cle_weekly_granularity_gate_20261027.evaluate',PREFIX+'.granularity_gate'),
        ("cle-weekly-granularity-family-router-20261027-v1",'cle-reduced-granularity-family-router-20261028-v1'),
        ("summary.get('completed') != 2730", "summary.get('completed') != 820"),
        ("    reasons = []\n    package =", "    reasons = []\n    from .scope import CONTROL, read\n    decision=read(CONTROL/'GR_decision.json') if (CONTROL/'GR_decision.json').exists() else {}\n    if decision.get('action') != 'freeze_and_gate':\n        reasons.append('adaptive_training_not_ready')\n    package =")])
    make('configs/cle_weekly_retrieval_20261027/prepare.py','retrieval_prepare.py',[
        ("COUNTS = {'D_grow': 273, 'D_gate': 298}","COUNTS = {'D_grow': 27, 'D_gate': 30}"),
        ('cle-weekly-retrieval-common-pool-20261027-v1','cle-reduced-retrieval57-20261028-v1')])
    make('configs/cle_weekly_retrieval_20261027/execute.py','retrieval_execute.py',[
        ('from configs.cle_weekly_retrieval_20261027 import prepare as prep','from . import retrieval_prepare as prep'),
        ('configs.cle_weekly_retrieval_20261027.execute',PREFIX+'.retrieval_execute'),
        ('cle-weekly-retrieval-bounded-execution-20261027-v1','cle-reduced-retrieval57-execution-20261028-v1'),
        ('PAIR_LIMIT = 107821','PAIR_LIMIT = 10767'),
        ('EXTRA_LIMIT = 43869','EXTRA_LIMIT = 4383'),
        ('1939 + 571 * 3','1939 + 57 * 3'),
        ("'initial_pair_cap': 63952", "'initial_pair_cap': 6384"),
        ("'absolute_task_card_upper_bound': 571 * 1939", "'absolute_task_card_upper_bound': 57 * 1939"),
        ("'273*3*(3 learning +10 retest +10 granularity)'", "'27*3*(3 learning +10 retest +10 granularity)'"),
        ("'298*3*(8 Q +10 F/S +6 classifier +4 old-library cross-model)'", "'30*3*(8 Q +10 F/S +6 classifier +4 old-library cross-model)'"),
        ("markers = (", "markers = ('configs.cle_weekly_reduced_20261028.',")])
    make('configs/cle_weekly_analysis_20261027/retest_analysis.py','retest_analysis.py',[
        ('from .analysis import','from configs.cle_weekly_analysis_20261027.analysis import'),
        ('    wanted = [r for r in rows', "    common=set(str(r['task_id']) for r in rows if r['condition']==treated) & set(str(r['task_id']) for r in rows if r['condition']==control)\n    planned_tasks=273 if (treated,control)==('Q2_K3','Q1') else 54\n    wanted = [r for r in rows if str(r['task_id']) in common"),
        ("if r['condition'] in (treated, control)]", "and r['condition'] in (treated, control)]"),
        ("metrics([r['attempts'][0] for r in items], planned_tasks*2)","metrics([r['attempts'][0] for r in items], (273 if condition in ('Q1','Q2_K3') else 54)*2)"),
        ("metrics([r['final'] for r in items], planned_tasks*2)","metrics([r['final'] for r in items], (273 if condition in ('Q1','Q2_K3') else 54)*2)"),
        ('len(schedule) == 2730','len(schedule) == 1416'),
        ('五项同题探索比较另列Holm校正', '最终K3对Q1覆盖273题；中间轮及K3对K0只在同一54题配对，五项比较另列Holm校正'),
        ('下一步完成原定全部五条件和两重复','下一步完成1416格分层规格和两重复')])
    make('configs/cle_weekly_analysis_20261027/granularity_analysis.py','granularity_analysis.py',[
        ('from .analysis import','from configs.cle_weekly_analysis_20261027.analysis import'),
        ('from .retest_analysis import collect','from configs.cle_weekly_analysis_20261027.retest_analysis import collect'),
        ("'planned': 2730", "'planned': len(schedule)"),
        ("], 546)","], len(tasks)*2)"),
        ('len(rows) == len(schedule) == 2730','len(rows) == len(schedule)'),
        ('{len(rows)}/2730','{len(rows)}/{len(schedule)}'),
        ('固定五档和两重复不按收益缩减','按已登记抽样名单完成五档和两重复'),
        ('cle-weekly-granularity-family-router-20261027-v1','cle-reduced-granularity-family-router-20261028-v1')])
    # 扩展批与首批题目互斥；独立目录、独立日志，只追加未生成过的题卡。
    make('configs/cle_weekly_reduced_20261028/granularity.py','granularity_extra.py',[
        (PREFIX+'.granularity',PREFIX+'.granularity_extra'),
        ("return base.RUN/'FG_LABELS'", "return base.RUN/'FG_LABELS_EXTRA'"),
        ("return package_root()/'inputs_contract_v2/tasks.json'", "return base.RUN/'FG_LABELS/inputs_contract_v2/tasks.json'"),
        ("return package_root()/'preflight_contract_v2/summary.json'", "return base.RUN/'FG_LABELS/preflight_contract_v2/summary.json'")])
    make('configs/cle_weekly_reduced_20261028/retrieval_prepare.py','retrieval_extra_prepare.py',[
        ("return RUN / 'FR'", "return RUN / 'FR_EXTRA'"),
        ('cle-reduced-retrieval57-20261028-v1','cle-reduced-retrieval-extra57-20261028-v1')])
    make('configs/cle_weekly_reduced_20261028/retrieval_execute.py','retrieval_extra_execute.py',[
        ('from . import retrieval_prepare as prep','from . import retrieval_extra_prepare as prep'),
        (PREFIX+'.retrieval_execute',PREFIX+'.retrieval_extra_execute'),
        ('cle-reduced-retrieval57-execution-20261028-v1','cle-reduced-retrieval-extra57-execution-20261028-v1')])
    make('configs/cle_weekly_reduced_20261028/granularity_analysis.py','granularity_extra_analysis.py',[
        ("package = root/'FG_LABELS'", "package = root/'FG_LABELS_EXTRA'")])


if __name__=='__main__':
    main()
