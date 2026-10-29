from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from tools.cle_live_workbench.app import PACKAGES, read_json, write_json
from tools.cle_live_workbench.current_view import apply_current_view


class CurrentViewTests(unittest.TestCase):
    def test_pauses_bounded_results_and_cost_are_display_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_json(root/'supervised_remaining_20261029.json', {'execution_owner':'current_chat'})
            write_json(root/'probe_relay_20261028/Q.retest/segment_002/summary.json',
                       dict(completed=16, known_reported_tokens=100, physical_HTTP=7))
            write_json(root/'probe_relay_20261028/BUILD.run/summary.json',
                       dict(completed=2, planned=2, known_reported_tokens=30, physical_HTTP=3, unknown_usage_HTTP=1))
            snapshot = {'packages':[dict(key=k, label=v[0], planned=v[1], completed=0,
                summary={}, stages={}, usage_summary={}, processes=[]) for k,v in PACKAGES.items()]}
            snapshot['packages'][0]['stages'] = {'K0':dict(known_reported_tokens=50, physical_HTTP=2)}
            original = {'tasks':[dict(id='Q.retest', status='blocked_external'),
                                  dict(id='BUILD.run.probe', status='ready'),
                                  dict(id='BUILD.run', status='deferred_full')]}
            before = deepcopy(original)
            view = apply_current_view(snapshot, original, root, read_json)
            self.assertEqual(original, before)
            self.assertEqual(view['tasks'][0]['display_status'], 'paused')
            self.assertEqual(view['tasks'][1]['status'], 'completed')
            self.assertEqual(view['tasks'][2]['status'], 'deferred_full')
            packages = {p['key']:p for p in snapshot['packages']}
            self.assertEqual(packages['FQ_RETEST']['display_completed'], 16)
            self.assertEqual(packages['FQ_RETEST']['completed'], 0)
            self.assertEqual(snapshot['usage']['physical_HTTP'], 12)
            self.assertEqual(snapshot['usage']['known_reported_tokens'], 180)
            self.assertEqual(snapshot['usage']['unknown_or_inflight_HTTP'], 1)

    def test_unrelated_run_keeps_existing_view(self):
        with tempfile.TemporaryDirectory() as folder:
            view = {'tasks':[]}
            snapshot = {'packages':[]}
            self.assertIs(apply_current_view(snapshot, view, Path(folder), read_json), view)
            self.assertNotIn('control', snapshot)
