"""冻结不看成绩的抽样名单，登记扩大门槛，保护尚未开始包的旧规格。"""
import copy
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
CONTROL = RUN/'scope_reduction_20261028'
SEED = '20261028-reduced-v1'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    from methods.sct_trajectory.replay_journal import write_json
    write_json(Path(path), value)


def sample(tasks, count, salt):
    """按CWE轮转、优先未覆盖family，再按固定哈希取样；不读取任何模型成绩。"""
    def rank(tid):
        return hashlib.sha256(f'{SEED}:{salt}:{tid}'.encode()).hexdigest()
    groups = defaultdict(list)
    for tid in sorted(tasks, key=rank):
        groups[str(tasks[tid]['CWE_ID'])].append(tid)
    chosen, families = [], set()
    while len(chosen) < count:
        for cwe in sorted(groups, key=lambda c: hashlib.sha256((salt+c).encode()).hexdigest()):
            available = groups[cwe]
            if not available:
                continue
            tid = next((i for i in available if tasks[i]['family_id'] not in families), available[0])
            chosen.append(tid)
            available.remove(tid)
            families.add(tasks[tid]['family_id'])
            if len(chosen) == count:
                break
        if not any(groups.values()) and len(chosen) < count:
            raise ValueError('sample_count_exceeds_pool')
    return chosen


def frozen_selection():
    path = CONTROL/'selection.json'
    if path.exists():
        return read(path)
    grow = read(RUN/'FG_LABELS/inputs_contract_v2/tasks.json')
    gate = read(RUN/'FQ_GATE/inputs_v3/tasks.json')
    split = read(RUN/'FG_LABELS/inputs/family_split.json')
    first, extra = [], []
    for role, a, b in [('train', 61, 62), ('development', 21, 20)]:
        available = {i: t for i, t in grow.items() if split['by_task'][i] == role}
        selected = sample(available, a, 'GR-'+role)
        first.extend(selected)
        extra.extend(sample({i: t for i, t in available.items() if i not in selected}, b, 'GR-extra-'+role))
    result = {'protocol': 'cle-reduced-scope-20261028-v1', 'seed': SEED,
        'selection_uses_outcomes': False, 'Q_intermediate_54': sample(grow, 54, 'Q'),
        'GR_first_82': first, 'GR_extra_82': extra,
        'FR_first_grow_27': sample({i:grow[i] for i in first}, 27, 'FR-grow'),
        'FR_first_gate_30': sample(gate, 30, 'FR-gate'),
        'original_family_split': split,
        'enlargement': {
            'Q': '54 fixed diagnostic tasks; final K3/Q1 all273; no automatic extra intermediate tasks',
            'GR': {'max_tasks': 164, 'min_training_label_families': 30,
                'min_classes_with_five_training_families': 2,
                'min_development_routed_levels': 2,
                'expand_if': 'initial labels have at least two preferred levels globally but engineering readiness is insufficient',
                'close_if': 'no memory intervention or fewer than two preferred levels, or still insufficient at164',
                'criterion_is': 'engineering readiness, not statistical evidence of Joint benefit'},
            'FR': {'max_tasks': 114, 'expand_if': 'major CWE strata missing or worst task-bootstrap 95% half-width exceeds0.10',
                'major_CWE': 'at least5% of its original pool', 'minimum_completed_pools': 57,
                'human_confirmation': 'never inferred from AI; final inference retains label source'}},
        'retained_full': ['FQ_LEARN1122', 'FFS2980', 'Q1_and_K3_1092', 'FQ_GATE2384', 'conditional_FG_GATE1788'],
        'unknown_cost_is_zero': False, 'paid_calls_by_preparation': 0}
    result['FR_extra_grow_27'] = sample({i:grow[i] for i in first if i not in result['FR_first_grow_27']},27,'FR-extra-grow')
    result['FR_extra_gate_30'] = sample({i:t for i,t in gate.items() if i not in result['FR_first_gate_30']},30,'FR-extra-gate')
    write(path, result)
    return result


def ensure_unstarted(package):
    path = RUN/package
    if (path/'execution_index.json').exists() or any(path.glob('segment_*/task_rows/*.json')):
        raise ValueError('cannot_reduce_started_package:'+package)


def archive(package, names):
    """只备份明确的未启动包配置；不移动活动运行和已完成响应。"""
    ensure_unstarted(package)
    target = CONTROL/'original_full'/package
    for name in names:
        source, dest = RUN/package/name, target/name
        if dest.exists() or not source.exists():
            continue
        if source.is_dir():
            shutil.copytree(source, dest)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)


def subset_split(split, tasks):
    value = copy.deepcopy(split)
    for role in ('train', 'development'):
        value[role+'_task_ids'] = [i for i in split[role+'_task_ids'] if i in tasks]
        value[role+'_families'] = sorted({tasks[i]['family_id'] for i in value[role+'_task_ids']})
    value['by_task'] = {i: split['by_task'][i] for i in tasks}
    value['task_family'] = {i: tasks[i]['family_id'] for i in tasks}
    value['family_cv_fold'] = {f: v for f,v in split['family_cv_fold'].items() if f in value['train_families']}
    return value


def prepare_labels(package, ids):
    """扩展批只生成新82题；首批820条完整轨迹留在原包，训练阶段合并。"""
    baseline = CONTROL/'original_full/FG_LABELS/inputs'
    inputs = RUN/package/'inputs'
    source = read(RUN/'FG_LABELS/inputs_contract_v2/tasks.json')
    tasks = {i: source[i] for i in ids}
    from configs.cle_weekly_granularity_20261027.evaluate import schedule
    protocol = read(baseline/'protocol.json')
    protocol.update(protocol='cle-reduced-granularity-'+package.lower()+'-20261028-v1',
        planned_P7=len(ids)*10, task_count=len(ids), sampling_protocol=str(CONTROL/'selection.json'),
        source_examples_file=str(inputs/'source_examples.json'),
        source_eligibility_file=str(inputs/'source_eligibility.json'),
        family_split_file=str(inputs/'family_split.json'),
        material_pair_upper_bound=len(ids)*12,
        material_budget_basis='selected tasks x2 repeats x2 attempts x3 cards; same source/public cache',
        budget_proposed={'conservative_model_and_embedding_tokens':len(ids)*2700000,
            'total_physical_HTTP_attempts':len(ids)*496,'embedding_HTTP_attempts_included_in_total':len(ids)*160},
        performance_gate_controls_dispatch=False)
    for name in ('source_examples.json','source_eligibility.json','reuse_manifest.json'):
        write(inputs/name, read(baseline/name))
    write(inputs/'tasks.json', tasks)
    write(inputs/'schedule.json', schedule(ids,tasks))
    write(inputs/'family_split.json', subset_split(frozen_selection()['original_family_split'],tasks))
    write(inputs/'protocol.json',protocol)
    return protocol


def prepare():
    selection = frozen_selection()
    for package,names in [('FQ_RETEST',['inputs','offline_checks.json']),
            ('FG_LABELS',['inputs','offline_checks.json']), ('FR',['inputs','execution_protocol.json','execution_schedule.json','execution_offline_checks.json','contexts']),
            ('FQ_GATE',['inputs_v3/protocol.json']),('FG_GATE',['inputs/protocol.json'])]:
        archive(package,names)
    inputs = RUN/'FQ_RETEST/inputs'
    protocol = read(CONTROL/'original_full/FQ_RETEST/inputs/protocol.json')
    tasks = read(inputs/'tasks.json')
    from configs.cle_weekly_eval_20261027.retest import schedule
    cells = [c for c in schedule(list(tasks),tasks) if c['condition'] in ('Q1','Q2_K3') or c['task_id'] in selection['Q_intermediate_54']]
    protocol.update(protocol='cle-reduced-frozen-q-primary273-intermediate54-20261028-v1',planned_P7=1416,
        task_count=273, diagnostic_task_count=54, sampling_protocol=str(CONTROL/'selection.json'),
        primary_comparisons=['Q2_K3-Q1'],diagnostic_conditions=['Q2_K0','Q2_K1','Q2_K2'],
        budget_proposed={'conservative_model_and_embedding_tokens':212400000,'total_physical_HTTP_attempts':56640,
            'embedding_HTTP_attempts_included_in_total':22656})
    write(inputs/'schedule.json',cells); write(inputs/'protocol.json',protocol)
    prepare_labels('FG_LABELS',selection['GR_first_82'])
    prepare_labels('FG_LABELS_EXTRA',selection['GR_extra_82'])
    qgate = read(RUN/'FQ_GATE/inputs_v3/protocol.json')
    qgate['completed_retest_required']=1416
    qgate['source_retest_protocol']=protocol['protocol']
    write(RUN/'FQ_GATE/inputs_v3/protocol.json',qgate)
    gate = read(RUN/'FG_GATE/inputs/protocol.json')
    gate.update(label_source_protocol=read(RUN/'FG_LABELS/inputs/protocol.json')['protocol'],
        model_protocol='cle-reduced-granularity-family-router-20261028-v1',
        adaptive_label_source=str(CONTROL/'GR_decision.json'))
    write(RUN/'FG_GATE/inputs/protocol.json',gate)
    # FR旧contexts全部保留在原备份；仅把57题引入当前测量。
    frids=selection['FR_first_grow_27']+selection['FR_first_gate_30']
    original=CONTROL/'original_full/FR/inputs'
    public=read(original/'public_tasks.json'); entries=read(original/'manifest.json')
    fp=read(original/'protocol.json')
    fp.update(protocol='cle-reduced-retrieval57-20261028-v1', task_count=57,pools={'D_grow':27,'D_gate':30},
        initial_pairs_cap=6384,sampling_protocol=str(CONTROL/'selection.json'))
    write(RUN/'FR/inputs/public_tasks.json',{i:public[i] for i in frids})
    write(RUN/'FR/inputs/manifest.json',[e for e in entries if e['task_id'] in frids])
    write(RUN/'FR/inputs/protocol.json',fp)
    for path in (RUN/'FR/contexts').glob('*.json'):
        if path.stem not in frids:
            path.unlink()  # 唯一副本已由上方archive完整保留；当前目录只保留预登记抽样题。
    for name in ('execution_protocol.json','execution_schedule.json'):
        path=RUN/'FR'/name
        if path.exists():
            path.unlink()  # 全量旧规格已备份，由新入口重新计算抽样上界。
    from . import retrieval_execute
    retrieval_execute.prepare()
    extraids=selection['FR_extra_grow_27']+selection['FR_extra_gate_30']
    write(RUN/'FR_EXTRA/inputs/public_tasks.json',{i:public[i] for i in extraids})
    write(RUN/'FR_EXTRA/inputs/manifest.json',[e for e in entries if e['task_id'] in extraids])
    fp.update(protocol='cle-reduced-retrieval-extra57-20261028-v1')
    write(RUN/'FR_EXTRA/inputs/protocol.json',fp)
    write(RUN/'FR_EXTRA/inputs/input_identity.json',read(original/'input_identity.json'))
    for i in extraids:
        cached=CONTROL/'original_full/FR/contexts'/(i+'.json')
        if cached.exists():
            write(RUN/'FR_EXTRA/contexts'/(i+'.json'),read(cached))
    from . import retrieval_extra_execute
    retrieval_extra_execute.prepare()
    for p in ('FQ_RETEST','FG_LABELS','FR','FG_LABELS_EXTRA'):
        # 测试结果由离线验证命令生成，准备阶段不伪签passed。
        write(RUN/p/'scope_revision.json',{'status':'prepared_pending_offline_checks','protocol':selection['protocol'],'new_API_calls':0})
    for p in ('FQ_RETEST','FG_LABELS','FG_LABELS_EXTRA','FQ_GATE','FG_GATE'):
        write(RUN/p/'offline_checks.json',{'status':'pending_reduced_scope_checks','new_API_calls':0})
    for p in ('FR','FR_EXTRA'):
        write(RUN/p/'execution_offline_checks.json',{'status':'pending_reduced_scope_checks','new_API_calls':0})
    write(CONTROL/'prepared.json', {'status':'prepared','Q_retest':1416,'GR_first':820,'GR_extra_max':820,
        'FR_first_tasks':57,'FR_max_tasks':114,'source':str(CONTROL/'selection.json'),'new_API_calls':0})
    return read(CONTROL/'prepared.json')


if __name__ == '__main__':
    print(json.dumps(prepare(),ensure_ascii=False))
