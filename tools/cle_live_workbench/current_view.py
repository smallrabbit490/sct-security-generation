"""当前人工接续的展示视图；只读结果，不修改原生状态或派发队列。"""
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone

PLAN_FILE = Path(__file__).resolve().parents[2] / 'configs/cle_weekly_closeout_20261101/execution_plan.json'


def batch_detail(package, run, read):
    """只读当前段、请求元数据及收尾产物；生成完成不等于分析完成。"""
    if not package.get('segment'):
        return
    segment = Path(package['segment'])
    root = segment.parent
    summary = package.get('display_summary') or {}
    planned = package['display_planned']
    completed = package['display_completed']
    switched = (root/'model_switch_flash_20261101/manifest.json').exists()
    if switched:
        replay = read(root/'model_switch_flash_20261101/replay_result.json', {})
        analysis = read(root/'model_switch_flash_20261101/analysis/summary.json', {})
        readiness = analysis.get('training_readiness', {})
        package['model_strata'] = summary.get('model_strata', {})
        package['model'] = summary.get('model', 'deepseek-v4.1-flash')
    else:
        replay = read(root/'zero_API_replay/replay_result.json', {})
        analysis = read(root/'analysis_20261101/summary.json', {})
        readiness = read(root/'analysis_20261101/training_readiness.json', {})
    native = package.get('native_state', {})
    live = bool(package.get('processes'))
    all_saved = completed == planned
    reviewed = analysis.get('case_review_status') == 'completed'
    finished = all_saved and replay.get('status') == 'passed' and analysis.get('status') == 'completed' and reviewed
    status = ('postprocessing' if live and all_saved else
              ('running' if package.get('status') == 'running' else 'waiting_window') if live else
              'completed' if finished else
              'awaiting_case_review' if all_saved and analysis.get('status') == 'completed' else
              'awaiting_analysis' if all_saved else
              native.get('status', package.get('status', 'not_started')))
    if not live and status in ('running', 'starting', 'waiting_time_window'):
        status = 'interrupted'
    package.update(display_status=status, status=status, last_saved_at=summary.get('updated_utc'),
                   display_note='固定小批；生成完成后自动回放和数值分析，实际案例复盘单独完成。全量不自动启动。')
    if status == 'postprocessing':
        for process in package['processes']:
            process['workers'] = 0
    package['workflow'] = {
        'generation': 'completed' if all_saved else status,
        'replay': replay.get('status', 'not_started'),
        'statistics': analysis.get('status', 'not_started'),
        'analyzed_cells': analysis.get('completed', 0),
        'statistics_current': bool(analysis) and analysis.get('completed') == completed,
        'case_review': analysis.get('case_review_status', 'not_started'),
        'training_readiness': readiness.get('status', 'not_started'),
        'analysis_time': analysis.get('observed_utc'),
    }
    requests = list((segment/'journals').glob('*/requests/*.json'))
    if requests:
        recent = max(requests, key=lambda p: p.stat().st_mtime_ns)
        record = read(recent, {})
        package['request'] = {k: record.get(k) for k in
            ('identity', 'status', 'started_utc', 'finished_utc', 'elapsed_seconds', 'error_type')}
        package['request'].update(cell_id=recent.parent.parent.name,
            stage='选卡' if record.get('selector') else '模型生成/分析',
            time=datetime.fromtimestamp(recent.stat().st_mtime, timezone.utc).isoformat())
    budget = read(segment/'budget.json', {})
    if budget:
        entries = budget.get('entries', [])
        unknown = sum(e.get('status') != 'reported' for e in entries)
        package['usage_summary'] = dict(
            known_reported_tokens=budget.get('known_reported_tokens', 0),
            physical_HTTP=budget.get('transport_attempts_including_prior', 0),
            unknown_or_inflight_HTTP=unknown)
        package['budget'] = {k: budget.get(k) for k in (
            'cap_tokens', 'cap_HTTP', 'charged_tokens_including_unknown_and_inflight_bounds',
            'transport_attempts_including_prior')}
    package['result_totals'] = {k: sum(a.get(k, 0) for a in summary.get('arms', {}).values())
                                for k in ('functional', 'security', 'joint', 'measured')}


def restored_view(snapshot, view, run, read, plan):
    """从已授权小批计划和真实文件构建展示，绝不写派发或实验控制。"""
    packages = {p['key']: p for p in snapshot['packages']}
    tasks = {t['id']: t for t in plan.get('tasks', [])}
    for key, node in (('FQ_RETEST', 'N1'), ('FG_LABELS', 'N3')):
        p, definition = packages[key], tasks[node]
        p.update(display_completed=max(p.get('completed', 0), p.get('display_completed', 0)),
                 display_planned=definition['planned'], scope=definition['unique_tasks'],
                 repeats=definition['repeats'], conditions=definition['conditions'])
        batch_detail(p, run, read)
    snapshot['workers'] = sum(p['workers'] for p in snapshot.get('processes', []))
    snapshot['control'] = dict(owner='已授权小批接续', autonomous_dispatch=False,
        Q='54题Q回测已恢复', memory='82题记忆标签已恢复，分类器付费评价暂停',
        full_tasks='排队全量跳过', retrieval='57题检索先完成续跑接线')
    snapshot['plan'] = dict(id=plan['plan_id'], report_due=plan.get('report_due'),
                            scope='54题Q回测 + 82题记忆标签；排队全量跳过')
    if any(p.get('model') == 'deepseek-v4.1-flash' for p in packages.values()):
        snapshot['model'] = 'deepseek-v4.1-flash · Q回测和记忆标签换模接续'
        snapshot['control']['Q'] = 'Q回测换模继续，前后结果分层统计'
        snapshot['control']['memory'] = '记忆标签换模继续，复用旧前缀另列'
    # 全量仍保留在表内，但不把局部探针分母冒充全量分母。
    for key in ('FQ_GATE', 'FG_GATE', 'FX_GATE', 'FX_EXTERNAL'):
        packages[key].update(display_planned=packages[key].get('planned'), display_status='deferred_full',
                             display_note='当前计划跳过排队全量；未解除模型、卡库或验证环境依赖。')
    packages['FQ_LEARN'].update(display_status='completed')
    for key in ('FG_LABELS_EXTRA', 'FR_EXTRA'):
        packages[key].update(display_status='deferred', display_note='追加批未授权启动，先完成当前小批和分析。')
    fr = tasks.get('N4', {})
    if not packages['FR'].get('processes') and fr.get('dispatch_ready') is False:
        packages['FR'].update(display_status='needs_wiring',
            display_note='57题候选池已齐；先接好保留缺失请求、只继续未派发题卡对的入口和盲审导出。人工标签尚未确认。')
    current = {'Q.retest.probe': 'FQ_RETEST', 'GR.labels': 'FG_LABELS'}
    analyses = {'Q.retest.probe.analysis': 'FQ_RETEST', 'GR.labels.analysis': 'FG_LABELS'}
    for task in view.get('tasks', []):
        tid = task['id']
        if tid in current:
            p = packages[current[tid]]
            task.update(title=p['label'], expected=p['display_planned'], kind='probe',
                        status=p['display_status'], display_status=p['display_status'],
                        reason=f"已保存{p['display_completed']}/{p['display_planned']}次；完成后回放和分析")
        elif tid in analyses:
            p = packages[analyses[tid]]
            w = p.get('workflow', {})
            stage = 'partial_analysis' if w.get('analyzed_cells') else 'waiting_dependency'
            if w.get('statistics') == 'completed' and w.get('statistics_current'):
                stage = 'awaiting_case_review'
            task.update(title=p['label']+'：回放、统计与案例复盘', status=stage, display_status=stage,
                reason=f"统计覆盖{w.get('analyzed_cells', 0)}次，当前已保存{p['display_completed']}次；案例复盘状态单独核对")
        elif tid == 'GR.train':
            task.update(title='标签完成后的离线训练资格分析', status='waiting_dependency',
                display_status='waiting_dependency', reason='820次及原生回放齐全后自动分析，只保存候选，不启动付费评价')
        elif tid == 'FR.run':
            task.update(status=packages['FR']['display_status'], display_status=packages['FR']['display_status'],
                        reason=packages['FR']['display_note'])
        elif tid in ('Q.retest', 'Q.retest.analysis', 'FS.run'):
            task.update(status='deferred_full', display_status='deferred_full', reason='当前计划跳过剩余或排队全量')
    counts = {}
    for task in view.get('tasks', []):
        counts[task['status']] = counts.get(task['status'], 0) + 1
    view.update(counts=counts, next_description='完成54题Q回测与82题记忆标签及分析；57题检索先补续跑接线。全量不自动启动。')
    q = packages['FQ_RETEST']
    snapshot['findings'][0]['impact'] = f"新Q同题回测已保存{q['display_completed']}/{q['display_planned']}次，完成固定小批后作主要比较。"
    snapshot['findings'][1].update(title='拆分经验在完整第一轮没有增加Joint通过数',
        result='原卡与分开写均125/298；第二轮当前有效配对188次，净少5次。',
        impact='完整第一轮与未齐第二轮分开报告；剩余547次继续暂缓。')
    snapshot['usage'] = {key: sum(s.get(key, 0) or 0 for p in snapshot['packages']
        for s in (p.get('stages', {}).values() if p['key'] == 'FQ_LEARN' else [p.get('usage_summary', {})]))
        for key in ('known_reported_tokens', 'physical_HTTP', 'unknown_or_inflight_HTTP')}
    snapshot['usage']['note'] = '各包采用物理累计账本或原生摘要；续段不相加。未知用量不折算为0费用，Codex用量另列。'


def extra_rows(run, read):
    for package, folder in (
        ('IR02', 'impact_radius_20261028/IR02/segment_001/task_rows/*.json'),
    ):
        for path in sorted(run.glob(folder)):
            row = read(path, {})
            if not row:
                continue
            if package == 'IR02':
                evidence = row.get('evidence', {})
                f = evidence.get('functional', {}).get('status')
                s = evidence.get('security', {}).get('status')
                measured = f in ('pass', 'fail') and s in ('pass', 'fail')
                final = dict(functional=f == 'pass', security=s == 'pass',
                             joint=f == s == 'pass', measured=measured)
                row.update(final=final, arm=row.get('condition'),
                           attempts=[dict(attempt=0, code=row.get('code'), **final)])
            row['_package'], row['_time'] = package, path.stat().st_mtime
            yield row


def apply_current_view(snapshot, autonomy, run, read):
    policy = read(run / 'supervised_remaining_20261029.json', {})
    if policy.get('execution_owner') != 'current_chat':
        return autonomy
    view = deepcopy(autonomy)
    snapshot['control'] = dict(owner='当前窗口接续', autonomous_dispatch=False,
                              full_tasks='排队全量跳过', Q='已暂停', memory='已暂停',
                              retrieval='57题检索测量继续，先补5题初析，再检查2题前缀')
    packages = {p['key']: p for p in snapshot['packages']}

    def display(key, label, count, planned, status, note, summary=None):
        p = packages.get(key)
        if p is None:
            p = dict(key=key, label=label, summary={}, stages={}, processes=[], activity=None)
            packages[key] = p
            snapshot['packages'].append(p)
        p.update(label=label, display_completed=count, display_planned=planned,
                 display_status=status, display_note=note)
        if summary is not None:
            p.update(summary=summary, display_summary=summary, usage_summary=summary)
        return p

    q_summaries = [read(p, {}) for p in sorted((run/'probe_relay_20261028/Q.retest').glob('segment_*/summary.json'))]
    q_summary = max(q_summaries, key=lambda s: s.get('completed', 0), default={})
    display('FQ_RETEST', '冻结Q同题回测 · 54题小批', q_summary.get('completed', 0), 540,
            'paused', '按用户要求暂停；已保存结果和成功响应保留。', q_summary)
    display('FG_LABELS', '五档记忆标签 · 82题小批', packages['FG_LABELS']['completed'], 820,
            'paused', '记忆标签及分类器暂停，不自动续跑。')
    for key in ('FQ_GATE', 'FG_GATE', 'FG_LABELS_EXTRA'):
        packages[key].update(display_status='paused', display_note='按用户要求暂停，等待明确恢复。')
    packages['FFS'].update(display_status='deferred_full',
        display_note='保存2433格；剩余全量跳过。已完成部分结果分析，不自动修复或续跑。')
    ir = read(run/'impact_radius_20261028/IR02/analysis/summary.json', {})
    cost = read(run/'impact_radius_20261028/IR02/analysis/cost.json', {})
    if ir:
        summary = dict(ir, known_reported_tokens=cost.get('known_reported_tokens', 0),
                       physical_HTTP=cost.get('transport_attempts_including_prior', 0),
                       unknown_or_inflight_HTTP=0)
        display('IR02', '影响半径 · 边界提醒对照', ir['completed'], ir['planned'], 'completed',
                '48格已回放分析；两臂Joint均8/24，净收益0。未通过扩大条件，96格确认不执行。', summary)
    build = read(run/'probe_relay_20261028/BUILD.run/summary.json', {})
    if build:
        summary = dict(build, unknown_or_inflight_HTTP=build.get('unknown_usage_HTTP', 0))
        display('BUILD_C41', '新模型建库 · 2题技术探针', build['completed'], build['planned'],
                'completed', 'Joint 2/2，产生5张临时卡；回放分析完成。全量建库跳过，临时库不用于正式交叉。', summary)
    edits = read(run/'FFS/analysis/single_edit_review/prefix_20261029/cases.json', {})
    if edits.get('status') == 'completed_prefix':
        count = len(edits['cases'])
        display('R01', '损失原因 · 单点修改本地复验', count, count, 'completed',
                '3题6次本地验证：两题恢复Joint，一题恢复功能但安全失败。仅完成该小批，不等于原最多6题全部完成。',
                dict(completed=count, planned=count, physical_HTTP=0, known_reported_tokens=0,
                     unknown_or_inflight_HTTP=0))
    initial_index = read(run/'FR/initial_recovery_20261029/execution_index.json', {})
    initial_root = run/'FR/initial_preparation_20261029'
    if initial_index.get('segments'):
        initial_root = type(run)(initial_index['segments'][-1])
    fr_state = read(initial_root/'state.json', {})
    contexts = list((run/'FR/contexts').glob('*.json'))
    missing = [tid for tid in ('110','156','167','461','479') if not (run/f'FR/contexts/{tid}.json').exists()]
    prep = read(initial_root/'summary.json', {})
    records = list((run/'FR/records').glob('*.json'))
    mapped = read(run/'FR/private_pair_mapping.json', [])
    expected_pairs = {}
    for pair in mapped:
        expected_pairs.setdefault(str(pair['task_id']), set()).add(pair['pair_id'])
    processed_pairs = {v['pair_id'] for v in read(run/'FR/reused_AI_labels.json', [])}
    for path in (run/'FR').glob('segment_*/labels/*.json'):
        label = read(path, {})
        if label.get('pair_id'):
            processed_pairs.add(label['pair_id'])
    labeled_tasks = sum(bool(pairs) and pairs <= processed_pairs for pairs in expected_pairs.values())
    fr_index = read(run/'FR/execution_index.json', {})
    prefix_state = read(type(run)(fr_index['segments'][-1])/'state.json', {}) if fr_index.get('segments') else {}
    fr_status = ('running' if packages['FR'].get('processes') else
                 'needs_technical_recovery' if prefix_state.get('status') == 'stopped_technical' else
                 'manual_pending' if prep.get('status') == 'completed' else
                 'waiting_window' if fr_state.get('status') == 'waiting_time_window' else
                 'needs_technical_recovery' if fr_state.get('status') == 'needs_technical_recovery' else
                 'running' if packages['FR'].get('processes') else 'preparing')
    display('FR', '经验检索质量 · 57题', labeled_tasks, 57, fr_status,
            f'初析已备{57-len(missing)}/57，候选池{len(records)}/57；已处理{len(processed_pairs)}个题卡对。先完成2题前缀检查，再接续其余标注；人工未确认。')
    fr_budget = read(type(run)(fr_index['segments'][-1])/'budget.json', {}) if fr_index.get('segments') else {}
    if fr_budget:
        packages['FR']['usage_summary'] = dict(
            known_reported_tokens=fr_budget.get('known_reported_tokens', 0),
            physical_HTTP=fr_budget.get('transport_attempts_including_prior', 0),
            unknown_or_inflight_HTTP=sum(e.get('status') != 'reported' for e in fr_budget.get('entries', [])))
    snapshot['retrieval_preparation'] = dict(status=fr_state.get('status', 'not_started'),
        completed=5-len(missing), planned=5, missing_ids=missing,
        summary=prep, contexts_on_disk=len(contexts))
    for key in ('FX_GATE', 'FX_EXTERNAL'):
        packages[key].update(display_status='waiting_dependency',
            display_note='等待完整冻结新卡库；v3.2已停用，Base/Plus另缺原验证镜像。')
    packages['FR_EXTRA'].update(display_status='waiting_dependency',
        display_note='先完成57题并分析扩大条件；未派发追加57题。')

    done = {'BUILD.run.probe', 'BUILD.run.probe.analysis', 'IR.prepare',
            'IR.association', 'IR.probe', 'IR.probe.analysis'}
    for task in view.get('tasks', []):
        tid = task['id']
        if tid in done and ((tid.startswith('BUILD') and build) or (tid.startswith('IR') and ir)):
            task.update(status='completed', display_status='completed', reason='verified_bounded_result')
        elif tid in ('IR.confirm','IR.confirm.analysis'):
            task.update(status='not_required', display_status='not_required', reason='negative_gate_stop')
        elif tid == 'FS.analysis':
            task.update(status='partial_analysis', display_status='partial_analysis', reason='2433格部分结果已分析；全量未完成')
        elif tid == 'FS.single_edit':
            task.update(status='partial_analysis', display_status='partial_analysis', reason='3题6次本地单点复验完成；原最多6题未全部执行')
        elif tid == 'FR.run':
            task.update(status=fr_status, display_status=fr_status, reason=packages['FR']['display_note'])
        elif tid in ('FR.analysis', 'FR.decide57', 'FR.human'):
            task.update(status='waiting_dependency', display_status='waiting_dependency',
                        reason='等待57题检索测量和分析；人工确认单独登记，不依赖已暂停的记忆标签。')
        elif (tid.startswith('Q.') and tid != 'Q.run' and not tid.startswith(('Q.K0.', 'Q.K1.', 'Q.K2.', 'Q.K3.'))) or tid.startswith('GR.'):
            task.update(status='paused', display_status='paused', reason='paused_by_user')
        elif task.get('status') == 'ready':
            task.update(display_status='manual_pending', reason='自主派发关闭，由当前窗口接续')
    counts = {}
    for task in view.get('tasks', []):
        counts[task['status']] = counts.get(task['status'], 0) + 1
    view.update(status='manual_supervision', counts=counts, next=None)

    sources = []
    for p in snapshot['packages']:
        if p['key'] == 'FQ_LEARN':
            sources.extend(p.get('stages', {}).values())
        else:
            sources.append(p.get('usage_summary', {}))
    if prep.get('budget') and not fr_budget:
        budget = prep['budget']
        sources.append(dict(known_reported_tokens=budget.get('known_reported_tokens', 0),
                            physical_HTTP=budget.get('transport_attempts_including_prior', 0),
                            unknown_or_inflight_HTTP=sum(e.get('status') != 'reported' for e in budget.get('entries', []))))
    snapshot['usage'] = {key: sum(s.get(key, 0) or 0 for s in sources)
        for key in ('known_reported_tokens','physical_HTTP','unknown_or_inflight_HTTP')}
    snapshot['usage']['note'] = '本轮已纳入原生累计摘要的实验用量；CLI独立计费，未报告Token不计为0费用。'
    snapshot['findings'] = [
        dict(title='Q学习已完成四轮', result='1122/1122；最后一轮Q覆盖769/1939张卡（39.7%）。', impact='同题回测已保存16/540，按要求暂停，尚无完整回测结论。'),
        dict(title='拆分经验未改善现有配对结果', result='486个BM/BFS有效配对：改善27、退步32，净少5个Joint通过。', impact='2433格部分结果已分析；剩余全量跳过。'),
        dict(title='边界提醒在12题中没有提高正确率', result='12题×两臂×两重复，48/48；原始编辑与边界提醒各Joint 8/24，改善0、退步0。', impact='回放一致，停止96格确认和后续全量。'),
        dict(title='从空库提卡链路已打通', result='2题Joint均通过，产生5张临时卡；17次HTTP，29944已报告Token。', impact='仅验证技术链路，未建立可供正式交叉比较的新卡库。'),
    ]
    if policy.get('status') == 'two_registered_batches_resumed':
        restored_view(snapshot, view, run, read, read(PLAN_FILE, {}))
    return view
