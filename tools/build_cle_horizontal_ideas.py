"""按七个横向阶段绘制独立思路图，来源仅放标题，分支保留独占行空间。"""
from __future__ import annotations

from dataclasses import dataclass, field
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import build_cle_idea_diagrams as previous

base = previous.base
base.STATES['deferred']=('暂缓','#64748b','#f1f5f9','#f8fafc')
base.STATES['running']=('正在运行','#c2410c','#ffedd5','#fff7ed')
# 图中合并运行与恢复；底层状态、故障记录和调度不变。
base.STATES['recovering']=base.STATES['running']
ROOT = base.ROOT
OUT = ROOT/'docs/research/diagrams/ideas_horizontal'
TEMP = ROOT/'translation_work/temp/cle_horizontal_idea_diagrams'
WIDTHS = [330, 410, 440, 470, 470, 490, 440]
GAP = 50
ROW_GAP = 50
MARGIN = 32
DETAIL = '../CLE_实验状态与阶段说明清单_v1.0.svg'
CURRENT_PLAN='../../CLE-TODO-20261022-20261028-v06.md'
REVIEW_PLAN='../../CLE-TODO-20261022-20261028-v08.md'
NARRATIVE='../../CLE-STORY-20261028-nine-ideas.md'
PLAN_SECTIONS={
    'C02':'idea02','C03':'idea03','B02':'idea04',
    'C04':'idea05','C04E':'idea05','C05':'idea05','C06':'idea05',
    'C07':'idea06','C07E':'idea06','C08':'idea06',
    'C09':'idea08','C10':'idea08','C11':'idea08','C12':'idea08','R01':'r01',
}
ET.register_namespace('', 'http://www.w3.org/2000/svg')

# 这里只改图中的表述；实验编号、真实状态、规模和跳转仍对应原记录。
CARD_TEXT = {
    'A01':('不限三张卡学习，再做同题','记录：学习通过109/273，回测100/273；并非纯排序对照。','同273题；两次流程各运行一遍'),
    'A02':('查看两种卡数上限的历史学习','记录：反馈卡669张和926张；两次起点不同，不能单算上限收益。','各303题；保留原起点与规则'),
    'A03':('旧模型比较4种选卡方式','结果：学习Q比相似度少对1题，比打乱Q多对2题。','298题；共同可比296题'),
    'A04':('反复选卡，检查Q是否换了卡','296题中281题换了卡集合，225题采用新增成员。','重复选择＋逐题采用检查'),
    'A05':('检查旧实验中18道由对变错的题','分类：13题覆盖配置，2题要求缺失，2题资源策略，1题网络。','旧模型Q实验；18题，原因可查原记录'),
    'A06':('检查检索到的卡能不能用','199题历史对照中，AI估计约9%—12%的卡直接适用。','另14题有914对AI初标；两批分开'),
    'A07':('新模型不带经验卡做题','结果：功能与安全共同通过96/297题。','298题交付；297题可测'),
    'A08':('新模型用旧卡，与无卡比较','结果：共同可测23次配对中，两组各通过7次。','12题×2种方式×2次'),
    'A09':('提醒文件与函数接口要对应','结果：8次都通过，没有拉开差距。','1题×4种设置×2次'),
    'A10':('同一批卡，换5种表达','结果：功能安全分开写，比原卡少通过4次。','12题×5种表达×2次'),
    'A11':('保住题目接口，再提供经验','结果：带经验通过14/24，无经验11/24。','12题×2种方式×2次，共48次'),
    'A12':('写代码前提醒功能要求','结果：最佳提醒比原做法多通过1次。','3种设置；合计72次'),
    'A13':('让模型按题目要求自行检查','结果：功能通过增加，共同通过反少2次。','合计192次'),
    'A14':('同题尝试5种经验详略','发现：部分题有差别，经验越详细不一定越好。','48题×5档×2次'),
    'A15':('训练分类器，自动选经验详略','结果：分类器21/48，固定简短提醒22/48。','24题×3种策略×2次'),
    'A16':('每种选卡方式重复5次','发现：Q换卡的影响超过模型自身波动。','8题×4种方式×5次'),
    'A17':('新模型尝试旧Q与三种对照','结果：学习Q通过11/48，相似度和打乱Q均13/48。','24题×4种方式×2次'),
    'A18':('从同一份代码开始修改','结果：带经验与无经验均通过6/12。','6题×2种方式×2次，共24次'),
    'A19':('换一批题，确认接口保护方案','结果：带经验多通过8次；p=0.078，未过原统计门。','24题×2种方式×2次'),
    'A20':('先在起始题上学习Q','看：哪些卡真正得到有效反馈。','303道起始题'),
    'A21':('增长题第1轮学习Q','看：换一批题后，哪些卡获得评分。','273题；第1轮'),
    'B01':('增长题第2轮学习Q','看：继续做题是否让更多卡获得有效反馈。','273题；第2轮'),
    'B02':('同298题比较5种经验用法','不给经验、给完整原卡、只给功能建议、只给安全建议、两类建议分栏。','每题5组各运行2次，共2980次'),
    'C01':('增长题第3轮学习Q','看：继续学习带来的评分是否还有用。','273题；第3轮'),
    'C02':('把评分固定，再做同一批题','比较：同54题看轮次，全273题看最终Q收益。','最终比较273题，中间轮54题；各2次'),
    'C03':('把学到的Q用到别的题族','比较：学习Q、相似度、打乱Q；原CLE作参照。','298题×4种方式×2次'),
    'C04':('同题试5档，先找真实差别','分清：正确性不同，还是只差Token消耗。','先82题×5档×2次'),
    'C05':('用训练题的留出结果选分类器','选能做对更多题的模型；平手再比输入Token。','原8个题目特征；3种参数；不重新生成'),
    'C06':('在新题上比较3种选档方式','比较：分类器、固定档、简单规则。','298题×3种策略×2次'),
    'C07':('逐张标注候选卡是否适用','比较三种查询找来的卡；每个题卡对只初标一次。','先57题；最多114题'),
    'C08':('人工确认哪些卡真正适用','用途：据此计算检索的四项指标。','本批所有题卡对'),
    'C09':('让v4.1从零积累自己的经验','先做题提卡，再按原CLE回放、改卡和筛选。','303题建起点＋原CLE三轮；不是三遍全273题'),
    'C10':('同一模型分别用无卡、旧库、新库','每格核准后复用无卡与旧库1192次，不重复付费。','298题×3组×2次；新增最多596次'),
    'C11':('换到Base/Plus再比较三种设置','看：新库的帮助能否延续到外部题集。','Base115题＋Plus140题；各设置2次'),
    'C12':('暂缓P3外部对照','原因：当前用同P7无卡回答经验是否有用。','本轮不做原255次；保留计划'),
    'D01':('旧模型剩余Q学习','状态：模型停用，剩余部分不再运行。','保留历史结果'),
    'D02':('旧模型使用新旧两库','状态：模型停用，反向比较不再运行。','保留历史结果'),
    'C04E':('标签不够时再补82题','用途：补足训练选档工具所需的例子。','再加82题；最多164题'),
    'C07E':('检索样本不足时再补57题','用途：补全主要漏洞类别，让指标估计更清楚。','再加57题；最多114题'),
    'R01':('只改一处，再用原测试验证原因','在独立副本撤销一处问题改动，比较修改前后的测试结果。','最多6题、12次本地验证；实验API调用0次'),
}

# 先写完整叙事，再把每段压缩为“为什么做—发现什么—引出哪一步”。
TASK_TEXT = {
    'q0':('给经验打分，能让代码更正确吗？','卡片历史上有用，不代表当前题也适用。','因此先查是否换卡，再查是否提分。'),
    'q1':('把选卡作用和正确率分开检验','相似度、学习Q、打乱Q共用首次候选，由模型最终选卡。','原CLE保留自己的候选规则，作系统参照。'),
    'q-old-learn':('先扩大反馈，结果却没有多做对题','反馈卡增加不等于评分更有用，因此还要比较选卡策略。'),
    'q-old-gate':('再用完整题单比较四种选卡方式',),
    'q-old-result':('旧Q没有稳定胜过相似度','这说明旧评分未达到提分目的；接着要确认它究竟有没有换卡。'),
    'q2':('成绩未升，先查Q是否真的换了卡','重复选择排除模型自身波动，采用记录检查新卡是否进入生成。'),
    'q3':('确认换卡后，再看新模型代码成绩','这里固定旧卡与旧Q，只换用v4.1完成代码比较。'),
    'q4':('旧Q未提分，因此由v4.1重新学评分','卡片正文不变，Q从零开始；先初始化，再做三轮增长题。'),
    'q5':('学完后固定评分，分两步验证收益','先做原题，再换审计题；各先试2题并计入正式名单。'),
    'q6':('已确认换卡；新评分的收益待比较','同时稳定胜过相似度和打乱Q，才确认本轮Q有额外价值。','只换卡没多做对题，就结论为改变选择、未改善本批正确率。'),
    'r0':('反复做题，是增加反馈还是增加收益？','学长提出分轮获取报错反馈，再在同题检查Joint。'),
    'r1':('先分清积累的是评分还是新卡','固定卡学Q回答追加反馈；另建新库回答新增经验。','两种变化分开，才能解释效果来自哪里。'),
    'r4-q':('先固定卡片，逐轮积累评分','反馈卡由445增至610、702张；下一步要查覆盖有没有转成收益。'),
    'r5-q':('在线成绩不可直接比较，因此重做同题','同54题比较轮次，再用全273题检查最终Q；两次运行均保留。'),
    'r6-q':('覆盖扩大后，有没有多做对题？','后轮在同题稳定更好，支持追加反馈；只增加覆盖、不提高Joint，就没有转化成正确代码。','在线成绩另列，不用它代替固定条件回测。'),
    'r2-card':('新卡支线先检查能否正常提取经验','先用正式名单中的2题试跑，保存结果后接续。'),
    'r4-card':('随后按原CLE提卡、回放和改卡',),
    'r5-card':('新库建好后，再与旧库和无卡比较',),
    'r6-card':('这条支线只判断最终新库的价值','每轮新卡没有同题对照，不推断越建越好。','最终新库和外部题集的判断接图08。'),
    't0':('会做练过的题，是否也会做同类新题？','要求先测同题，再测同种漏洞、不同题族。'),
    't1':('先固定目标集合，再看代码成绩','Q反馈覆盖过的CWE、没覆盖过的family，才是本条目标。','生成前确定集合；旧卡来源是否见过也单列。'),
    't4':('先完成已有题上的评分学习','这里产出待检验的Q，不在审计题上更新。'),
    't5':('第一步：练过的题能否受益？','完成两次同题比较，给后面的迁移一个参照。'),
    't5-gate':('第二步：固定评分后换题族','在298题上完成四组、两次比较，分别分析目标集合。'),
    't6':('原题提升与跨题族提升分别下结论','只在原题观察到提升，就只确认原题收益。','同漏洞异题族也稳定胜过相似度和打乱Q，才支持该范围迁移。'),
    'f0':('安全通过了，为什么功能却坏了？','功能与安全要求可能混在卡里，因此尝试分开表达。'),
    'f1':('同一张卡换表达，才知道分栏有没有用','比较原卡、仅功能、仅安全、分栏，再加无卡参照。'),
    'f2':('先前提醒实验已经验证流程可运行','全部通过只说明没有拉开差距。'),
    'f3':('随后小对照没有出现分栏收益',),
    'f-interface':('解释支线：先保护题目原有接口',),
    'f-confirm':('开发有增加，再用保留题确认',),
    'f-interface-result':('接口保护有净增，但未过原统计门','这是另一种方法，不用它证明功能安全分栏有效。'),
    'f-edit':('解释支线：从同一份代码再编辑',),
    'f-edit-result':('编辑对照持平，未增加通过次数','这说明本次编辑没有净收益；它不是五组分栏的结论。'),
    'f5':('小对照少通过4次，仍完成原定全量','主要看分栏对原卡的Joint；其余三组解释功能、安全差异。','首次来源卡相同；完整结果后读救回和损失代码。'),
    'f6':('分栏带来兼顾、取舍，还是没有改善？','Joint增加且安全总通过数不降，支持本批更能兼顾。','功能升安全降，是取舍；无净增，就是本次未改善。','完成统计后，再用图09的代码复验解释原因。'),
    'g0':('每道题都需要同样详细的经验吗？','如果不同题需要不同表达，就有按题自动选择的价值。'),
    'g1':('同题比较五种呈现，先看差别','无经验、短提醒、原理、目标模板、来源示例。','模板和示例是两种用法，不是越详细一定越好。'),
    'g2':('旧实验有档位差异，但分类器没胜固定档',),
    'g3':('分类器未胜固定档，先补真实选择依据','82题比较五档、各两次；查同向差别和重复翻转。','只差Token时，就研究省算力。'),
    'g4':('有可训练标签，再选一个简单分类器','用训练侧留出题实际Joint选模型；开发题只检查。'),
    'g5':('模型定好后，到新题上与简单方法比较','先用6题验证流程，再完成298题、两次运行。'),
    'g6':('自动选档到底提高正确率还是节省成本？','同时稳定胜过固定档和规则，支持提分。','Token减少至少20%、质量区间下界高于−1个百分点，支持省Token。','两者都未达到，就结束本轮分类器路线。'),
    'g3-extra':('若有选择机会，但训练例子还不够','不足30个训练题族、或两档未各覆盖5个题族等原条件触发时，再补82题。'),
    'g4-return':('补完后仍不足，就结束这一轮','满足条件则返回同一项C05，不再增加模型和批次。'),
    's0':('经验没帮忙，是没找到还是没用好？','先知道哪些卡适用，才能区分检索、选择和实现。'),
    's1':('用共同评价池，公平比较三种查询','题面、初析、二者合并分别检索；合并候选，再加固定随机16张。'),
    's2':('历史估计显示，直接适用卡比例偏低',),
    's3':('因此先用57题逐卡判断适用性','先试增长、审计各1题，再完成其余题。','一对题卡只初标一次，三查询共用标签。'),
    's-human':('AI给初判，人工决定正式标签','先用2题统一标准，再确认本批完整评价池。'),
    's6':('标签把检索、选择和实现三个问题分清','适用但未召回是检索漏失；已召回未选是选择漏失。','采用后写错须读匹配代码；没有匹配轨迹就不拼链。','人审后给池内四指标，再判断哪种查询值得保留。'),
    's3-extra':('若覆盖不足或区间太宽，再补57题','按既定条件只扩大一次，最多114题。'),
    's6-return':('追加题同样经人工确认，再合并指标','不重标旧题，不挑比例更好的一批替换首批。'),
    'a0':('都做全量太贵，只做探针又答不了主问题','因此主要效果完整比较，辅助探索先抽样。'),
    'a1':('保留关键全量，压缩辅助规模','活动实验照原计划；中间Q轮次54题、记忆82题、检索57题。'),
    'a2':('先试通新流程，试跑算入正式名单','技术正确就接续；不因少量低分取消主要比较。'),
    'a4':('Q学习保持原规模，避免改变已启动条件',),
    'a5':('学习后完整回答同题和换题收益',),
    'a6':('每阶段分析后，再按价值接续','稳定提分达到2个百分点，优先继续；省Token至少20%且守住质量，保留效率成果。','实际账本记录费用，理论复用量不写成已节省。'),
    'a3':('记忆先找训练机会，最多补一批',),
    'a-fr':('检索先估适用性，最多补一批',),
    'a6-sample':('交付实际样本的正式指标','人审后报告57题或114题结果，不外写成全题池。'),
    'a-fs':('已启动功能安全全量继续完成','结果和原因各有去处，见图04和图09。'),
    'a-gr':('标签足够后，离线选定分类器',),
    'a-gr-gate':('最后的选档收益仍靠完整比较','同298题比较固定档与规则，见图05。'),
    'a-build':('先建出新库，再购买效果比较',),
    'a-cross':('复用严格匹配结果，只补缺少的条件','审计集和外部集分开回答，见图08。'),
    'x0':('换模型后，旧经验还合适吗？','先固定v4.1，判断旧库是否够用、新库是否值得建立。'),
    'x1':('保持做题流程相同，只换经验设置','比较无卡、旧库、新库；P3只作另一流程的参照。'),
    'x-p3':('已有无经验P3成绩，作为起点参照',),
    'x2':('同P7的小对照中，旧卡没有拉开差距',),
    'x2-new':('因此先让v4.1用2题试着产生经验','提取和验证正常后，复用这2题继续原名单。'),
    'x4':('按原CLE建立新模型自己的卡库','三轮提取、回放、改卡和筛选，保存最终新库。'),
    'x5':('建出新库后，再检验这笔投入的价值','同模型同流程比较三库；先12题计入总体。','核准复用1192次，新生成最多596次；建库费用另算。'),
    'x6':('新库是否比旧库与无卡都更好？','稳定胜过两组，才确认这套新库的额外价值。','审计题参与过建库筛选；外部迁移看下面另一条比较。'),
    'x5-external':('换到外部题集，检查收益能否延续','等原验证环境；每集先2题，再完成三库比较。'),
    'x6-external':('外部结果决定能把结论推广到哪里','Base和Plus分别比较；两集都胜才说两集均有收益。','只一集胜就报告那一集；建库成本另算。'),
    'x5-p3':('同P7空卡已能回答问题，暂缓重复投入','P3外部255次留待流程比较，本轮不做。'),
    'x-end':('v3.2停用，双模型交互不再强行补测','保留已有结果；不由单模型三库差异推断谁更会生产经验。'),
    'm0':('同样参考经验，为什么有时反而写错？','经验可能带来安全修复，也可能夹带来源题的错误假设。'),
    'm1':('先在同一对照内找出具体代码差别','本轮先看原卡与分栏；Q、新旧库分别检查自己的对照。'),
    'm-old':('旧18题先给出要查哪些问题',),
    'm-old-result':('先查配置覆盖，再查要求是否缺失','旧代码已发现这些问题；本轮还需读取自己的差异代码。'),
    'm3':('此前尝试过提醒、自查和固定代码编辑',),
    'm-history-result':('几个方法的结果没有形成同一条提分曲线','提醒最多净增1次，自查净少2次，固定代码编辑持平。','因此不能只换一种提示，就认定已解决原因。'),
    'm5':('先从完整对照中挑出由对变错或由错变对的题','一起读题面、卡、计划、两份代码和测试，先提出原因预测。','使用已有结果；不另买一轮代码生成。'),
    'm6':('先登记原因预测，再做单点复验','原失败复现、单处修改恢复测试，支持该处的局部作用。','未恢复说明单独这一处不足；功能恢复安全退步是取舍。','结果回写本条与功能安全图，不替换正式成绩。'),
}

PLAIN_PHASES = ['S0 为什么做','S1 怎样比较','S2 先验证哪一步','S3 小实验与发现',
                'S4 继续学习或建方法','S5 完成主要比较','S6 结论与下一步']

STORY_LINES = [
    '反馈更多未提分 → 确认Q确实换卡 → 旧Q迁移仍未提分 → 重学Q后检验收益',
    '分轮练习 → 分开评分与新卡 → 固定同题回测 → 判断追加反馈是否值得',
    '先看原题收益 → 固定评分换题族 → 按真实反馈来源分组 → 判断迁移范围',
    '安全修复损坏功能 → 同卡拆分表达 → 小对照未改善 → 全量检验并读代码',
    '详略可能因题而异 → 旧分类器未胜固定档 → 找稳定差异 → 新题验证提分或省Token',
    '返回卡适用比例低 → 建共同评价池 → AI初标与人工确认 → 定位卡丢在哪一步',
    '全量过多、探针不足 → 保留主比较 → 辅助抽样与精确复用 → 按收益决定后续投入',
    '换模型后旧卡未显优势 → 从零建新库 → 同模型三库比较 → 外部题集验证',
    '经验可能引入错误假设 → 旧例提供线索 → 本轮找代码差异 → 单点复验检验原因',
]


def wrap_clean(text,width,size,max_lines=None):
    tokens=[]
    for token in re.findall(r'[A-Za-z0-9_]+(?:[./-][A-Za-z0-9_]+)*|.',str(text),re.S):
        if token in '，。；：、？！）】》' and tokens and tokens[-1]!='\n':
            tokens[-1]+=token
        else:
            tokens.append(token)
    lines=[]
    line=''
    for token in tokens:
        if token=='\n':
            lines.append(line);line=''
        elif line and base.length(line+token,size)>width:
            lines.append(line);line=token
        else:
            line+=token
    if line:
        lines.append(line)
    return lines[:max_lines] if max_lines else lines


base.wrap=wrap_clean


@dataclass
class Task:
    key: str
    phase: int
    title: str
    text: list[str] = field(default_factory=list)
    experiments: list[str] = field(default_factory=list)
    children: list['Task'] = field(default_factory=list)
    state: str | None = None
    href: str | None = None
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0
    span: float = 0


def task(key, phase, title, *text, experiments=(), children=(), state=None, href=None):
    return Task(key, phase, title, list(text), list(experiments), list(children), state, href)


def specifications():
    def spec(stem, question, source, start):
        return dict(stem=stem, question=question, source=source, root=start)
    return [
        spec('01_Q值选卡', 'Q值能否改变选卡并提高正确率？', '王老师：引入记忆奖励Q，检验选卡与正确率',
            task('q0',0,'明确Q的作用','比较卡片编号、实际采用和Joint。',children=[
                task('q1',1,'固定对照','固定1939张卡正文。','回测统一使用预检通过的修订契约。','四臂：原CLE、相似度、学习Q、打乱Q。',children=[
                    task('q-old-learn',4,'旧模型完整学习',experiments=['A01','A02'],children=[
                        task('q-old-gate',5,'旧Q全量四臂',experiments=['A03'],children=[
                            task('q-old-result',6,'复用历史判断','Q已经影响选卡；旧冻结Q迁移未提高Joint。',state='done')])]),
                    task('q2',2,'检查改选与模型波动',experiments=['A04','A16'],children=[
                        task('q3',3,'新模型使用旧Q',experiments=['A17'],children=[
                            task('q4',4,'v4.1重新学习Q',experiments=['A20','A21','B01','C01'],children=[
                                task('q5',5,'先检查前缀，再完成冻结对照','C02先2题20格；C03先2题16格。','通过后接续原名单，前缀计入总量。',experiments=['C02','C03'],children=[
                                    task('q6',6,'判断Q是否带来增益','比较学习Q与相似度、打乱Q的Joint。','分析配对救回与损失、Q覆盖、采用及成本。',state='todo')])])])])])])),
        spec('02_分轮积累', '分轮追加做题反馈后，Q能否帮助做对更多同题？', '学长：分轮获取报错反馈，再在同题上选卡测试Joint',
            task('r0',0,'比较各轮学习效果','关注正确率、反馈卡覆盖和实际采用。',children=[
                task('r1',1,'分开两种积累','固定卡片学Q；从空库生成新卡。',children=[
                    task('r4-q',4,'分轮积累Q反馈',experiments=['A20','A21','B01','C01'],children=[
                        task('r5-q',5,'先2题贯通，再冻结各轮Q回测','五条件两重复20格计入1416格。',experiments=['C02'],children=[
                            task('r6-q',6,'绘制轮次变化','比较各轮Joint、Q覆盖和实际采纳。',state='todo')])]),
                    task('r2-card',2,'C09先做2题原生建卡探针','从空库沿原题序做题、提卡与落盘。','技术通过后复用前缀继续。',state='todo',children=[
                    task('r4-card',4,'原CLE积累新经验',experiments=['C09'],children=[
                        task('r5-card',5,'冻结后比较新旧库',experiments=['C10'],children=[
                            task('r6-card',6,'分析新卡的作用','检查哪些新卡被采用，以及它们救回或损失了哪些题。',state='todo')])])])])])),
        spec('03_跨题族迁移', '同种CWE、不同题族上还能获益吗？', '用户：先验证同题，再迁移到同CWE、不同family的题目',
            task('t0',0,'检验跨题族迁移','CWE表示漏洞类别；family表示题族。',children=[
                task('t1',1,'隔离学习与审计题族','固定303题初始化、273题增长和298题审计名单。','修订契约下配对；审计时冻结Q及经验卡。',children=[
                    task('t4',4,'完成分轮Q学习',experiments=['A20','A21','B01','C01'],children=[
                        task('t5',5,'同题回测',experiments=['C02'],children=[
                            task('t5-gate',5,'不同题族评价',experiments=['C03'],children=[
                                task('t6',6,'对比同题与迁移收益',state='todo')])])])])])),
        spec('04_功能安全分开', '功能与安全经验分开，能否减少功能损失？', '王老师：分开功能与安全经验，在保证安全的同时保留正常功能',
            task('f0',0,'同时保住功能与安全','比较功能、安全及共同通过率Joint。',children=[
                task('f1',1,'固定同卡五组对照','无卡、原混合卡、仅功能、仅安全、功能安全分栏。','首次带卡四组使用相同来源卡编号。',children=[
                    task('f2',2,'检查关键约束提醒',experiments=['A09'],children=[
                        task('f3',3,'比较表达与代码改动',experiments=['A10'],children=[
                            task('f5',5,'完整298题五组两重复',experiments=['B02'],children=[
                                task('f6',6,'判断分栏是否有效',state='todo')])])]),
                    task('f-interface',3,'接口保护开发',experiments=['A11'],children=[
                        task('f-confirm',3,'接口保护保留题确认',experiments=['A19'],children=[
                            task('f-interface-result',6,'历史接口保护结论',state='done')])]),
                    task('f-edit',3,'固定原代码编辑',experiments=['A18'],children=[
                        task('f-edit-result',6,'历史编辑结论',state='done')])])])),
        spec('05_记忆程度分类', '能否为不同题目选择合适的记忆程度？', '王老师：按题目需要的记忆程度训练分类器',
            task('g0',0,'按题目选择记忆程度','比较分类器、固定档位和简单规则。',children=[
                task('g1',1,'固定五档与题族划分','L0无记忆；L1风险提醒；L2机制与前提。','L3目标操作模板；L4来源示例。',children=[
                    task('g2',3,'复用五档与路由探索',experiments=['A14','A15'],children=[
                        task('g3',3,'先2题五档贯通，再形成82题标签','先20格检查真实档位与共同来源卡，接续其余800格。',experiments=['C04'],children=[
                            task('g4',4,'满足训练条件后冻结','训练≥30个family；至少两档各≥5个训练family。','分类器非常量，开发路由至少使用两档。',experiments=['C05'],children=[
                                task('g5',5,'新分类器先6题，再全量比较','先36逻辑格核对公开路由、档位复用与两重复独立。',experiments=['C06'],children=[
                                    task('g6',6,'判断按题选档的收益','比较Joint、档位变化和成本，分析哪些题需要更具体的记忆。',state='todo')])]),
                            task('g3-extra',3,'有档位差异但未就绪：追加82题','最多累计164题。',experiments=['C04E'],state='conditional',children=[
                                task('g4-return',4,'达标后继续C05训练','仍不具备训练条件则结束分类器分支。',state='conditional',href='#g4')])])])])])),
        spec('06_检索质量', '检索找到了多少真正适用的经验？', '王老师：测四项检索指标；学长：补测召回率',
            task('s0',0,'测量题卡适用性','报告准确率、精确率、召回率和F1。',children=[
                task('s1',1,'固定共同候选池','原题、初析、两者合并三种查询。','向量Top24＋词面Top8联集，再加随机16张未召回卡。',children=[
                    task('s2',3,'复用历史检索测量',experiments=['A06'],children=[
                        task('s3',3,'先2题完整池，再完成57题','增长、审计各1题贯通三查询与逐卡盲标。','依赖同版初析和分析，不等待新库交叉。',experiments=['C07'],children=[
                            task('s-human',3,'人工确认',experiments=['C08'],children=[
                                task('s6',6,'计算四指标',state='todo')]),
                            task('s3-extra',3,'达到扩大条件：追加57题','主要CWE缺覆盖，或区间半宽>0.10，或有效正类任务<20题。','最多累计114题。',experiments=['C07E'],state='conditional',children=[
                                task('s6-return',6,'继续C08人工复核与指标分析',state='conditional',href='#s-human')])])])])])),
        spec('07_全量与抽样安排', '哪些比较必须全量，哪些探索先抽样？', '用户：保留主要全量比较，未启动探索按54、82、57题减量',
            task('a0',0,'为每条问题分配实验规模','主要结论靠完整比较，辅助探索采用固定样本。',children=[
                task('a1',1,'固定执行规模','活动学习与功能安全全量继续。','Q中间54题；记忆首批82题；检索首批57题。',children=[
                    task('a2',2,'新流程先检查正式名单前缀','探针计入原规模与预算。','只按技术检查放行，不按低Joint取消主比较。',state='todo',children=[
                    task('a4',4,'完整学习',experiments=['A20','A21','B01','C01'],children=[
                        task('a5',5,'完成冻结对照',experiments=['C02','C03'],children=[
                            task('a6',6,'完成全量后给出主结论','分析Joint、配对损益、题族差异与成本。',state='todo')])])]),
                    task('a-fs',5,'活动功能安全',experiments=['B02']),
                    task('a3',3,'记忆抽样',experiments=['C04'],children=[
                        task('a-gr',4,'记忆训练',experiments=['C05'],children=[
                            task('a-gr-gate',5,'选档全量评价',experiments=['C06'])])]),
                    task('a-fr',3,'检索抽样',experiments=['C07'],children=[
                        task('a6-sample',6,'人工与正式指标',experiments=['C08'])]),
                    task('a-build',4,'新建库',experiments=['C09'],children=[
                        task('a-cross',5,'新库比较',experiments=['C10','C11'])])])])),
        spec('08_模型与卡库交叉', 'v4.1使用新库是否优于旧库和无卡？', '用户：建立v4.1新库，并比较同一模型使用不同经验库',
            task('x0',0,'比较模型与卡库的配合','区分代码生成模型与经验卡来源。',children=[
                task('x1',1,'固定卡库比较条件','同P7比较无卡、v3.2旧库、v4.1新库。','P3无经验基线单独保留。',children=[
                    task('x-p3',5,'复用换模P3全量基线',experiments=['A07']),
                    task('x2',2,'复用旧库迁移探针',experiments=['A08'],children=[
                        task('x2-new',2,'新库建卡先2题真实探针','沿原初始化题序检查提卡、验证和落盘；通过后接续。',state='todo',children=[
                        task('x4',4,'从空库建立v4.1新库','主动回放首2题再核对更新链；保持原三轮和全局门控。',experiments=['C09'],children=[
                            task('x5',5,'先12题三库对照，再完成298题','前缀72逻辑格：48格复用FFS，最多新生成24格。',experiments=['C10'],children=[
                                task('x6',6,'分别判断审计集效果与外部泛化','建库使用D_gate门控，C10回答同审计集的卡库效果。','独立外部泛化由Base/Plus结果判断。',state='todo')]),
                            task('x5-external',5,'原环境就绪后外部确认',experiments=['C11'],state='external',children=[
                                task('x6-external',6,'外部结论',state='todo')])])])]),
                    task('x5-p3',5,'P3外部暂缓',experiments=['C12'],state='deferred'),
                    task('x-end',6,'v3.2剩余计划结束','v3.2已停用，保留历史结果。',experiments=['D01','D02'],state='ended')])])),
        spec('09_经验代码改动', '经验改了哪些代码，为什么会损害功能？', '10月22日汇报思路：通过代码改动分析记忆的作用',
            task('m0',0,'解释经验带来的代码变化','区分安全检查、对象重建、参数替换和来源假设。',children=[
                task('m1',1,'对照题面、卡片与代码','围绕接口、输入、返回格式和安全要求检查差异。',children=[
                    task('m-old',3,'历史退步题',experiments=['A05'],children=[
                        task('m-old-result',6,'旧实验排查线索',state='done')]),
                    task('m3',3,'独立的历史改错尝试',experiments=['A12','A13','A18'],children=[
                        task('m-history-result',6,'历史判断',state='done')]),
                    task('m5',5,'在全量五组中追踪改动',experiments=['B02'],children=[
                        task('m6',6,'解释救回与损失',experiments=['R01'],state='todo')])])]))
    ]


def walk(n):
    yield n
    for c in n.children:
        yield from walk(c)


def simplify(specs,items,snapshot):
    """只替换图示文字，原实验数据与执行协议不写回。"""
    keys={n.key for s in specs for n in walk(s['root'])}
    assert keys==set(TASK_TEXT),('unmapped_stage_cards',keys-set(TASK_TEXT),set(TASK_TEXT)-keys)
    assert set(items)==set(CARD_TEXT),'unmapped_experiment_card'
    for s in specs:
        for n in walk(s['root']):
            n.title,*n.text=TASK_TEXT[n.key]
    display={}
    for identity,item in items.items():
        title,meaning,scale=CARD_TEXT[identity]
        display[identity]={**item,'title':title,'meaning':meaning,'scale':scale}
    # 队列把协议省略视为依赖可继续；图上仍明确是暂缓未执行，而非实验完成。
    display['C12'].update(state='deferred',progress='暂缓；未执行')
    r01=next((t for t in snapshot.get('tasks',[]) if t['id']=='FS.single_edit'),{})
    if r01.get('status')=='completed':
        display['R01']['state']='done'
    elif r01.get('status')=='running':
        display['R01']['state']='running'
    learning=next(p for p in snapshot['packages'] if p['key']=='FQ_LEARN')
    for identity,stage in [('A20','K0'),('A21','K1'),('B01','K2'),('C01','K3')]:
        summary=learning.get('stages',{}).get(stage,{})
        if display[identity]['state']=='done' and summary.get('Q_covered_cards') is not None:
            display[identity]['meaning']=f"结果：已有{summary['Q_covered_cards']}张卡得到做题反馈。"
    return display


def rows(text, width, size):
    return base.wrap(text,width,size)


def exp_height(item,w):
    return (40+len(rows(item['title'],w-28,22))*30
            +len(rows(item['meaning'],w-28,20))*27
            +len(rows(item['scale'],w-28,18))*25+16)


def measure(n,items):
    n.w=WIDTHS[n.phase]-24
    n.h=28+len(rows(n.title,n.w-32,24))*33+12
    n.h+=sum(len(rows(t,n.w-32,20))*28+10 for t in n.text)
    n.h+=sum(exp_height(items[e],n.w-24)+12 for e in n.experiments)
    n.h+=18
    for c in n.children:
        assert c.phase>=n.phase, 'phase_goes_backwards'
        measure(c,items)
    cursor=0
    for c in n.children:
        if c.phase==n.phase:
            cursor=max(cursor,n.h+ROW_GAP)
        cursor+=c.span+ROW_GAP
    n.span=max(n.h,cursor-ROW_GAP if n.children else 0)


def place(n,xs,y):
    n.x=xs[n.phase]+12
    n.y=y
    cursor=y
    for c in n.children:
        if c.phase==n.phase:
            cursor=max(cursor,y+n.h+ROW_GAP)
        place(c,xs,cursor)
        cursor+=c.span+ROW_GAP


def draw_task(d,n,items):
    color=base.STATES[n.state][1] if n.state else '#94a3b8'
    fill=base.STATES[n.state][3] if n.state else '#ffffff'
    d.rect(n.x,n.y,n.w,n.h,fill,color,8,id=n.key,href=n.href,
           dash=n.state in ('conditional','external','ended','deferred'))
    y=n.y+31
    y+=d.text(n.x+16,y,n.title,24,'#0f172a',True,width=n.w-32)+12
    for t in n.text:
        y+=d.text(n.x+16,y,t,20,'#334155',width=n.w-32)+10
    for identity in n.experiments:
        item=items[identity]
        state=item['state']
        _,color,pale,_=base.STATES[state]
        h=exp_height(item,n.w-24)
        href=(REVIEW_PLAN+'#'+PLAN_SECTIONS[identity]) if identity in PLAN_SECTIONS else DETAIL+'#'+identity
        d.rect(n.x+12,y-12,n.w-24,h,pale,'none',5,href=href)
        d.text(n.x+24,y+9,identity,19,color,True,href=href)
        bw=base.length(base.STATES[state][0],17)+22
        d.badge(n.x+n.w-24-bw,y-10,'',state=state)
        yy=y+40
        yy+=d.text(n.x+24,yy,item['title'],22,'#0f172a',True,width=n.w-52,href=href)
        yy+=d.text(n.x+24,yy+5,item['meaning'],20,'#334155',width=n.w-52)
        d.text(n.x+24,yy+12,item['scale'],18,'#475569',width=n.w-52)
        y+=h+12


def verify(root):
    nodes=list(walk(root))
    for n in nodes:
        assert len({c.key for c in nodes})==len(nodes)
        for c in n.children:
            assert c.y>=n.y
            assert c.y+c.span<=n.y+n.span+.01
        for a,b in zip(n.children,n.children[1:]):
            assert b.y>=a.y+a.span+ROW_GAP-.01, 'branch_space_collapsed'
        for other in nodes:
            if other.key<=n.key:
                continue
            assert min(n.x+n.w,other.x+other.w)<=max(n.x,other.x) or min(n.y+n.h,other.y+other.h)<=max(n.y,other.y), 'task_overlap'


def current_answers(snapshot):
    """将历史研究判断与本轮实际完成数分开，避免绿色完成被读成正收益。"""
    packages={p['key']:p for p in snapshot['packages']}
    def progress(key):
        p=packages[key]
        return f"{p.get('completed',0)}/{p.get('planned','待定')}"
    return [
        '已确认Q改变具体卡号；旧Q未胜相似度。本轮新Q迁移已完成'+progress('FQ_GATE')+'次。',
        '固定卡片的分轮Q回测已完成'+progress('FQ_RETEST')+'次；每轮新卡的同题收益尚未检验。',
        '本轮跨Q反馈题族比较已完成'+progress('FQ_GATE')+'次；学习覆盖增加不是迁移收益。',
        '12题小对照中分栏比原卡少通过4次；298题主比较已完成'+progress('FFS')+'次。',
        '旧分类器通过21/48，固定提醒22/48；新五档标签已完成'+progress('FG_LABELS')+'次。',
        '已有历史AI适用率估计；本轮人工确认的正式四指标仍须由C08交付。',
        '主要对照保留全量；Q中间轮54题、记忆82题、检索57题；已有结果逐格核准复用。',
        '已完成新模型消费旧库的试跑；新库收益尚待比较，停用的v3.2不参与新配对。',
        '旧18题已定位配置等问题；本轮原因先读代码，再用最多6题单点复验检查。',
    ]


def export(s,items):
    root=s['root']
    measure(root,items)
    xs=[]
    x=MARGIN
    for width in WIDTHS:
        xs.append(x)
        x+=width+GAP
    width=x-GAP+MARGIN
    top=312
    place(root,xs,top)
    height=top+root.span+34
    d=base.Diagram(width,height,s['question'])
    d.background(0,0,width,height,'#f8fafc','none',0)
    d.text(MARGIN,52,s['question'],36,'#0f172a',True)
    d.text(MARGIN,96,s['source'],25,'#334155')
    d.text(MARGIN,134,'当前判断：'+s['answer'],22,'#334155',href=s['narrative_href'])
    d.text(MARGIN,168,'叙事：'+s['story'],21,'#334155',href=s['narrative_href'])
    for p,label in enumerate(PLAIN_PHASES):
        fill='#eaf2ff' if p<4 else '#fff3d6' if p<6 else '#e9f8ee'
        d.background(xs[p]-4,212,WIDTHS[p]+8,height-234,fill,'none',10)
        d.rect(xs[p],226,WIDTHS[p],60,'#0f172a','none',7)
        d.text(xs[p]+15,265,label,25,'#ffffff',True)
        if p<6:
            d.line([(xs[p]+WIDTHS[p]+3,256),(xs[p+1]-7,256)],'#64748b')
    for n in walk(root):
        for c in n.children:
            if c.phase==n.phase:
                if len(n.children)>1:
                    lane=n.x-GAP*.25
                    pts=[(n.x,n.y+n.h/2),(lane,n.y+n.h/2),(lane,c.y+c.h/2),(c.x,c.y+c.h/2)]
                else:
                    pts=[(n.x+n.w*.88,n.y+n.h),(n.x+n.w*.88,c.y)]
            else:
                gutter=n.x+n.w+(GAP+24)/2
                pts=[(n.x+n.w,n.y+n.h/2),(gutter,n.y+n.h/2),(gutter,c.y+c.h/2),(c.x,c.y+c.h/2)]
            d.line(pts,source=n.key,target=c.key)
    for n in walk(root):
        draw_task(d,n,items)
    verify(root)
    d.export(s['stem'])
    path=TEMP/(s['stem']+'.svg')
    svg=ET.parse(path).getroot()
    svg.find('{http://www.w3.org/2000/svg}desc').text='横向七阶段任务图，任务按执行状态着色。'
    (OUT/path.name).write_text(ET.tostring(svg,encoding='unicode'),encoding='utf-8')
    return d


def export_pngs(files):
    """同步导出两倍分辨率PNG，内嵌原生图；不改变SVG内容。"""
    from PIL import Image,PngImagePlugin
    node=Path('C:/Users/fujunye/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    sharp=node.parents[1]/'node_modules/sharp'
    code="const fs=require('fs'),sharp=require(process.argv[1]);(async()=>{for(const f of JSON.parse(process.argv[2])){const out=f.replace(/\\.svg$/,'.png'),tmp=out+'.rendering';const b=await sharp(fs.readFileSync(f),{density:144}).png().toBuffer();fs.writeFileSync(tmp,b);fs.renameSync(tmp,out);}})().catch(e=>{process.stderr.write(String(e));process.exit(1)});"
    subprocess.run([str(node),'-e',code,str(sharp),json.dumps([str(p) for p in files])],check=True)
    for svg in files:
        source=ET.parse(svg).getroot()
        info=PngImagePlugin.PngInfo()
        info.add_text('mxfile',urllib.parse.quote(source.attrib['content'],safe="~()*!.'-"))
        png=svg.with_suffix('.png')
        with Image.open(png) as image:
            image.load()
            assert image.size==(round(float(source.attrib['width'])*2),round(float(source.attrib['height'])*2))
            image.save(png,pnginfo=info,dpi=(144,144))
        with Image.open(png) as image:
            image.verify()


def apply_updates(specs, items, updates):
    """把阶段分析的实际结论压入对应图；结构、实验编号和科学结果均不推算。"""
    for number, change in updates.items():
        spec = specs[int(number)-1]
        nodes = {n.key:n for n in walk(spec['root'])}
        experiments = {e for n in nodes.values() for e in n.experiments}
        if not change.get('answer') or set(change.get('tasks', {})) - set(nodes):
            raise ValueError('invalid_idea_stage_update:' + str(number))
        if set(change.get('cards', {})) - experiments:
            raise ValueError('invalid_idea_experiment_update:' + str(number))
        spec['answer'] = change['answer']
        if change.get('story'):
            spec['story'] = change['story']
        for key, text in change.get('tasks', {}).items():
            if len(text) != 3 or not all(isinstance(t,str) and t.strip() for t in text):
                raise ValueError('stage_update_needs_title_and_two_lines')
            nodes[key].title, *nodes[key].text = text
        for key, text in change.get('cards', {}).items():
            if len(text) != 3 or not all(isinstance(t,str) and t.strip() for t in text):
                raise ValueError('card_update_needs_title_result_and_scale')
            items[key] = {**items[key], **dict(zip(('title','meaning','scale'),text))}


def main(snapshot_path=None,only=None,updates_path=None):
    OUT.mkdir(parents=True,exist_ok=True)
    TEMP.mkdir(parents=True,exist_ok=True)
    base.OUT=TEMP
    snapshot=base.status_snapshot(snapshot_path)
    items={i['id']:i for i in base.build_items(snapshot)}
    items['R01']={'id':'R01','state':'todo','actors':['Codex分析'],'title':'单点代码复验','meaning':'本地复验','scale':'最多6题'}
    r01=next((t for t in snapshot.get('tasks',[]) if t['id']=='FS.single_edit'),{})
    if r01.get('status') in ('completed','running'):
        items['R01']['state']='done' if r01['status']=='completed' else 'running'
    specs=specifications()
    for i,(s,answer,story) in enumerate(zip(specs,current_answers(snapshot),STORY_LINES),1):
        s['answer']=answer
        s['story']=story
        s['narrative_href']=NARRATIVE+f'#idea{i:02d}'
    items=simplify(specs,items,snapshot)
    if updates_path:
        apply_updates(specs,items,json.loads(Path(updates_path).read_text(encoding='utf-8')))
    covered={e for s in specs for n in walk(s['root']) for e in n.experiments}
    assert covered==set(items), ('missing_experiments',set(items)-covered)
    if only is not None:
        specs=[s for i,s in enumerate(specs,1) if i in only]
    ns={'s':'http://www.w3.org/2000/svg'}
    checked=0
    for s in specs:
        export(s,items)
        path=OUT/(s['stem']+'.svg')
        svg=ET.parse(path).getroot()
        for a in svg.findall('.//s:a',ns):
            href=urllib.parse.unquote(a.get('href',''))
            url=urllib.parse.urlsplit(href)
            target=path.parent/url.path if url.path else path
            assert target.is_file(),href
            if url.fragment and target.suffix=='.svg':
                assert any(n.get('id')==url.fragment for n in ET.parse(target).getroot().iter()),href
            elif url.fragment:
                assert f'id="{url.fragment}"' in target.read_text(encoding='utf-8'),href
            checked+=1
        visible=''.join(t.text or '' for t in svg.findall('.//s:text',ns))
        assert all(word not in visible for word in ['v1.0','状态快照','返回逐条','经用户转述','本图','版本说明',
            '前缀','逻辑格','贯通','公开路由','物理HTTP','冻结','自动恢复','正在恢复','运行中'])
    export_pngs([OUT/(s['stem']+'.svg') for s in specs])
    (TEMP/'source_snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(svgs=len(specs),local_links=checked,covered=len(covered),output=str(OUT)),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,help='使用叙事对应的只读状态，避免同次交付的统计时点不同。')
    parser.add_argument('--only',type=int,nargs='+',choices=range(1,10),help='仅刷新指定思路编号，其他图原样保留。')
    parser.add_argument('--updates',type=Path,help='已完成阶段的实际结论与卡片文字；不改变图结构或实验。')
    args=parser.parse_args()
    main(args.snapshot,args.only,args.updates)
