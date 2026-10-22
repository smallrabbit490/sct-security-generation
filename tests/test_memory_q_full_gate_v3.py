import json
from methods.cle_ablation import run_memory_q_full_gate_v3 as s


def test_jsonl_unicode_separator_is_inside_a_record(tmp_path):
    path=tmp_path/'rows.jsonl'
    expected=[{'task_id':'103','code':'value='+chr(0x2028)+'end'},{'task_id':'104'}]
    path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in expected),encoding='utf-8')
    assert s.read_rows(path)==expected


def test_completed_worker_result_is_recovered_without_regeneration(tmp_path):
    row={'task_id':'x','arm':'Q2','code':'saved'}
    s.write(tmp_path/'task_rows/x/Q2.json',row)
    assert s.recover_worker_rows(tmp_path)==[row]
    assert s.recover_worker_rows(tmp_path)==[row]
    assert s.read_rows(tmp_path/'rows.jsonl')==[row]
