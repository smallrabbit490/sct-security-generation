"""把新增授权和真实进度写回既有任务清单；历史成绩保留。"""
from __future__ import annotations

import csv
import io
import shutil
from pathlib import Path

from .policies import ROOT,RUN,read
from .report import CURATED


def main(quiet=False):
    progress=read(CURATED/'summary.json');by={s['id']:s for s in progress['stages']}
    offline_only=not progress.get('dispatch_control',{}).get('paid_execution_enabled',True)
    folder=ROOT/'docs/cle_memory_mechanisms_20261023'
    path=folder/'tasks.csv'
    snapshot=RUN/'previous_task_status'
    snapshot.mkdir(parents=True,exist_ok=True)
    for file in (path,folder/'07_当前执行清单与决策门.md'):
        if file.exists() and not (snapshot/file.name).exists():shutil.copy2(file,snapshot/file.name)
    with path.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream);fields=reader.fieldnames;rows=list(reader)
    targets={'B02':'B02','B03R':'B03R','B05':'B05','C02':'C02','C03':'C03_C04a','C04a':'C03_C04a',
             'C04b':'C04b','D02':'D02','D03a':'D03a','D03b':'D03b','S2_M1':'S2_M1','S2_P13_P22':'S2_P13_P22','S4':'S4'}
    present={r['id'] for r in rows}
    for identifier in ('S2_M1','S2_P13_P22','S4'):
        if identifier not in present:
            rows.append({**{f:'' for f in fields},'id':identifier,'package':'S','stage':'v4.1迁移基础比较',
                         'task':by[identifier]['name'],'mode':'已授权固定样本、两重复','output':by[identifier]['root']})
    for row in rows:
        identifier=row['id']
        if identifier in targets:
            s=by[targets[identifier]]
            row.update(status=f"{s['status']}；真实{s['completed']}/{s['planned']}",
                dependency='2026-10-26明确授权及固定输入；前序收益不再作付费审批门',
                mode='零API拟合/分析' if s['kind']=='classifier' else '已授权付费基础比较；复用格不重复计费',
                stop_condition='收益不足不停止本基础包；不扩大题目和重复；不可恢复缺项单列并继续独立包',
                next_action='依完整清单自动推进；收益门只用于解释，不再逐项申请付费许可',
                current_evidence='；'.join(f"{a}:Joint{v['joint']}/{v['completed']}，可测{v['measured']}" for a,v in s['arms'].items()) or '未产生真实结果，不写0分',
                current_gate='完成基础比较；若效果不成立照实收口，不追加题目或重复',
                current_plan='configs/cle_v41_completion_20261026/protocol.json',updated_at='2026-10-26')
        elif identifier=='A02':
            row.update(next_action='使用已修复v2固定96题，1348语义歧义单列分层，不从隐藏测试补阈值',current_gate='不换题，不用歧义题阻断其他已授权基础包',updated_at='2026-10-26')
        elif identifier in ('B01','C01'):
            row.update(status='新来源呈现材料随固定选卡准备；保留原卡',next_action='按公开来源生成并验证分区/绑定，缺来源卡在五档共同排除',
                current_gate='AI制作方式单列，不代签人类检索标签，不用目标答案补来源',current_plan='configs/cle_v41_completion_20261026/README.md',updated_at='2026-10-26')
        elif identifier=='D04':
            row.update(status='授权真实执行中；时段、累计预算、原请求日志和恢复已接入',next_action='持续记录原生行和未知用量，已完成响应精确复用，完成包后零API回放',
                current_gate='不按低分重跑；执行清单未完时继续，不因收益不足暂停',current_plan='configs/cle_v41_completion_20261026/README.md',updated_at='2026-10-26')
        elif identifier in ('B04','D05'):
            row.update(status='已完成旧批次保留；新批次随执行收尾',next_action='汇总新记录的足迹、配对成绩、成本及原生产物回放；缺项如实记录',
                current_plan='configs/cle_v41_completion_20261026/README.md',updated_at='2026-10-26')
        if offline_only and identifier in targets and by[targets[identifier]]['status']!='completed':
            s=by[targets[identifier]]
            row.update(status=f"待后续API授权；已保存{s['completed']}/{s['planned']}",
                mode='仅零API复算；不派发模型或Embedding请求',
                next_action='复用已保存记录做回放和分析；新增生成、补齐标签所需生成及确认实验不执行',
                dependency='最新用户指令关闭付费派发；完整清单保留',
                stop_condition='无新授权不恢复API，不在18:00自动续跑')
            if s['kind']=='classifier':
                row.update(status='零API入口可用，但缺完整C02真实训练/开发结果',
                    dependency='C02当前仅20/480；不得用缺失结果或部分题代造最佳档标签',
                    next_action='保留拟合入口；待完整真实输入可用后零API拟合，不为拟合追加API')
        if offline_only and identifier in ('B04','D05'):
            row.update(status='本轮已保存275格零API复盘完成；全清单尚未完成',
                mode='零API回放、统计与实际代码核对',
                next_action='阅读CLE_v41迁移零API复盘与待执行清单_20261026.md；不恢复付费派发',
                current_plan='docs/CLE_v41迁移零API复盘与待执行清单_20261026.md')
        if offline_only and identifier=='D04':
            row.update(status='付费派发关闭；停止时零在途HTTP；自动续跑监控PAUSED',
                next_action='保留原失败、未知用量、已返回响应及断点，不自动恢复API')
        if offline_only and identifier in ('B01','C01'):
            row.update(mode='仅只读已生成材料和零API一致性检查',
                next_action='复用已有来源分区/绑定；新增AI标注或绑定需要API，先不执行')
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    path.write_text(stream.getvalue(),encoding='utf-8-sig',newline='')
    lines=['# 当前执行清单与阶段决策门','',f"更新：{progress['updated_at']}。2026-10-26用户已授权完整执行v4.1基础迁移清单，取代旧付费暂停；收益门仅用于结论，不阻断预定比较。",'',
        '[当前完整执行记录](../CLE_v41迁移基础实验完整执行记录_20261026.md) · [任务表](tasks.csv) · [执行入口与预算](../../configs/cle_v41_completion_20261026/README.md)', '',
        '## 已复用与本轮完成','',
        '新P3全PLT 298题、S0、S1 48格、B03 16格保留并复用，不重复付费。B03R已8/8，四条件各Joint2/2；8格零API回放一致、0新增HTTP。该单family出现天花板，不支持关系提醒额外提分。', '',
        '## 当前基础清单','', '| 包 | 真实完成/计划 | 状态 |', '|---|---:|---|']
    for s in progress['stages']:lines.append(f"| {s['id']} {s['name']} | {s['completed']}/{s['planned']} | {s.get('dispatch_status',s['status'])} |")
    lines+=['','## 执行与结论边界','',
        '工作日09:00–12:00和14:00–18:00不派发新模型请求；进程在边界等待后继续，不取消实验。固定模型、最多三卡、原P7修复/交付和原验证器；M1、契约消费者分别以整体包报告。', '',
        '所有已授权基础格完整执行。分数不好、天花板、未采用、改选不足均保留为结果；不换题、不加重复来追分。接线问题修复后复用保存响应；未知用量继续保留。', '',
        'A01原始Notion配对、A03人类金标准和Base/Plus原镜像仍缺，不能由Agent伪造；这些缺项不阻断其余实验。H01旧Q学习、H02全298题Q、H03不限卡消融及完整CLE/MASE不属于本次快速迁移清单。', '',
        '分析：本轮B03R只能说明相同已知题上的两种生成提醒都已通过，不能视为总体收益；后续用既定独立比较检查表达、消费者、粒度和Q。下一步：监督器按固定清单持续执行，完成后统一零API回放、足迹分析、配对统计和报告。', '',
        '旧状态快照保存在本轮运行根的previous_task_status，旧原始成绩和用户手改Word未修改。']
    if offline_only:
        lines[4:4]=['**最新指令优先：需要API的下一步先不执行。付费派发及自动续跑已关闭，只完成已有记录的零API回放、统计和代码分析。**','']
        lines=[line.replace('下一步：监督器按固定清单持续执行，完成后统一零API回放、足迹分析、配对统计和报告。',
            '下一步：完成现有记录的零API回放、足迹分析、配对统计和报告；缺生成结果的分类器、确认及Q比较留待后续授权。') for line in lines]
    (folder/'07_当前执行清单与决策门.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if not quiet:print('updated existing tasks.csv and current checklist; previous status retained')


if __name__=='__main__':main()
