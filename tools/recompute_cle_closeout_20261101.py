"""从下载还原的逐题记录复算两批结果；不生成代码、不联网、不写入运行目录。"""
import argparse
import json
from pathlib import Path
import socket
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def no_network(*args, **kwargs):
    raise RuntimeError('offline_recomputation_network_disabled')


def recompute(run_root, output):
    socket.socket.connect = no_network
    socket.create_connection = no_network
    from configs.cle_weekly_closeout_20261101.switch_analysis import stratum, COHORTS
    from configs.cle_weekly_analysis_20261027.retest_analysis import collect
    result = {}
    for kind, relative, planned in [('q','probe_relay_20261028/Q.retest',540),('gr','FG_LABELS',820)]:
        root = Path(run_root)/relative
        read = lambda p: json.loads(p.read_text(encoding='utf-8'))
        rows, paths, duplicates = collect(sorted(root.glob('segment_*')), read(root/'inputs/schedule.json'))
        assert len(rows) == planned, (kind,len(rows),planned)
        cohorts = {}
        for cohort in COHORTS:
            items = [r for r in rows if r.get('model_cohort','1017_only') == cohort]
            value = stratum(items,paths,kind)
            value.pop('case_review_queue',None)
            value.pop('mechanisms',None)
            expected = read(root/'model_switch_flash_20261101/analysis'/(cohort+'.json'))
            assert value['arms'] == expected['arms'], (kind,cohort,'arm_metrics_mismatch')
            for actual, saved in zip(value['comparisons'],expected['comparisons']):
                for key in ('pairs','wins','losses','net_joint','difference','p_family_swap'):
                    if key in saved:assert actual[key] == saved[key], (kind,cohort,key)
            cohorts[cohort] = value
        result[kind] = {'completed':len(rows),'measured':sum(bool(r['final']['measured']) for r in rows),
                        'duplicates_consistent':duplicates,'cohorts':cohorts,'saved_metrics_match':True}
    destination = Path(output)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({kind:{k:v for k,v in value.items() if k != 'cohorts'} for kind,value in result.items()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-root',required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    recompute(args.run_root,args.output)
