"""Q参与的训练顺序、实际采用授信和门控冻结边界；全部离线。"""
import copy
import unittest

from methods.cle_ablation import run_memory_q_online as study
from methods.sct_trajectory.hsk_tree import SecurityInvariantNode


def node(identifier):
    return SecurityInvariantNode(invariant_id=identifier, cwe='22', high_level_invariant='Keep file access inside its root.')


def attempt(adopted, joint, completed=True):
    return {'attempt': 0, 'code': 'def f(): return 1', 'measured': True, 'joint': joint,
        'generation': {'workflow_completed': completed,
            'retrieved_cards': [{'invariant_id': 'a'}, {'invariant_id': 'b'}],
            'cards': [{'invariant_id': i} for i in adopted]},
        'validation': {'evidence': {'functional': {'status': 'pass'},
            'security': {'status': 'pass' if joint else 'fail'}}}}


def row(*attempts):
    return {'task_id': '1', 'family_id': 'f', 'pool': 'D_init', 'arm': 'Q2', 'attempts': list(attempts)}


class OnlineQTests(unittest.TestCase):
    def test_actual_adoption_unique_only(self):
        bank = [node('a'), node('b')]
        events = study.credit(row(attempt(['a', 'a'], True)), bank)
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(bank[0].q_value, .3)
        self.assertEqual(bank[0].q_visits, 1)
        self.assertEqual(bank[1].q_visits, 0)

    def test_sequential_feedback_changes_next_state(self):
        bank = [node('a'), node('b')]
        study.credit(row(attempt(['a'], True)), bank)
        study.credit(row(attempt(['a'], False)), bank)
        self.assertAlmostEqual(bank[0].q_value, -.09)
        self.assertEqual(bank[0].q_visits, 2)

    def test_c0_then_c1(self):
        bank = [node('a'), node('b')]
        study.credit(row(attempt(['a'], False), attempt(['a'], True)), bank)
        self.assertAlmostEqual(bank[0].q_value, .09)

    def test_incomplete_and_unqualified_not_credited(self):
        for complete, eligible in [(False, True), (True, False)]:
            bank = [node('a'), node('b')]
            events = study.credit(row(attempt(['a'], True, complete)), bank, eligible)
            self.assertEqual(bank[0].q_visits, 0)
            self.assertFalse(events[0]['credited'])

    def test_Dgate_write_rejected(self):
        item = row(attempt(['a'], True)); item['pool'] = 'D_gate'
        with self.assertRaises(ValueError):
            study.credit(item, [node('a'), node('b')])

    def test_cap_and_adoption_contract(self):
        item = row(attempt(['c'], True))
        with self.assertRaises(ValueError):
            study.credit(item, [node('a'), node('b'), node('c')])

    def test_replay_preserves_body(self):
        bank = [node('a'), node('b')]; before = copy.deepcopy(study.body(bank))
        study.credit(row(attempt(['a'], True)), bank)
        self.assertEqual(before, study.body(bank))

    def test_old_baselines_reusable(self):
        bank = study.load_memory(study.BASE / 'Lall/all_feedback/frozen/m_star_q.jsonl')
        certificate = study.reuse_certificate(bank)
        self.assertEqual(certificate['reusable_rows'], 596)


if __name__ == '__main__':
    unittest.main()
