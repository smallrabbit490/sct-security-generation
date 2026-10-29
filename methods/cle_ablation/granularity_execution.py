"""C02逐格请求、完整成本与原P7接续；不创建客户端或授予付费执行权限。

复用RequestBudget和run_one_level。每格隔离请求/修复检索；已返回的相同请求
只回放，失败或未决请求不自动重发。调用者负责冻结协议及实际客户端的启用门。
"""
from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .granularity_results import native_errors, execution_gate
from .memory_granularity_study import VERSION, run_one_level
from .memory_view_study import read
from .provider_adaptation import carried_budget, normalize_structured_response
from .run_joint_contract import BudgetExceeded
from methods.sct_trajectory.memory_granularity import GranularityPreparationRequired
from methods.sct_trajectory.selector_protocol import SelectorPrompt


def save(path, value):
    """网络前持久化预算/未决状态；原子替换避免中断留下半份状态。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


class SavedOperationBlocked(RuntimeError):
    """保存的操作失败、未决或输入变化；保留原件，禁止自动重新付费。"""


class CellJournal:
    """一格的聊天/选卡、向量和修复检索；全局预算由所有格共用。"""
    def __init__(self, out, cell, budget, native_request):
        self.out, self.cell, self.budget = Path(out), cell, budget
        self.native_request = native_request
        self.positions = {'chat': 0, 'selector': 0, 'retrieval': 0}
        self.replayed = 0
        self.blocked = None

    def flush(self):
        save(self.out / 'cost.json', self.budget.snapshot())

    def _operation(self, kind, value, invoke, completion_cap):
        if self.blocked:
            raise self.blocked
        directory = self.out / 'requests' / self.cell['cell_id'] / kind
        serialized = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        if kind == 'embedding':
            # 向量缓存命中会省略调用，不能用聊天的序号定位；只匹配本格相同输入。
            paths = sorted(directory.glob('*.json'))
            path = next((p for p in paths if read(p)['input'] == serialized),
                        directory / f'{len(paths) + 1:04d}.json')
        else:
            self.positions[kind] += 1
            path = directory / f'{self.positions[kind]:04d}.json'
        if path.exists():
            saved = read(path)
            if saved['input'] != serialized or saved['status'] != 'returned':
                self.blocked = SavedOperationBlocked(f'{kind}:{saved["status"]}:saved_input_or_state_not_reusable')
                raise self.blocked
            record = next((r for r in self.budget.records
                           if r.get('operation_file') == str(path.relative_to(self.out))), None)
            if record is None:
                self.blocked = SavedOperationBlocked('returned_operation_missing_budget_record')
                raise self.blocked
            # 响应已落盘而预算终态尚未来得及写入时，用原响应补记usage，绝不新增调用。
            record.update(status='returned', usage=saved['raw_response'].get('usage'),
                          model=saved['raw_response'].get('model'))
            self.flush()
            self.replayed += 1
            return copy.deepcopy(saved['delivered_response'])

        record = self.budget.reserve(kind, serialized, attempts=1, completion_cap=completion_cap)
        record.update(cell_id=self.cell['cell_id'], source_protocol=VERSION,
                      operation_file=str(path.relative_to(self.out)))
        saved = {'kind': kind, 'input': serialized, 'status': 'submitted',
                 'cell_id': self.cell['cell_id'], 'submitted_utc': datetime.now(timezone.utc).isoformat()}
        save(path, saved)
        self.flush()  # 先保存已占预算与未决请求，再发生真实第三方调用。
        try:
            response = invoke()
            record.update(status='returned', usage=response.get('usage'), model=response.get('model'))
            delivered, note = ((response, None) if kind == 'embedding' else
                               normalize_structured_response(value, response))
            saved.update(status='returned', raw_response=response,
                         delivered_response=delivered, normalization=note)
            save(path, saved)
            return copy.deepcopy(delivered)
        except Exception as exc:
            self.blocked = exc
            record.update(status='failed', error_type=type(exc).__name__)
            saved.update(status='failed', error_type=type(exc).__name__)
            save(path, saved)
            raise
        finally:
            self.flush()

    def request(self, prompt):
        """选择器保留原SelectorPrompt及其截止；每个真实操作只请求一次。"""
        selector = isinstance(prompt, SelectorPrompt)
        return self._operation('selector' if selector else 'chat', prompt,
                               lambda: self.native_request(prompt), 256 if selector else 4096)

    def embedding(self, texts, invoke):
        """向量适配接点；invoke返回vectors及真实usage，缓存命中不调用本方法。"""
        return self._operation('embedding', texts, invoke, 0)

    def retrieve(self, query, invoke):
        """只复用本格相同修复查询的完整选卡，防止恢复时再付费选一次。"""
        if self.blocked:
            raise self.blocked
        self.positions['retrieval'] += 1
        path = self.out / 'retrievals' / self.cell['cell_id'] / f'{self.positions["retrieval"]:04d}.json'
        if path.exists():
            saved = read(path)
            if saved['query'] != query or saved['status'] != 'returned':
                self.blocked = SavedOperationBlocked('retrieval:saved_input_or_state_not_reusable')
                raise self.blocked
            self.replayed += 1
            return copy.deepcopy(saved['cards']), copy.deepcopy(saved['trace'])
        saved = {'query': copy.deepcopy(query), 'status': 'submitted'}
        save(path, saved)
        try:
            cards, trace = invoke(query, self)
            if trace.get('status') != 'completed':
                raise ValueError('repair_selection_not_completed')
            saved.update(status='returned', cards=cards, trace=trace)
            save(path, saved)
            return cards, trace
        except Exception as exc:
            self.blocked = exc
            saved.update(status='failed', error_type=type(exc).__name__)
            save(path, saved)
            raise

    def cost(self, *, preparation_cost_complete, completed):
        """包括本格复析、规划、生成、修复选卡及向量；共享首次起点另外报告。"""
        records = [r for r in self.budget.records if r.get('cell_id') == self.cell['cell_id']]
        known = [r for r in records if r['status'] == 'returned' and isinstance(r.get('usage'), dict)
                 and type(r['usage'].get('prompt_tokens')) is int and r['usage']['prompt_tokens'] >= 0]
        complete = completed and preparation_cost_complete and bool(records) and len(known) == len(records)
        return {'cell_id': self.cell['cell_id'], 'complete': complete,
                'prompt_tokens': sum(r['usage']['prompt_tokens'] for r in known) if complete else None,
                'known_prompt_tokens': sum(r['usage']['prompt_tokens'] for r in known),
                'known_embedding_prompt_tokens': sum(r['usage']['prompt_tokens'] for r in known if r['kind'] == 'embedding'),
                'unknown_input_usage_operations': len(records) - len(known),
                'preparation_cost_complete': preparation_cost_complete,
                'shared_start_cost_included': False, 'replayed_operations_this_invocation': self.replayed}


def run_cells(cells, tasks, starts, materials, native_request, retrieve, execution, out, *,
              resume=False, preparation_cost_complete=False, is_experiment_score=False,
              runtime_metadata=None, stop_after=None, phase=None, prepare_start=None):
    """固定前缀的原P7编排；客户端由调用者提供，本函数不恢复授权或改变Q。

    retrieve(query,journal)必须通过journal.request/embedding记账；静态制作材料
    可以明确声明零模型成本，未说明材料成本时不产生首选粒度标签。
    """
    out = Path(out)
    if len({c['cell_id'] for c in cells}) != len(cells):
        raise ValueError('duplicate_execution_cell')
    limit = len(cells) if stop_after is None else stop_after
    if not 1 <= limit <= len(cells):
        raise ValueError('invalid_fixed_prefix_limit')
    if resume:
        if read(out / 'schedule.json') != cells:
            raise ValueError('resume_schedule_changed')
        metadata = read(out / 'run_metadata.json')
        if metadata['is_experiment_score'] != is_experiment_score:
            raise ValueError('resume_execution_or_evidence_kind_changed')
        if metadata.get('runtime') != runtime_metadata:
            raise ValueError('resume_frozen_runtime_changed')
        previous_limit = metadata.get('prefix_limit', len(cells))
        extending = limit > previous_limit
        if limit < previous_limit:
            raise ValueError('cannot_shrink_execution_prefix')
        if metadata['execution'] != execution:
            old = metadata['execution']
            caps = ('max_http_attempts', 'max_conservative_tokens', 'max_embedding_attempts')
            if not extending or any(execution[k] < old[k] for k in caps):
                raise ValueError('resume_execution_or_evidence_kind_changed')
            # 阶段升级的新累计预算必须由调用入口授权；旧已占费用全部带入，不清零。
            metadata.setdefault('execution_history', []).append(old)
            metadata['execution'] = execution
        if (metadata['status'] not in ('running', 'waiting_materials', 'waiting_shared_start')
                and not (metadata['status'] == 'completed_fixed_prefix' and extending)):
            raise SavedOperationBlocked('terminal_run_must_not_be_restarted')
        budget = carried_budget(execution, [read(out / 'cost.json')])
    else:
        out.mkdir(parents=True, exist_ok=False)
        save(out / 'schedule.json', cells)
        budget = carried_budget(execution, [])
        metadata = {'protocol': VERSION, 'status': 'running', 'execution': execution,
                    'planned_P7': len(cells), 'completed_P7': 0, 'Q_updates': 0,
                    'is_experiment_score': is_experiment_score, 'runtime': runtime_metadata,
                    'prefix_limit': limit, 'phase': phase}
        save(out / 'run_metadata.json', metadata)
        save(out / 'cost.json', budget.snapshot())
    # 实际并发与付费边界；遗留锁须核对真实进程后由执行者处理，不能仅凭超时删除。
    lock = out / 'writer.lock'
    handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(handle, str(os.getpid()).encode())
    os.close(handle)
    rows = []
    try:
        completed_paths = list((out / 'task_rows').glob('*.json'))
        expected_ids = [c['cell_id'] for c in cells]
        saved_ids = {p.stem for p in completed_paths}
        if saved_ids != set(expected_ids[:len(saved_ids)]):
            raise ValueError('saved_rows_must_be_completed_prefix')
        if len(saved_ids) > limit:
            raise ValueError('saved_rows_exceed_requested_phase')
        metadata.update(prefix_limit=limit, phase=phase)
        for cell in cells[:limit]:
            row_path = out / 'task_rows' / f'{cell["cell_id"]}.json'
            if row_path.exists():
                row = read(row_path)
                if (any(row.get(k) != cell[k] for k in ('cell_id', 'task_id', 'repeat', 'memory_level'))
                        or row.get('protocol') != VERSION or row.get('Q_updates') != 0
                        or row.get('is_experiment_score') != is_experiment_score
                        or native_errors(row)):
                    raise SavedOperationBlocked('saved_prefix_is_not_qualified_P7')
                rows.append(row)
                continue
            if phase:
                gate = execution_gate(cells, rows, phase, native_protocol=VERSION)
                if not gate['ready']:
                    metadata.update(status='stopped_stage_gate', stage_gate=gate)
                    break
            journal = CellJournal(out, cell, budget, native_request)
            metadata.pop('reason', None)
            metadata.update(status='running', current_cell=cell['cell_id'])
            save(out / 'run_metadata.json', metadata)
            try:
                tid, repeat = cell['task_id'], cell['repeat']
                if (tid, repeat) not in starts:
                    path = out / 'shared_starts' / f'{tid}_r{repeat}.json'
                    if path.exists():
                        starts[tid, repeat] = read(path)
                    elif prepare_start is None:
                        metadata.update(status='waiting_shared_start', reason=f'{tid}_r{repeat}')
                        break
                    else:
                        shared_cell = {'cell_id': f'shared_{tid}_r{repeat}'}
                        common = CellJournal(out, shared_cell, budget, native_request)
                        starts[tid, repeat] = prepare_start(tasks[tid], repeat, common, retrieve)
                        save(path, starts[tid, repeat])
                        save(out / 'shared_start_costs' / f'{tid}_r{repeat}.json',
                             common.cost(preparation_cost_complete=True, completed=True))
                row = run_one_level(tasks[tid], starts[tid, repeat], cell['memory_level'],
                    journal.request, lambda query: journal.retrieve(query, retrieve), materials[tid])
            except GranularityPreparationRequired as exc:
                metadata.update(status='waiting_materials', reason=str(exc))
                save(out / 'pending_materials' / f'{cell["cell_id"]}.json',
                     {'cell': cell, 'selected_cards': starts[tid, repeat]['selected_cards'],
                      'public_contract': starts[tid, repeat]['public_contract'], 'reason': str(exc)})
                save(out / 'run_metadata.json', metadata)
                break
            except Exception as exc:
                metadata.update(status='stopped_technical_error', error_type=type(exc).__name__)
                save(out / 'run_metadata.json', metadata)
                raise
            row.update(**cell, protocol=VERSION, Q_updates=0, is_experiment_score=is_experiment_score)
            complete = not row.get('preparation_blocked_reason')
            cost = journal.cost(preparation_cost_complete=preparation_cost_complete, completed=complete)
            save(out / 'cell_costs' / f'{cell["cell_id"]}.json', cost)
            if not complete:
                destination = out / 'partials' / cell['cell_id']
                number = len(list(destination.glob('*.json'))) + 1
                save(destination / f'{number:04d}.json', row)
                metadata.update(status='waiting_materials', reason=row['preparation_blocked_reason'])
                save(out / 'run_metadata.json', metadata)
                break
            save(row_path, row)
            for position, attempt in enumerate(row['attempts']):
                save(out / 'attempts' / cell['cell_id'] / f'{position}.json', attempt)
                for key in ('generation', 'validation', 'retrieval_trace'):
                    if key in attempt:
                        save(out / key / cell['cell_id'] / f'{position}.json', attempt[key])
            rows.append(row)
            metadata.update(completed_P7=len(rows), last_completed_cell=cell['cell_id'])
            errors = native_errors(row)
            if errors:
                metadata.update(status='stopped_budget' if budget.exhausted else 'stopped_technical_error', errors=errors)
                save(out / 'run_metadata.json', metadata)
                break
            save(out / 'run_metadata.json', metadata)
        else:
            metadata.update(status='completed_fixed_prefix', completed_P7=len(rows))
        return metadata
    except (BudgetExceeded, SavedOperationBlocked) as exc:
        metadata.update(status='stopped_budget' if isinstance(exc, BudgetExceeded) else 'blocked_saved_operation',
                        reason=str(exc), completed_P7=len(rows))
        raise
    finally:
        save(out / 'run_metadata.json', metadata)
        save(out / 'cost.json', budget.snapshot())
        # task_rows是逐格权威记录；派生JSONL可在中断后重建，不重复追加已付费格。
        with (out / 'rows.jsonl').open('w', encoding='utf-8') as stream:
            for path in [out / 'task_rows' / f'{c["cell_id"]}.json' for c in cells]:
                if path.exists():
                    stream.write(json.dumps(read(path), ensure_ascii=False) + '\n')
        with (out / 'cell_costs.jsonl').open('w', encoding='utf-8') as stream:
            for path in [out / 'cell_costs' / f'{c["cell_id"]}.json' for c in cells]:
                if path.exists():
                    stream.write(json.dumps(read(path), ensure_ascii=False) + '\n')
        lock.unlink()
