"""Carry native task identity into nested executor jobs without changing prompts."""
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from concurrent.futures import ThreadPoolExecutor

CURRENT_TASK = ContextVar('cle_build_task_identity', default=None)


@contextmanager
def task_identity(identity):
    token = CURRENT_TASK.set(str(identity))
    try:
        yield
    finally:
        CURRENT_TASK.reset(token)


@contextmanager
def propagate_task_identity():
    original = ThreadPoolExecutor.submit

    def submit(executor, function, /, *args, **kwargs):
        context = copy_context()
        return original(executor, context.run, function, *args, **kwargs)

    ThreadPoolExecutor.submit = submit
    try:
        yield
    finally:
        ThreadPoolExecutor.submit = original


@contextmanager
def native_task_scopes():
    from methods.sct_trajectory.closed_loop import CleRunner
    from methods.sct_trajectory import global_gate_runtime

    phase1, phase2 = CleRunner._phase1_one, CleRunner._phase2_one
    gate = global_gate_runtime.run_global_gate

    def scoped_phase1(self, row, *args, **kwargs):
        with task_identity('phase1:' + str(row['index'])):
            return phase1(self, row, *args, **kwargs)

    def scoped_phase2(self, row, retriever, repairs, round_index=1, *args, **kwargs):
        with task_identity('phase2:' + str(round_index) + ':' + str(row['index'])):
            return phase2(self, row, retriever, repairs, round_index, *args, **kwargs)

    def scoped_gate(tasks, retrieve, generate, validate, **kwargs):
        def wrap(function, label):
            def call(row, *args, **inner_kwargs):
                with task_identity('gate:' + label + ':' + str(row['index'])):
                    return function(row, *args, **inner_kwargs)
            return call
        if kwargs.get('retrieve_filtered') is not None:
            kwargs['retrieve_filtered'] = wrap(kwargs['retrieve_filtered'], 'retrieve_filtered')
        return gate(tasks, wrap(retrieve, 'retrieve'), wrap(generate, 'generate'),
                    validate, **kwargs)

    CleRunner._phase1_one, CleRunner._phase2_one = scoped_phase1, scoped_phase2
    global_gate_runtime.run_global_gate = scoped_gate
    try:
        with propagate_task_identity():
            yield
    finally:
        CleRunner._phase1_one, CleRunner._phase2_one = phase1, phase2
        global_gate_runtime.run_global_gate = gate
