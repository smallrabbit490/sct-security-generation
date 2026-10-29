"""C01五档呈现与C02离线排程/统计；不调API或训练分类器。"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from . import runner
from .memory_view_study import RAW,read,write
from methods.sct_trajectory.memory_granularity import LEVELS,apply_memory_level,payload_character_count
from methods.sct_trajectory.context_pipeline import experience_text

VERSION='cle-memory-granularity-source-bound-v1'


class GranularityProvider:
    """同题首次使用共享卡，修复按本臂代码重新检索并保持档位；L0修复也无卡。"""
    def __init__(self,start,level,retrieve,materials,target_family):
        if level not in LEVELS:raise ValueError('unknown_memory_level')
        self.start,self.level,self.retrieve=start,level,retrieve
        self.materials,self.target_family=materials,target_family
        self.calls=0
        self.preparation_error=None
        self.pending_materials=None
        # 首次材料在原P7开始前准备，缺材料时一个生成请求也不发送。
        self.first_cards,self.first_trace=self.render(start['selected_cards'],copy.deepcopy(start['retrieval_trace']),start['query'])
        self.first_trace['shared_first_selection']=True

    def render(self,cards,trace,query):
        if len(cards)>3:raise ValueError('original_CLE_card_cap_exceeded')
        before=[card['invariant_id'] for card in cards]
        try:
            material={} if self.level=='L0' else self.materials(cards,self.start['public_contract'],self.level)
            rendered=apply_memory_level(cards,self.level,self.start['public_contract'],
                target_family=self.target_family,**material)
        except Exception as exc:
            # 原流水线会记录降级再尝试生成；局部准备失败另外关闭网络边界，原异常不吞掉。
            self.preparation_error=exc
            self.pending_materials={'cards':copy.deepcopy(cards),'query':copy.deepcopy(query),
                                    'trace_before_view':copy.deepcopy(trace),'level':self.level}
            exc.retrieval_trace={**copy.deepcopy(trace),'status':'preparation_required',
                'memory_level':self.level,'pre_level_selected_ids':before,
                'preparation_error':type(exc).__name__}
            raise
        trace.update(memory_level=self.level,pre_level_selected_ids=before,
                     selected_ids=[card['invariant_id'] for card in rendered])
        return rendered,trace

    def __call__(self,query):
        if self.preparation_error:raise self.preparation_error
        self.calls+=1
        if self.calls==1:
            if query!=self.start['query']:
                self.preparation_error=ValueError('first_query_differs_from_shared_start')
                self.pending_materials={'cards':copy.deepcopy(self.start['selected_cards']),
                    'query':copy.deepcopy(query),'trace_before_view':copy.deepcopy(self.first_trace),'level':self.level}
                raise self.preparation_error
            return copy.deepcopy(self.first_cards),copy.deepcopy(self.first_trace)
        elif self.level=='L0':
            cards,trace=[],{'status':'completed','candidate_ids':[],'selected_ids':[],
                            'reason':'L0_memory_disabled_in_repair'}
        else:
            cards,trace=self.retrieve(query)
            if trace.get('status')!='completed':raise ValueError('repair_selection_not_completed')
        return self.render(cards,trace,query)


def run_one_level(task,start,level,requester,retrieve,materials):
    """复用原P7及验证器；调用者提供已有请求器，本函数不创建网络客户端、不更新Q。"""
    if runner.plt_contract(task)!=start['public_contract']:
        raise ValueError('task_public_contract_differs_from_shared_start')
    provider=GranularityProvider(start,level,retrieve,materials,task['family_id'])
    def prepared_request(prompt):
        if provider.preparation_error:raise provider.preparation_error
        return requester(prompt)
    row=runner.run_one('PLT',task,'P7',prepared_request,{'full':[]},None,
        retrieval_mode='semantic_llm',delta=-1,lambda_q=.5,max_experiences=3,candidate_order=None,
        initial_analysis=copy.deepcopy(start['initial_analysis']),retrieval_provider=provider)
    row.update(memory_level=level,protocol=VERSION,Q_updates=0)
    if 'repeat' in start:
        row.update(repeat=start['repeat'],cell_id=f"{row['task_id']}_r{start['repeat']}_{level}")
    if provider.preparation_error:
        row['preparation_blocked_reason']=type(provider.preparation_error).__name__+':'+str(provider.preparation_error)
        row['pending_materials']=provider.pending_materials
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['preview','plan','summarize'])
    parser.add_argument('--rows',type=Path,help='原生C02 rows.jsonl；不含预览或B02记录')
    parser.add_argument('--cell-costs',type=Path,help='独立逐格完整成本JSONL；缺项不补零')
    parser.add_argument('--out',type=Path,help='新输出目录，不覆盖旧产物')
    args=parser.parse_args()
    if args.command!='preview':
        from .granularity_results import make_schedule,evaluate
        config=runner.ROOT/'configs/cle_memory_mechanisms_20261023'
        protocol=read(config/'granularity_protocol.json')
        schedule=make_schedule(read(config/'manifest.json'),protocol['schedule_seed'])
        if args.command=='plan' and (args.rows or args.cell_costs):
            parser.error('plan只生成固定排程；结果输入使用summarize')
        def read_jsonl(path):
            if path is None:return []
            return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        summary=evaluate(schedule,read_jsonl(args.rows),native_protocol=VERSION,
                         cell_costs=read_jsonl(args.cell_costs))
        out=args.out or RAW/('C02_offline_plan_v1' if args.command=='plan' else 'C02_offline_summary_v1')
        out.mkdir(exist_ok=False)
        write(out/'schedule.json',schedule)
        write(out/'protocol.json',protocol)
        write(out/'summary.json',summary)
        with (out/'level_outcomes.jsonl').open('w',encoding='utf-8') as stream:
            for row in summary['level_outcomes']:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps({'output':str(out),'scheduled_total':len(schedule),
            'received_pilot_rows':summary['received_pilot_rows'],'C1':summary['C1'],
            'API_calls':0,'paid_execution_enabled':False},ensure_ascii=False),flush=True)
        return
    if args.rows or args.cell_costs or args.out:
        parser.error('preview沿用既有固定输出；结果参数仅用于plan或summarize')
    from configs.cle_memory_mechanisms_20261023.prepare_granularity_views import load_materials
    specs,bindings,examples=load_materials()
    source=RAW/'B02_shared_starts/shared_starts'
    out=RAW/'C01_granularity_preview_v2'
    tasks={str(t['index']):t for t in read(RAW/'v2/tasks_train.json')}
    previews=[]
    paths=sorted(source.glob('*.json'))
    for path in paths:
        start=read(path);tid=start['task_id']
        for level in LEVELS:
            cards=apply_memory_level(start['selected_cards'],level,start['public_contract'],card_specs=specs,
                bindings=bindings[tid],examples=examples,target_family=tasks[tid]['family_id'])
            previews.append({'task_id':tid,'repeat':start['repeat'],'level':level,
                'pre_level_selected_ids':[c['invariant_id'] for c in start['selected_cards']],
                'presented_ids':[c['invariant_id'] for c in cards],
                'model_visible_memory':experience_text(cards),'characters':payload_character_count(cards),
                'API_calls':0,'is_experiment_score':False})
    # 所有免费呈现先成功，再写新目录；已有结果仍不覆盖。
    out.mkdir(exist_ok=False)
    with (out/'granularity_previews.jsonl').open('w',encoding='utf-8') as stream:
        for row in previews:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    summary={'protocol':VERSION,'shared_starts':len(paths),'levels':list(LEVELS),'rendered_cells':len(previews),
        'unique_card_specs':len(specs),'unique_task_card_bindings':sum(len(b) for b in bindings.values()),
        'API_calls':0,'Q_updates':0,'new_generated_code':0,'classifier_trained':False,
        'real_P7_completed':0,'is_experiment_score':False,
        'other_selected_cards_require_preparation':True}
    write(out/'summary.json',summary)
    write(runner.ROOT/'results/curated/cle_memory_mechanisms_20261023/granularity_preview.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
