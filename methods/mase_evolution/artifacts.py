"""记录阶段的原子文件及追加事件；保留失败证据、拒绝版本覆盖，不触碰正式库。"""
from __future__ import annotations
import json
import re
import threading
import uuid
from pathlib import Path


def write_json(path, value):
    """原子保存小型JSON，避免网页读到半份文件；输入仅允许脱敏实验内容。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def read_jsonl(path):
    """读取完整行并报告坏行位置；尾部截断明确列出，不静默降低分母。"""
    path = Path(path)
    if not path.exists():
        return [], []
    rows, errors = [], []
    lines = path.read_text(encoding='utf-8').splitlines()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError('object_required')
            rows.append(value)
        except (ValueError, json.JSONDecodeError):
            errors.append({'line': i+1, 'type': 'truncated_line' if i == len(lines)-1 else 'invalid_line'})
    return rows, errors


class Store:
    """版本与事件存储；运行器有写权限，网页只读。锁保护追加，不改长期库。"""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def version_dir(self, version_id):
        """严格短ID定位当前run版本，拒绝路径穿越。"""
        if not re.fullmatch(r'[A-Za-z0-9_-]+', version_id):
            raise ValueError('invalid_version_id')
        return self.root / 'versions' / version_id

    def create_version(self, version):
        """创建新版本与架构快照；同编号已经存在就拒绝，保留失败与旧证据。"""
        directory = self.version_dir(version['version_id'])
        try:
            directory.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise ValueError('version_already_exists') from exc
        write_json(directory/'version.json', {k:v for k,v in version.items() if k != 'architecture'})
        write_json(directory/'architecture.json', version['architecture'])

    def append(self, version_id, filename, record):
        """追加脱敏事件/结果并flush；输出文件白名单，调用方保证事件ID唯一。"""
        if filename not in ('events.jsonl', 'rows.jsonl', 'hypotheses.jsonl'):
            raise ValueError('unsupported_record_file')
        directory = self.version_dir(version_id)
        directory.mkdir(parents=True, exist_ok=True)
        with self.lock, (directory/filename).open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False)+'\n')
            stream.flush()
