"""检索测量的独立首次分析准备；不生成代码、不学习Q或记忆标签。"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import urllib.request

from configs.cle_v41_relation_20261026.execution import StudyExecution
from configs.cle_v41_relation_20261026.wiring import SETTINGS
from configs.cle_v41_migration_20261025.resume import RecoveryBudget
from configs.cle_weekly_reduced_20261028 import retrieval_execute as native
from methods.sct_trajectory.run_memory_q_study import prepare_initial_analysis
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

ROOT = native.paths()
INITIALS = ROOT / 'initial_preparation_20261029'
IDS = ['110', '156', '167', '461', '479']


def initial_sources():
    index = ROOT/'initial_recovery_20261029/execution_index.json'
    return [INITIALS] + ([Path(p) for p in native.prep.read(index)['segments']] if index.exists() else [])


def initial_summary():
    return native.prep.read(initial_sources()[-1]/'summary.json')


def initial_inputs():
    public = native.prep.read(ROOT/'inputs/public_tasks.json')
    return {tid:public[tid] for tid in IDS}


def initials():
    public = initial_inputs()
    if INITIALS.exists():
        raise ReplayStop('existing_initial_preparation_requires_reconciliation_no_reissue')
    schedule = [{'cell_id':'initial_'+tid,'task_id':tid,'unit':'public_analysis_only'} for tid in IDS]
    protocol = {'protocol':'cle-FR57-five-initials-20261029-v1','planned_P7':5,
        'execution_units_are_P7':False,'paid_execution_enabled':True,'code_generations':0,'Q_updates':0,
        'budget_proposed':{'conservative_model_and_embedding_tokens':100000,
            'total_physical_HTTP_attempts':5,'embedding_HTTP_attempts_included_in_total':0},
        'parent_budget':'FR/execution_protocol.json; all initial wire charged to subsequent FR cumulative ledger',
        'authorization':'2026-10-29 user explicitly permits retrieval measurement; fill missing public analyses only'}
    from methods.sct_trajectory import run_closed_loop as provider
    def factory(identity):
        return provider._requester(SETTINGS['model'],180,4096,1,thinking='disabled',max_attempts=1,
            stream=True,hard_timeout=300,gate_wait_timeout=600,
            endpoint='https://api.chatanywhere.org/v1/chat/completions')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7897'}))
    io=StudyExecution(INITIALS,protocol,schedule,client_factory=factory,physical_open=opener.open,
        live=True,fixed_eight=False,protected_paths=[ROOT/'inputs/public_tasks.json'])
    write_json(INITIALS/'public_inputs.json',public)
    complete=[]
    try:
        with io.physical_records():
            for tid in IDS:
                if (ROOT/'contexts'/f'{tid}.json').exists():
                    raise ReplayStop('initial_context_created_by_another_process')
                value=prepare_initial_analysis({'task_description':public[tid]},io.request_for('initial_'+tid))
                write_json(ROOT/'contexts'/f'{tid}.json',{'task_id':tid,
                    'public_contract_digest':native.prep.contract_digest(public[tid]),
                    'initial_analysis':value,'source_file':str(INITIALS/'public_inputs.json'),
                    'source_repeat':1,'no_new_API':False,'purpose':'retrieval_only_public_initial'})
                complete.append(tid)
                io.save('summary',{'status':'running','completed':len(complete),'task_ids':complete})
        io.save('summary',{'status':'completed','completed':5,'task_ids':complete,
            'code_generations':0,'Q_updates':0,'budget':io.budget.snapshot()})
    except BaseException as exc:
        io.save('state',{'status':'needs_technical_recovery','completed':len(complete),'reason':str(exc)})
        raise


@contextmanager
def cumulative_initial_budget():
    """在原FR总上限内加入准备5份初析的物理账本，不另加预算。"""
    previous=native.RetrievalIO.__init__
    def initialize(self,*args,**kwargs):
        previous(self,*args,**kwargs)
        cap=self.protocol['budget_proposed']
        wires=[Path(p)/'wire' for p in self.resume_sources]+[p/'wire' for p in initial_sources()]
        self.budget=RecoveryBudget(self.root/'budget.json',list(dict.fromkeys(wires)),
            max_tokens=cap['conservative_model_and_embedding_tokens'],
            max_calls=cap['total_physical_HTTP_attempts'],
            max_embedding=cap['embedding_HTTP_attempts_included_in_total'])
        self.prior_physical_count=len(self.budget.entries)
    native.RetrievalIO.__init__=initialize
    try:
        yield
    finally:
        native.RetrievalIO.__init__=previous


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['check','initials'])
    a=p.parse_args()
    if a.action=='check':
        public=initial_inputs()
        from methods.sct_trajectory.context_pipeline import analysis_prompt
        bounds=[RecoveryBudget.make_entry({'model':SETTINGS['model'],'messages':[{'role':'user','content':analysis_prompt(t)}],
            'max_tokens':4096,'thinking':{'type':'disabled'},'temperature':0,'stream':True})['bound'] for t in public.values()]
        assert sum(bounds)<=100000
        print(json.dumps({'status':'passed','fixed_missing_initials':IDS,'request_bound_sum':sum(bounds),
            'max_HTTP':5,'new_HTTP':0,'Q_updates':0}));return
    initials()


if __name__=='__main__':
    main()
