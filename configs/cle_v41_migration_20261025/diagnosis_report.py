"""汇总事后逐题归因、51张采用卡复核与下一次诊断规格；不调用模型。"""
import csv
import json
from collections import Counter
from pathlib import Path
from .resume import ROOT,RUN,read,write

RAW=RUN/'diagnosis_v1'
CURATED=ROOT/'results/curated/cle_v41_migration_20261025/diagnosis'

NOTES={
 '100':('当前测试通过','先解码再验证落实；没有新观察到的功能损害。','unquote','保留功能的安全动作'),
 '1256':('当前测试通过，边界覆盖有限','254长度上限来自经验，题面未写具体长度；当前测试未验证该边界，不能记成已证实有害。','254','来源数值条件'),
 '1266':('公开绑定不完整＋重建空数据','题面给Patient但未说明patients注册表；模型新建Patient及空注册表，合法患者被当作不存在。','PATIENT','公共环境与模型实现共同问题'),
 '335':('题面与测试输入类型冲突','题面pwd:str；夹具实际全部传bytes。模型遵从str后在hash前拒绝，不能归因于Q或黑名单机制。','isinstance(pwd','输入类型契约冲突'),
 '1306':('允许输入范围未说明','测试把application/*+json列为合法；题面只说检查content type。两臂仅接收application/json，拒绝该例。','application/json','功能边界未明，存在额外输入限制'),
 '1317':('默认值/返回结构缺失＋XML实现错误','题面未说明format_type默认json和XML返回字典；代码又使用缺失依赖或标准库不支持的XMLParser参数。','XMLParser','错误API与来源任务返回假设'),
 '1322':('模型覆盖已公开外部绑定','题面明确提供ALLOWED_DOMAINS，两臂都重新定义为空列表；允许外域因此被拒绝。','ALLOWED_DOMAINS','明确公共绑定被覆盖'),
 '1341':('模型改变接口/模板绑定，另有转义错误','题面只有user_content入参、xml_template为外部上下文；代码改为必需入参或使用自造默认模板。E1-r1还有重复转义。','def generate_xml_response','接口与绑定错误'),
 '1343':('一次输出截断，其他三格通过','E0-r1规划JSON错误且生成截断；E1两重复都落实安全解析建议；第二重复E0也过，未建立稳定增益。','def execute_custom_query','采用实现链成立，效果证据有限'),
 '1352':('当前测试通过，阈值与共享状态未充分测量','记忆引入4096消息字节/128发送者长度等来源常量；题面未给数值。夹具仅测1条正常消息和1条长消息，未测容量边界。','MAX_','来源常量与弱测量边界'),
 '1409':('模型覆盖已公开外部绑定','题面明确给VALID_SIGNATURES，两臂重定义为空字典；合法签名查找失败，安全错误签名因一律0而通过。','VALID_SIGNATURES','明确公共绑定被覆盖'),
 '1000':('模板绑定被覆盖＋来源占位符遗留','BLOG_FORMAT被自造HTML覆盖。E1-r2首次采用源999卡的heading/description，修复轮虽拒绝卡仍保留该假设。','BLOG_FORMAT','来源任务假设的具体传递路径'),
}


def csv_write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    packets=[read(p) for p in (RAW/'tasks').glob('*.json')]
    original=[json.loads(s) for s in (RUN/'final/rows.jsonl').read_text().splitlines()]
    allcards=read(RAW/'cards.json');bycard={};rowreviews=[];taskreviews=[]
    for p in packets:
        tid=p['task_id'];primary,reason,token,role=NOTES[tid]
        result={'task_id':tid,'family_id':p['family_id'],'primary':primary,'reason':reason,'rows':[]}
        for r in p['rows']:
            final=r['attempts'][-1];history=sorted({i for a in r['attempts'] for i in a['adopted_ids']})
            code=Path(final['code_path']).read_text(encoding='utf-8')
            lines=[i+1 for i,s in enumerate(code.splitlines()) if token in s]
            for a in r['attempts']:
                for i in a['adopted_ids']:
                    bycard.setdefault(i,[]).append({'task_id':tid,'cell_id':r['cell_id'],'attempt':a['attempt'],
                        'code':a['code_path'],'joint':a['joint']})
            item={'task_id':tid,'cell_id':r['cell_id'],'arm':r['migration_arm'],'repeat':r['repeat'],
                'measured':final['measured'],'F':final['functional'],'S':final['security'],'Joint':final['joint'],
                'primary':primary,'reason':reason,'history_adopted_ids':';'.join(history),
                'final_adopted_ids':';'.join(final['adopted_ids']),'code':final['code_path'],
                'key_lines':';'.join(map(str,lines)),'native_evidence':final['evidence_path'],
                'source_packet':str(RAW/'tasks'/f'{tid}.json'),'review_basis':'Codex posthoc fixture-visible; not blinded applicability labels'}
            rowreviews.append(item);result['rows'].append(item)
        taskreviews.append(result)
    csv_write(CURATED/'row_diagnoses.csv',rowreviews);write(CURATED/'task_diagnoses.json',taskreviews)
    cardreviews=[]
    for identifier,sites in sorted(bycard.items()):
        c=allcards[identifier];tid=sites[0]['task_id'];text=' '.join(str(c.get(k) or '') for k in
            ('high_level_invariant','positive_principle','negative_guardrail','fix_directive','applicability','exclusion_conditions'))
        risks=[]
        if 'XMLParser(resolve_entities=False)' in text:risks.append('本机标准库参数错误已复现；目标代码包含相同用法')
        if 'heading=' in text or 'description=' in text:risks.append('源999占位符名称在1000-r2代码及修复分析中延续')
        if '254' in text:risks.append('源任务长度阈值；目标题面未给数字，当前测试未证实边界')
        if '4096' in text or '128' in text:risks.append('源任务容量/作者长度常量；目标题面未给该数字')
        if 'Element' in text and tid=='1317':risks.append('XML返回Element/字典需目标契约裁决；不得照搬来源约定')
        if 'IOError' in text or ('return None' in text and tid=='1409'):risks.append('来源异常/失败返回约定需改为目标的FileNotFoundError及0/1')
        cardreviews.append({'card_id':identifier,'source_task_id':c['source_task_id'],'target_task':tid,
            'adopted_occurrences':len(sites),'observed_code_paths':';'.join(sorted({s['code'] for s in sites})),
            'organization_review':NOTES[tid][3],'specific_risks':'；'.join(risks) or '未发现可单列的已证实特定风险；不代表完整适用性通过',
            'functional_requirement': '保护目标输入、返回、绑定与异常；具体差异见逐题表',
            'implementation_scope':{
                '100':'代码有unquote及后续字符检查；当前测试通过，不能证明独立增益',
                '1256':'第二重复有254长度检查及正则；该阈值未被目标测试单独验证',
                '1266':'含字段白名单/替换尝试；原执行先被空注册表阻断，不能将后续防护当已动态触发',
                '335':'含算法拒绝表；原执行先被bytes类型检查阻断，S通过不证明走到弱算法分支',
                '1306':'Mapping兼容建议被有限采用；主要失败仍是+json类型边界',
                '1317':'有格式白名单及XML安全配置尝试；API错误、缺依赖和返回语义需分别处理',
                '1322':'有域名比较；空ALLOWED_DOMAINS使合法外域被拒绝',
                '1341':'有转义尝试；新增必需参数先阻断调用，部分转义另有重复编码错误',
                '1343':'有受限解析器和静态操作映射；动态F/S通过，空卡第二重复也通过',
                '1352':'锁与单条/总量检查可见；固定用例未测总容量和全部阈值',
                '1409':'有签名比较分支；空VALID_SIGNATURES使正例无法进入有效比较',
                '1000':'源999占位符在首次代码及后续代码留存；后续拒绝卡未消除已有假设'
            }[tid],
            'security_guidance':c['positive_principle'] or c['high_level_invariant'],
            'full_fix_directive':c['fix_directive'],'applicability':c['applicability'],
            'exclusions':c['exclusion_conditions'],'review_type':'Codex事后诊断；非人工盲标签、不计检索四指标'})
    assert len(cardreviews)==51 and sum(c['adopted_occurrences'] for c in cardreviews)==72
    csv_write(CURATED/'adopted_card_reviews.csv',cardreviews);write(RAW/'adoption_sites.json',bycard)
    cf=read(RAW/'counterfactuals/summary.json')['results'];registry=read(RAW/'registry_binding_v2/summary.json')['results']
    clean=[e for e in cf if e['task_id'] in ('1322','1409')]
    explicit=[e for e in cf if e['task_id'] in ('1322','1409','1341','1000') and e['variant']=='binding_only']
    failed=[r for r in rowreviews if r['measured'] and not r['F']]
    summary={'API_calls':0,'new_model_generations':0,'P7_rows_reviewed':48,'tasks_reviewed':12,
        'selected_unique_cards':76,'adopted_unique_cards':51,'adopted_occurrences':72,
        'model_results_unchanged':True,'posthoc_fixture_visible':True,'retrieval_metrics_computed':False,
        'measured_function_failures':len(failed),'failure_primary_counts':dict(Counter(r['primary'] for r in failed)),
        'unmeasured_rows':[r['cell_id'] for r in rowreviews if not r['measured']],
        'clean_explicit_binding_counterfactual':{'rows':len(clean),'Joint_pass':sum(e['state']=='A' for e in clean)},
        'four_task_binding_counterfactual':{'rows':len(explicit),'F_pass':sum(e['after']['functional']=='pass' for e in explicit),
            'Joint_pass':sum(e['state']=='A' for e in explicit)},
        'registry_binding_counterfactual':{'rows':len(registry),'Joint_pass':sum(e['state']=='A' for e in registry)},
        'local_diagnostic_validations':38+4,'reference_validations':8,
        'diagnostic_patch_error_preserved':'1266 initial transformer failed to remove renamed empty registry; corrected in separate registry_binding_v2',
        'decision':'design 2-task 4-arm public-binding-protection diagnostic; paid execution disabled; defer Q and classifier'}
    write(CURATED/'summary.json',summary)
    plan={'protocol':'cle-v41-public-binding-diagnostic-plan-v1','paid_execution_enabled':False,
        'status':'designed_not_executed','purpose':'test whether public binding preservation improves generation and whether memory adds benefit under same preserved bindings',
        'task_ids':['1322','1409'],'selection':'posthoc diagnosed two distinct CWE/families; not independent confirmation sample',
        'source_tasks':str(RUN/'inputs/tasks.json'),'task_values_modified':False,
        'arms':{'A':'native P7 empty','B':'native P7 legacy1939','C':'native P7 empty + public binding protection',
                'D':'native P7 legacy1939 + public binding protection'},
        'public_binding_names':{'1322':'ALLOWED_DOMAINS','1409':'VALID_SIGNATURES'},
        'implementation_constraint':'Use the runtime-provided binding already named in the public context. Do not declare, replace, reset, or populate it. Preserve the documented entry point, arguments, return values, and exception behavior.',
        'constraint_scope':'experience reanalysis, planning and generation only; original public first analysis and retrieval query unchanged',
        'shared_initial':'one base-public initial analysis per task/repeat across all4 arms',
        'shared_first_selection':'B and D share same first query/candidates/LLM selection; repairs use own code and feedback',
        'model':'deepseek-v4.1-flash-1017','thinking':'disabled','temperature':0,'max_tokens':4096,
        'message_roles':['user'],'max_experiences':3,'max_attempts':2,'first_joint_early_stop':True,
        'delivery':'last native attempt','Q_updates':False,'card_generation':False,'freeze_memory':True,
        'repeats':2,'P7_runs':16,'probe_included':'first repeat2 tasks x4 arms=8; then second repeat8, no extra tasks',
        'allowed_time':'Asia/Shanghai; block weekdays09:00-12:00 and14:00-18:00, left closed/right open',
        'technical_stop':'unresolved requests, environment failure, model mismatch, frozen input mutation or budget exhaustion; native model degradation retained',
        'budget_proposed':{'model_token_cap':2_000_000,'total_HTTP_cap':300,'embedding_HTTP_cap':60,
            'expected_tokens':'rough0.7-1.0M using S1 per-arm observed usage, not bill quote; unknown retries retain conservative reservation'},
        'binding_gate':'C and D each Joint>=3/4; each gains>=2 vs A/B respectively; no S decline; both families show binding preserved in code',
        'interpretation':{'C_D_both_improve':'public binding is supported bottleneck; memory extra gain unestablished if D does not exceed C',
            'C_pass_D_fail':'inspect concrete memory interference; consider functional/security expression only on reproducible cases',
            'C_D_both_fail':'return to implementation/contract diagnosis; do not expand memory or Q'},
        'not_authorized':['validation24','full D_gate','Q learning','classifier','Base','Plus']}
    plan_path=ROOT/'configs/cle_v41_migration_20261025/public_binding_next_plan.json'
    # 本报告记录诊断时的v1建议；后续经网页复审修订的协议不能被历史汇总回滚。
    if not plan_path.exists() or read(plan_path).get('protocol')==plan['protocol']:
        write(plan_path,plan)
    lines=['# v4.1 P7逐题功能失败、经验作用与后续最小实验', '',
        '结论：当前主要瓶颈是公开接口/外部绑定未被正确消费，以及题面与夹具的类型、默认值和返回约定不一致。没有观察到带卡相对空卡的Joint损失，不能把全部失败解释为经验过度防御。建议先验证公开绑定保持，再决定是否需要功能/安全经验分离。','',
        '本轮为零API事后分析：48次P7、12题族、76张选入的不同卡、51张声明采用的不同卡、72张次采用。逐题查看公开题面与原夹具，但这些事后标签不计为人工盲评，不计算检索准确率/召回率。未修改原48条模型成绩、题库或经验。',
        '原实验最终Joint为E0空卡7/24、E1带卡8/24；共同可测23配对均7/23。32次有完整测量但功能失败，另1次代码截断缺测。','',
        '## 1. 逐题归因','', '| 题号 | 原始Joint E0/E1（各两次） | 主要证据 | 处置 |','|---|---|---|---|']
    for p in packets:
        tid=p['task_id'];counts={a:sum(bool(r['attempts'][-1]['joint']) for r in p['rows'] if r['migration_arm']==a) for a in ('E0','E1')}
        lines.append(f"| {tid} | {counts['E0']}/2，{counts['E1']}/2 | {NOTES[tid][0]}：{NOTES[tid][1]} | 查看逐行证据，保留原分母 |")
    lines+=['','32次功能失败的主分类（互斥归档，用于导航，不等于唯一因果）：',
        '公开绑定/接口被覆盖：1322、1409、1341、1000，共16次；公开注册表缺失并重建空数据：1266，共4次；题面/夹具类型与默认返回不一致并伴XML实现错误：335、1317，共8次；JSON媒体类型边界未明：1306，共4次。1343另有1次缺测。','',
        '## 2. 零API局部修订验证','',
        '所有改动只写在diagnosis_v1的代码副本，以原生PLT本地验证器执行。下表是人工修改代码的事后诊断，不是新模型成绩，也不预测新提示一定有效。',
        '| 诊断 | 本地结果 | 能支持的判断 |','|---|---|---|',
        '| 1322、1409：只删除空ALLOWED_DOMAINS/VALID_SIGNATURES定义 | 8/8 Joint通过，原先0/8 | 已公开绑定被覆盖是这8份代码的直接阻断点；无需改变安全逻辑 |',
        '| 再加1341与1000：只保持外部绑定/接口 | 15/16功能通过、14/16 Joint通过 | 接口/模板保持比当前记忆排序更接近具体故障位置 |',
        '| 1266：使用真实注册表并保留提供的Patient类 | 4/4 Joint通过 | 需说明注册表名称；同时停止自行重建类与空数据 |',
        '| 335：接受字节密码并保持原字节 | 4/4 Joint通过 | 输入类型冲突是阻断点，不能指责模型未遵从str题面 |',
        '| 1306：接收测试要求的application/*+json | 4/4 Joint通过 | 允许类型边界需公开声明；两臂共有的额外限制 |',
        '| 1317：仅补默认json / 再修XML后端与字典返回 | 前者JSON例通过但整体F仍失败；后者4/4 Joint通过 | 默认值、XML表示和实现兼容性同时有问题，不能只换一张卡归因 |',
        '本轮共42次人工副本复验、8次原生参考复验；参考8/8 Joint通过。1266首版诊断变换器因“重命名后未删除空注册表”失败，原记录保留；修正于独立registry_binding_v2，不计入模型错误。','',
        '## 3. 经验采用与实际实现','',
        '“声明采用”按每次尝试统计；修复轮未声明采用，仍可能从上一轮代码继承来源假设。完整51卡表见adopted_card_reviews.csv，72个采用位置见原始adoption_sites.json。',
        '| 案例 | 采用→实现→结果 | 归因强度 |','|---|---|---|',
        '| 100 | 两张URL卡强调先解码再验证；实际调用unquote后检查字符；两重复通过 | 建议落实，空卡也通过，未建立增益 |',
        '| 1256 | 源卡带254上限；第二重复代码确实用254，当前用例通过 | 已证实额外条件被迁移，未证实导致本题失败 |',
        '| 1317 | hint-502-2688312304942497856及pitfall-502-6897897503790105597写ET.XMLParser(resolve_entities=False)，目标代码包含相同调用 | 本机标准库实际TypeError；defusedxml未安装。具体坏API已证实，空卡也有同类问题，不能定全部由卡导致 |',
        '| 1000-r2 | 首次采用源999的hint-79-8445194146159361244、guard-79-3710351121249422672；heading/description进入代码，修复轮拒绝卡后仍写入功能不变量并保留 | 具体来源假设传递路径；只恢复BLOG_FORMAT仍KeyError，再适配目标占位符才过。空卡也覆盖模板，故无整组Joint损失证据 |',
        '| 1343 | seed-842/seed-831的受限解析与白名单在代码落实，F/S过；另一次用blind/pitfall卡也过 | 可核对实现，唯一差异对端为截断缺测，第二重复空卡亦过 |',
        '| 1352 | 容量检查和锁落实，4096消息字节与128发送者字节也从来源条件迁移 | 当前只测正常返回与一条长消息，不证明房间上限、共享状态及全部阈值正确 |',
        '| 1322、1409 | 白名单/签名比较安全动作存在，但依赖表被清空，合法输入一直被拒绝 | 安全通过可能伴随功能阻断；两臂都有，不能当成记忆独有副作用 |','',
        '注意：原S通过不总能证明预期安全动作已执行。1266先因找不到患者抛ValueError，335先因bytes被类型检查拒绝，1409先因空签名表返回0，均可能恰好满足攻击用例预期。保留官方S分数，同时标注防护分支是否实际可达。','',
        '## 4. 经验组织的具体缺点','',
        '功能边界、危险动作、来源修复细节混在同一正文；“No fix required/only two lines”会依赖来源代码。XML类存在错误API，另有Element与字典返回方向相反的来源条件。博客卡带来源占位符名；邮箱/聊天卡带来源数值阈值。当前采用机制可拒绝正文，却不保证清除上次代码里的来源假设。',
        '建议保留原卡，先生成可核对的视图字段：必须保持的目标功能、可执行安全动作、适用前提/环境依赖、禁止照搬的来源常量/名称、已知技术错误。先修明确坏API及绑定，再研究表达分离；将F/S两座库直接拆开并不能自动解决这些问题。','',
        '## 5. 下一次最小实验：公开绑定保护','',
        '选择1322与1409，两题均已有明确公开全局名，来自不同CWE/题族，8份现有失败代码仅删除空配置即可救回。选择是事后诊断选择，不能当独立确认。',
        '四臂：A原P7空卡；B原P7带1939卡；C空卡＋公开绑定保护；D带卡＋相同保护。每题两重复，共16次P7，先首重复8次检查链路，计入总数。所有臂用新共享首次初析，B/D共享首次查询候选及终选；修复按各自代码与原许可反馈。',
        '保护只进入复析/规划/生成：使用题面已给的ALLOWED_DOMAINS或VALID_SIGNATURES，不声明、替换、清空或填入新值。只传符号及类型关系，不传允许域名、签名、测试输入、期望输出或参考代码。原三卡、4096、一次修复、模型、验证器与调用时段不变，Q冻结。',
        '预计约0.7–1.0M Token（按本批观察粗估，非账单）；建议上限2M Token/300总HTTP/60 Embedding。未执行、API预算未消耗，配置paid_execution_enabled=false。',
        '推进条件：C/D各至少3/4 Joint，分别较A/B净增至少2/4，无安全退化，两题均能确认代码保留外部绑定。C/D同时改善说明绑定是优先瓶颈；D不高于C仍不支持记忆额外收益。若C过D失败且存在具体卡影响，再设计功能/安全表达对照；两者都失败则继续契约/实现诊断。',
        '本轮不自动启动这16次，也不恢复Q、分类器、24题确认、全D_gate或Base/Plus。','',
        '## 6. 产物与复现','',
        f'- 原始任务/卡/代码/诊断副本：{RAW}',
        f'- 精简逐题48行、51卡审阅与分类：{CURATED}',
        '- 下一试验规格：configs/cle_v41_migration_20261025/public_binding_next_plan.json。',
        '- collect：python -B -X utf8 -m configs.cle_v41_migration_20261025.diagnose。',
        '- 人工副本复验：diagnostic_patches.py（已有输出不覆盖）；registry-followup保留首版诊断错误。',
        '- 报告汇总：python -B -X utf8 -m configs.cle_v41_migration_20261025.diagnosis_report。',
        '诊断读取夹具是为了事后解释；其数值不回填给生成模型。主实验7/24与8/24完全保留。']
    path=ROOT/'docs/CLE_v41_P7功能失败归因与经验作用核对_20261025.md'
    if read(plan_path).get('protocol')!=plan['protocol']:
        lines[2:2]=['当前方案已由[6 Pro复审与任务更新](cle_memory_mechanisms_20261023/25_v41迁移复审与任务清单更新.md)修订。本文第5节保留诊断时的v1提议；现行v2门、接线状态和执行边界以更新报告及JSON为准。','']
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(path),'summary':summary},ensure_ascii=False))


if __name__=='__main__':main()
