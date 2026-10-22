"""从已校验的2026-10-22原始Release恢复本研究的最小输入；零API，不覆盖差异文件。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = '51436d2c9018eedc1854d21f94a3462bf4444d94e787de5bee96614425d6a261'
PREFIX = 'translation_work/diagnostics/20261020/cle_q_online_v1/'
FILES = ('tasks_D_init.json', 'tasks_D_grow.json', 'tasks_D_gate.json', 'run_metadata.json',
         'D_init/rows.jsonl', 'D_grow/rows.jsonl', 'D_init/frozen/m_star_q.jsonl',
         'D_grow/frozen/m_star_q.jsonl')


def main():
    """只解包固定白名单，先验证整包SHA；已有不同内容报错，绝不重写历史证据。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    with args.archive.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    if digest != EXPECTED:
        raise ValueError('release_sha256_mismatch')
    restored = []
    with zipfile.ZipFile(args.archive) as archive:
        for name in FILES:
            relative = PREFIX + name
            target = (ROOT / relative).resolve()
            if not target.is_relative_to((ROOT / 'translation_work').resolve()):
                raise ValueError('unsafe_extraction_path')
            data = archive.read('sct-security-generation/' + relative)
            sha = hashlib.sha256(data).hexdigest()
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != sha:
                raise ValueError('existing_historical_input_differs:' + relative)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            restored.append({'path': relative, 'sha256': sha, 'bytes': len(data)})
    print(json.dumps({'archive_sha256': digest, 'verified_files': restored}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
