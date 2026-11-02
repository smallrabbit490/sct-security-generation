"""换模桥接保留响应原模型、旧文件及固定流程；全测试禁用模型网络。"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from configs.cle_weekly_closeout_20261101 import switch_flash as s
from methods.sct_trajectory.replay_journal import write_json
from configs.cle_v41_relation_20261026.execution import StudyExecution
from tools.cle_live_workbench.app import worker_processes


class FlashSwitchTests(unittest.TestCase):
    def embedding_fixture(self,root):
        source=root/'segment_001';path=source/'journals/embedding/requests/pending.json'
        record={'identity':'embedding-000001','settings':s.EMBEDDING_SETTINGS,'selector':False,
            'prompt':json.dumps(['exact saved query']),'status':'failed_or_unresolved',
            'started_utc':'2026-11-01T12:18:41+00:00','elapsed_seconds':5.219,'diagnostics':[]}
        write_json(path,record)
        wire=source/'wire/000001.request.json'
        write_json(wire,{'started_utc':'2026-11-01T12:18:41+00:00',
            'body':{'model':'text-embedding-3-large','input':['exact saved query'],'encoding_format':'float'}})
        write_json(source/'wire/000001.status.json',{'status':'transport_error',
            'error_type':'URLError','reason_type':'SSLEOFError','http_status':None})
        return source,path,record

    def test_embedding_empty_diagnostics_requires_exact_failed_wire(self):
        with tempfile.TemporaryDirectory() as folder:
            source,path,record=self.embedding_fixture(Path(folder));before=path.read_bytes()
            with patch('socket.socket.connect',side_effect=AssertionError('no network')):
                boundary=s.embedding_transport_boundary(path,record)
            self.assertEqual(boundary['operation'],'embedding')
            self.assertEqual(boundary['identity'],record['identity'])
            self.assertEqual(path.read_bytes(),before)
            wire=source/'wire/000001.request.json';value=s.READ(wire);value['body']['input']=['different query'];write_json(wire,value)
            with self.assertRaisesRegex(s.ReplayStop,'missing_wire_for_embedding_timeout'):
                s.embedding_transport_boundary(path,record)

    def test_embedding_partial_response_and_certificate_error_do_not_reissue(self):
        with tempfile.TemporaryDirectory() as folder:
            source,path,record=self.embedding_fixture(Path(folder))
            raw=source/'wire/000001.response.raw';raw.write_bytes(b'partial')
            with self.assertRaisesRegex(s.ReplayStop,'saved_embedding_response_requires_reconciliation'):
                s.embedding_transport_boundary(path,record)
        with tempfile.TemporaryDirectory() as folder:
            source,path,record=self.embedding_fixture(Path(folder))
            write_json(source/'wire/000001.status.json',{'status':'transport_error',
                'error_type':'URLError','reason_type':'SSLCertVerificationError','http_status':None})
            with self.assertRaisesRegex(s.ReplayStop,'embedding_failure_not_authorized_transport'):
                s.embedding_transport_boundary(path,record)

    def test_embedding_audit_reuses_successful_successor(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source,path,record=self.embedding_fixture(root)
            write_json(root/'execution_index.json',{'segments':[str(source)]})
            write_json(root/'closeout_20261101/server_timeout_decision_required.json',{'blocked_requests':[]})
            with patch.object(s,'prepare',return_value={'planned':2}),patch.object(s,'root_for',return_value=root),patch.object(s,'RUN',root):
                _,evidence=s.audit('gr')
                self.assertEqual(len(evidence['boundaries']),1)
                successor=source/'journals/embedding/requests/success.json'
                write_json(successor,{**record,'status':'completed','response':{'vectors':[[1.,0.]]}})
                _,evidence=s.audit('gr')
                self.assertEqual(evidence['boundaries'],[])
                self.assertEqual(evidence['pending_paths'],[str(path)])

    def test_saved_native_replay_can_be_reused_only_with_matching_results(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';probe=root/'probe'
            row={'cell_id':'1_r1_L0','task_id':'1','repeat':1,'condition':'L0',
                'final':{'code':'saved code','functional':True,'security':True,'joint':True,'measured':True}}
            write_json(source/'task_rows/1_r1_L0.json',row)
            write_json(probe/'task_rows/1_r1_L0.json',row)
            write_json(source/'input_identity.json',{'fixed':'inputs'})
            write_json(probe/'input_identity.json',{'fixed':'inputs'})
            write_json(probe/'launch.json',{'offline':True})
            self.assertEqual(s.saved_replay_count(probe,[source]),1)
            write_json(probe/'task_rows/1_r1_L0.json',{**row,'final':{**row['final'],'code':'changed'}})
            with self.assertRaisesRegex(s.ReplayStop,'saved_native_prefix_result_differs'):
                s.saved_replay_count(probe,[source])

    def test_saved_replay_rejects_different_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';probe=root/'probe'
            write_json(source/'input_identity.json',{'fixed':'original'})
            write_json(probe/'input_identity.json',{'fixed':'changed'})
            write_json(probe/'launch.json',{'offline':True})
            with self.assertRaisesRegex(s.ReplayStop,'saved_prefix_inputs_changed'):
                s.saved_replay_count(probe,[source])

    def test_old_response_preserved_and_new_request_only_uses_flash(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'old';target=root/'new'
            response={'model':s.OLD,'choices':[{'message':{'content':'old unchanged'}}]}
            identity=s.digest_request('saved',s.OLD_SETTINGS,False)+'-000001'
            file=old/'journals/cell/requests'/(identity+'.json')
            write_json(file,{'identity':identity,'settings':s.OLD_SETTINGS,'prompt':'saved','selector':False,
                'status':'completed','response':response})
            before=file.read_bytes();calls=[]
            def fresh(prompt):
                calls.append(str(prompt));return {'model':s.MODEL,'choices':[{'message':{'content':'new'}}]}
            protocol={'paid_execution_enabled':False,'protocol':'fixture','planned_P7':1,'budget_proposed':{
                'conservative_model_and_embedding_tokens':10000,'total_physical_HTTP_attempts':10,'embedding_HTTP_attempts_included_in_total':0}}
            # 此处只测模型来源和成功响应复用，使用离线许可，避免工作日时段导致夹具等待。
            with patch.object(s.prior,'setup',return_value=object),patch('methods.sct_trajectory.provider_policy.ensure_model_call_allowed'),s.runtime('q',2),patch('socket.socket.connect',side_effect=AssertionError('no network')):
                io=StudyExecution(target,protocol,[{'cell_id':'cell'}],client_factory=lambda _:fresh,
                    physical_open=lambda *_:None,live=False,fixed_eight=False,resume_sources=[old])
                request=io.request_for('cell')
                self.assertEqual(request('saved'),response)
                self.assertEqual(request('fresh')['model'],s.MODEL)
                self.assertEqual(calls,['fresh'])
                self.assertEqual([v['reported_model'] for v in io.model_request_lineage['cell']],[s.OLD,s.MODEL])
                self.assertEqual(io.protocol['model_settings']['model'],s.MODEL)
                self.assertEqual(io.input_state(),io.inputs_before)
            self.assertEqual(file.read_bytes(),before)
            self.assertEqual(s.prior.q.base.wiring.SETTINGS['model'],s.OLD)

    def test_new_worker_entry_and_parents_deduplicated(self):
        cmd='python -m '+s.MODULE+' run --kind q --workers 2'
        actual=worker_processes([{'ProcessId':1,'ParentProcessId':0,'CommandLine':cmd},
                                {'ProcessId':2,'ParentProcessId':1,'CommandLine':cmd}])
        self.assertEqual(len(actual),1)
        self.assertEqual((actual[0]['package'],actual[0]['workers']),('FQ_RETEST',2))


if __name__=='__main__':unittest.main()
