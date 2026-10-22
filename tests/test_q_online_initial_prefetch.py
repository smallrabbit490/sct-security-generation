"""验证提前初析只改变调用调度，原生缓存与公开输入保持一致。"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from configs.cle_q_online_20261020 import prefetch_initials as mod


class PrefetchTests(unittest.TestCase):
    def test_same_public_contract_and_preserve_existing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mod.study.write(root / 'manifest.json', {'D_grow': ['a', 'b']})
            mod.study.write(root / 'tasks_D_grow.json', {'a': 'public-a', 'b': 'public-b'})
            mod.study.write(root / 'run_metadata.json', {'status': 'running_D_init'})
            original = {'task_id': 'a', 'initial_analysis': {'saved': True}}
            mod.study.write(root / 'D_grow/initials/a.json', original)
            seen = []
            tracker = SimpleNamespace(snapshot=lambda: {'total': {'calls': 1}})
            api = SimpleNamespace(bind=lambda i, arm: (lambda prompt: None, tracker))
            def prepare(row, request):
                seen.append(row)
                return {'vulnerability_hypothesis': ['public risk'], 'functional_invariants': ['public function']}
            with patch.object(mod.study, 'OUT', root), patch.object(mod.study, 'verify', return_value={'status': 'running_D_init'}), patch.object(mod.study, 'Requests', return_value=api), patch.object(mod.study, 'frozen_runner', return_value=SimpleNamespace(plt_contract=lambda task: task)), patch.object(mod.study, 'prepare_initial_analysis', side_effect=prepare):
                result = mod.run()
            self.assertEqual(seen, [{'task_description': 'public-b'}])
            self.assertEqual(mod.study.read(root / 'D_grow/initials/a.json'), original)
            saved = mod.study.read(root / 'D_grow/initials/b.json')
            self.assertEqual(set(saved), {'task_id', 'initial_analysis', 'error_type', 'accounting', 'reused_initial'})
            self.assertEqual(saved['accounting'], {'calls': 1})
            self.assertEqual(result['saved'], 1)
            self.assertFalse(result['Q_updated'])

    def test_refuses_competing_learning_stage(self):
        with patch.object(mod.study, 'verify', return_value={'status': 'running_D_grow'}):
            with self.assertRaisesRegex(AssertionError, 'prefetch_only'):
                mod.run()


if __name__ == '__main__':
    unittest.main()
