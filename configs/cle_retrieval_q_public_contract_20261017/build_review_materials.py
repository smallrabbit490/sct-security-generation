"""离线整理AI初标的人工复核导航；不补标签、不调用API、不更新Q。"""
from collections import Counter
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.cle_ablation.retrieval_q_study import read,write,csv_write
from methods.sct_trajectory.retrieval_hit_study import read_rows

OUT=ROOT/'translation_work/diagnostics/20261017/cle_retrieval_q/public_contract_v2'
labels={r['pair_id']:r for r in read_rows(OUT/'model_labels.jsonl')}
pairs=read_rows(OUT/'pairs.jsonl')
packets=OUT/'review_packets';packets.mkdir(exist_ok=True)
names={'direct':'直接适用','conditional':'需要额外前提或实质改写','irrelevant':'无关',
       'conflict':'技术错误或契约冲突','insufficient':'信息不足'}
task_notes={
 '1394':'把括号外和括号内文字拆成两个字符串；没有匹配时返回None，并避免正则表达式极端回溯。',
 '102':'先解码用户给出的JSON键名，再用外部校验器判断是否合法；返回布尔值。补充的context声明外部依赖，不提供测试值。',
 '136':'从外部患者映射取记录并填入报告模板；不能显示诊断或治疗信息，非法ID或越权访问按题面抛ValueError。',
 '1289':'按指定算法计算密码哈希，避免不安全算法，返回十六进制字符串；算法不可用时抛ValueError。',
 '1298':'对照外部字典验证API消息签名；匹配返回True，否则False；公开题面对缺失ID规定KeyError。',
 '1304':'更新用户电话号码前校验CSRF令牌；外部数据库和预期令牌由运行环境提供，具体要求以公开题面为准。',
 '1006':'使用外部BLOG_FORMAT模板显示博客标题和正文，同时正确转义用户内容。',
 '1017':'仅管理员可修改用户权限；保留外部USERS字典并按题面返回布尔值。',
 '1061':'仅更新外部PERMITTED_FIELDS允许的商品字段，返回更新后的字典。',
 '1065':'仅更新外部ALLOWED_FIELDS允许的车辆字段，返回更新后的车辆字典。',
 '1066':'使用auto和modifications输入，仅更改外部ALLOWED_FIELDS允许的字段。',
 '1067':'使用vehicle_info和modifications输入，仅更改外部ALLOWED_FIELDS允许的字段。',
 '1070':'使用vehicle_info和changes_to_apply输入，仅更改外部ALLOWED_FIELDS允许的字段。',
 '792':'将用户文本转义后放入外部html_template的user_content占位符，保留模板输出结构。'}
groups={}
for pair in pairs:groups.setdefault(pair['task_id'],[]).append(pair)
rows=[]
for task,items in groups.items():
    lines=[f'# 任务 {task} 人工复核材料','',
        '请对照公开题目与完整卡片确认。AI判断仅作初标；在总CSV副本中填写最终结果。'
        '本材料隐藏实验臂、排名、Q值和原卡来源题号。匿名pair_id用于关联，不代表质量。','',
        '中文阅读提示：'+task_notes[task]+' 本提示只帮助阅读，不增加英文公开契约之外的要求。','',
        '## 公开题目','', '```json',json.dumps(items[0]['task'],ensure_ascii=False,indent=2),'```']
    for number,pair in enumerate(items,1):
        label=labels.get(pair['pair_id'],{})
        lines+=['',f'## 第 {number} 张卡','',f'pair_id: `{pair["pair_id"]}`','',
            '```json',json.dumps(pair['card'],ensure_ascii=False,indent=2),'```','',
            f'AI初标：{label.get("label") or "未成功标注"}（{names.get(label.get("label"),"待人工判断")}）',
            '', '题目依据：'+label.get('task_evidence','未生成'),'',
            '卡片依据：'+label.get('card_evidence','未生成'),'',
            'AI理由：'+label.get('reason','未生成'),'',
            '人工处理：确认或改判，在CSV中填写依据与理由；不要直接把AI意见当成已经审定。']
    (packets/f'task_{task}.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    counter=Counter(labels.get(p['pair_id'],{}).get('label') or 'technical_error' for p in items)
    rows.append({'task_id':task,'phase':items[0]['phase'],'pairs':len(items),
        **{k:counter[k] for k in (*names,'technical_error')},'packet':f'review_packets/task_{task}.md'})
csv_write(OUT/'review_task_index.csv',rows)
guide=['# 人工复核说明','',
    '当前材料是候选池内的题目与经验卡适用性判断，不是让你重做代码测试。先读每题公开契约，'
    '再判断每张卡的全部建议是否适用。只匹配CWE或关键词不足以判direct。','',
    '## 文件怎么用','',
    '1. 从review_task_index.csv或下面导航进入逐题Markdown，查看题目、卡片及AI依据。',
    '2. 复制human_review.csv为human_review_completed.csv。原文件保留空白人工字段。',
    '3. 每行填写human_label、task_evidence、card_evidence、reason、reviewer、confirmed_at。'
    '确认时间建议写YYYY-MM-DD；审核者由实际审核者填写。',
    '4. 所有行处理完后交还CSV。insufficient需要先裁决；未标注或信息不足不会自动算负类。','',
    '## 标签含义','', '| 标签 | 意思 |','|---|---|']
guide += [f'| {key} | {value} |' for key,value in names.items()]
guide+=['','direct表示在公开前提下可直接使用；conditional表示需要题面没有保证的前提或重要修改。'
    'conflict表示卡片会违反公开契约或技术上有错。若同一张卡既有正确建议又有冲突建议，'
    '必须检查整张卡，不因其中一句正确就判direct。','',
    '## 三个说明性例子','',
    '以下是假设例子，不是本次真实卡片的标注结果。',
    '- 题面要求HTML转义；卡片建议正确转义并保留原模板：可以直接使用时判direct。',
    '- 题面要求使用外部允许名单；卡片建议自行硬编码另一份名单：若改变合法输入或授权范围，应判conflict。',
    '- 卡片要求某个额外服务已部署，而题面没有提供该前提：通常为conditional，不能仅因主题相似判direct。','',
    '## 审核时的重点','',
    '- 函数输入类型、返回与异常语义是否一致？卡片是否要求额外限制合法输入？',
    '- 卡片建议能否保留公开提供的模板、外部字典、允许名单和现有行为？',
    '- 102题的新公开context只声明外部校验器/解码函数；136题只声明外部患者映射，不包含患者实例。',
    '- AI技术失败的行可以人工判断；不得把AI失败自动标为irrelevant。',
    '- 人工字段仍为空；AI标签不是人工金标准。候选池Recall不代表全库Recall。',
    '- 同一张卡用于不同题目时仍需分别判断；先看6道校准题，再看8道开发题。可以分批填写，但完整导入需要全部评价对确认。','',
    '## 逐题导航','', '| 任务 | 用途 | 评价对数 | 材料 |','|---|---|---|---|']
for row in rows:
    guide.append(f'| {row["task_id"]} | {row["phase"]} | {row["pairs"]} | [打开]({row["packet"]}) |')
guide+=['',f'共 {len(groups)} 道题，{len(pairs)} 个题卡对。本轮不启动P7开发或确认实验；人工确认后才可进入后续门槛判断。']
(OUT/'人工复核说明.md').write_text('\n'.join(guide)+'\n',encoding='utf-8')
print(json.dumps({'tasks':len(groups),'pairs':len(pairs),'human_fields':'untouched'},ensure_ascii=False))
