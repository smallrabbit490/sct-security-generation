"""Publish the new bank only after its real native run and replay match."""
import argparse
import hashlib
import json
from pathlib import Path

from .prepare_inputs import RUN, read
from .completion import rows
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

BUILD = RUN / 'BUILD_C41'


def certify(replay_result):
    replay_result = Path(replay_result)
    result = read(replay_result)
    sources = [Path(path) for path in result.get('saved_segments', [])]
    if (result.get('status') != 'primary_outputs_match' or result.get('new_HTTP') != 0
            or result.get('comparison', {}).get('status') != 'primary_outputs_match' or not sources):
        raise ReplayStop('build_real_replay_not_passed')
    state = read(sources[-1] / 'state.json')
    native_check = read(sources[-1] / 'native_verification.json')
    if (state.get('status') != 'completed_pending_verification'
            or native_check.get('status') != 'native_outputs_complete_pending_replay_and_analysis'):
        raise ReplayStop('build_real_native_run_not_completed')
    original = Path(result['original_native_output'])
    expected = BUILD / 'native' / sources[-1].name
    if original.resolve() != expected.resolve():
        raise ReplayStop('build_replay_original_output_mismatch')
    bank = original / 'frozen/m_star.jsonl'
    cards = rows(bank)
    certificate = {'status': 'verified_native_primary_replay', 'bank_path': str(bank),
                   'bank_sha256': hashlib.sha256(bank.read_bytes()).hexdigest(),
                   'card_count': len(cards), 'model': 'deepseek-v4.1-flash-1017',
                   'replay_result': str(replay_result), 'source_segments': [str(p) for p in sources],
                   'meaning': 'technical replay confirmation, not a performance or human-review claim',
                   'API_calls': 0}
    output = BUILD / 'verified_library.json'
    if output.exists() and read(output) != certificate:
        raise ReplayStop('existing_verified_library_differs')
    write_json(output, certificate)
    return certificate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('replay_result')
    args = parser.parse_args()
    print(json.dumps(certify(args.replay_result), ensure_ascii=False))


if __name__ == '__main__':
    main()
