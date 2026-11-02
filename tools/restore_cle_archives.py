"""按原路径还原 CLE 基础包与增量包；可仅还原离线统计所需材料。"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def restore(base, increment, output, scope):
    base, increment, output = map(Path,(base,increment,output))
    merged = {}
    for folder in (base,increment):
        for row in json.loads((folder/'manifest.json').read_text(encoding='utf-8'))['files']:
            merged[row['path']] = row
    roots = ('external_runs/20261027_full_requirements/probe_relay_20261028/Q.retest/',
             'external_runs/20261027_full_requirements/FG_LABELS/')
    selected = [r for r in merged.values() if scope == 'all' or r['path'].startswith(roots)]
    if scope == 'recompute':
        selected = [r for r in selected if any(x in r['path'] for x in ('/task_rows/','/inputs/','/model_switch_flash_20261101/analysis/'))]
    index = {}
    for folder in (base,increment):
        for p in sorted(folder.glob('*blobs-*.zip')):
            with zipfile.ZipFile(p) as archive:
                for name in archive.namelist():index[name] = p
    missing = [r['blob'] for r in selected if 'blobs/'+r['blob'] not in index]
    assert not missing, ('missing_archive_blobs',len(missing))
    selected.sort(key=lambda r:(str(index['blobs/'+r['blob']]),r['path']))
    count = 0; current = None; archive = None
    try:
        for row in selected:
            target = output/row['path']
            assert target.resolve().is_relative_to(output.resolve()), row['path']
            if target.exists():raise FileExistsError(target)
            path = index['blobs/'+row['blob']]
            if path != current:
                if archive:archive.close()
                archive = zipfile.ZipFile(path);current = path
            target.parent.mkdir(parents=True,exist_ok=True)
            h = hashlib.sha256()
            with archive.open('blobs/'+row['blob']) as source, target.open('wb') as dest:
                while chunk := source.read(1024*1024):h.update(chunk);dest.write(chunk)
            expected = row.get('export_sha256',row['blob'])
            if not row.get('export_redacted'):assert h.hexdigest() == expected, row['path']
            count += 1
    finally:
        if archive:archive.close()
    receipt = {'scope':scope,'restored_files':count,'missing_blobs':0,'existing_files_overwritten':False,
               'original_runtime_modified':False}
    (output/'restore_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base',required=True)
    parser.add_argument('--increment',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--scope',choices=['all','closeout','recompute'],default='closeout')
    args = parser.parse_args()
    restore(args.base,args.increment,args.output,args.scope)
