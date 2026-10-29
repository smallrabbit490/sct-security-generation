"""真实建库结束后按已保存段回放并签发技术库证明；不生成新响应。"""
import json
import os
from pathlib import Path
import subprocess
import sys

from configs.cle_weekly_build_20261027 import execute as original
from configs.cle_weekly_build_20261027.certify import certify
from methods.sct_trajectory.replay_journal import ReplayStop


def finish():
    build = original.BUILD
    index = build / 'execution_index.json'
    segments = [Path(p) for p in original.read(index)['segments']] if index.exists() else [build / 'execution/segment_001']
    if original.read(segments[-1] / 'state.json').get('status') != 'completed_pending_verification':
        raise ReplayStop('build_not_completed_before_replay')
    output = build / 'zero_API_replay'
    result = output / 'replay_result.json'
    if not result.exists():
        command = [sys.executable, '-B', '-X', 'utf8', '-m',
                   'configs.cle_weekly_build_readiness_20261027.execute', 'replay']
        for source in segments:
            command += ['--source', str(source)]
        command += ['--original', str(build / 'native' / segments[-1].name), '--destination', str(output)]
        subprocess.run(command, cwd=original.ROOT, check=True,
                       env={**os.environ, 'PYTHONHASHSEED':'20261027'},
                       creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return certify(result)


if __name__ == '__main__':
    print(json.dumps(finish(), ensure_ascii=False))
