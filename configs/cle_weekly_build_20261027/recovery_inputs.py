"""Check saved build sources and construct a fresh recovery output path."""
import hashlib
from pathlib import Path

from .prepare_inputs import ROOT
from .prepare_inputs import RUN
from methods.sct_trajectory.replay_journal import ReplayStop


def verify_source_snapshot(segment):
    snapshot = Path(segment) / 'source_bundle'
    if not snapshot.is_dir():
        raise ReplayStop('build_source_snapshot_missing')
    files = list(snapshot.rglob('*.py'))
    if not files:
        raise ReplayStop('build_source_snapshot_empty')
    changed = []
    for saved in files:
        current = ROOT / saved.relative_to(snapshot)
        if not current.is_file() or hashlib.sha256(current.read_bytes()).digest() != hashlib.sha256(saved.read_bytes()).digest():
            changed.append(str(saved.relative_to(snapshot)))
    if changed:
        raise ReplayStop('build_source_changed_before_recovery:' + changed[0])
    saved_helper = Path(segment) / 'source_bundle_external/transport_resume_stream_20261027.py'
    current_helper = RUN / 'FQ_LEARN/transport_resume_stream_20261027.py'
    if not saved_helper.is_file() or not current_helper.is_file() or saved_helper.read_bytes() != current_helper.read_bytes():
        raise ReplayStop('build_external_recovery_helper_changed')
    return len(files)


def recovery_arguments(arguments, output, embedding_cache):
    args = list(arguments)
    for flag, value in (('--out', output), ('--embedding-cache', embedding_cache)):
        if args.count(flag) != 1:
            raise ReplayStop('invalid_build_recovery_arguments:' + flag)
        args[args.index(flag) + 1] = str(value)
    # A saved-prefix replay starts from an empty pool and consumes saved
    # responses; native --resume-from would skip work needed for that replay.
    if '--resume-from' in args:
        raise ReplayStop('unexpected_native_resume_flag')
    return args


def verify_input_snapshot(segment):
    snapshot = Path(segment) / 'input_snapshot'
    names = ('inputs/plt_tasks.json', 'inputs/pools.json', 'inputs/manifest.json',
             'native_arguments.json', 'budget.json')
    for name in names:
        saved, current = snapshot / name, RUN / 'BUILD_C41' / name
        if not saved.is_file() or not current.is_file() or saved.read_bytes() != current.read_bytes():
            raise ReplayStop('build_input_changed_before_recovery:' + name)
    return len(names)
