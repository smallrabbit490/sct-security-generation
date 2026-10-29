"""保存基准运行实际HTTP正文和响应字节；认证头从不落盘。"""
import json
import threading
import time
import urllib.request
from datetime import datetime, timezone

from .replay_journal import write_json


class WireRecording:
    """仅记录ChatAnywhere模型/向量请求，逐次保留重试和流式片段。"""
    def __init__(self, root, *, transport=None):
        self.root = root
        self.transport = transport
        root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.number = len(list(root.glob('*.request.json')))

    def __enter__(self):
        self.original = urllib.request.urlopen

        def urlopen(req, *args, **kwargs):
            if not isinstance(req, urllib.request.Request) or req.host not in (
                    'api.chatanywhere.tech', 'api.chatanywhere.org'):
                return self.original(req, *args, **kwargs)
            with self.lock:
                self.number += 1
                stem = self.root / f'{self.number:07d}'
            body = json.loads((req.data or b'{}').decode('utf-8'))
            write_json(stem.with_suffix('.request.json'), {'url': req.full_url,
                'body': body, 'started_utc': datetime.now(timezone.utc).isoformat()})
            started = time.monotonic()
            try:
                response = (self.transport or self.original)(req, *args, **kwargs)
            except Exception as exc:
                reason = getattr(exc, 'reason', None)
                write_json(stem.with_suffix('.status.json'), {'status': 'transport_error',
                    'error_type': type(exc).__name__, 'http_status': getattr(exc, 'code', None),
                    'reason_type': type(reason).__name__ if reason is not None else None,
                    'elapsed_seconds': time.monotonic() - started})
                raise
            return _Tee(response, stem, started)
        urllib.request.urlopen = urlopen
        return self

    def __exit__(self, *exc):
        urllib.request.urlopen = self.original


class _Tee:
    def __init__(self, response, stem, started):
        self.response, self.stem, self.started = response, stem, started
        self.file = stem.with_suffix('.response.raw').open('xb')

    def __enter__(self):
        return self

    def __iter__(self):
        return self

    def __next__(self):
        chunk = next(self.response)
        self.file.write(chunk)
        self.file.flush()
        return chunk

    def read(self, *args):
        chunk = self.response.read(*args)
        self.file.write(chunk)
        self.file.flush()
        return chunk

    def __exit__(self, kind, value, tb):
        self.file.close()
        self.response.close()
        write_json(self.stem.with_suffix('.status.json'), {
            'status': 'response_closed' if kind is None else 'response_read_error',
            'error_type': kind.__name__ if kind else None,
            'http_status': getattr(self.response, 'status', None),
            'elapsed_seconds': time.monotonic() - self.started})
