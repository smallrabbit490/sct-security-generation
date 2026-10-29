"""Frozen V4.1 C41 evaluation using the original P7 consumer."""
import copy
import hashlib
import shutil

from configs.cle_weekly_eval_20261027 import retest as base
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from .prepare import RUN, read

PACKAGE = RUN / 'FX_GATE/V41_C41'


def snapshot_sources(destination, prior):
    directories = ('methods', 'src', 'configs/cle_weekly_full_20261027',
                   'configs/cle_weekly_eval_20261027', 'configs/cle_weekly_cross_20261027',
                   'configs/cle_v41_relation_20261026', 'configs/cle_v41_migration_20261025',
                   'configs/cle_weekly_proxy_recovery_20261027')
    paths = [p for directory in directories for p in (base.ROOT / directory).rglob('*.py')]
    identity = {p.relative_to(base.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    for previous in prior:
        if read(previous / 'source_identity.json') != identity:
            raise ReplayStop('cross_saved_runtime_source_changed')
    for source in paths:
        target = destination / 'source_bundle' / source.relative_to(base.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    write_json(destination / 'source_identity.json', identity)


class NewBankRetest(base.FrozenRetest):
    conditions = ('C41',)
    controlled_conditions = ('C41',)
    reference_bank = 'C41'
    pool = 'D_gate'
    runner_module = 'configs.cle_weekly_cross_20261027.new_bank_runner'

    def package_directory(self):
        return PACKAGE

    def additional_protected_paths(self):
        return [self.input_directory() / 'shared_initials.json']

    def __init__(self, sources=(), *, offline=False, destination=None):
        self.shared_initials = read(self.input_directory() / 'shared_initials.json')
        original = base.snapshot_sources
        base.snapshot_sources = snapshot_sources
        try:
            super().__init__(sources, offline=offline, destination=destination)
        finally:
            base.snapshot_sources = original

    def policy(self, arm):
        if arm != 'C41':
            raise ValueError('unknown_new_bank_arm')
        return {'candidate_order': None, 'delta': None, 'record_arm': 'Q0', 'Q_checkpoint': None}

    def start(self, task, repeat):
        key = f'{task["index"]}_r{repeat}'
        value = copy.deepcopy(self.shared_initials[key])
        self.io.save('shared_starts/' + key, value)
        return value

    def run_p7(self, cell, start, request):
        return base.runner.run_one('PLT', self.tasks[cell['task_id']], 'P7', request,
            {'full': self.banks['C41']}, self.embedding, retrieval_mode='semantic_llm',
            delta=None, candidate_order=None, max_experiences=3,
            initial_analysis=copy.deepcopy(start['initial_analysis']))

    def decorate_row(self, row, cell):
        row.update(model_arm='V41', bank_arm='C41', Q_sorting=False,
                   shared_initial_source='FFS matched task and repeat')

    def validate_saved_rows(self, rows):
        super().validate_saved_rows(rows)
        for row in rows:
            self.inspect_native_row(row)
