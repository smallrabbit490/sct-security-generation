"""B03R完整8格控制规则，使用原P7/请求器和日志，外部服务完全合成。"""
import copy
import json
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime
from pathlib import Path

from configs.cle_v41_relation_20261026 import offline_execution_check as fixture
from configs.cle_v41_relation_20261026 import offline_check as old
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed, ModelTimeWindowError
from methods.sct_trajectory.replay_journal import write_json
from configs.cle_v41_relation_20261026.execution import route_decision, StudyStop


class RelationExecutionTest(unittest.TestCase):
    def setUp(self):
        parent = (old.ROOT / 'translation_work/temp').resolve()
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='relation_execution_', dir=parent)
        self.root = Path(self.temp.name).resolve()
        assert self.root.is_relative_to(parent)
        self.addCleanup(self.temp.cleanup)
        self.number = 0

    def run_fixture(self, **kwargs):
        self.number += 1
        return fixture.fixture_run(self.root / str(self.number), **kwargs)

    def protocol(self, **caps):
        protocol = old.read(old.CFG / 'protocol.json')
        protocol['budget_proposed'].update(caps)
        return protocol

    def test_complete_eight_shared_usage_native_payloads_and_technical_gate(self):
        c, service, clock, state = self.run_fixture()
        self.assertEqual(state['status'], 'completed_offline_integration', state)
        self.assertEqual(len(c.rows), 8)
        self.assertEqual(sum(len(r['attempts']) for r in c.rows), 16)
        self.assertEqual(c.saved['technical_gate']['completed_cells'], 4)
        self.assertEqual(c.saved['completion_gate']['completed_cells'], 8)
        self.assertFalse(c.saved['technical_gate']['score_used_for_progression'])
        self.assertEqual(len(service.calls), len(c.budget.entries))
        self.assertEqual(len(list((c.root / 'wire').glob('*.request.json'))), len(service.calls))
        self.assertEqual(len([name for name in c.saved if name.startswith('plan_reviews/')]), 4)
        summaries = c.saved['logical_summary']
        self.assertEqual(sum(s['logical_requests'] for s in summaries.values()), len(service.calls))
        self.assertEqual(c.budget.charged(), sum(e['usage']['total_tokens'] for e in c.budget.entries))
        for call in service.calls:
            body = call['body']
            if body['model'] == 'text-embedding-3-large': continue
            self.assertEqual([m['role'] for m in body['messages']], ['user'])
            self.assertEqual(body['temperature'], 0)
            self.assertEqual(body['thinking'], {'type': 'disabled'})
            self.assertTrue(body['stream'])
            self.assertEqual(body['max_tokens'], 256 if body['messages'][0]['content'].startswith('Select fixture') else 4096)

    def test_original_window_boundaries_and_weekends(self):
        for value, blocked in [('2026-10-26T08:59:59+08:00', False), ('2026-10-26T09:00:00+08:00', True),
            ('2026-10-26T11:59:59+08:00', True), ('2026-10-26T12:00:00+08:00', False),
            ('2026-10-26T14:00:00+08:00', True), ('2026-10-26T17:59:59+08:00', True),
            ('2026-10-26T18:00:00+08:00', False), ('2026-10-31T09:00:00+08:00', False),
            ('2026-10-26T01:00:00+00:00', True)]:
            with self.subTest(value=value):
                if blocked:
                    with self.assertRaises(ModelTimeWindowError):
                        ensure_model_call_allowed('deepseek-v4.1-flash-1017', now=datetime.fromisoformat(value))
                else:
                    ensure_model_call_allowed('deepseek-v4.1-flash-1017', now=datetime.fromisoformat(value))

    def test_forbidden_start_waits_without_reserving_or_dispatching(self):
        c, service, clock, state = self.run_fixture(clock=fixture.Clock('2026-10-26T09:15:00+08:00'))
        self.assertEqual(state['completed_P7'], 8, state)
        self.assertEqual(clock.waits, 1)
        self.assertTrue(all(datetime.fromisoformat(call['time']).hour == 12 for call in service.calls))
        self.assertEqual(len(service.calls), len(c.budget.entries))

    def test_retry_crossing_prohibited_time_waits_and_counts_only_actual_attempts(self):
        c, service, clock, state = self.run_fixture(fail_first=True, cross_window=True)
        self.assertEqual(state['completed_P7'], 8, state)
        self.assertEqual(clock.waits, 1)
        self.assertEqual(c.budget.entries[0]['status'], 'failed_unknown')
        self.assertTrue(all(datetime.fromisoformat(v['time']).hour in (8, 12) for v in service.calls))
        logical = sum(s['logical_requests'] for s in c.saved['logical_summary'].values())
        self.assertEqual(len(service.calls), logical + 1)
        self.assertEqual(len(list((c.root/'wire').glob('*.request.json'))), len(service.calls))

    def test_zero_http_or_token_budget_blocks_before_physical_records(self):
        for cap in ({'total_physical_HTTP_attempts': 0}, {'conservative_model_and_embedding_tokens': 1}):
            with self.subTest(cap=cap):
                c, service, _, state = self.run_fixture(protocol=self.protocol(**cap))
                self.assertEqual(state['reason'], 'physical_budget_exhausted')
                self.assertEqual(service.calls, [])
                self.assertEqual(c.budget.entries, [])
                self.assertEqual(len(list((c.root/'wire').glob('*.request.json'))), 0)
                self.assertEqual(len(c.rows), 0)

    def test_embedding_budget_is_in_total_and_stops_before_selector(self):
        c, service, _, state = self.run_fixture(protocol=self.protocol(embedding_HTTP_attempts_included_in_total=0))
        self.assertEqual(state['reason'], 'physical_budget_exhausted')
        self.assertEqual(len(service.calls), 1)  # 仅共享初析，向量尚未派发
        self.assertNotIn('text-embedding-3-large', [e['model'] for e in c.budget.entries])
        self.assertFalse(service.generations)

    def test_retry_exhausts_http_cap_without_releasing_unknown_charge(self):
        c, service, _, state = self.run_fixture(protocol=self.protocol(total_physical_HTTP_attempts=1), fail_first=True)
        self.assertEqual(state['reason'], 'physical_budget_exhausted')
        self.assertEqual(len(service.calls), 1)
        self.assertEqual(c.budget.entries[0]['status'], 'failed_unknown')
        self.assertEqual(c.budget.charged(), c.budget.entries[0]['bound'])

    def test_missing_usage_keeps_reservations_and_completed_logical_responses(self):
        c, service, _, state = self.run_fixture(missing_usage=True)
        self.assertEqual(state['completed_P7'], 8, state)
        unknown = [e for e in c.budget.entries if e['usage'] is None]
        self.assertTrue(unknown)
        self.assertTrue(all(e['status'] == 'unknown_after_close' for e in unknown))
        expected = sum(e['bound'] if e['usage'] is None else e['usage']['total_tokens'] for e in c.budget.entries)
        self.assertEqual(c.budget.charged(), expected)

    def test_low_scores_do_not_gate_repeat_two_or_expand_beyond_eight(self):
        c, service, _, state = self.run_fixture(all_fail=True)
        self.assertEqual(state['completed_P7'], 8, state)
        self.assertFalse(any(a['joint'] for r in c.rows for a in r['attempts']))
        self.assertEqual({r['repeat'] for r in c.rows}, {1, 2})
        self.assertEqual(len({r['cell_id'] for r in c.rows}), 8)

    def test_all_three_plan_labels_are_accepted_and_recorded_before_generation(self):
        for label in ('explicit', 'ambiguous', 'absent'):
            with self.subTest(label=label):
                c, service, _, state = self.run_fixture(label=label, first_pass=True)
                self.assertEqual(state['completed_P7'], 8, state)
                reviews = [value for name, value in c.saved.items() if name.startswith('plan_reviews/')]
                self.assertEqual(len(reviews), 4)
                self.assertTrue(all(v['review']['label'] == label and v['before_generation'] for v in reviews))
                self.assertEqual(sum(service.generations.values()), 8)  # 原首次通过早停

    def test_missing_or_mismatched_review_preserves_prefix_and_never_generates(self):
        for option, reason in [('no_review', 'waiting_plan_review'), ('bad_review', 'plan_review_missing_or_mismatched')]:
            c, service, _, state = self.run_fixture(**{option: True})
            self.assertEqual(state['reason'], reason)
            self.assertFalse(service.generations)
            self.assertEqual(len(c.rows), 0)
            self.assertTrue(c.saved['shared_prefixes/1409_r1_K']['events'])

    def test_native_format_degradation_is_not_technical_abort_or_forced_adoption(self):
        c, service, _, state = self.run_fixture(malformed_analysis=True)
        self.assertEqual(state['completed_P7'], 8, state)
        self.assertTrue(all(not a['generation']['cards'] for r in c.rows for a in r['attempts']))
        self.assertTrue(all('experience_analysis:' in a['generation']['error_type'] for r in c.rows for a in r['attempts']))

    def test_environment_failure_and_wrong_model_stop_new_dispatch(self):
        c, service, _, state = self.run_fixture(environment_error=True)
        self.assertEqual(state['reason'], 'validation_environment_failure')
        self.assertEqual(len(c.rows), 1)
        self.assertNotIn('technical_gate', c.saved)
        c, service, _, state = self.run_fixture(wrong_model=True)
        self.assertEqual(state['reason'], 'reported_model_mismatch')
        self.assertEqual(len(service.calls), 1)
        self.assertEqual(len(c.rows), 0)

    def test_unresolved_after_completed_prefix_preserved_and_cannot_replay_into_dispatch(self):
        c, service, _, state = self.run_fixture(fail_identity='1409_r1_K_bind')
        self.assertEqual(len(c.rows), 1)
        self.assertIn('shared_prefixes/1409_r1_K', c.saved)
        self.assertTrue(any(d['status'] != 'completed' for j in c.journals.values() for d in j.records.values()))
        r, repeated, _, replay_state = self.run_fixture(replay_source=c.root)
        self.assertEqual(replay_state['reason'], 'replay_source_contains_unresolved_request')
        self.assertEqual(repeated.calls, [])
        self.assertEqual(repeated.factories, [])

    def test_full_zero_api_replay_reuses_requests_and_never_recharges(self):
        c, service, _, state = self.run_fixture()
        r, repeated, _, replay_state = self.run_fixture(replay_source=c.root)
        self.assertEqual(replay_state['completed_P7'], 8, replay_state)
        self.assertEqual(fixture.normalized(c.rows), fixture.normalized(r.rows))
        self.assertEqual(repeated.calls, [])
        self.assertEqual(repeated.factories, [])
        self.assertEqual(r.budget.entries, [])

    def test_atomic_file_retry_is_bounded_and_never_dispatches(self):
        original = Path.replace
        attempts = []
        def transient(path, target):
            attempts.append(str(path))
            if len(attempts) == 1: raise PermissionError('offline transient file lock')
            return original(path, target)
        path = self.root / 'atomic.json'
        with patch.object(Path, 'replace', transient):
            write_json(path, {'value': 'saved without HTTP'})
        self.assertEqual(len(attempts), 2)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['value'], 'saved without HTTP')
        with patch.object(Path, 'replace', side_effect=PermissionError('persistent file lock')) as replace:
            with self.assertRaises(PermissionError): write_json(path, {'value': 'new'})
            self.assertEqual(replace.call_count, 3)

    def test_persistent_artifact_failure_is_engineering_stop_not_model_degradation(self):
        c, service, _, state = self.run_fixture(first_pass=True)
        before = len(service.calls)
        with patch('configs.cle_v41_relation_20261026.execution.write_json', side_effect=PermissionError):
            with self.assertRaises(StudyStop): c.save('fixture_critical', {'new': True})
        self.assertEqual(c.reason, 'artifact_write_failure')
        self.assertEqual(len(service.calls), before)

    def test_route_ceiling_negative_and_missing_evidence_never_expand(self):
        c, _, _, _ = self.run_fixture(first_pass=True)
        rows = copy.deepcopy(c.rows)
        self.assertEqual(route_decision(rows, 'E')['status'], 'inconclusive_ceiling')
        for row in rows:
            if row['relation_arm'] == 'E_bind': row['attempts'][-1]['joint'] = row['repeat'] == 2
        d = route_decision(rows, 'E')
        self.assertEqual(d['status'], 'inconclusive_missing_code_relation_evidence')
        code = {r['cell_id']: {'relation_status': 'consistent', 'verified_rescue_path': 'synthetic verified path'}
                for r in rows if r['relation_arm'] == 'E_rel'}
        d = route_decision(rows, 'E', code_reviews=code, plan_labels={'1409_r1_E': 'explicit'})
        self.assertEqual(d['status'], 'limited_development_signal')
        self.assertFalse(d['automatic_expansion'])
        self.assertEqual(d['scope'], 'implementation_of_explicit_plan')
        d = route_decision(rows, 'E', code_reviews=code, plan_labels={'1409_r1_E': 'absent'})
        self.assertEqual(d['scope'], 'omission_or_ambiguous_plan_reminder')
        for row in rows:
            if row['relation_arm'] == 'E_rel': row['attempts'][-1]['joint'] = False
        self.assertEqual(route_decision(rows, 'E')['status'], 'stop_this_reminder_version')

    def test_route_incomplete_unmeasured_and_no_adoption_stay_inconclusive(self):
        c, _, _, _ = self.run_fixture(first_pass=True)
        self.assertEqual(route_decision(c.rows[:4], 'E')['status'], 'inconclusive_incomplete')
        rows = copy.deepcopy(c.rows)
        for row in rows:
            if row['relation_arm'] == 'K_rel': row['attempts'][0]['generation']['cards'] = []
        self.assertEqual(route_decision(rows, 'K')['status'], 'inconclusive_no_c0_memory_adoption')
        rows[0]['attempts'][-1]['measured'] = False
        self.assertEqual(route_decision(rows, 'K')['status'], 'inconclusive_unmeasured')


if __name__ == '__main__':
    unittest.main()
