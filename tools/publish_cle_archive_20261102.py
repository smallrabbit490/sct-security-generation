"""续传已冻结的 CLE 归档；保留同名远端附件，只补缺失项并核对大小。"""
import argparse
import json
import os
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor

REPO = 'smallrabbit490/sct-security-generation'


def gh(*args):
    env = dict(os.environ, HTTPS_PROXY='http://127.0.0.1:7897')
    if args[:2] == ('release', 'upload'):
        env.update(HTTPS_PROXY='', HTTP_PROXY='', ALL_PROXY='', GODEBUG='http2client=0')
    return subprocess.check_output(['gh', *args], env=env, text=True, encoding='utf-8')


def publish(folder, tag, defer_name=None):
    folder = Path(folder)
    files = sorted(folder.glob('*blobs-*.zip')) + [folder/n for n in ('manifest.json', 'restore.py', 'receipt.json')]
    assert files and all(p.is_file() for p in files)
    release = next(r for r in json.loads(gh('api', f'repos/{REPO}/releases')) if r['tag_name'] == tag)
    release_id = release['id']
    assets = {a['name']: a for a in release['assets']}
    missing = []
    for p in files:
        if p.name in assets:
            assert assets[p.name]['size'] == p.stat().st_size, p.name
            continue
        if p.name != defer_name:missing.append(p)
    def upload(p):
        print('upload', p.name, p.stat().st_size, flush=True)
        gh('release', 'upload', tag, str(p), '--repo', REPO)
        print('uploaded', p.name, flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(upload,missing))
    release = json.loads(gh('api', f'repos/{REPO}/releases/{release_id}'))
    assets = {a['name']: a for a in release['assets']}
    for p in files:
        assert assets[p.name]['size'] == p.stat().st_size, p.name
    receipt = {'tag': tag, 'release_id': release['id'], 'all_assets_size_verified': True,
               'draft': release['draft'], 'assets': [{'name': p.name, 'size': p.stat().st_size,
               'url': assets[p.name]['browser_download_url']} for p in files]}
    (folder/'uploaded.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print('ALL_ASSETS_VERIFIED', len(files), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder')
    parser.add_argument('tag')
    parser.add_argument('--defer-name')
    args = parser.parse_args()
    publish(args.folder, args.tag, args.defer_name)
