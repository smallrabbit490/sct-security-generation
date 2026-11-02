"""为已保存的 CLE 结果制作增量归档；复用旧分卷，不改动实验目录。"""
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile

BASE = Path('E:/ResearchExports/CLE/20261029')
OUT = Path('E:/ResearchExports/CLE/20261102')
RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
SECRET = re.compile(rb'(?<![A-Za-z0-9_-])(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{25,})|Bearer\s+[A-Za-z0-9_.-]{30,}')
TEXT = {'.py','.md','.json','.jsonl','.txt','.toml','.yaml','.yml','.csv','.js','.html','.xml','.svg','.ps1','.log','.ini','.cfg','.sh','.bat'}


def export():
    OUT.mkdir(exist_ok=True)
    old = json.loads((BASE/'manifest.json').read_text(encoding='utf-8'))
    previous = {x['path']: x for x in old['files']}
    old_blobs = {x['blob'] for x in old['files']}
    manifest = []; new = {}; scanned = unchanged = 0
    for parent, dirs, files in os.walk(RUN):
        dirs[:] = sorted(d for d in dirs if d not in {'__pycache__','.git','node_modules','local_secrets','workbench_monitor'})
        for name in sorted(files):
            p = Path(parent)/name
            if name.startswith(('.env','~$')) or any(s in name.lower() for s in ('apikey','api_key','credentials','password','cookie')) or p.suffix.lower() in {'.pem','.key','.pyc','.pyo','.lock'}:
                continue
            rel = 'external_runs/20261027_full_requirements/'+p.relative_to(RUN).as_posix()
            st = p.stat(); scanned += 1
            prior = previous.get(rel)
            if prior and prior['size'] == st.st_size and prior.get('mtime_ns') == st.st_mtime_ns:
                unchanged += 1
                continue
            data = p.read_bytes()
            clean, count = SECRET.subn(b'[REDACTED_CREDENTIAL]', data) if p.suffix.lower() in TEXT else (data, 0)
            digest = hashlib.sha256(data).hexdigest()
            if prior and prior['blob'] == digest:
                unchanged += 1
                continue
            exported = hashlib.sha256(clean).hexdigest()
            row = {'path':rel,'size':len(clean),'original_size':len(data),'blob':digest,
                   'export_sha256':exported,'mtime_ns':st.st_mtime_ns,'redacted_matches':count,
                   'storage':'base' if digest in old_blobs and not count else 'increment'}
            manifest.append(row)
            if row['storage'] == 'increment':new.setdefault(digest, p)
            if scanned % 5000 == 0:print('scanned',scanned,'changed',len(manifest),'new_blobs',len(new),flush=True)
    parts = 0; archive = None
    try:
        for digest, p in new.items():
            if archive is None or archive.fp.tell() > 650_000_000:
                if archive:archive.close()
                parts += 1
                archive = zipfile.ZipFile(OUT/f'CLE-increment-20261102-blobs-{parts:03}.zip','w',zipfile.ZIP_DEFLATED,compresslevel=1)
                print('packing',parts,flush=True)
            data = p.read_bytes()
            if p.suffix.lower() in TEXT:data = SECRET.sub(b'[REDACTED_CREDENTIAL]',data)
            archive.writestr('blobs/'+digest,data)
    finally:
        if archive:archive.close()
    payload = {'format':'content-addressed-increment-v1','base_release':'cle-project-snapshot-20261029',
               'files':manifest,'excluded_active_runtime':'workbench_monitor; experiment source files are read-only'}
    (OUT/'manifest.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    receipt = {'scanned_runtime_files':scanned,'unchanged_base_files':unchanged,'changed_or_new_paths':len(manifest),
               'new_blobs':len(new),'parts':parts,'archives_bytes':sum(p.stat().st_size for p in OUT.glob('*blobs-*.zip')),
               'redacted_matches':sum(x['redacted_matches'] for x in manifest),'originals_modified':False}
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('DONE',json.dumps(receipt),flush=True)


if __name__ == '__main__':
    export()
