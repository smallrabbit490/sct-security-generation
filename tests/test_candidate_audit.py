"""新增题库审计的可见性与双判定标签边界。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/external_bank_audit'))


def test_formal_defect_needs_two_matching_defect_types():
    from formal_candidates import adjudicate
    a = {'verdict': '有缺陷', 'defect_type': '接口契约', 'test_quality': '充分', 'test_integrity': '完整'}
    b = dict(a, defect_type='业务规则或数据')
    r = adjudicate([a, b])
    assert r['verdict'] == '无法判定' and r['defect_type'] is None
    assert r['review_status'] == '双判分歧'
    assert adjudicate([a, a])['defect_type'] == '接口契约'
    assert adjudicate([a, None])['verdict'] == '无法判定'


def test_autosuit_generation_does_not_leak_reference_or_alternate_prompts():
    from prepare_candidates import autosuit_sources
    row = {'code_description': 'PUBLIC', 'code_file_name': 'a.py', 'context': 'ALTERNATE_CONTEXT',
           'cwe_description': 'CWE_AWARE', 'secure_code': 'GOLD', 'vulnerable_code': 'PATCH_INPUT',
           'functional_test': 'assert a() == 1', 'security_test': '',
           'functional_test_file': 'test.py', 'security_test_file': ''}
    sources = autosuit_sources(ROOT / 'data/fake.jsonl', row)
    public = '\n'.join(s['text'] for s in sources if s['role'] == 'public')
    assert 'PUBLIC' in public and 'a.py' in public
    assert all(x not in public for x in ('GOLD', 'PATCH_INPUT', 'CWE_AWARE', 'ALTERNATE_CONTEXT'))
    assert any(s['role'] == 'test' for s in sources)
