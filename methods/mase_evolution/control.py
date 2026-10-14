"""MASE调度控制与进度落盘：协调暂停边界，不参与模型决策或经验库写入。"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import time


TERMINAL = {'completed', 'failed'}


class ControlStore:
    """控制阶段读写单次运行状态；输入为控制文件，输出原子状态快照。

    控制文件损坏时报错，避免误派任务；不读取验证证据，也不允许改长期记忆。
    """

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def read(self):
        """读取当前控制快照；旧运行无文件时返回只读兼容的运行态。"""
        if not self.path.exists():
            return {'status': 'running', 'updated_at': None, 'legacy': True}
        value = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(value, dict) or value.get('status') not in {'running', 'pause_requested', 'paused', *TERMINAL}:
            raise ValueError('invalid_control_state')
        return value

    def _write(self, value):
        """控制阶段原子替换 JSON；写入失败保留旧状态并向调度层报告。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        value = {**value, 'updated_at': datetime.now(timezone.utc).isoformat()}
        fd, temp_name = tempfile.mkstemp(prefix=self.path.name + '.', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
                json.dump(value, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            # Windows may briefly deny replacement while the dashboard reads the prior snapshot.
            for attempt in range(6):
                try:
                    os.replace(temp_name, self.path)
                    break
                except PermissionError:
                    if attempt == 5:
                        raise
                    time.sleep(0.02 * (attempt + 1))
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return value

    def request_pause(self):
        """人工控制阶段登记暂停请求；完成/失败运行拒绝改变状态。"""
        with self._lock:
            state = self.read()
            if state['status'] == 'pause_requested':
                return state
            if state['status'] != 'running':
                raise ValueError('invalid_control_transition')
            return self._write({**state, 'status': 'pause_requested'})

    def mark_paused(self):
        """調度阶段仅在在途任务均保存后确认暂停。"""
        with self._lock:
            state = self.read()
            if state['status'] != 'pause_requested':
                raise ValueError('invalid_control_transition')
            return self._write({**state, 'status': 'paused'})

    def request_resume(self):
        """人工控制阶段从已暂停状态恢复派发；其他迁移均拒绝。"""
        with self._lock:
            state = self.read()
            if state['status'] != 'paused':
                raise ValueError('invalid_control_transition')
            return self._write({**state, 'status': 'running'})

    def set_terminal(self, status):
        """运行收尾阶段记录完成或失败，避免后续接口恢复终态任务。"""
        if status not in TERMINAL:
            raise ValueError('invalid_terminal_status')
        with self._lock:
            state = self.read()
            return self._write({**state, 'status': status})

    def update_heartbeat(self, values):
        """进度阶段原子写入心跳字段；字段来自调度与请求统计，不含模型私有推理。"""
        if not isinstance(values, dict):
            raise ValueError('invalid_heartbeat')
        with self._lock:
            state = self.read()
            return self._write({**state, **values, 'status': state['status']})


def schedule_tasks(tasks, saved_ids, work, persist, control, workers=1):
    """运行阶段有界派发独立任务；保存回调成功后才纳入续跑集合。

    输入为任务序列、已保存ID及解题/持久化函数；输出completed或paused。
    任务/写盘异常向上抛出，由run.py记录失败；只消费评分证据，不修改经验库。
    """
    if workers < 1:
        raise ValueError('invalid_worker_count')
    normalized_saved = {str(value) for value in saved_ids}
    pending = iter(task for task in tasks
                   if str(task['index'] if isinstance(task, dict) else task) not in normalized_saved)
    active = {}
    exhausted = False
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while active or not exhausted:
            if control.read()['status'] == 'pause_requested':
                if active:
                    done, _ = wait(active, return_when=FIRST_COMPLETED)
                    for future in done:
                        row = future.result()
                        persist(row)
                        active.pop(future)
                    continue
                control.mark_paused()
                return 'paused'
            while not exhausted and len(active) < workers:
                if control.read()['status'] == 'pause_requested':
                    break
                try:
                    task = next(pending)
                except StopIteration:
                    exhausted = True
                    break
                active[pool.submit(work, task)] = task
            if active:
                done, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    row = future.result()
                    persist(row)
                    active.pop(future)
                continue
            if exhausted:
                return 'completed'
    return 'completed'
