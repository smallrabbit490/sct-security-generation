"""仅将用户授权的CLE研究材料汇总供既有网页6 Pro审阅；不含凭据或原始HTTP头。"""
import csv
import json
from pathlib import Path
from .resume import ROOT,RUN,read,write

OUT=RUN/'pro_review_20261025'


def main():
    OUT.mkdir(exist_ok=False)
    summary=read(ROOT/'results/curated/cle_v41_migration_20261025/summary.json')
    diagnosis=read(ROOT/'results/curated/cle_v41_migration_20261025/diagnosis/summary.json')
    packets=[read(p) for p in (RUN/'diagnosis_v1/tasks').glob('*.json')]
    rows=[json.loads(s) for s in (RUN/'final/rows.jsonl').read_text().splitlines()]
    native=[]
    for r in rows:
        native.append({k:r[k] for k in ('cell_id','task_id','family_id','migration_arm','repeat','protocol')})
        native[-1]['attempts']=[]
        for a in r['attempts']:
            g=a.get('generation',{})
            native[-1]['attempts'].append({**{k:a.get(k) for k in ('attempt','code','measured','functional','security','joint','error_type')},
                'selected_ids':[c['invariant_id'] for c in g.get('retrieved_cards') or []],
                'adopted_ids':[c['invariant_id'] for c in g.get('cards') or []],
                'stages':g.get('stages'),'adoption':g.get('adoption'),'analysis':g.get('experience_analysis'),
                'plan':g.get('plan_parsed')})
    write(OUT/'01_current_native_evidence.json',{'operation':'offline_source_extract_not_new_model_results',
        'summary':summary,'diagnosis_summary':diagnosis,'tasks_and_validation_evidence':packets,
        'actual_native_attempts':native,'selected_card_bodies':read(RUN/'diagnosis_v1/cards.json'),
        'counterfactuals':read(RUN/'diagnosis_v1/counterfactuals/summary.json'),
        'registry_followup':read(RUN/'diagnosis_v1/registry_binding_v2/summary.json'),
        'reference_checks':read(RUN/'diagnosis_v1/counterfactuals/reference_checks.json'),
        'integrity':read(RUN/'final/integrity_checks.json'),
        'replay':read(RUN/'replay_results/completed_48/summary.json')})
    prior_files=['docs/cle_memory_mechanisms_20261023/07_当前执行清单与决策门.md',
        'docs/cle_memory_mechanisms_20261023/tasks.csv',
        'docs/cle_memory_mechanisms_20261023/02_功能安全与影响边界.md',
        'docs/cle_memory_mechanisms_20261023/03_记忆粒度与分类器.md',
        'docs/CLE_v32成果汇总与v41Flash1017迁移验证方案_20261025.md',
        'configs/cle_v41_migration_20261025/source_evidence.json',
        'configs/cle_v41_migration_20261025/assets.csv',
        'configs/cle_v41_migration_20261025/validation_checklist.csv']
    sources=['methods/cle_ablation/runner.py','methods/cle_ablation/joint_contract.py',
        'methods/sct_trajectory/context_pipeline.py','methods/sct_trajectory/semantic_retrieval.py',
        'methods/sct_trajectory/public_contract_checks.py','methods/sct_trajectory/public_repair_policy.py']
    text=['# Historical plans and current source excerpts\nHistorical status is not current; current evidence supersedes old model/transport/partial progress facts.\n']
    for name in prior_files:
        text+=['\n\n## FILE '+name+'\n',(ROOT/name).read_text(encoding='utf-8-sig')]
    for name in sources:
        text+=['\n\n## SOURCE '+name+'\n',(ROOT/name).read_text(encoding='utf-8-sig')]
    (OUT/'02_prior_plans_and_current_sources.txt').write_text(''.join(text),encoding='utf-8')
    current_files=['docs/CLE_P3无经验Agent_PLT全量基准报告_20261025.md',
        'docs/CLE_v41Flash1017_P7空卡与1939卡迁移实验报告_20261025.md',
        'docs/CLE_v41_P7功能失败归因与经验作用核对_20261025.md',
        'configs/cle_v41_migration_20261025/public_binding_next_plan.json',
        'results/curated/cle_memory_q_full_gate_cap3_20261019/summary.json',
        'results/curated/cle_q_online_20261020/D_grow_summary.json']
    text=['# Current reports; claims remain executor assertions until checked against attachment01.\n']
    for name in current_files:
        text+=['\n\n## FILE '+name+'\n',(ROOT/name).read_text(encoding='utf-8-sig')]
    (OUT/'03_current_reports_and_next_plan.txt').write_text(''.join(text),encoding='utf-8')
    briefing='''# CLE v3.2→v4.1 Flash 1017 全量背景更新与任务清单复审

这是同一CLE项目既有“Review Q Extension”会话的完整批次更新。人类用户明确要求：汇总换模后的全部实际信息，让网页6 Pro完整把握既有记录，并指导本地Codex更新原任务清单对应方案。请先完整读取四个附件。你只能访问网页可见附件，不能宣称已执行本地项目或已经产生新成绩。研究建议不授权任何付费实验；不用再接管仓库、生成PR或启动代码。

## 0. 目标、限制与事实优先级
实验室课题是旧版CLE安全代码生成：同一份最终代码同时通过功能F与安全S为Joint。目标是可靠的功能/安全联合改善，不预设必须用Q。用户原手改Word是历史报告权威，保留不覆盖；本批新增原始记录更新后续状态。范围只含旧CLE；新版CLE/MASE暂停。
网页已有旧Q、MemRL、38不一致例、资格清理与21d21c0公开契约消费者的讨论，请保留其已完成结论，不再要求重做已完成资格清理或旧Q3曝光核对。
P0–P7是生成策略，不是Phase；P3为无经验、不复析、初析→规划→生成、最多一次修复；P7为初析→检索终选0–3→经验复析/采用→规划→生成、最多一次修复。PLT首次Joint早停，否则交付末次；Base/Plus固定两次且隐藏反馈隔离。固定库评测不等于完整CLE训练。

## 1. 历史资产与尚未完成事项
PLT原1411组，项目当前可加载874，D_init303/D_grow273/D_gate298（family为项目推断分组）。Base115/Plus140 Python。旧经验1939卡。最新在线Q为972有visits，D_init303已完，随后D_grow只23/273、Joint11/23，余250未执行；“已做过旧独立全D_grow学习”与“这次在线强化23/273”分开。原全298四臂Joint Q0=97、Q1=104、Q2=102、Q3=100；原Q2完整测量296/298，其他298。该全量旧Q快照不是972新快照，新972Q2/Q3全D_gate没跑。
旧不限量选择重复160次支持Q可超过模型波动影响集合，但不能继承为新模型限三张证据，更不能当Joint收益。
旧候选池914对AI标签、人工0；全库召回未测。旧高δ和当前Qδ=-1不混。15卡L4缺来源代码。原B/C完整12题中的1348资源政策未决，影响该名单完整先导，不是所有两题工作都阻塞。C1真实粒度效果0，分类器未训练。B视图草稿不等于全部审核，原B02只有故障记录，没有有效新模型五臂配对。
原P0–P7三集现已在E盘原生4424行复算完整：PLT2384、Base920、Plus1120（附件02具体数字）。旧文档105行中断状态是早期快照。旧P3 PLT52/298；P7=70/298与后来的Q0=97/298不是同次实验。旧Base/Plus原环境历史仍有容器/超时诊断边界。
你此前实现的P7_public_contract_v1已在21d21c0，新增公开return/raise映射、接口/绑定检查、公开测试及保守交付；这些代码存在/离线通过，不代表新模型付费效果已测。旧P7路径仍有return/raise检索白名单缺口；本轮S1故意保留原P7，不把契约消费者行为混入。后续比较若改变反馈/交付必须标为整体消费者包。

## 2. 换模与工程已完成
deepseek-v3.2中转出现403/拒绝加法身份问题后，用户指定deepseek-v4.1-flash-1017。原单user、thinking disabled、temp0、4096、原生重试/selector预算保留。每次HTTP检查北京时间工作日09–12和14–18禁发，其余允许，周末允许。实际本批均2026-10-25周日。
同服务org端点、透明UA、仅本实验绕失效显式代理、TLS证书/主机名验证不关闭。P3已完成PLT298，F111/S232/Joint96，297可测，1125截断。旧P3 Joint52→新96（+14.77pp），但JSON反斜杠格式提示及workers8→4有差异，不把全部差归因于模型。完整零API回放一致。P3已知3,841,636 Token，30次历史HTTP未知，保留；不是仍290/298。
Base/Plus仍缺原safecoder-python-validator:local及父porta-bench-runtime-python3:latest，不以普通Python代替。未执行不记0。曾误启动完整新CLE训练已明确停止，隔离不并入P3、没有本轮全新M*。
S0：run_joint_contract硬编码v3.2改为实际--model与metadata一致，历史默认保留；新同P7空卡控制保持复析与修复；静态同模型向量缓存复用；模型响应、物理HTTP重试、代码验证及冻结源码完整保留。

## 3. 已完成S1：原P7空卡 vs 旧1939卡
固定原48契约manifest前12个不同family：1256,100,1266,335,1409,1306,1317,1322,1341,1343,1352,1000。恢复URLv2输入。每题两臂两重复48次，先2题8次技术检查计入48。两臂同题同重复共享新模型首次初析；E0所有轮空卡，E1原semantic_llm终选0–3、原候选顺序，Q不介入/不更新，不生成新卡，正文/生命周期冻结。
技术8次通过。v1在15次时335空卡修复复析非法JSON后按整批零降级门停；用户随后明确批准更新：保留原P7的模型输出降级与原始成绩，只有基础设施/未决请求/错模型/预算耗尽等停。原15行不重写，独立v2续段复用11个精确旧阶段响应、补33次，最后48/48。原严格门未被追改通过。预算并发.tmp隐患串行化；800万cap不变，已知usage结算、未知与在途保守占额。模型、提示、选卡、验证与修复规则未改。38项相关离线检查通过。
结果：E0 F7/S18/J7/24，23可测；E1 F8/S20/J8/24，24可测。按重复Joint E0=3/12,4/12；E1=4/12,4/12。唯一变化1343-r1：E0规划JSON错且代码达到4096截断，E1通过；r2两组都过。共同可测23配对Joint都7/23。72张次声明采用、51张不同采用卡、21/24带卡运行有采用；不能用“声明采用”替代实现。
实际40+40次代码尝试（含截断），48行零API回放除selector真实耗时外逐字段一致。生成/验证/原15行/卡库皆保持。391物理传输尝试，376有usage，15未知（4 PermissionError、11 TLS EOF），所有逻辑最终已返回。已知输入1,773,619/输出289,510/总2,063,129 Token；其中Embedding物理响应46,461。客户端embedding累计差值日志51,344因并发重叠偏高，不做账单；以原始响应为准。逻辑模型E0=404,357,E1=1,577,287，约3.90倍，另共享初析35,024。无本模型账单单价，不填人民币实付。
原S1门要求净增≥2/24、两重复非负、F/S不降、测量完整、至少两族采用落实救回：未过，未启动24题验证或Q。只完成执行不等于收益成立。

## 4. 最新零API逐题诊断
附件01有全部12题公开描述、原fixture及reference、48格所有尝试代码/阶段/采用、76张选入卡、完整原生验证证据和人工局部修改结果。此处是事后可见fixture诊断，不是生成提示，也不是人审盲标签。
32次完整测量的F失败集中在8题族：
- 1322/1409（8格）：已公开ALLOWED_DOMAINS/VALID_SIGNATURES被两组代码重设为空。只删除空定义，8份代码副本全部Joint通过。
- 1341（4格）：公开只有user_content入参，外部xml_template；两组新增模板参数或自造默认。保持接口/全局后4份F过、3份Joint过；E1-r1重复转义另修后过。
- 1000（4格）：两组都覆盖BLOG_FORMAT；只保留全局3/4 Joint过。E1-r2采用source999卡的heading/description，c1虽拒绝卡仍将其作为功能不变量保留；保持真实模板后KeyError，适配真实占位符才过。具体来源遗留链，不等于已测整组记忆损失。
- 1266（4格）：公开Patient但未给patients注册表名；模型自行重建Patient和空注册表。对诊断副本恢复注册表并保留提供类后4/4过。
- 335（4格）：题面pwd:str，测试却传bytes；局部支持原字节后4/4过。不能说模型遵从str本身错。
- 1306（4格）：测试接受application/*+json，公开没有说明。两臂都只接受application/json；放开该例后4/4过。卡的Mapping建议不解决这个边界。
- 1317（4格）：未公开format_type默认json、XML要字典；还使用缺失defusedxml/标准库不支持XMLParser(resolve_entities=False)。只加默认能过JSON例，整体仍失败；兼容XML后端+字典映射后4/4过。2张采用卡含实错API；另有Element/字典相反的来源约定。
1343-r1另1缺测，其他3格通过。100/1256/1352当前全部过，但1256采用254上限、1352采用4096/128阈值源条件，题面没给数值；固定测试没测所有边界，不写成已证有害或完整安全。
重要：有些S通过来自提前拒绝一切或空表返回0，未证明预期安全动作可达。例如1409空表查不到合法签名；1266查不到患者先ValueError；335先拒绝bytes恰好匹配安全例ValueError。官方分数保留，额外解释可达性。
共42次人工副本本地复验、8次参考复验（8/8过）；1266首版诊断变换器因重命名后未删空表出错，另v2修正保留失败，不算模型失误。人工改代码后的分不加回7/24和8/24。

## 5. 已设计、未执行的下一步
附件03中public_binding_next_plan.json拟选1322/1409（事后选出的已知可救案例，仅诊断）×A原P7空卡/B原P7带卡/C空卡+绑定保护/D带卡+同保护×2重复=16次。只有复析/规划/生成加入“使用题面已给外部对象，不重定义/清空/填新值，保接口返回异常”；不传域名、签名、fixture值。共享基础c0初析，B/D共享首次候选及终选，修复各自检索。预算提议2M Token/300HTTP/60embedding，paid=false。建议工程门C/D各≥3/4，较A/B净增≥2，无S退化且两族正确保绑定。
这是Codex的候选建议，请独立审查，不需顺从。它是否仅证明提示修复已知bug、是否缺强简单基线、是否该复用现有公开契约消费者而不是另造原型，需你决定。不能凭事后8/8承诺在线一定改善。

## 6. 请输出完整中文审阅及可直接落实的任务清单更新
1. 先列“已确认/仍仅执行者陈述/未测量”的当前事实；尽可能用附件01独立复算48行得分、采用分母、唯一差异和人工副本统计。不要宣称运行了项目。
2. 判断目前失败主要在哪里；哪些卡内容真错/条件错/模型没落实/契约不明；原S通过是否足够支撑安全机制结论。
3. 给原任务ID A01–A04/B01–B05/C01–C04b/D01–D05和迁移S0–S4逐项状态、证据、唯一下一动作、继续/停止条件。区别完成、待资料/人审、待设计、待授权、暂停、停止；删除已完成待办，不把边界全部变新审计。
4. 明确对下一最小实验16次的GO/修改后GO/STOP建议；若修改，给精确臂、共享阶段、是否改变消费者、题目选择、预算、判定门及结果→结论表。不要把建议当付费授权；只选一项最高价值任务，不并行铺开B/C/Q。
5. 解释功能/安全表达B、公开契约消费者D02、记忆粒度C1/分类器C2、Q效用/信用D各自还有什么独立研究问题及贡献边界；哪些先后依赖，哪些无需重做。Q不应被强迫保留，暂不学习新Q。
6. 列出本地Codex现在可直接完成的零API修改及新付费试验之前最后条件。输出一份按原ID的“旧计划→新事实→更新决定→证据→停止条件”表和可机器转录的简洁任务列表。允许有理由停止，不承诺三集必然提分，不靠改测试/换题/超预算救结果。
所有旧成果/人工Word/原卡/Q/原始失败保留。Base/Plus缺原镜像、Q972新D_gate未执行、人审0等是边界，不要求无止境补全。请完成本批综合审阅后给明确优先级，Codex再核对并更新本地文件。
'''
    (OUT/'00_review_briefing.md').write_text(briefing,encoding='utf-8')
    write(OUT/'review_manifest.json',{'reviewer':'GPT-6 Pro web','conversation_url':'https://chatgpt.com/c/6ad626a2-c670-83ea-9191-8e17f218ae59',
        'status':'prepared_not_submitted','model_experiments_authorized':False,
        'files':[{'path':str(p),'bytes':p.stat().st_size} for p in OUT.iterdir() if p.is_file()]})
    print(json.dumps(read(OUT/'review_manifest.json'),ensure_ascii=False))


if __name__=='__main__':main()
