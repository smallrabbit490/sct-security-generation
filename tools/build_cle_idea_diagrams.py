"""将CLE任务来源与实验拆为独立SVG；子树独占宽度，不压缩结束分支的空白。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import build_cle_research_stage_map as base

ROOT = base.ROOT
OUT = ROOT / 'docs/research/diagrams/ideas_v1.0'
INDEX = 'CLE_逐条想法与来源索引_v1.0'
PLAN = '../../CLE-PLAN-20261027-seven-requirements-v01.md'
REDUCED = '../../../../configs/cle_weekly_reduced_20261028/README.md'
DETAILS = '../CLE_实验状态与阶段说明清单_v1.0.svg'
NOTION = 'https://app.notion.com/p/2026-10-22-3fcc97140eca80e39773c961ea806824'
MATERIAL = '../../../cle_memory_mechanisms_20261023/05_资料与研究依据.md'
GAP = 64
PAD = 44
SIZE = 20


def wrap_text(text, width, size, max_lines=None):
    """中文按字换行，模型名、Joint和family等连续字母数字不从中间折断。"""
    lines=[]
    line=''
    for token in re.findall(r'[A-Za-z0-9_]+(?:[./-][A-Za-z0-9_]+)*|.', str(text), re.S):
        if token=='\n':
            lines.append(line)
            line=''
        elif line and base.length(line+token,size)>width:
            lines.append(line)
            line=token
        else:
            line+=token
    if line:
        lines.append(line)
    if max_lines and len(lines)>max_lines:
        lines=lines[:max_lines]
        while base.length(lines[-1]+'…',size)>width:
            lines[-1]=lines[-1][:-1]
        lines[-1]+='…'
    return lines


base.wrap=wrap_text


@dataclass
class Node:
    id: str
    title: str
    stage: str
    body: list[str] = field(default_factory=list)
    experiments: list[str] = field(default_factory=list)
    children: list['Node'] = field(default_factory=list)
    state: str | None = None
    href: str | None = None
    width: int = 610
    height: int = 0
    span: float = 0
    x: float = 0
    y: float = 0
    depth: int = 0


def node(identity, title, stage, *body, experiments=(), children=(), state=None, href=None, width=610):
    return Node(identity, title, stage, list(body), list(experiments), list(children), state, href, width)


def specifications():
    """来源归属取已保存的原话；新增方法与执行规模明确归本项目细化。"""
    def idea(identity, question, people, quote, source, content, note=''):
        return dict(id=identity, question=question, people=people, quote=quote, source=source,
                    note=note, root=node(identity+'-source', '来源：'+people, 'S0 提出问题',
                    '要求要点：'+quote, *([note] if note else []), children=[content], width=760))

    return [
        idea('I01', 'Q值能否改变选卡并提高正确率？', '王老师（经用户转述）',
            '把记忆奖励信号Q引入CLE，测试实际作用。', PLAN+'#r1',
            node('q-plan', '固定卡片正文，分开检验选择与收益', 'S1 固定方案',
                 'Q是经验卡根据解题反馈获得的评分。正确率用Joint衡量：同一份代码功能与安全同时通过。',
                 children=[
                     node('q-history', '已做：旧模型完整学习与四臂', 'S4—S5 历史完整实验',
                          '历史结果用于说明机制与旧模型表现；不抵扣本轮新Q的分数。',
                          experiments=['A01', 'A02', 'A03'], children=[
                              node('q-mechanism', '已做：究竟换了哪些卡？', 'S2—S3 机制验证',
                                   '重复选卡区分Q影响与模型波动；核对实际采用和代码落实。',
                                   experiments=['A04', 'A16', 'A17'], children=[
                                       node('q-known', '现有判断：Q会改选，旧Q迁移未提分', 'S6 已有结论',
                                            '改选本身已经发生；是否有收益，必须看完成后的配对Joint。', state='done')])]),
                     node('q-current', '本轮：让v4.1学习自己的Q', 'S4 完整学习',
                          '固定1939张卡；先初始化303题，再增长273题三轮。每轮结束冻结Q。',
                          experiments=['A20', 'A21', 'B01', 'C01'], children=[
                              node('q-retest', '冻结后先看同题，再看迁移', 'S5 冻结完整对照',
                                   '同题回测1416次；审计集298题四臂两重复2384次。',
                                   'Q0原CLE；Q1相似度呈现；Q2学习Q；Q3同CWE打乱Q。均由LLM终选。',
                                   experiments=['C02', 'C03'], children=[
                                       node('q-conclusion', '主要判断：学习Q能否超过两种对照？', 'S6 待完成分析',
                                            '比较Q2与Q1、Q3的配对收益和损失，同时报告改选、采用及成本。',
                                            '两项主要比较用Holm校正；按题族计算区间，单独报告重复波动。', state='todo')])])])),
        idea('I02', '分轮积累解题反馈后，同题表现是否改善？', '学长（经用户转述）',
            '在D_grow分轮做题、获取报错反馈，再在这些题上选卡测Joint。', PLAN+'#r2',
            node('round-plan', '把“学Q”与“新建经验”分开', 'S1 区分两种积累',
                 '左支固定卡片只更新Q；右支从解题过程生成、演化卡片。两条支路不能混称同一种学习。',
                 children=[
                     node('round-q', '固定库：连续三轮积累反馈', 'S4 完整Q学习',
                          'K0初始化后，K1→K2→K3保持顺序；只给合法反馈且实际采用的卡更新Q。',
                          experiments=['A20', 'A21', 'B01', 'C01'], children=[
                              node('round-frozen', '同一批增长题，冻结快照回测', 'S5 同题比较',
                                   'Q1与最终K3各全273题两重复；K0/K1/K2各同54题两重复。',
                                   experiments=['C02'], children=[
                                       node('round-analysis', '轮次增加有没有产生可用信息？', 'S6 待完成分析',
                                            '画Joint、Q反馈卡覆盖和实际采纳的轮次曲线；中间54题按抽样结果解释。', state='todo')])]),
                     node('round-build', '新建库：原CLE积累新经验', 'S4 从空库建卡',
                          '三轮、主动回放与全局门控；保留每轮新卡和拒收记录。',
                          experiments=['C09'], children=[
                              node('round-use', '新卡有用，还是仅仅卡变多？', 'S5 冻结卡库比较',
                                   '新库建成后，同一模型分别使用无卡、旧库、新库。', experiments=['C10'], children=[
                                       node('round-build-analysis', '分析新卡来源及增益路径', 'S6 待完成分析',
                                            '将正文变化与Q变化分开；新增数量不等于正确率改善。', state='todo')])])])),
        idea('I03', '在同种CWE、不同题族上还能获益吗？', '用户补充；接续学长验证路径',
            '先在获取经验的题上测试，再迁移到同CWE、不同family题型。', PLAN+'#r2',
            node('transfer-define', '先固定“迁移”的边界', 'S1 数据与任务边界',
                 'CWE是漏洞类别；family是共享来源或结构的题族。训练与审计按family隔离。',
                 '本轮检验的是Q反馈跨题族迁移；旧卡库的历史暴露另列，不能称完全未见题。', children=[
                     node('transfer-same', '先确认增长题上的冻结效果', 'S4—S5 学习与同题回测',
                          '所有学习轮次完成并冻结；同题回测后进入审计集。',
                          experiments=['A20', 'A21', 'B01', 'C01', 'C02'], children=[
                              node('transfer-gate', '再在298题审计集比较四臂', 'S5 跨题族全量验证',
                                   '冻结Q与卡片；审计反馈不回流。每题每臂两次独立代码生成。', experiments=['C03'], children=[
                                       node('transfer-answer', '收益能跨题族保留，还是只改善同题？', 'S6 待完成分析',
                                            '按同CWE不同family分组看救回、损失和区间；共同报告总体Joint。', state='todo')])])])),
        idea('I04', '功能与安全经验分开，能否减少功能损失？', '王老师（经用户转述）',
            '功能安全经验分开，检查怎样在保证安全的同时让功能正常。', PLAN+'#r3',
            node('fs-define', '同一来源卡，改变功能与安全的表达', 'S1 固定干预',
                 '五组为无卡、原混合卡、仅功能、仅安全、功能安全分栏。首次带卡四组共享卡编号。',
                 '这次检验同卡分区表达；独立双库和双检索不是已完成的干预。', children=[
                     node('fs-small', '已做：小范围呈现方式对照', 'S2—S3 局部实验',
                          '比较五组，复查同一代码的修改及来源经验。', experiments=['A10', 'A18', 'A19'], children=[
                              node('fs-full', '正在推进：完整298题五组两重复', 'S5 全量功能安全对照',
                                   '固定2980次；已有完成格原位复用，负结果保留在分母。', experiments=['B02'], children=[
                                       node('fs-analysis', '分栏能否安全不退化且功能更好？', 'S6 待完成分析',
                                            '主看分栏对混合的Joint，拆出功能/安全四象限；实际读损失和救回代码。',
                                            '把公开要求缺项、来源假设误用和模型实现错误分别归因。', state='todo')])])])),
        idea('I05', '能否为不同题目选择合适的记忆程度？', '王老师（经用户转述）；汇报截图定义档位',
            '根据记忆程度训练分类器，判断什么题目对应什么程度。', PLAN+'#r4',
            node('gran-define', '程度表示内容有多具体', 'S1 固定五档',
                 'L0不用记忆；L1风险提醒；L2机制与前提；L3目标操作模板；L4来源示例。',
                 '程度不是卡片数量，也不是Q高低。新训练只用本轮真实结果。', children=[
                     node('gran-old', '已做：五档与分类器局部比较', 'S3 历史探索',
                          '五档480次；分类器、固定档、规则三策略144逻辑格。', experiments=['A14', 'A15']),
                     node('gran-first', '先用82题形成五档标签', 'S3 当前抽样探索',
                          '五档两重复820次；训练61题、开发21题，按family隔离。', experiments=['C04'], children=[
                              node('gran-ready', '就绪：离线训练并冻结', 'S4 训练',
                                   '训练≥30个family；至少两档各≥5个训练family；分类器非常量，开发路由≥两档。',
                                   experiments=['C05'], children=[
                                       node('gran-gate', '检验路由是否胜过固定档与规则', 'S5 全298题三策略',
                                            '298题×3策略×2次＝1788逻辑格。', experiments=['C06'], children=[
                                                node('gran-analysis', '按题选程度，是否真的带来收益？', 'S6 待完成分析',
                                                     '看Joint、档位变化和成本；区分“能训练”与“能提分”。', state='todo')])]),
                              node('gran-extra', '有档位差异但不就绪：只追加一次', 'S3 条件扩大',
                                   '新增互斥82题，累计164题；有真实干预且至少两种首选档才进入。',
                                   experiments=['C04E'], state='conditional', children=[
                                       node('gran-return', '追加后就绪：转左支训练', 'S4 汇合引用',
                                            '仍不就绪，或首批没有档位差异/干预：结束分类器分支，不生成其成绩。',
                                            '此处仅引用同一次C05，不增加第二次训练。', state='conditional', href='#gran-ready')])])])),
        idea('I06', '检索找到了多少真正适用的经验？', '王老师：四指标；学长：补测召回率',
            '测准确率、精确率、召回率、F1；将检索质量与代码Joint分开。', PLAN+'#r5',
            node('ret-define', '题目—卡片对，使用共同评价池', 'S1 固定测量',
                 '原题、初析、两者合并三查询；Top24向量与Top8词面联集，再加随机未召回16张。',
                 '每个题卡对AI盲标一次；人工确认后才是正式标签。', children=[
                     node('ret-old', '已做：历史模型辅助检索测量', 'S3 历史探索',
                          '199道检索任务；914个题卡对AI标签。未完成人工确认。', experiments=['A06']),
                     node('ret-first', '首批57题：增长27＋审计30', 'S3 当前抽样探索',
                          '复用同版初析和完整候选池；缺向量不能记成空返回。', experiments=['C07'], children=[
                              node('ret-human', '不需扩大：提交人工复核', 'S6 人工确认与指标',
                                   '逐对确认适用性，待裁决不算负类；导入后复算四指标。', experiments=['C08'], children=[
                                       node('ret-answer', '检索、终选、代码实现分别错在哪里？', 'S6 分层分析',
                                            '报候选池内指标；随机漏召回只作线索，不能宣称整库召回率已测。', state='todo')]),
                              node('ret-extra', '条件触发：追加互斥57题', 'S3 条件扩大',
                                   '主要CWE占原池≥5%仍缺覆盖，或任一召回区间半宽>0.10，或有效正类任务<20题。',
                                   '累计114题后结束扩大；原题卡对不重标。', experiments=['C07E'], state='conditional', children=[
                                       node('ret-return', '扩大完成：转左支人工复核', 'S6 汇合引用',
                                            '输出全部复核材料；不新增第二项人工任务。', state='conditional', href='#ret-human')])])])),
        idea('I07', '哪些问题必须完整验证，哪些可以先抽样？', '用户：全量要求及10月28日减量授权',
            '主要问题完成全量；在途实验不变，未启动探索按54/82/57题减量。', PLAN+'#r6',
            node('scope-define', '分配验证规模，不以小样本低分取消主比较', 'S1 执行要求',
                 '这张图是执行要求，不是独立科学假设；各卡均链接同一批实验，重复出现不增加运行数。',
                 href=REDUCED, children=[
                     node('scope-full', '保留完整实验', 'S4—S5 主比较',
                          'Q学习1122题次；功能安全2980次；最终Q迁移2384次；新库后卡库比较1788逻辑格。',
                          experiments=['A20', 'A21', 'B01', 'C01', 'B02', 'C03', 'C10'], children=[
                              node('scope-full-analysis', '完成后给主要问题的判断', 'S6 全量分析',
                                   '复算完整分母、配对损益、题族区间和重复波动；不将正常失败删去。', state='todo')]),
                     node('scope-sample', '未启动探索先减量', 'S3 抽样与扩大规则',
                          '中间轮同54题不自动扩大；记忆82题最多164；检索57题最多114。',
                          experiments=['C02', 'C04', 'C07'], children=[
                              node('scope-sample-analysis', '按条件扩大，按范围解释', 'S6 抽样分析',
                                   '记忆看标签可训练性；检索看覆盖与区间。探针不代替保留的主要全量。',
                                   '预算与缺原验证环境决定执行状态；成绩高低决定研究结论。', state='todo')])])),
        idea('I08', '模型能力与经验来源是否存在交叉适配？', '用户提出的研究扩展',
            '比较v3.2与v4.1使用同库、不同库，并为v4.1建立新经验库。', PLAN+'#r7',
            node('cross-define', '区分使用模型与卡库来源', 'S1 固定交叉变量',
                 '旧库1939卡由v3.2产生；新库由v4.1从空库建立。无卡对照须同P7，P3单列。',
                 'v3.2已不可用；保留其历史结果，不用v4.1冒充反向交叉。', children=[
                     node('cross-old', '已做：换模基线与旧库迁移', 'S2—S5 现有证据',
                          'P3给无经验基线；同P7空卡与旧库对照检查迁移。', experiments=['A07', 'A08']),
                     node('cross-new', '建立v4.1新库，再冻结比较', 'S4 新库建设',
                          '原CLE三轮、主动回放、全局门控；冻结新卡正文及其来源。', experiments=['C09'], children=[
                              node('cross-plt', 'PLT：同v4.1消费无卡/旧库/新库', 'S5 全量库对照',
                                   '298题三条件两重复；同时分析卡数、来源、内容和采用。', experiments=['C10'], children=[
                                       node('cross-conclusion', '判断具体卡库适配与增益', 'S6 待完成分析',
                                            '三条件可判断这两套库在v4.1上的表现；不能补成已完成的双模型交互结论。', state='todo')]),
                              node('cross-external', 'Base/Plus：在外部题集再验证', 'S5 外部环境待办',
                                   'Base115题、Plus140题；卡库三条件与P3分别保留。原验证镜像到位后执行。',
                                   experiments=['C11', 'C12'], state='external')]),
                     node('cross-ended', '旧模型剩余计划已结束', '结束分支',
                          'v3.2在线学习剩余项与反向卡库交叉不再派发；保留旧结果。', experiments=['D01', 'D02'], state='ended')])) ,
        idea('I09', '经验究竟改了哪些代码，为什么会损害功能？', '10月22日汇报材料／用户提供截图',
            '区分有用的安全检查与重建对象、替换参数、复制来源假设等改动。', MATERIAL,
            node('footprint-define', '记忆足迹：查看有卡与无卡的代码差异', 'S1 定义观察对象',
                 '截图同时出现模板检查、重定义Person、替换person。它是说明性例子，不冒充实际损失题。',
                 '汇报中的AST足迹是结构改动指标；改动量不是因果原因，仍须读具体代码。', href=NOTION, children=[
                     node('footprint-cases', '已做：从实际损失题读原因', 'S6 逐题复盘',
                          '先查题面要求，再查经验、计划、代码及验证错误。', experiments=['A05', 'A11'], children=[
                              node('footprint-remind', '已做：能否保护接口与公开要求？', 'S2—S3 最小干预',
                                   '文件—签名关系提醒、功能保持提醒、公开契约检查分别对照。',
                                   experiments=['A09', 'A12', 'A13'])]),
                     node('footprint-edit', '已做：同一代码改动哪些部分？', 'S3 反事实验证',
                          '共享原代码起点，比较功能、安全修改及来源经验的作用。', experiments=['A18', 'A19'], children=[
                              node('footprint-full', '在完整功能安全对照中追踪改动', 'S5 全量机制观察',
                                   '复用同一次B02，不新增独立付费矩阵；比较救回与损失代码的具体变化。', experiments=['B02'], children=[
                                       node('footprint-answer', '判断问题在契约、来源假设还是实现', 'S6 待完成分析',
                                            '分别标公开要求是否明确、卡片假设是否适用、代码是否落实；不只报“改动太多”。', state='todo')])])]),
            '材料没有单独标明想法提出者；足迹分析方法属于本项目细化，不署为老师原话。')
    ]


def walk(n):
    yield n
    for c in n.children:
        yield from walk(c)


def experiment_height(item, width):
    return 31 + 26*len(base.wrap(item['title'], width-32, SIZE)) + 24*len(base.wrap(
        item.get('progress', item['scale'])+'；'+item['scale'] if item.get('progress') else item['scale'], width-32, 18)) + 16


def measure(n, items, depth=0):
    n.depth = depth
    n.height = 78 + len(base.wrap(n.title, n.width-40, 23))*31
    n.height += sum(len(base.wrap(p, n.width-40, SIZE))*27+12 for p in n.body)
    n.height += sum(experiment_height(items[e], n.width-36)+10 for e in n.experiments)
    n.height += 28 if n.href else 0
    for c in n.children:
        measure(c, items, depth+1)
    n.span = max(n.width, sum(c.span for c in n.children)+GAP*max(0, len(n.children)-1))


def arrange(n, left, ys):
    n.x = left+(n.span-n.width)/2
    n.y = ys[n.depth]
    used = sum(c.span for c in n.children)+GAP*max(0, len(n.children)-1)
    cursor = left+(n.span-used)/2
    for c in n.children:
        arrange(c, cursor, ys)
        cursor += c.span+GAP


def draw_node(d, n, items):
    state = n.state
    border = base.STATES[state][1] if state else '#94a3b8'
    fill = base.STATES[state][3] if state else '#ffffff'
    if n.depth == 0:
        border, fill = '#0f766e', '#ecfdf5'
    d.rect(n.x, n.y, n.width, n.height, fill, border, 10, id=n.id,
           dash=state in ('conditional', 'external', 'ended'))
    x = n.x+20
    y = n.y+29
    d.text(x, y, n.stage, 18, '#475569', True)
    if state:
        label = base.STATES[state][0]
        badge_w = base.length(label, 17)+22
        d.badge(n.x+n.width-20-badge_w, n.y+11, label, state=state)
    y += 38
    y += d.text(x, y, n.title, 23, '#0f172a', True, width=n.width-40)
    y += 10
    for p in n.body:
        y += d.text(x, y, p, SIZE, '#334155', width=n.width-40)+12
    for identity in n.experiments:
        item = items[identity]
        _, color, pale, _ = base.STATES[item['state']]
        h = experiment_height(item, n.width-36)
        href = DETAILS+'#'+identity
        d.rect(n.x+18, y-15, n.width-36, h, pale, 'none', 6, href=href)
        d.text(x+10, y+7, identity, 19, color, True, href=href)
        bw = base.length(base.STATES[item['state']][0], 17)+22
        d.badge(n.x+n.width-30-bw, y-13, '', state=item['state'])
        yy = y+36
        yy += d.text(x+10, yy, item['title'], SIZE, '#0f172a', True, width=n.width-68, href=href)
        progress = item.get('progress')
        caption = (progress+'；' if progress else '')+item['scale']
        d.text(x+10, yy+3, caption, 18, '#475569', width=n.width-68)
        y += h+10
    if n.href:
        d.text(x, n.y+n.height-15, '打开依据／对应步骤 ↗', 18, '#2563eb', href=n.href)


def verify_tree(root):
    """只校验用户要求的分支独占、父项居中、文字边界与点击目标。"""
    nodes = list(walk(root))
    ids = [n.id for n in nodes]
    assert len(ids) == len(set(ids)), 'duplicate_node_id'
    for n in nodes:
        for c in n.children:
            assert c.y >= n.y+n.height+70, (n.id, 'missing_vertical_gap')
        if n.children:
            outer_left = min(c.x-(c.span-c.width)/2 for c in n.children)
            outer_right = max(c.x+(c.span+c.width)/2 for c in n.children)
            assert abs(n.x+n.width/2-(outer_left+outer_right)/2) < .01, 'parent_not_centered'
            for a, b in zip(n.children, n.children[1:]):
                right_a = a.x+(a.span+a.width)/2
                left_b = b.x-(b.span-b.width)/2
                assert left_b-right_a >= GAP-.01, 'subtree_columns_overlap'
        for m in nodes:
            if n.id >= m.id:
                continue
            overlap_x = min(n.x+n.width,m.x+m.width)-max(n.x,m.x)
            overlap_y = min(n.y+n.height,m.y+m.height)-max(n.y,m.y)
            assert overlap_x <= 0 or overlap_y <= 0, 'card_overlap'
    return dict(nodes=len(nodes), branches=sum(len(n.children)>1 for n in nodes),
                parent_centering='passed', subtree_reserved_space='passed', card_overlap=0)


def export_idea(spec, items, time):
    root = spec['root']
    measure(root, items)
    heights = defaultdict(int)
    for n in walk(root):
        heights[n.depth] = max(heights[n.depth], n.height)
    ys = {0:218}
    for depth in range(1,len(heights)):
        ys[depth] = ys[depth-1]+heights[depth-1]+100
    width = max(1320, root.span+PAD*2)
    arrange(root, (width-root.span)/2, ys)
    bottom = max(n.y+n.height for n in walk(root))
    d = base.Diagram(width,bottom+130,spec['question'])
    d.background(0,0,width,bottom+130,'#f8fafc','none',0)
    d.text(PAD,50,spec['id']+'  '+spec['question'],30,'#0f172a',True)
    d.text(PAD,88,'一条想法一张图 · 来源在起点 · 每个分支独占自己的列宽，结束分支下方留空',19,'#475569')
    cursor = PAD
    for state in ('done','running','recovering','todo','conditional','external','ended'):
        cursor += d.badge(cursor,108,'',state=state)+14
    d.text(PAD,164,'箭头表示本想法的验证路径；真正运行前置保留在实验详情。点击彩色实验行查看证据与前置。',18,'#475569')
    for n in walk(root):
        for c in n.children:
            x1,x2 = n.x+n.width/2,c.x+c.width/2
            middle = c.y-50
            d.line([(x1,n.y+n.height),(x1,middle),(x2,middle),(x2,c.y)],source=n.id,target=c.id)
    for n in walk(root):
        draw_node(d,n,items)
    d.text(PAD,bottom+45,'返回逐条想法索引 ↗',20,'#2563eb',True,href=INDEX+'.svg#'+spec['id'])
    d.text(PAD,bottom+80,'来源依据 ↗',18,'#2563eb',href=spec['source'])
    d.text(PAD+170,bottom+80,'当前减量协议 ↗',18,'#2563eb',href=REDUCED)
    d.text(PAD,bottom+112,'状态快照：'+time+'；相同实验在多图引用只执行一次。',17,'#64748b')
    stem='CLE_'+spec['id']+'_'+spec['question'].replace('？','')+'_v1.0'
    d.export(stem)
    result=verify_tree(root)
    result.update(file=stem+'.svg',width=width,height=bottom+130,
                  experiments=sorted({e for n in walk(root) for e in n.experiments}))
    return stem,result


def export_index(specs, filenames, snapshot, items):
    width,height=1320,360+len(specs)*146
    d=base.Diagram(width,height,'CLE逐条想法与来源索引')
    d.background(0,0,width,height,'#f8fafc','none',0)
    d.text(40,52,'CLE研究想法：谁提出，怎样验证？',32,'#0f172a',True)
    d.text(40,94,'选择一条问题，进入独立图；每张图都有来源、已有实验、下一步及判断方式。',21,'#334155')
    d.text(40,129,'8张研究问题图＋1张执行要求图；覆盖37项实验和2项条件扩展，引用重复不增加实验数。',19,'#475569')
    x=40
    for state in base.STATES:
        x+=d.badge(x,152,'',state=state)+17
    for i,(s,stem) in enumerate(zip(specs,filenames)):
        y=214+i*146
        d.rect(40,y,1240,130,'#ffffff','#cbd5e1',9,id=s['id'],href=stem+'.svg')
        d.rect(40,y,7,130,'#0f766e','none',2)
        d.text(62,y+36,s['id']+'  '+s['question'],24,'#0f172a',True,href=stem+'.svg')
        d.text(62,y+72,'来源：'+s['people'],21,'#0f766e',True)
        ids=sorted({e for n in walk(s['root']) for e in n.experiments})
        counts=Counter(items[e]['state'] for e in ids)
        labels=' · '.join(base.STATES[k][0]+str(v) for k,v in counts.items())
        d.text(62,y+107,'引用实验 '+str(len(ids))+'项：'+labels,19,'#475569')
        d.text(1170,y+74,'打开 →',20,'#2563eb',True,href=stem+'.svg')
    d.text(40,height-94,'来源归属按已保存的对话转述与汇报材料登记；未提供姓名的“学长”保留原称呼。',19,'#475569')
    d.text(40,height-58,'逐项实验状态与完整说明 ↗',20,'#2563eb',True,href=DETAILS)
    d.text(40,height-25,'状态快照：'+snapshot['time']+'。实时运行见工作台；本次只更新图与导航。',18,'#64748b')
    d.export(INDEX)


def check_links(files):
    ns={'s':'http://www.w3.org/2000/svg'}
    checked=0
    for path in files:
        root=ET.parse(path).getroot()
        assert root.get('content'), 'missing_editable_drawio'
        for a in root.findall('.//s:a',ns):
            href=urllib.parse.unquote(a.get('href',''))
            if href.startswith(('http:','https:')):
                continue
            url=urllib.parse.urlsplit(href)
            target=path.parent/url.path if url.path else path
            assert target.is_file(), (path.name,href)
            if url.fragment and target.suffix=='.svg':
                assert any(n.get('id')==url.fragment for n in ET.parse(target).getroot().iter()), (target,url.fragment)
            checked+=1
    return checked


def render(files):
    nodejs=Path('C:/Users/fujunye/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    sharp=nodejs.parents[1]/'node_modules/sharp'
    code="const sharp=require(process.argv[1]);const fs=require('fs');(async()=>{for(const f of JSON.parse(process.argv[2])){await sharp(fs.readFileSync(f)).resize({width:Math.min(1800,Math.round((await sharp(f).metadata()).width))}).png().toFile(f.replace(/\\.svg$/,'.png'));}})().catch(e=>{process.stderr.write(String(e));process.exit(1)});"
    subprocess.run([str(nodejs),'-e',code,str(sharp),json.dumps([str(f) for f in files])],check=True)


def register(specs,stems,time):
    path=ROOT/'docs/research/registers/documents.csv'
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
    known={r['document_id'] for r in rows}
    for identity,title,stem in [('index','CLE逐条想法与来源索引',INDEX)]+[(s['id'],s['question'],t) for s,t in zip(specs,stems)]:
        for ext in ('svg','drawio'):
            docid=f'CLE-DGM-20261028-idea-{identity}-{ext}'
            if docid in known:
                continue
            relative=(OUT/(stem+'.'+ext)).relative_to(ROOT).as_posix()
            rows.append(dict(document_id=docid,title=title,format=ext,original_path=relative,
                document_type='single_idea_source_experiment_diagram',authority='saved_user_quotes_and_confirmed_inventory',
                review_scope='source_people_subtree_spacing_links_and_native_structure_checked',
                proposed_standard_path=relative,move_status='new_split_view_history_preserved',
                format_relationship='shared_geometry_svg_embeds_drawio',registered_at=time))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot');parser.add_argument('--render',action='store_true')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);base.OUT=OUT
    snapshot=base.status_snapshot(args.snapshot)
    if 'snapshot' in snapshot:
        snapshot=snapshot['snapshot']
    items={i['id']:i for i in base.build_items(snapshot)}
    specs=specifications();stems=[];checks=[]
    for s in specs:
        stem,check=export_idea(s,items,snapshot['time']);stems.append(stem);checks.append(check)
    export_index(specs,stems,snapshot,items)
    files=[OUT/(s+'.svg') for s in [INDEX]+stems]
    covered={e for s in specs for n in walk(s['root']) for e in n.experiments}
    assert covered==set(items), ('experiment_coverage',set(items)-covered)
    links=check_links(files)
    if args.render:
        render(files)
    data=dict(snapshot=snapshot,source_rule='original_request_and_research_implementation_are_separate',
              ideas=[{**s,'root':asdict(s['root']),'svg':stem+'.svg'} for s,stem in zip(specs,stems)],experiments=items)
    (OUT/'ideas_and_sources.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    result=dict(ideas=len(specs),core_experiments=37,conditional_extensions=2,local_links_checked=links,
                all_experiments_covered=True,figures=checks)
    (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    register(specs,stems,snapshot['time'])
    print(json.dumps(dict(index=str(files[0]),ideas=len(specs),links=links,snapshot=snapshot['time']),ensure_ascii=False))


if __name__=='__main__':
    main()
