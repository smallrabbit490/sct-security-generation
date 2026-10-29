from pathlib import Path
import sys,json,re,csv
from zipfile import ZipFile
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
repo=root.parents[3]
sys.path.insert(0,str(repo))
from tools.build_cle_weekly_package_20261028 import bars
p=root/'10月22日-10月28日实验探索报告.md'
s=p.read_text(encoding='utf8')
s=s.replace('PLT是本项目使用的代码安全题集','CLE是本项目使用经验辅助生成代码的Agent系统。PLT是本项目使用的代码安全题集')
s=s.replace('比较登记的P00、P13、P22三种生成模板','比较三种生成模板：P00保留原提示；P13增加保持正常行为和检查安全风险的要求；P22再加入三个通用示例及最小必要改动要求')
s=s.replace('![图1 本周两个起步实验分别统计；P3与P7不是同一流程]','![图1 两项起步实验的Joint通过次数；P3计划298次，P7每条件计划24次，不比较柱高推断经验收益]')
s=s.replace('![图2 四种选卡条件的计划通过占比；各计划48次，Q3有1次缺测]','![图2 四种选卡条件的Joint通过次数；各计划48次，Q3有1次缺测]')
s=s.replace('![图3 五种经验表达条件的Joint通过率，各为12题族两重复]','![图3 五种经验表达条件的Joint通过次数；每条件24次，均已测]')
s=s.replace('![图4 五档表达的计划通过占比；各计划96次，L0有1次缺测]','![图4 五档表达的Joint通过次数；各计划96次，L0有1次缺测]')
s=s.replace('![图5 三种策略的计划通过占比；各计划48次，公开规则有1次缺测]','![图5 三种策略的Joint通过次数；各计划48次，公开规则有1次缺测]')
s=s.replace('![图7 来源经验在开发和保留题上的Joint通过率，两部分样本分别统计]','![图7 来源经验的Joint通过次数；开发每条件24次，保留每条件48次，两阶段分别比较]')
s=s.replace('图1左侧给出','图1第一项给出').replace('右侧只说明','后两项只说明')
charts=[
('a8_baselines.png','两项实验分别阅读：Joint通过次数',['P3无经验（计划298）','P7空卡（计划24）','P7旧卡（计划24）'],[96,7,8],'次数；P3与P7流程及样本量不同，不直接比较。'),
('a1_q_joint.png','改变选卡后，Joint通过了多少次？',['原CLE','相似度排序','学习Q排序','打乱Q排序'],[11,13,11,13],'各计划48次；打乱Q已测47次，其余均已测48次。'),
('a2_fs_joint.png','同来源经验改变表达后，Joint通过次数',['无卡','原混合卡','仅功能建议','仅安全建议','功能安全分段'],[12,13,13,12,9],'各条件12题、每题两次重复，共24次；均已测。'),
('a3_levels_joint.png','五种表达的Joint通过次数',['L0 无卡','L1 风险提醒','L2 原理和条件','L3 目标模板','L4 来源示例'],[44,46,44,47,42],'各计划96次；L0已测95次，其他各96次。'),
('a4_classifier_joint.png','选档策略在保留题上的Joint通过次数',['分类器选档','固定L1提醒','公开文字规则'],[21,22,19],'各计划48次；公开规则已测47次，其余各48次。'),
('a5_public_metrics.png','D02流程比较：同一指标内比较两条柱',['原P7 功能','PUBLIC 功能','原P7 安全','PUBLIC 安全','原P7 Joint','PUBLIC Joint'],[37,42,67,64,30,28],'每条件计划96次；原P7已测95次，PUBLIC已测96次。'),
('a6_m1_comparison.png','来源经验：开发与保留分别比较',['开发 无经验（24次）','开发 M1（24次）','保留 无经验（48次）','保留 M1（48次）'],[11,14,20,28],'柱长表示Joint通过次数；开发用于选方案，保留用于固定方案后比较。'),
('a7_completion.png','基础清单已保存规模（不是独立题数）',['代码运行','仅选卡运行'],[1376,160],'代码运行含重复和复用；仅选卡不生成代码。'),
('a9_q_learning.png','累计获得反馈的卡片数',['初始化K0','增长第一轮K1','增长第二轮K2','增长第三轮K3（部分）'],[445,610,702,762],'总库1939张；K3截至23:01只完成243/273题。'),
('a10_fs_progress.png','功能安全阶段读数：已测Joint比例',['无卡（已测461次）','原卡（已测462次）','仅功能（已测459次）','仅安全（已测463次）','分段（已测464次）'],[38.61,42.86,39.22,41.47,41.81],'各条件已测题目集合不同；不是同题配对收益。')]
for name,title,labels,vals,foot in charts:
    bars(root/'figures'/name,title,labels,vals,suffix='%' if name=='a10_fs_progress.png' else '',foot=foot)
s=s.replace('![图9 各学习阶段累计获得反馈的卡片比例；分母1939张，K3仅完成243题]','![图9 各学习阶段累计获得反馈的卡片数；总库1939张，K3仅完成243题]')
p.write_text(s,encoding='utf8')
actions=[
'主线首段补Q定义、更新对象及反馈覆盖含义，A2区分历史Q与新模型学习Q。',
'主线补CLE、PLT、P3/P7及三数据池定义；A1图和正文明确两实验不可直接比较。',
'按内容重映射A3/A6/A7到功能安全、A4/A5到记忆选择、A8到检索及成本；A1保留新旧卡问题链接，因该节确实包含旧卡迁移。',
'A1同时列96/298计划比例与96/297已测比例。',
'A1保留原始8/24与共同配对7/23，说明截断导致缺测，不把差异算卡片收益。',
'A2图改通过次数，正文给13/47已测口径；保留原48计划分母及原检验，不把缺测写已测失败。',
'A4图改通过次数，补44/95已测口径和原差值分母；不擅自改历史检验。',
'A5补19/47已测口径，图标明计划48和缺测1；不采纳把缺测说成失败的建议。',
'A6说明191次可测、192条终态可回放是不同对象；回放含缺测记录，补30/95。',
'原文F/S是两项计数而非分数。拆为首次功能、首次安全、最终功能、最终安全四列，数值不变。',
'A9明确K0至K2完成，K3仅243/273。',
'A9定义采用卡次、更新次数、奖励资格；未查明的差额不编造逐项原因。',
'A10同时列2315已保存及2309已测，各条件分母和非配对性质明确。',
'A8新增10包逐项组成表，合计1376，明确不含P3及P7起步迁移、160仅选卡及训练复用。',
'A8/A11分别定义基础包与后续学习/功能安全账本范围，不给未经逐请求去重的总费用。',
'A8把0/0改成Q更新0次、新经验0张，并明确仅限10月26日基础包。',
'原文其余部分并不等于1788，但表述易误读；明确全1788、先36、余1752。',
'A5明确确认24题族来自单独确认名单，不属于36训练+12开发的再拆分；保留原数据来源链接。',
'读取实际rule_level与features代码，写出规则和8特征，不新拟合或改阈值。',
'A7明确开发是选方案，保留是固定方案后比较；D02历史暴露继续披露。',
'A7明确主表分母为全部24/48运行而非实际注入17/37；不另造按注入筛选的提分数字。',
'A3说明B0仅共享初析、始终无卡，四带卡条件共享卡号；补分区文字处理含义。',
'A6改成PUBLIC整套流程的结果，不把净变化归因于检查组件。',
'A9解释逐题更新与重新生成代码混合，冻结同题回测才检验评分；不改历史题序。',
'A2将Q作用证据落在同边界Q2-Q1/Q3，Q2-Q0另含候选路径差异，不声称正确率收益。',
'A4标题改为不同经验表达，区分L3/L4内容类型；补48=31+2+15及全失败不证明作用相同。',
'重绘10张结果图，统一次数/比例和分母说明，图6只表示D02。',
'主线补单元/配对/救回损失定义；T3/T4/T6/T7补规模公式；A9区分采用、更新及代码落实。',
'A9明确保存响应回放与代码重新执行不同；原已发现不一致和原成绩保留，不凭该观察虚构总体不一致率。',
'T8明示审计集参与入库筛选，不能算独立泛化；定义外部Base/Plus。独立开发集替换属新实验设计，本次写作不追溯修改。']
raw=(root/'review/dsh_session_full.md').read_text(encoding='utf-8-sig')
(root/'review/dsh_readability_original.md').write_text(raw.split('## Assistant',1)[-1].strip()+'\n',encoding='utf8')
(root/'review/readability_actions.md').write_text('# 上周周报易读性修订清单\n\n保留10月28日23:01统计截止；只修复表达、图表和导航，不修改实验及成绩。编号对应独立审阅原文。\n\n'+'\n\n'.join(f'{i}. {a}' for i,a in enumerate(actions,1))+'\n',encoding='utf8')
events=[json.loads(x) for x in (root/'review/dsh_events.jsonl').read_text(encoding='utf-8-sig').splitlines() if x.strip()]
tools=[e for e in events if 'tool' in e.get('type','')]
(root/'review/readability_verification.json').write_text(json.dumps({'session':'session-25d41bd1-35cc-462a-b22a-370303257b0f','issues':30,'processed':30,'tool_events':tools,'review_scope':'provided report text, tables and chart captions; no image pixels','source_cutoff':'2026-10-28T23:01:00+08:00'},ensure_ascii=False,indent=2),encoding='utf8')
print('Revised report, 10 charts, 30 issue dispositions; tool events',len(tools))
