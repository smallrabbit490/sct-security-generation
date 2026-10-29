"""Repackage the two existing report periods without changing historical evidence."""
from pathlib import Path
import csv
import shutil
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/research'
REPORTS = DOCS / 'reports'
STAMP = datetime.now().astimezone().isoformat(timespec='seconds')


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + '\n', encoding='utf-8')


def replace(path, old, new):
    text = path.read_text(encoding='utf-8-sig')
    assert old in text, (path, old[:60])
    write(path, text.replace(old, new))


def main():
    calendar = '''# CLE周报周期与时间归属

本规则依据用户2026年10月27日的明确要求。周报以北京时间记录：首期为10月14日至21日，属于一次性的八日周期；此后固定为周四至下周三，每周三完成当周总结和写作。

| 周期ID | 日期范围（首尾均包含） | 周三收尾日 | 当前报告定位 |
| --- | --- | --- | --- |
| W20261014 | 2026-10-14至2026-10-21 | 10月21日 | 历史周报，现按新格式追溯整理 |
| W20261022 | 2026-10-22至2026-10-28 | 10月28日 | 本周报告；10月28日收尾前为周中稿 |
| W20261029 | 2026-10-29至2026-11-04 | 11月4日 | 下一周期，尚未开始 |

标题分别为“10月14日-10月21日实验探索报告”“10月22日-10月28日实验探索报告”“10月29日-11月4日实验探索报告”。文件ID使用完整年月日，例如CLE-RPT-20261022-20261028-weekly-v01；实验本身原有ID和运行路径不随周报改名。

## 三个时间分别登记

实验发生时间决定结果归属哪一周；结果统计截止时间说明这版报告实际看到了哪里；报告整理时间说明何时完成写作。10月22日写出的报告不因此把10月21日前的实验改算到下一周。之后新增的原因分析应标为后续复盘，不能写成当时已得出的判断。

跨周实验按运行ID连接：上一周记当时完成的前缀及剩余任务，下一周记本周新增和累计完成。总量不能重复算成两周新增。只有完整组间对照完成后，才能用对应完整分母报告结论。

## 待做实验的时间边界

“待做实验”位于详细实验列表之前，记录该周已经提出、截至该版截止时间仍未完成的当周任务及跨周遗留。每项有名称、原因、步骤和当周状态；状态注明提出或来源时间，必要时标明由哪一周结转。尚未发生的未来结果不能用于改写历史待做状态。

本周新提出但尚未排入本周执行的完整研究包，放在“本周新增后续规划”中并链接全局任务清单，不能写成这周承诺完成的实验。跨周结转也不代表重新授权运行。已经在本周完成的任务进入【A】结果，不再留在期末【T】待做列表。截止日之后才提出的任务不得倒填到本周。

历史报告保留当时的暂停、未测和未完成人审状态。后续恢复或完成，写入后续周报并附日期互引，不把旧周报的“未完成”改成“已完成”。

## 周三写作

每周三22:00（Asia/Shanghai）启动当周总结，标明实际结果截止时刻；当日截止后有实质新结果，作为同周期增补，不移入下周、不预填未来结果。周中版本明确标“周中稿”，周三完成来源核对和写作后再标“周三收尾版”。数据或人审仍缺失时如实交付，写报告不启动新付费实验。

Markdown是重组周报的编辑源，Word由同一正文生成，并核对内部跳转与分页。用户手动定稿的历史Word保留为原件，不以旧Markdown覆盖。当前模板为CLE-TPL-weekly-experiment-report-v03；旧周一至周日模板和10月26日-11月1日报告保留，但不再作为有效周历入口。
'''
    write(DOCS / 'weekly_reporting_calendar.md', calendar)

    oldtpl = DOCS / 'templates/CLE-TPL-weekly-experiment-report-v02.md'
    tpl = oldtpl.read_text(encoding='utf-8-sig')
    tpl = tpl.replace('［周一日期］至［周日日期］　统计截至：［日期、时间］', '［周四日期］至［下周三日期］　结果统计截至：［日期、时间，北京时间］\n\n版本状态：［周中稿／周三收尾版／历史追溯整理版］。安排状态截至：［日期、时间］；整理日期：［日期］。首期仅一次使用2026年10月14日至21日。')
    tpl = tpl.replace('本节列出截至本报告统计时间尚未完成的实验，按实际执行顺序排列。', '本节还原本报告所属周的待做事项：只收录当周已提出并安排、或由前周结转且截至本版统计时间仍未完成的任务，按当时执行顺序排列。不得把现在的新任务倒填进历史周，也不得用后来的完成结果覆盖当周未完成状态。')
    tpl = tpl.replace('实验原因：为了回答', '当周状态：［未开始／进行中／暂停／等待材料；写明截至日期］。来源时间：［当周提出日期，或前周结转的原任务与日期］。\n\n实验原因：为了回答', 1)
    tpl = tpl.replace('实验原因：根据[要求二]', '当周状态：［截至日期及未完成量］。来源时间：［提出日期／结转周］。\n\n实验原因：根据[要求二]', 1)
    tpl = tpl.replace('下一步先执行[【T1】](#t1)，解决［最直接的证据缺口］；随后完成[【T2】](#t2)，判断［后续问题］。具体操作已在“待做实验”中列明，本节集中说明执行优先级及其对研究主线的影响。', '截至当周截止时点，拟将[【T1】](#t1)中的［未完成部分］结转至［下周期日期］，随后安排[【T2】](#t2)。这表示当时的计划，不预先声称下周已经执行。尚未排入当周的全量研究包另列“本周新增后续规划”，链接全局任务清单；下一周新出现的要求只写入下一周报告。')
    tpl = tpl.replace('报告按周一至周日编排，标题为“10月X日-10月X日实验探索报告”，跨月写全日期。注明统计截止时间，旧实验说明复用范围，累计用量不冒充本周新增。', '报告按周四至下周三编排，每周三完成总结与写作。首期2026年10月14日至21日为唯一例外；随后为10月22日至28日、10月29日至11月4日。标题为“10月X日-10月X日实验探索报告”，跨月写全日期。分别登记实验发生时间、统计截止时间和写作时间；旧实验说明复用范围，累计用量不冒充本周新增。具体规则见[周报周期与时间归属](../weekly_reporting_calendar.md)。')
    tpl = tpl.replace('本模板v02', '本模板v03')
    write(DOCS / 'templates/CLE-TPL-weekly-experiment-report-v03.md', tpl)

    old = REPORTS / 'CLE-RPT-20261026-20261101-weekly-v01'
    new = REPORTS / 'CLE-RPT-20261022-20261028-weekly-v01'
    new.mkdir(exist_ok=True)
    shutil.copytree(old / 'figures', new / 'figures', dirs_exist_ok=True)
    body = (old / (old.name + '.md')).read_text(encoding='utf-8-sig')
    body = body.replace('# 10月26日-11月1日实验探索报告', '# 10月22日-10月28日实验探索报告', 1)
    body = body.replace('报告周期：2026年10月26日至11月1日　结果统计截至：10月27日01:02', '报告周期：2026年10月22日至10月28日　结果统计截至：10月27日01:02（北京时间）\n\n版本状态：周中稿，10月28日周三收尾。安排状态截至10月27日本次修订；本版于10月27日整理。10月28日尚未发生的结果不计入；本周以前的材料仅作为明确标注的历史参照。')
    body = body.replace('截至统计时间，v4.1基础迁移清单已完成', '本周先完成无经验P3的298题基线及原P7空卡／1939卡的48次局部对照[【A8】](#a8)。截至统计时间，后续v4.1基础迁移清单已完成', 1)
    start = body.index('<a id="todo"></a>')
    end = body.index('<a id="experiments"></a>')
    pending = '''<a id="todo"></a>
## 二、本周待做实验与结转事项

本节记录10月22日至28日这周截至本版的未完成事项。前周已暂停的v3.2在线学习仍作为历史缺口保存，不把它当成本周已经恢复的任务。10月26日至27日新提出的全量矩阵属于本周新增研究规划，后文单列；它不是10月14日至21日已经安排的实验。

<a id="t1"></a>
### 【T1】下一批全量验证的共同规格与精确复用核对

当周状态：10月27日已形成七项要求与全量包清单；共同执行规格、逐格抵扣和最终预算尚待落实。本项是本周新安排的零API准备工作，尚未执行的付费包不写成已启动。

实验原因：回应[要求六](#r6)和[要求七](#r7)。只有确认旧结果与新对照使用相同输入和规则，才能完整利用已有工作，同时知道还缺哪些全量实验。

实验步骤：

1. 固定D_init 303题、D_grow 273题、D_gate 298题及题族归属，登记公开题面和契约版本。
2. 对齐模型、P7流程、卡库、Q状态、候选范围、重复编号与验证器，逐格确定直接复用或仅作历史参照。
3. 列出剩余任务、完整规模、执行顺序和累计预算，将其写入对应全量包；本周报告只登记计划，不自动派发。

[返回要求六](#r6)　[返回待做实验](#todo)

<a id="t2"></a>
### 【T2】检索适用性标签的人工复核与正式四指标

当周状态：前周结转；本版仍未完成人工确认。914个题卡对的AI标签是历史材料，不能写成本周新标注914对，也不能自动当作人工结论。

实验原因：回应[要求五](#r5)。缺少确认后的适用卡分母，无法给出正式召回率，代码通过率和Q覆盖率都不能代替这个判断。

实验步骤：

1. 核对已有题目、卡片正文和标签规则是否仍一致，直接复用一致的AI初标和复核表。
2. 人工逐对确认直接适用、有条件适用、无关、冲突或信息不足；信息不足单独裁决。
3. 在共同候选池内计算四指标，单列空返回、技术失败和冲突率；未完成人审时保留模型辅助估计，不填正式通过。

[返回要求五](#r5)　[返回待做实验](#todo)

<a id="t3"></a>
### 【T3】Base与Plus原验证环境补齐

当周状态：10月24日至25日换模基线任务遗留。PLT已完成，Base 115题与Plus 140题尚未运行，等待原验证镜像。

实验原因：原三集基线需要使用同一套有效验收规则。没有原镜像，不能用其他后端的成绩冒充已完成外部验证[【A8】](#a8)。

实验步骤：

1. 补齐原safecoder-python-validator:local及其必要父镜像，核对与原项目的对应关系。
2. 完成官方参考实现的正向校准，确认隐藏测试反馈不回传，保持经验和Q边界。
3. 环境满足后再按对应已授权实验协议接续Base／Plus；先记录完成数、缺测、F／S／Joint及成本，不将未运行计为0分。

[返回待做实验](#todo)　[前往基线结果](#a8)

### 本周新增后续规划

10月26日至27日新增或重排了新模型分轮Q学习、同题回测和全D_gate评价、功能安全全量对照、记忆程度与分类器全量验证、新卡库及两模型交叉比较。这些包尚未执行，具体步骤、数量及先后依赖见[七项要求全量任务清单](../../CLE-PLAN-20261027-seven-requirements-v01.md)。本周首先落实【T1】，不把整个未来矩阵列作本周待完成的承诺。10月28日收尾时按当时记录更新本节，再决定哪些任务结转到10月29日至11月4日。

<!-- pagebreak -->
'''
    body = body[:start] + pending + body[end:]
    body = body.replace('实验导航：[【A1】Q作用]', '实验导航：[【A8】本周换模基线](#a8)　[【A1】Q作用]', 1)
    next_start = body.index('<a id="next"></a>')
    body = body[:next_start] + '''<!-- pagebreak -->
<a id="a8"></a>
### 【A8】本周先完成的无经验基线与旧卡库迁移对照

#### 1. 实验思路

本周先回答“换成v4.1后，无记忆Agent能做对多少题；旧1939卡库加入原P7后是否已有明显帮助”。前一个问题采用原P3无经验流程，后一个问题采用原P7空卡与带卡对照，两者生成步骤不同，分别统计，不能直接相减当作记忆收益。这是[要求七](#r7)后续交叉实验的基础材料。

#### 2. 实验步骤

1. 使用deepseek-v4.1-flash-1017，保持原P3初析、规划、生成和最多一次修订，在PLT的298道D_gate题运行；不输入、不生成经验，不更新Q。
2. 保留原43题结果，修复实际TLS传输问题后续跑247题，再依用户授权补跑剩余8题；保留失败请求和未知用量，最终298题保存代码均零API回放。
3. 另外固定12题、每题两次重复，在P7中比较空卡与旧1939卡库；每个题次共享首次初析，最多三卡、最多一次修复，不学习Q。
4. 对48个P7单元逐一回放；将技术缺测与模型答错分开，比较完整配对成绩，而不是把单次多通过一题直接归为经验作用。

#### 3. 实验结果

![图8 本周两个起步实验分别统计；P3与P7不是同一流程](figures/a8_baselines.png)

| 实验与条件 | 执行／计划 | F通过 | S通过 | Joint通过 |
| --- | --- | --- | --- | --- |
| P3 无经验 | 298／298 | 111／298 | 232／298 | 96／298 |
| P7 空卡 | 24／24 | 7／24 | 18／24 | 7／24 |
| P7 1939卡 | 24／24 | 8／24 | 20／24 | 8／24 |

P3完整测量297题，最终Joint为32.21%；P7空卡完整测量23个单元，带卡24个，双方均完整的23对中Joint均为7／23。P3已知Token为3,841,636，30次物理请求用量未知；P7合计2,063,129 Token（其中Embedding 46,461），另15次请求尝试用量未知。两个来源的请求计数口径不同，费用均不写成实付账单，也不与【A7】累计数直接相加。

#### 4. 实验分析

图8左侧给出新模型在无经验完整任务集上的基线；右侧只说明这12题两重复的旧卡迁移表现。P7原始总分带卡多1个通过，但唯一差异涉及空卡生成截断；排除不完整配对后双方相同。因此，这一轮建立了可复用的换模起点，尚未证明旧卡能够稳定提分。它也不能替代后来要求的同P7、同名单、两模型两卡库全量交叉分析。后续【A1】至【A6】是在此后开展的机制比较，不把这些局部单元追加到P3的298题分母。

原始证据：[10月25日P3全量报告](../../../CLE_P3无经验Agent_PLT全量基准报告_20261025.md)、[10月25日P7迁移报告](../../../CLE_v41Flash1017_P7空卡与1939卡迁移实验报告_20261025.md)。原始完成时间分别见各报告；本节属于10月22日至28日这一周。

[返回要求七](#r7)　[返回本周实验主线](#main)　[返回实验导航](#experiments)

<a id="next"></a>
## 四、阶段判断与当周后续安排

截至10月27日，已经完成的固定机制清单说明：Q确实影响选卡，但稳定提分仍未建立；功能安全分区和分类器也尚未形成优势；来源经验M1出现值得完整验证的正向信号。全量无经验P3已经完成，不能把P3与P7的流程差异当成卡片收益。这些判断分别由【A1】至【A8】限定在其实际条件内。

本周剩余工作首先是[【T1】共同规格与复用核对](#t1)，为完整实验确定实际缺口；同时保留[【T2】人工标签](#t2)及[【T3】原验证环境](#t3)的未完成状态。10月28日周三再核对当周新增结果与任务状态，完成本期总结。下一周期为10月29日至11月4日；现有全量矩阵的最终排期写入全局任务清单，不提前把下一周实验写成已开展。

## 五、周期与文档映射

本报告覆盖10月22日至28日，当前仍为周中稿。原“10月26日-11月1日”版本的实验数据保留，其周历划分已由本版更正；两版不能作为两次独立实验累计。10月14日至21日的Q结果见[首期历史周报](../CLE-RPT-20261014-20261021-weekly-v01/CLE-RPT-20261014-20261021-weekly-v01.md)。10月22日用户手动定稿和10月26日14:26快照仍保留原件。

每周三总结，日期归属、历史待做及跨周结转按[周报时间规则](../../weekly_reporting_calendar.md)执行。结果、累计用量、写作日期与后续安排分别登记；MD与Word的【A】【T】编号对应同一正文和内部书签。
'''
    write(new / (new.name + '.md'), body)

    # Update only navigation and current template policy; old reports are untouched.
    readme = DOCS / 'README.md'
    text = readme.read_text(encoding='utf-8-sig')
    a = text.index('- **当前周报格式与示例')
    b = text.index('- **当前研究安排', a)
    text = text[:a] + '''- **周报周期**：[周期与时间归属](weekly_reporting_calendar.md)。首期10月14–21日；此后周四至下周三，10月22–28日、10月29日–11月4日，每周三总结。待做还原该周截止时状态，后来的任务不倒填。
- **首期历史周报**：[Word](reports/CLE-RPT-20261014-20261021-weekly-v01/10月14日-10月21日实验探索报告.docx) · [Markdown](reports/CLE-RPT-20261014-20261021-weekly-v01/CLE-RPT-20261014-20261021-weekly-v01.md)。结果截至10月21日22:26暂停快照；10月27日追溯整理，不覆盖10月22日用户定稿。
- **本周周中稿**：[10月22日-10月28日 Word](reports/CLE-RPT-20261022-20261028-weekly-v01/10月22日-10月28日实验探索报告.docx) · [Markdown](reports/CLE-RPT-20261022-20261028-weekly-v01/CLE-RPT-20261022-20261028-weekly-v01.md)。结果截至10月27日01:02，安排状态截至10月27日修订；10月28日再收尾。包含本周P3／P7起步实验及后续机制清单，未来全量矩阵单独链接。
- **当前周报模板v03**：[Word](templates/CLE-TPL-weekly-experiment-report-v03.docx) · [Markdown](templates/CLE-TPL-weekly-experiment-report-v03.md)。主线、当周待做、实验结果互相跳转。v02和原10月26日–11月1日版本保留为周历修订前历史材料，不再作为当前入口。生成命令为 `tools/build_cle_weekly_report.py --source <Markdown路径> --output <Word路径>`。
''' + text[b:]
    text = text.replace('周报已采用上方v02', '周报已采用上方v03')
    write(readme, text)
    for path in [ROOT/'AGENTS.md', ROOT/'skills/cle-result-analysis/SKILL.md']:
        text = path.read_text(encoding='utf-8-sig').replace('CLE-TPL-weekly-experiment-report-v02', 'CLE-TPL-weekly-experiment-report-v03').replace('周报模板v02', '周报模板v03')
        text = text.replace('按周一至周日编排', '首期2026年10月14–21日，此后按周四至下周三编排，每周三总结；待做还原该周截止时状态，不倒填后来任务')
        needle = '## '
        pos = text.find(needle)
        instruction = '周报时间归属以 `docs/research/weekly_reporting_calendar.md` 为准：10月14–21日为一次性首期，随后10月22–28日、10月29日–11月4日，固定周四至周三。每周三总结写作；周中稿不预填未来结果。历史待做保留当周状态，后续计划和当周待做分列，写作日期不改变实验归属。\n\n'
        if path.name == 'AGENTS.md':
            text = text[:pos] + instruction + text[pos:]
        write(path, text)

    registry = DOCS / 'registers/documents.csv'
    with registry.open(encoding='utf-8-sig', newline='') as f:
        reader=csv.DictReader(f); fields=reader.fieldnames; rows=list(reader)
    for row in rows:
        if row['document_id'] in ['CLE-TPL-weekly-experiment-report-v02',old.name]:
            row['authority']='historical_calendar_superseded_20261027_original_preserved'
    entries=[('CLE-TPL-weekly-experiment-report-v03','10月X日-10月X日实验探索报告（周报模板）',DOCS/'templates','template','current_weekly_template'),
             (new.name,'10月22日-10月28日实验探索报告',new,'weekly_report','current_week_in_progress_cutoff_20261027_0102'),
             ('CLE-RPT-20261014-20261021-weekly-v01','10月14日-10月21日实验探索报告',REPORTS/'CLE-RPT-20261014-20261021-weekly-v01','weekly_report','retrospective_week_cutoff_20261021_222642')]
    for did,title,folder,kind,authority in entries:
        for fmt in ['md','docx']:
            name=did+'.'+fmt if fmt=='md' or kind=='template' else title+'.docx'
            rel=(folder/name).relative_to(ROOT).as_posix()
            rows.append(dict(zip(fields,[did,title,fmt,rel,kind,authority,'pending_render_and_link_review',rel,'new_edition_originals_preserved','markdown_master_same_body_word_export',STAMP])))
    with registry.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


if __name__=='__main__':
    main()
