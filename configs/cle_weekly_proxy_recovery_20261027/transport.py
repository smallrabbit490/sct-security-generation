"""Route authorized recovery through the verified local HTTPS CONNECT proxy."""
import shutil
import sys
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from configs.cle_v41_relation_20261026.execution import StudyExecution


@contextmanager
def verified_proxy_transport():
    previous = StudyExecution.__init__
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({'https': 'http://127.0.0.1:7897'}))

    def initialize(self, *args, **kwargs):
        if kwargs.get('live'):
            kwargs['physical_open'] = opener.open
        previous(self, *args, **kwargs)
        if kwargs.get('live'):
            self.save('transport_route', {'https_proxy': '127.0.0.1:7897',
                      'same_endpoint_and_model': True, 'TLS_certificate_validation': 'default',
                      'reason': 'direct port 443 timeout; proxy CONNECT and TLS 1.3 verified'})
            folder = self.root / 'source_bundle_external'
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(__file__), folder / 'proxy_transport.py')
            launcher = Path(sys.argv[0])
            if launcher.is_file():
                shutil.copy2(launcher, folder / 'proxy_recovery_launcher.py')

    StudyExecution.__init__ = initialize
    try:
        yield
    finally:
        StudyExecution.__init__ = previous
