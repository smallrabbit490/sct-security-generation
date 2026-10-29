"""按实际恢复段选择FFS前缀检查缓存，保留原模型、记录和恢复边界。"""
import argparse
import json

from configs.cle_weekly_http403_recovery_20261028 import resume as original
from methods.sct_trajectory.replay_journal import ReplayStop, write_json


previous_probe = original.probe


def probe(kind):
    """新网络中断不得复用另一组未决请求的旧检查；Q路径原样委托。"""
    if kind == 'q':
        return previous_probe(kind)
    helper = original.helper(kind)
    prior = helper['sources']()
    result = helper['probe'](prior=prior,
        label='confirmed_http403_20261028_after_segment_%03d' % len(prior))
    if result.get('status') != 'passed' or result.get('new_HTTP') != 0:
        raise ReplayStop('current_recovery_segment_prefix_not_exact')
    write_json(original.EVIDENCE / 'ffs_prefix_check.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    parser.add_argument('--kind', choices=['q', 'ffs'], required=True)
    args = parser.parse_args()
    original.probe = probe
    original.MODULE = 'configs.cle_weekly_http403_probe_refresh_20261028.resume'
    result = {'probe': probe, 'launch': original.launch, 'run': original.run}[args.action](args.kind)
    if result is not None:
        print(json.dumps({k: v for k, v in result.items() if k != 'targets'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
