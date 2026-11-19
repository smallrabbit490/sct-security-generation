"""冻结新候选数据的上游文件；只下载获准子集，按 Git blob 去重复用。"""
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import time
import requests

ROOT = Path(__file__).resolve().parents[2]
DATE = '20261118'


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], timeout=180))


def selected(name, path):
    if name == 'pythonsecurityeval':
        return path.startswith('data/PythonSecurityEval/') or path in ('README.md', 'Prompts_and_PostID_from_StackOverflow.csv', 'Evaluation.ipynb') or 'license' in path.lower()
    if name == 'lscbench_function':
        return (path.startswith('tasks/') and '_function/' in path) or path in ('README.md', 'LICENSE', 'tasks/dataset.toml')
    if name == 'safecoder':
        return not path.startswith(('data_train_val/', 'data_eval/func_eval/'))
    return True


def main():
    repos = {'pythonsecurityeval': 'Kamel773/LLM-code-refine', 'lscbench_function': 'alibaba/last-secure-code-benchmark', 'codelmsec': 'codelmsec/codelmsec', 'safecoder': 'eth-sri/SafeCoder'}
    cache = ROOT / 'translation_work/cache/candidate_git_blobs'
    cache.mkdir(parents=True, exist_ok=True)
    for name, repo in repos.items():
        target = ROOT / 'data/external' / name / f'upstream_{DATE}'
        target.mkdir(parents=True, exist_ok=True)
        manifest_path = target.parent / f'download_manifest_{DATE}.json'
        if manifest_path.exists():
            commit = json.loads(manifest_path.read_text(encoding='utf-8'))['commit']
        else:
            commit = api(f'repos/{repo}/commits/HEAD')['sha']
        tree = api(f'repos/{repo}/git/trees/{commit}?recursive=1')
        if tree.get('truncated'):
            raise RuntimeError('Truncated upstream tree')
        files = [x for x in tree['tree'] if x['type'] == 'blob' and selected(name, x['path'])]
        manifest = {'repository': repo, 'commit': commit, 'selection': name, 'files': [], 'status': 'downloading'}
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

        def fetch(item):
            blob = cache / item['sha']
            if not blob.exists():
                for attempt in range(4):
                    try:
                        response = requests.get(f'https://raw.githubusercontent.com/{repo}/{commit}/{item["path"]}', timeout=60)
                        response.raise_for_status()
                        data = response.content
                        break
                    except requests.RequestException:
                        if attempt == 3:
                            raise
                        time.sleep(attempt + 1)
                actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                if actual != item['sha']:
                    raise RuntimeError('Git blob hash mismatch')
                blob.write_bytes(data)
            data = blob.read_bytes()
            dest = target / item['path']
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return {'path': item['path'], 'bytes': len(data), 'git_blob': item['sha'], 'sha256': hashlib.sha256(data).hexdigest()}

        print(name, commit, len(files), 'files', flush=True)
        with ThreadPoolExecutor(max_workers=10) as pool:
            for future in as_completed([pool.submit(fetch, item) for item in files]):
                manifest['files'].append(future.result())
                if len(manifest['files']) % 100 == 0:
                    print(name, len(manifest['files']), '/', len(files), flush=True)
        manifest['files'].sort(key=lambda x: x['path'])
        manifest['status'] = 'complete'
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(name, 'complete', flush=True)


if __name__ == '__main__':
    main()
