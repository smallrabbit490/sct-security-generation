"""把v08未来分析交付和已验证入口落实到自主队列，不改活动/已完成任务。"""
import argparse
import copy
import json
import tempfile

from configs.cle_weekly_reduced_20261028.scope import ROOT, RUN, read, write
from tools.cle_live_workbench.autonomy import AutonomousPlan
from tools.build_cle_research_stage_map import status_snapshot


def bind(plan):
    result = copy.deepcopy(plan)
    by = {t['id']:t for t in result['tasks']}
    by['Q.K3.analysis']['narrative'] = {
        'source':'docs/research/CLE-STORY-20261028-nine-ideas.md',
        'sections':['idea01','idea02'], 'skill':'cle-idea-narrative'}
    for task in result['tasks']:
        if task.get('narrative'):
            task['narrative']['receipt'] = 'workbench_monitor/autonomy/deliveries/' + task['id'] + '/receipt.json'
    by['BUILD.run']['commands'] = ['configs.cle_weekly_build_readiness_20261027.execute check',
                                  'configs.cle_weekly_build_readiness_20261027.execute launch']
    by['BUILD.analysis']['commands'] = ['configs.cle_weekly_build_readiness_20261027.finish']
    by['CROSS.v41']['commands'] = ['configs.cle_weekly_cross_readiness_20261028.execute check',
                                 'configs.cle_weekly_cross_readiness_20261028.execute launch --workers {workers}']
    by['CROSS.v41']['max_workers'] = 3
    by['CROSS.analysis']['commands'] = ['configs.cle_weekly_cross_readiness_20261028.execute replay',
                                      'configs.cle_weekly_cross_readiness_20261028.execute finalize']
    result['plan_id'] = 'cle-autonomy-20261028-executable-narrative-v7'
    return result


def install(preview=False):
    path = ROOT / 'tools/cle_live_workbench/autonomy_plan.json'
    before = read(path)
    after = bind(before)
    snapshot = status_snapshot()
    old = {t['id']:t for t in before['tasks']}
    changed = [t['id'] for t in after['tasks'] if old[t['id']] != t]
    protected = {t['id'] for t in snapshot['tasks'] if t['status'] in ('completed','running','waiting_window')}
    protected.update(('Q.run','FS.run'))
    if protected.intersection(changed):
        raise ValueError('cannot_change_active_or_completed:' + ','.join(sorted(protected.intersection(changed))))
    with tempfile.TemporaryDirectory() as temp:
        AutonomousPlan(temp,after)
    result = {'changed_tasks':changed, 'protected_unchanged':sorted(protected),
              'experiment_API_calls':0, 'scientific_inputs_changed':False, 'plan_id':after['plan_id']}
    if not preview:
        out = RUN / 'narrative_plan_20261028/execution_binding'
        if not (out / 'before_plan.json').exists():
            write(out / 'before_plan.json',before)
        if read(path) != before:
            raise ValueError('plan_changed_during_binding')
        write(path,after)
        write(out / 'install_result.json',result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['preview','install'])
    print(json.dumps(install(parser.parse_args().action=='preview'),ensure_ascii=False))
