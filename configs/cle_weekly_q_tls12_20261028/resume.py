"""默认 TLS 握手失败、TLS 1.2 实测可用后的 Q 精确前缀接续。"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import urllib.request
import ssl

from configs.cle_weekly_http403_recovery_20261028 import resume as original
from configs.cle_weekly_proxy_recovery_20261027 import transport
from configs.cle_v41_relation_20261026.execution import StudyExecution

MODULE = 'configs.cle_weekly_q_tls12_20261028.resume'


def tls_context():
    """只调整连接协商；保留证书链及主机名校验。"""
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    return context


@contextmanager
def tls12_transport():
    """接续阶段注入物理传输；模型/提示/预算仍由原执行器逐请求检查。"""
    previous = StudyExecution.__init__
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({'https': 'http://127.0.0.1:7897'}),
        urllib.request.HTTPSHandler(context=tls_context()))

    def initialize(self, *args, **kwargs):
        if kwargs.get('live'):
            kwargs['physical_open'] = opener.open
        previous(self, *args, **kwargs)
        if kwargs.get('live'):
            self.save('transport_route', {
                'https_proxy': '127.0.0.1:7897', 'TLS_version': 'TLSv1.2',
                'TLS_certificate_validation': 'default',
                'same_endpoint_and_model': True,
                'reason': 'default TLS handshake timed out; certificate-verified TLS1.2 handshake passed'})
            folder = self.root / 'source_bundle_external'
            folder.mkdir(exist_ok=True)
            shutil.copy2(Path(__file__), folder / 'q_tls12_resume.py')

    StudyExecution.__init__ = initialize
    try:
        yield
    finally:
        StudyExecution.__init__ = previous


def run():
    previous = transport.verified_proxy_transport
    transport.verified_proxy_transport = tls12_transport
    try:
        original.run('q')
    finally:
        transport.verified_proxy_transport = previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    parser.add_argument('--kind', choices=['q'], default='q')
    args = parser.parse_args()
    if args.action == 'run':
        run()
    else:
        # 复用原互斥、精确前缀、累计预算与注册表，不创建另一套调度。
        original.MODULE = MODULE
        result = original.probe('q') if args.action == 'probe' else original.launch('q')
        print(json.dumps({k: v for k, v in result.items() if k != 'targets'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
