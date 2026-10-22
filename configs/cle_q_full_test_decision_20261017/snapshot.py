"""零 API 决策快照：读取原研究阶段门，不运行生成、验证或 Q 学习。"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from datetime import datetime


ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name('protocol.json')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def research_decision(gate_b, gate_d, summary, *, code_reviewed, confirmation_reviewed):
    """复用原门槛结论；等待证据与已经执行但未达标分别报告。"""
    if not gate_b.get('passed'):
        if gate_b.get('reason') == 'no_direct_positive_in_calibration_stop':
            return 'STOP_COVERAGE', '校准池没有人工确认的直接适用正例'
        if gate_b.get('reason') == 'calibration_contract_defect_no_API':
            return 'STOP_TECHNICAL', '公开契约预检未通过，本协议停止付费执行'
        return 'WAIT_HUMAN', '人工标签或裁决尚未完整，未启动新开发实验'
    if gate_d is None:
        return 'WAIT_DEVELOPMENT', '尚无新协议八题开发门结果'
    if not gate_d.get('complete') or not gate_d.get('technical_gate'):
        return 'STOP_TECHNICAL', '开发完整性、流程或测量门未通过，不能解释为Q性能失败'
    if not code_reviewed:
        return 'WAIT_CODE_REVIEW', '先完成已有生成代码的落实审查，不新增API'
    if not gate_d.get('q_passed'):
        return 'STOP_Q_DEVELOPMENT', '开发Q收益、介入或选卡质量门未过；检索路线另判'
    if not summary.get('confirmation_run'):
        return 'WAIT_CONFIRMATION', '开发Q门通过，预留确认尚未完成'
    conclusion = summary.get('confirmation_conclusion')
    if not confirmation_reviewed or conclusion in (None, 'insufficient_until_complete_human_labels_and_code_review'):
        return 'WAIT_CONFIRMATION_REVIEW', '确认标签、格式或代码落实证据尚未完成'
    if conclusion != 'supported_Q_benefit_under_protocol':
        return 'STOP_Q_CONFIRMATION', '确认未建立预设Q收益，区分方向信号与证据不足'
    return 'SCIENTIFIC_SIGNAL_CHECK_FUNCTION', '原确认科学门通过，仍核对功能不退化及全量环境'


def environment_snapshot():
    """只读本机Docker与镜像清单；不构建、不拉取、不启动或清理容器。"""
    images = []
    daemon = False
    if shutil.which('docker'):
        info = subprocess.run(['docker', 'info', '--format', '{{.ServerVersion}}'], capture_output=True, text=True)
        daemon = info.returncode == 0
        if daemon:
            listing = subprocess.run(['docker', 'image', 'ls', '--format', '{{.Repository}}:{{.Tag}}'],
                                     capture_output=True, text=True)
            if listing.returncode == 0:
                images = listing.stdout.splitlines()
    required = ['safecoder-python-validator:local', 'porta-bench-runtime-python3:latest']
    free = shutil.disk_usage(ROOT).free
    return {'docker_daemon_available': daemon, 'required_images': {name: name in images for name in required},
            'project_drive_free_bytes': free, 'original_validator_positive_control': 'not_executed',
            'frozen_CWE_shuffle_qualification': 'not_executed', 'watchdog_qualification': 'not_executed',
            'full_environment_qualified': False}


def main():
    config = read(CONFIG)
    source = ROOT / config['study_run']
    target = ROOT / config['decision_run']
    # 不覆盖旧决策；后续快照另建带时间戳目录。
    if target.exists():
        target = target.with_name(target.name + '_' + datetime.now().strftime('%Y%m%dT%H%M%S'))
    target.mkdir(parents=True, exist_ok=False)
    gate_b = read(source / 'gate_B.json')
    gate_d = read(source / 'gate_D.json') if (source / 'gate_D.json').exists() else None
    summary = read(source / 'summary.json')
    manifest = read(source / 'manifest.json')
    metadata = read(source / 'run_metadata.json')
    if metadata['protocol'] != config['study_protocol']:
        raise ValueError('study_protocol_mismatch')
    state, reason = research_decision(gate_b, gate_d, summary,
        code_reviewed=(source / 'agent_code_review.json').exists(),
        confirmation_reviewed=(source / 'confirmation_code_review.json').exists())
    if state == 'SCIENTIFIC_SIGNAL_CHECK_FUNCTION':
        confirmation = rows(source / 'confirmation/rows.jsonl')
        functional = {arm: sum(r['final']['functional'] for r in confirmation if r['arm'] == arm) for arm in ('B', 'C')}
        state, reason = ('SCIENTIFIC_PASS_ENVIRONMENT_PENDING', '确认Q科学门及功能保护条件通过，等待全量环境资格') if (
            functional['C'] >= functional['B']) else ('STOP_Q_CONFIRMATION', '确认C功能通过数低于B，不推荐全量')
    env = environment_snapshot()
    human = read(source / 'human_labels.json') if (source / 'human_labels.json').exists() else []
    result = {'protocol': config['protocol'], 'study_protocol': config['study_protocol'],
        'status': state, 'reason': reason, 'scientific_failure': state.startswith('STOP_') and state != 'STOP_TECHNICAL',
        'full_test_started': False, 'full_test_ready': False,
        'next': '人工完成CSV并导入，随后按门槛运行原8题开发' if state == 'WAIT_HUMAN' else reason,
        'calibration': manifest['calibration'], 'development': manifest['development'],
        'reserved_confirmation_count': len(manifest['confirmation']),
        'model_labeled': len(rows(source / 'model_labels.jsonl')), 'human_confirmed': len(human),
        'gate_B': gate_b, 'gate_D': gate_d,
        'confirmation_conclusion': summary.get('confirmation_conclusion', 'not_executed'),
        'environment': env, 'snapshot_new_model_calls': 0, 'snapshot_new_embedding_calls': 0,
        'source_run': str(source.relative_to(ROOT)),
        'source_files': ['run_metadata.json', 'manifest.json', 'summary.json', 'gate_B.json', 'model_labels.jsonl'],
        'note': '决策快照不启动全量；失败时仍需按模板完成逐题分析和实际成本'}
    run_metadata = {'protocol': config['protocol'], 'observed_at': datetime.now().astimezone().isoformat(),
        'source_branch': metadata['branch'], 'source_HEAD': metadata['HEAD'], 'source_run': result['source_run'],
        'source_model': metadata['parameters']['model'], 'parameters': config,
        'operation': 'read_only_source_and_docker_inventory', 'new_model_calls': 0, 'Q_updates': False}
    for name, value in [('summary.json', result), ('run_metadata.json', run_metadata), ('environment_preflight.json', env)]:
        (target / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': state, 'reason': reason, 'out': str(target), 'new_model_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
