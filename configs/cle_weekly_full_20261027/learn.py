"""固定1939卡的新模型在线Q学习：K0(D_init)→K1/K2/K3(D_grow)。

单worker消费完整名单，原P7完成后按实际采用卡更新Q。日志和费用复用既有执行层，
已完成任务从保存行重建Q，不重买响应；未决HTTP不自动再发。此入口不运行其他包。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from configs.cle_v41_relation_20261026.execution import StudyExecution
from configs.cle_v41_relation_20261026 import wiring
from methods.cle_ablation import runner
from methods.cle_ablation.run_memory_q import prepare_shared_initial, record_result
from methods.cle_ablation.run_memory_q_online import credit, inspect_row, mechanism
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from methods.sct_trajectory.run_memory_q_study import _write_memory
from .prepare import ROOT, CFG, RUN, STAGES, PROTOCOL, read, disk_check, configure_validation


def now():
    return datetime.now(timezone.utc).isoformat()


def save_memory(path, bank):
    temp = path.with_suffix('.jsonl.tmp')
    _write_memory(temp, bank)
    temp.replace(path)


def body_state(bank):
    items = []
    for card in bank:
        item = card.to_dict()
        item.pop('q_value', None)
        item.pop('q_visits', None)
        items.append(item)
    return items


def apply_credit(row, bank, eligible):
    events = credit(row, bank, eligible=eligible)
    for event in events:
        event['protocol'] = PROTOCOL
        event['learning_checkpoint'] = row['learning_checkpoint']
    return events


def restore_prefix(cells, sources, bank, eligibility):
    """只沿固定完成前缀重建Q；原子保存行是已完成付费任务的恢复依据。"""
    saved = {}
    for root in sources:
        for path in (Path(root)/'task_rows').glob('*.json'):
            row = read(path)
            key = row['cell_id']
            if key in saved and saved[key] != row:
                raise ReplayStop('conflicting_completed_task_row:' + key)
            saved[key] = row
    prefix, gap = [], False
    expected = {cell['cell_id'] for cell in cells}
    if set(saved) - expected:
        raise ReplayStop('completed_task_outside_manifest')
    for cell in cells:
        key = cell['cell_id']
        if key not in saved:
            gap = True
            continue
        if gap:
            raise ReplayStop('learning_results_not_completed_prefix')
        row = saved[key]
        inspect_row(row)
        events = apply_credit(row, bank, eligibility[row['task_id']]['reward_eligible'])
        if events != row['q_credit_events']:
            raise ReplayStop('credit_replay_diverged:' + key)
        prefix.append(row)
    return prefix


def unresolved_requests(sources):
    # 成功物理响应尚未解析也不能盲目重发；保留现场交给零API恢复。
    return [str(path) for root in sources for path in (Path(root)/'journals').glob('*/requests/*.json')
            if read(path).get('status') != 'completed']


def source_snapshot(destination, prior=()):
    paths = []
    for directory in ('methods', 'src', 'configs/cle_weekly_full_20261027',
                      'configs/cle_v41_relation_20261026', 'configs/cle_v41_migration_20261025'):
        paths.extend((ROOT/directory).rglob('*.py'))
    identity = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    if prior and read(Path(prior[0])/'source_identity.json') != identity:
        raise ReplayStop('runtime_source_changed_before_resume_requires_explicit_review')
    for p in paths:
        target = destination/'source_bundle'/p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
    write_json(destination/'source_identity.json', identity)


class LearningStage:
    def __init__(self, stage, pool, sources=(), *, offline=False, destination=None):
        self.stage, self.pool = stage, pool
        self.sources = [Path(p) for p in sources]
        self.offline = offline
        protocol = read(RUN/'protocol.json')
        manifest = read(RUN/'manifest.json')
        self.ids = manifest['pools'][pool]
        self.tasks = read(RUN/'shared_inputs'/f'tasks_{pool}.json')
        self.eligibility = read(RUN/'preflight/qualification.json')['tasks']
        self.cells = [{'cell_id': f'{stage}_{key}', 'task_id':key, 'pool':pool,
                       'repeat':1, 'condition':'Q2', 'learning_checkpoint':stage} for key in self.ids]
        stage_index = [s for s,p in STAGES].index(stage)
        self.bank_source = (RUN/'shared_inputs/memory1939_q0.jsonl' if stage_index==0 else
                            RUN/'FQ_LEARN/frozen'/f'{STAGES[stage_index-1][0]}.jsonl')
        self.bank = runner.load_memory(self.bank_source)
        self.body_before = body_state(self.bank)
        self.rows = [] if offline else restore_prefix(self.cells, self.sources, self.bank, self.eligibility)
        if unresolved_requests(self.sources):
            raise ReplayStop('unresolved_saved_requests_require_zero_API_reconciliation')
        self.out = Path(destination) if destination else RUN/'FQ_LEARN'/stage/f'segment_{len(self.sources)+1:03d}'
        cap = read(RUN/'budget.json')['stages'][stage]
        protocol.update(planned_P7=len(self.cells), stage=stage, pool=pool,
            paid_execution_enabled=not offline, bank_source=str(self.bank_source),
            budget_proposed={'conservative_model_and_embedding_tokens':cap['tokens'],
                'total_physical_HTTP_attempts':cap['HTTP'],
                'embedding_HTTP_attempts_included_in_total':cap['embedding_HTTP']})
        self.slots = threading.Semaphore(1)
        from methods.sct_trajectory import run_closed_loop as native
        def forbidden(*args, **kwargs):
            raise ReplayStop('zero_API_replay_no_network_or_missing_response')
        def factory(identity):
            if offline:
                return forbidden
            return native._requester(wiring.SETTINGS['model'],180,4096,4,
                thinking='disabled', stream=True, endpoint='https://api.chatanywhere.org/v1/chat/completions',
                hard_timeout=300, gate_wait_timeout=600, semaphore=self.slots)
        direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.io = StudyExecution(self.out, protocol, self.cells, client_factory=factory,
            physical_open=forbidden if offline else direct.open, live=not offline, fixed_eight=False,
            resume_sources=self.sources, protected_paths=[self.bank_source, RUN/'protocol.json', RUN/'manifest.json',
                                                        RUN/'shared_inputs'/f'tasks_{pool}.json'])
        if offline:
            self.io.replay_source = self.out
            self.io.state['evidence_kind'] = 'zero_API_saved_response_replay'
        self.io.save('launch', {'pid':os.getpid(), 'started_utc':now(), 'stage':stage,
            'runner':'configs.cle_weekly_full_20261027.learn', 'branch':subprocess.check_output(
                ['git','branch','--show-current'], cwd=ROOT,text=True).strip(),
            'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'resume_sources':list(map(str,self.sources)), 'offline_replay':offline})
        source_snapshot(self.out, self.sources)
        import methods.sct_trajectory.semantic_retrieval as semantic
        semantic.MAX_SELECTOR_CHARS = 420000
        from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
        cache = self.out/'embeddings.sqlite3'
        seed = self.sources[-1]/'embeddings.sqlite3' if self.sources else RUN/'shared_inputs/embeddings.sqlite3'
        with closing(sqlite3.connect(f'file:{seed.as_posix()}?mode=ro',uri=True)) as src:
            with closing(sqlite3.connect(cache)) as dst:
                src.backup(dst)
        self.embedding = EmbeddingClient(cache_path=cache, key_loader=forbidden if offline else native.load_key,
            semaphore=self.slots, timeout=180, hard_timeout=300, gate_wait_timeout=600)
        original = self.embedding._request
        def embedded(texts):
            if offline:
                return forbidden()
            def call(items):
                before = self.embedding.usage
                vectors = original(items)
                after = self.embedding.usage
                usage = None if after['usage_missing_calls']>before['usage_missing_calls'] else {
                    k:after[k]-before[k] for k in ('prompt_tokens','total_tokens')}
                return {'vectors':vectors, 'usage':usage}
            return self.io.embedding(texts,call)['vectors']
        self.embedding._request = embedded
        configure_validation()

    def checkpoint(self, status):
        first = [r['attempts'][0] for r in self.rows]
        final = [r['final'] for r in self.rows]
        def metrics(items):
            return {key:sum(bool(r.get(key)) for r in items) for key in ('functional','security','joint','measured')}
        events = [e for r in self.rows for e in r['q_credit_events']]
        budget = self.io.budget.snapshot()
        summary = {'protocol':PROTOCOL, 'stage':self.stage, 'pool':self.pool, 'status':status,
            'planned':len(self.cells), 'completed':len(self.rows), 'first':metrics(first), 'final':metrics(final),
            'Q_covered_cards':sum(n.q_visits>0 for n in self.bank), 'card_count':len(self.bank),
            'Q_coverage':sum(n.q_visits>0 for n in self.bank)/len(self.bank),
            'credited_events':sum(e['credited'] for e in events),
            'adopted_positions':sum(len(a.get('generation',{}).get('cards',[])) for r in self.rows for a in r['attempts']),
            'known_reported_tokens':budget['known_reported_tokens'],
            'physical_HTTP':budget['transport_attempts_including_prior'],
            'unknown_or_inflight_HTTP':sum(not self.io.budget.valid_usage(e['usage']) for e in budget['entries']),
            'currency_cost':None, 'no_performance_stop':True, 'updated_utc':now()}
        self.io.save('summary', summary)
        self.io.state.update(status=status, completed_P7=len(self.rows), stage=self.stage, updated_utc=now())
        self.io.save('state', self.io.state)
        self.io.save('logical_summary', {key:j.summary() for key,j in self.io.journals.items()})
        self.io.save('budget', budget)
        temp = self.out/'rows.jsonl.tmp'
        temp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in self.rows),encoding='utf-8')
        temp.replace(self.out/'rows.jsonl')
        return summary

    def execute(self):
        self.checkpoint('running_replay' if self.offline else 'running')
        try:
            with self.io.physical_records():
                for cell in self.cells[len(self.rows):]:
                    disk_check()
                    task = self.tasks[cell['task_id']]
                    request = self.io.request_for(cell['cell_id'])
                    started = perf_counter()
                    shared = prepare_shared_initial(task, request)
                    self.io.save('initials/'+cell['cell_id'],shared)
                    if self.io.reason:
                        raise ReplayStop(self.io.reason)
                    row = runner.run_one('PLT',task,'P7',request,{'full':self.bank},self.embedding,
                        retrieval_mode='semantic_llm', delta=-1, lambda_q=.5, max_experiences=3,
                        candidate_order='q', initial_analysis=shared['initial_analysis'])
                    if self.io.reason:
                        self.io.save('incomplete_tasks/'+cell['cell_id'],row)
                        raise ReplayStop(self.io.reason)
                    row = record_result(row,task,'Q2',self.pool,perf_counter()-started)
                    row.update(cell_id=cell['cell_id'], learning_checkpoint=self.stage, protocol=PROTOCOL,
                        repeat=1, shared_initial_error=shared['error_type'],
                        reward_eligible=self.eligibility[cell['task_id']]['reward_eligible'])
                    inspect_row(row)
                    row['mechanism'] = mechanism(row,self.bank)
                    row['q_credit_events'] = apply_credit(row,self.bank,row['reward_eligible'])
                    # 同一个原子行包含代码和Q事件；即使后续摘要写入失败，恢复也不会重跑此题。
                    self.io.save('task_rows/'+cell['cell_id'],row)
                    self.rows.append(row)
                    self.checkpoint('running_replay' if self.offline else 'running')
                    if len(self.rows)==2:
                        self.io.save('technical_probe',{'status':'passed', 'included_in_full_manifest':True,
                            'completed':2, 'joint_not_used_as_gate':True})
            if body_state(self.bank) != self.body_before or self.io.input_state()!=self.io.inputs_before:
                raise ReplayStop('frozen_text_lifecycle_or_inputs_changed')
            if self.offline:
                originals = {r['cell_id']:r for root in self.sources for p in (root/'task_rows').glob('*.json') for r in [read(p)]}
                diffs = [r['cell_id'] for r in self.rows if any(r['final'].get(k)!=originals[r['cell_id']]['final'].get(k)
                         for k in ('code','functional','security','joint','measured')) or
                         r['q_credit_events']!=originals[r['cell_id']]['q_credit_events']]
                self.io.save('replay_result',{'status':'passed' if not diffs else 'different',
                    'completed':len(self.rows), 'differences':diffs, 'new_HTTP':len(list((self.out/'wire').glob('*.request.json')))})
                if diffs:
                    raise ReplayStop('native_replay_diverged')
            else:
                save_memory(RUN/'FQ_LEARN/frozen'/f'{self.stage}.jsonl', self.bank)
            return self.checkpoint('completed')
        except BaseException as exc:
            self.io.state['reason'] = self.io.reason or (str(exc) if isinstance(exc,ReplayStop) else type(exc).__name__)
            self.checkpoint('needs_technical_recovery')
            raise
        finally:
            self.embedding._db.close()


def coordinate(resume_stage=None):
    """本包固定四段，不按Joint/覆盖率提前停；进程互斥防止自动化重复派发。"""
    import msvcrt
    disk_check()
    lock = (RUN/'learning.lock').open('a+b')
    if lock.tell()==0:
        lock.write(b'0'); lock.flush()
    lock.seek(0)
    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        if not read(RUN/'preflight/state.json').get('FQ_LEARN_ready'):
            raise ReplayStop('offline_runner_gate_not_ready')
        index_file = RUN/'execution_index.json'
        index = read(index_file) if index_file.exists() else {}
        for stage,pool in STAGES:
            key = 'FQ_LEARN_'+stage
            sources = [Path(p) for p in index.get(key,[])]
            if sources and read(sources[-1]/'state.json')['status']=='completed':
                continue
            if sources and stage != resume_stage:
                raise ReplayStop('existing_segment_requires_explicit_recovery_command:'+stage)
            if unresolved_requests(sources):
                raise ReplayStop('unresolved_saved_requests_require_zero_API_reconciliation:'+stage)
            destination = RUN/'FQ_LEARN'/stage/f'segment_{len(sources)+1:03d}'
            index[key] = list(map(str,sources))+[str(destination)]
            write_json(index_file,index)
            write_json(RUN/'supervisor_state.json',{'status':'running', 'package':'FQ_LEARN',
                'stage':stage, 'pid':os.getpid(), 'updated_utc':now(), 'root':str(RUN)})
            worker = LearningStage(stage,pool,sources)
            worker.execute()
            # 每轮向量持久化后下一轮复用相同文本；不共享代码或初析模型响应。
            with closing(sqlite3.connect(f'file:{(worker.out/"embeddings.sqlite3").as_posix()}?mode=ro',uri=True)) as src:
                with closing(sqlite3.connect(RUN/'shared_inputs/embeddings.sqlite3')) as dst:
                    src.backup(dst)
        write_json(RUN/'supervisor_state.json',{'status':'awaiting_agent_analysis','package':'FQ_LEARN',
            'completed':1122,'updated_utc':now(),'next':'zero_API_replay_and_case_analysis_then_FQ_RETEST'})
    except BaseException as exc:
        state = read(RUN/'supervisor_state.json') if (RUN/'supervisor_state.json').exists() else {}
        write_json(RUN/'supervisor_state.json',{**state,'status':'needs_technical_recovery',
            'reason':str(exc) if isinstance(exc,ReplayStop) else type(exc).__name__, 'updated_utc':now()})
        raise
    finally:
        lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()


def launch():
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    ensure_model_call_allowed(wiring.SETTINGS['model'])
    if not read(RUN/'preflight/state.json').get('FQ_LEARN_ready'):
        raise ReplayStop('offline_runner_gate_not_ready')
    script = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*configs.cle_weekly_full_20261027.learn run*' } | Select-Object ProcessId | ConvertTo-Json -Compress"
    actual = subprocess.run(['powershell','-NoProfile','-Command',script],capture_output=True,text=True,check=True)
    if actual.stdout.strip():
        print(json.dumps({'status':'already_running','process':json.loads(actual.stdout)}));return
    out=RUN/'FQ_LEARN';out.mkdir(parents=True,exist_ok=True)
    with (out/'stdout.log').open('a',encoding='utf-8') as stdout,(out/'stderr.log').open('a',encoding='utf-8') as stderr:
        process=subprocess.Popen([sys.executable,'-B','-X','utf8','-m','configs.cle_weekly_full_20261027.learn','run'],
            cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    write_json(RUN/'launch.json',{'pid':process.pid,'started_utc':now(),'package':'FQ_LEARN','root':str(RUN)})
    print(json.dumps({'status':'launched','pid':process.pid,'root':str(RUN)}))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['launch','run','resume','replay'])
    p.add_argument('--stage',choices=[s for s,pool in STAGES])
    args=p.parse_args()
    if args.action=='launch':launch()
    elif args.action=='run':coordinate()
    elif args.action=='resume':
        if not args.stage:p.error('--stage required for explicit resume')
        coordinate(resume_stage=args.stage)
    else:
        if not args.stage:p.error('--stage required for replay')
        sources=read(RUN/'execution_index.json')['FQ_LEARN_'+args.stage]
        if read(Path(sources[-1])/'state.json')['status']!='completed':
            raise ReplayStop('stage_incomplete_no_full_replay')
        destination=RUN/'FQ_LEARN'/args.stage/'zero_API_replay'
        if (destination/'replay_result.json').exists():
            print(json.dumps(read(destination/'replay_result.json')));return
        LearningStage(args.stage,dict(STAGES)[args.stage],sources,offline=True,destination=destination).execute()


if __name__=='__main__':main()
