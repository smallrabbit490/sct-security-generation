"""本地只读审阅服务：版本/图/脱敏逐题证据；不访问密钥、夹具或启动实验。"""
from __future__ import annotations
import argparse
import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from ..artifacts import read_jsonl
from ..metrics import summarize, compare
from ..import_history import DEFAULT_OUT
from ..control import ControlStore

STATIC=Path(__file__).parent/'static'
METHOD=Path(__file__).parent.parent
EVENT_FIELDS={'event_id','task_id','attempt_id','node_id','parent_node_id','round','operation','status',
              'started_at','ended_at','input_refs','model_role','provider','model','request_status',
              'usage','usage_status','input_sha256','code_sha256','error_type','error_code','reason','missing_refs'}


def public_event(event):
    """网页审计阶段仅输出允许字段；不暴露候选源码、模型回复、提示词或隐藏输入。"""
    return {key:value for key,value in event.items() if key in EVENT_FIELDS}


def proposal_diagnostics(proposal):
    """将图结构检查错误翻译成人话；只读提案元数据，不暴露模型原始回复。"""
    if not isinstance(proposal,dict):
        return []
    graph=proposal.get('architecture') if isinstance(proposal.get('architecture'),dict) else {}
    labels={node.get('id'):node.get('label') or node.get('id')
            for node in graph.get('nodes',[]) if isinstance(node,dict) and isinstance(node.get('id'),str)}
    result=[]
    for error in proposal.get('errors',[]):
        if not isinstance(error,str):
            continue
        parts=error.split(':')
        if len(parts)==3 and parts[0]=='input_without_edge':
            node,ref=parts[1:]
            result.append(f'节点“{labels.get(node,node)}”需要“{labels.get(ref,ref)}”，但架构中缺少 {ref} → {node} 连线。')
        else:
            result.append(f'架构检查未通过：{error}')
    return result


def design_attempts(proposal):
    """逐次调用仅展示上限、结束原因与安全错误类别，不返回提示词或模型正文。"""
    if not isinstance(proposal,dict):
        return []
    trace=proposal.get('design_trace',[])
    if not isinstance(trace,list):
        return []
    fields=('output_limit','finish_reason','error_type','action','seconds','usage','usage_status')
    return [{key:event.get(key) for key in fields}
            for event in trace if isinstance(event,dict)]


def safe_identifier(value):
    """HTTP参数只允许短ID，路径穿越和目录外读取被拒绝。"""
    return bool(isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,160}',value))


def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def run_status(directory, metadata):
    """读取运行阶段状态：只把近期心跳/准备活动认作运行中，不修改历史元数据。"""
    status = metadata.get('status', 'unknown')
    terminal = {'completed', 'failed', 'stopped', 'exploration_completed',
                'incomplete_evidence', 'paused'}
    candidates = []
    heartbeat_paths = list((directory / 'versions').glob('*/heartbeat.json'))
    for path in heartbeat_paths:
        try:
            heartbeat = load(path) or {}
            stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            candidates.append((stamp, heartbeat.get('status', status), path))
        except (OSError, ValueError, TypeError):
            continue
    if not candidates and status == 'running':
        # 无版本的运行可能仍在准备数据；准备检查文件必须近期更新才算活跃。
        paths = [directory / 'run_metadata.json', *list((directory / 'public_checks').glob('*.json'))]
        for path in paths:
            try:
                candidates.append((datetime.fromtimestamp(path.stat().st_mtime, timezone.utc), status, path))
            except OSError:
                continue
    if not candidates:
        return {'is_active': False, 'display_status': _status_label(status),
                'last_activity_at': None, 'status_stale': False}
    stamp, observed_status, _ = max(candidates, key=lambda item: item[0])
    age_seconds = max(0, (datetime.now(timezone.utc) - stamp).total_seconds())
    active = status not in terminal and observed_status not in terminal and age_seconds <= 120
    display = '正在运行' if active else ('状态过期，进程未确认' if status == 'running' else _status_label(status))
    return {'is_active': active, 'display_status': display,
            'last_activity_at': stamp.isoformat(), 'status_stale': status == 'running' and not active}


def _status_label(status):
    return {'running': '状态待核实', 'completed': '已完成', 'failed': '运行失败',
            'stopped': '已停止', 'exploration_completed': '探索已结束',
            'incomplete_evidence': '证据不完整', 'paused': '已暂停',
            'invalid_structure': '架构检查未通过', 'baseline_completed': '基线已完成'}.get(status, status or '状态未知')


def make_handler(data_root):
    """输入已授权运行根→只读handler；静态资源与API均按白名单定位，不读任意路径。"""
    root=Path(data_root).resolve()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def send_value(self,value,status=200):
            self.send_bytes(json.dumps(value,ensure_ascii=False).encode(),'application/json; charset=utf-8',status)

        def send_bytes(self,body,kind,status=200):
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed=urlparse(self.path)
            path=unquote(parsed.path)
            query=parse_qs(parsed.query)
            try:
                if path=='/api/runs':
                    runs=[]
                    for p in sorted(root.glob('*/run_metadata.json')):
                        if p.parent.is_symlink():
                            continue
                        meta=load(p)
                        meta['version_count']=len(list((p.parent/'versions').glob('*/version.json')))
                        checks=p.parent/'public_checks'
                        manifest=load(p.parent/'manifest.json') or {}
                        meta['prepared_checks']=(len(list(checks.glob('*.json'))) if checks.exists() else 0)
                        meta['planned_tasks']=len(manifest.get('tasks',[]))
                        meta.update(run_status(p.parent, meta))
                        runs.append(meta)
                    runs.sort(key=lambda item: item.get('last_activity_at') or '', reverse=True)
                    runs.sort(key=lambda item: not item.get('is_active', False))
                    return self.send_value(runs)
                if path=='/api/design':
                    return self.send_value({'text':(METHOD/'design.md').read_text(encoding='utf-8')})
                if path.startswith('/api/'):
                    rid=query.get('run',[''])[0]
                    if not safe_identifier(rid):
                        return self.send_value({'error':'invalid_run'},400)
                    directory=(root/rid).resolve()
                    if root not in directory.parents or not directory.exists():
                        return self.send_value({'error':'run_not_found'},404)
                    if path=='/api/versions':
                        return self.send_value([load(p) for p in sorted((directory/'versions').glob('*/version.json'))
                                                if directory in p.resolve().parents])
                    if path=='/api/audit':
                        return self.send_value(load(directory/'audit.json') or {'status':'未记录'})
                    vid=query.get('version',[''])[0]
                    if not safe_identifier(vid):
                        return self.send_value({'error':'invalid_version'},400)
                    version=(directory/'versions'/vid).resolve()
                    if directory not in version.parents or not version.exists():
                        return self.send_value({'error':'version_not_found'},404)
                    rows,errors=read_jsonl(version/'rows.jsonl')
                    info=load(version/'version.json')
                    if path in ('/api/live','/api/events'):
                        control_path=version/'control.json'
                        heartbeat=load(version/'heartbeat.json')
                        events,event_errors=read_jsonl(version/'events.jsonl')
                        try:
                            cursor=int(query.get('after',['0'])[0])
                        except (TypeError,ValueError):
                            return self.send_value({'error':'invalid_event_cursor'},400)
                        if cursor<0:
                            return self.send_value({'error':'invalid_event_cursor'},400)
                        if path=='/api/events':
                            fresh=[e for index,e in enumerate(events,1) if index>cursor]
                            return self.send_value({'events':[public_event(e) for e in fresh],
                                'cursor':len(events),'recording_errors':event_errors})
                        summary=load(version/'summary.json')
                        if summary is None and (version/'rows.jsonl').exists():
                            rows,_=read_jsonl(version/'rows.jsonl')
                            summary=summarize(rows,info.get('expected',len(rows))) if rows else None
                        safe_events=[public_event(e) for e in events]
                        return self.send_value({'run_id':rid,'version_id':vid,'version':info,
                            'heartbeat':heartbeat,'summary':summary,'control':{
                                'available':control_path.exists(),
                                'status':ControlStore(control_path).read()['status'] if control_path.exists() else None,
                                'reason':None if control_path.exists() else 'legacy_run_read_only'},
                            'events':safe_events, 'recent_events':safe_events[-50:],
                            'event_count':len(events),'recording_errors':event_errors})
                    if path=='/api/version':
                        proposal=load(version/'proposal.json')
                        return self.send_value({'info':info,'graph':load(version/'architecture.json'),
                            'decision':load(version/'decision.json'),'proposal':proposal,
                            'proposal_diagnostics':proposal_diagnostics(proposal),
                            'design_attempts':design_attempts(proposal),
                            'summary':summarize(rows,info.get('expected',len(rows))) if rows else None,
                            'rows':[{'task_id':r['task_id'],'family_id':r.get('family_id'),'cwe':r.get('cwe'),
                                     'final':{k:v for k,v in r.get('final',{}).items() if k not in ('code','evidence')},
                                     'memory':r.get('memory'), 'calls':r.get('usage',{}).get('calls'),
                                     'error_type':r.get('error_type'), 'error_code':r.get('error_code')} for r in rows], 'recording_errors':errors})
                    if path=='/api/task':
                        task=query.get('task',[''])[0]
                        row=next((r for r in rows if str(r['task_id'])==task),None)
                        from ..views import measurement_view
                        return self.send_value(measurement_view(row) if row else {'error':'task_not_found'},200 if row else 404)
                    if path=='/api/compare':
                        other=query.get('other',[''])[0]
                        if not safe_identifier(other):
                            return self.send_value({'error':'invalid_other'},400)
                        other_dir=(directory/'versions'/other).resolve()
                        if directory not in other_dir.parents:
                            return self.send_value({'error':'invalid_other'},400)
                        second=load(other_dir/'version.json')
                        if not second or info.get('phase')!=second.get('phase'):
                            return self.send_value({'comparable':False,'reason':'不同阶段或版本不存在，不能配对'})
                        other_rows,other_errors=read_jsonl(other_dir/'rows.jsonl')
                        a={(str(r['task_id']),r.get('family_id')) for r in rows}
                        b={(str(r['task_id']),r.get('family_id')) for r in other_rows}
                        if not a or a!=b or errors or other_errors:
                            return self.send_value({'comparable':False,'reason':'无真实结果、任务清单不一致或记录损坏'})
                        return self.send_value({'comparable':True,'baseline':vid,'candidate':other,'paired':compare(rows,other_rows)})
                    return self.send_value({'error':'unknown_api'},404)
                allowed={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/style.css':'style.css'}
                if path not in allowed:
                    return self.send_value({'error':'not_found'},404)
                file=STATIC/allowed[path]
                types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8'}
                return self.send_bytes(file.read_bytes(),types[file.suffix])
            except (ValueError,OSError,KeyError,TypeError):
                self.send_value({'error':'recording_or_schema_error','message':'记录缺失/损坏；未把缺测当通过，请检查文件'},500)

        def do_POST(self):
            parsed=urlparse(self.path)
            if unquote(parsed.path)!='/api/control':
                return self.send_value({'error':'unknown_api'},404)
            query=parse_qs(parsed.query)
            rid=query.get('run',[''])[0]
            vid=query.get('version',[''])[0]
            if not safe_identifier(rid) or not safe_identifier(vid):
                return self.send_value({'error':'invalid_run_or_version'},400)
            directory=(root/rid).resolve()
            version=(directory/'versions'/vid).resolve()
            if root not in directory.parents or directory not in version.parents or not version.is_dir():
                return self.send_value({'error':'version_not_found'},404)
            if self.client_address[0] not in ('127.0.0.1','::1'):
                return self.send_value({'error':'loopback_only'},403)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length<1 or length>4096:
                    return self.send_value({'error':'invalid_request_body'},400)
                body=json.loads(self.rfile.read(length))
                action=body.get('action') if isinstance(body,dict) else None
                store=ControlStore(version/'control.json')
                result=store.request_pause() if action=='pause' else store.request_resume() if action=='resume' else None
                if result is None:
                    return self.send_value({'error':'invalid_action'},400)
                return self.send_value({'status':result['status'],'updated_at':result.get('updated_at')})
            except ValueError as exc:
                if str(exc)=='invalid_control_transition':
                    return self.send_value({'error':str(exc)},409)
                return self.send_value({'error':'invalid_request_body'},400)
            except (OSError,json.JSONDecodeError):
                return self.send_value({'error':'control_unavailable'},503)
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8781)
    parser.add_argument('--data-root',type=Path,default=DEFAULT_OUT)
    args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(args.data_root))
    print(f'MASE review: http://127.0.0.1:{args.port}',flush=True)
    server.serve_forever()


if __name__=='__main__':
    main()
