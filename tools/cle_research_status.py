"""零API读取CLE研究进度：区分当前固定清单与尚待实施的全量交叉计划。"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'translation_work/diagnostics/20261026/cle_v41_completion'


def main():
    """只读现有协议和状态，不调用模型、不写记录、不读取凭据。"""
    progress = json.loads((RUN / 'progress.json').read_text(encoding='utf-8'))
    protocol = json.loads((ROOT / 'configs/cle_v41_completion_20261026/protocol.json').read_text(encoding='utf-8'))
    kinds = {stage['id']: stage['kind'] for stage in protocol['stages']}
    completed = planned = 0
    print('CLE研究实时总览 | 运行汇总时间：' + progress['updated_at'])
    print('当前授权：v4.1固定基础迁移；新全量交叉矩阵仍为规划，未自动派发。')
    for stage in progress['stages']:
        count = f"{stage['completed']}/{stage['planned']}" if stage['planned'] else '非生成任务'
        print(f"{stage['id']:<14} {count:<12} {stage['status']:<24} {stage['name']}")
        if kinds[stage['id']] not in ('q_selection', 'classifier', 'report'):
            completed += stage['completed']
            planned += stage['planned']
    print(f'代码运行单元：{completed}/{planned}；选卡重复另列，不能混成独立任务数。')
    print('全量总体：D_init303 / D_grow273 / D_gate298题；旧D_gate四臂含217个family。')
    print('已知完整历史：ds32 P0-P7三集4424行；ds32旧Q四臂1192行；ds41 P3 PLT298行。')
    print('新缺口：C41建库、同P7六条件全量交叉、匹配Q学习与四臂、老师任务的全量验证。')
    print('说明：当前48题等固定清单完成，不等于298题全量交叉完成。')
    print('总览：' + str(ROOT / 'docs/research/README.md'))


if __name__ == '__main__':
    main()
