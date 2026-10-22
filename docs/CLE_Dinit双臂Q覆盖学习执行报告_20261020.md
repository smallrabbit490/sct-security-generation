# D_init Q覆盖学习：双臂执行、逐题机制与阶段门报告

日期：2026-10-20。协议：`cle-dinit-coverage-cross-family-design-v3`。实际状态：`stopped_probe_gate`。

## 1. 结论与执行边界

已执行阶段的预设门未过（probe_gate.json），停止扩大；保留本轮获得的两种Q授信视图。

本实验研究曝光策略（哪些卡先呈现给模型）能否增加实际采用后的有效反馈。L0为原候选顺序，L1为同候选中未学习卡优先；Q效用数值不参与这批解题。**训练内Joint通过率不等于Q参与选卡后的提分。**

当前已保存24次P7，覆盖同一固定12题，共42份实际代码尝试；新增D_gate生成0次、Base/Plus0次。旧实验、原数据与436卡起点均保留。

**L0与L1最终Joint均为3/12（25%），通过题相同：831、1350、1008。L0新增3张跨族卡、L1新增4张，均未达6张；L1多1张，未达多3张；新跨族卡实现并Joint的题族为0。按原门停止60/296题，不是因为API故障或预算不足。**原协议库和事后资格屏蔽库均单独保留，本轮未选择获胜策略、未提升任何一库为后续默认Q库；学习前436卡仍为明确基准。

## 2. 执行规格与数据

D_init候选296题/212个项目推断题族：74题为新修复正负对照合格，222题继承旧资格。拟执行但尚未在同环境完成对照的题先做零API检查，资格失败保留而不换题。生成只读取公开字段，修复后的完整测试对象用于原验证器。

固定经验库1939卡，436卡已有有效反馈（22.49%）。卡正文、生命周期不变。L0/L1各自从同一起点授信；全反馈允许同源题族，跨题族增量拒绝同族或未还原的合并来源，只限制本轮新增事件，不追溯认证旧436卡。

原P7：共享首次初析，同题首次查询/候选/余弦核对一致；LLM最多选3卡，复析决定实际采用；首次Joint早停，否则至多一次修复，交付末次。修复轮看各组自己的代码和原许可反馈。

模型deepseek-v3.2、thinking disabled、temperature=0、普通输出4096、选择器256；text-embedding-3-large、delta=-1、alpha=0.3、并发2。原本地python -I验证器/20秒；进程PATH提供已有Git echo/cat，未mock测试。

每个c0/c1仅对实际采用、流程完整、代码非空且F/S有效测量的卡更新：Q←Q+0.3×(r−Q)，Joint为+1，否则−1。选入、被召回或参考答案通过都不会直接赋Q。

## 3. 实际生成结果

|组|已执行题数|F/S有效测量|末次完整流程|F|S|Joint|不同选入卡|不同采用卡|采用卡次|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|L0|12|12/12|10/12|4/12|8/12|3/12|48|30|31|
|L1|12|12/12|11/12|5/12|7/12|3/12|47|31|35|

Joint（同一份最终代码的功能与安全均通过）按已执行任务报告，未执行阶段不填0%。采用卡次可能含同题c0/c1重复，不代表不同卡或不同题族。模型格式失败、技术失败保留在计划分母。

## 4. Q覆盖与训练候选触达

|组/授信视图|有反馈卡|覆盖率|新增卡|新增训练参照卡|触及参照题数|有效更新次数|核对实现且Joint的不同题族|
|---|---:|---:|---:|---:|---:|---:|---:|
|L0/all_feedback|441/1939|22.74%|5|5|22|28|0|
|L0/cross_family|439/1939|22.64%|3|3|15|13|0|
|L1/all_feedback|447/1939|23.05%|11|11|50|33|0|
|L1/cross_family|440/1939|22.69%|4|4|35|12|0|

新增反馈不等于新增成功经验：L0全反馈新5卡均只获负奖励；L1全反馈新11卡中1卡获正奖励、10卡获负奖励。严格跨族新增的3/4张卡全部只获负奖励，L1唯一新增正反馈卡属于同题族来源，不能拿来凑跨族成功。


训练参照固定为228道D_grow的1167张历史候选卡；没有使用D_gate候选或成绩选学习题、曝光策略或扩展轮数。卡级奖励共享整份代码结果，不能解释为单卡因果贡献。

## 5. 预设门与停止决定

上述是原协议原始回放。发现契约问题后，另存事后资格屏蔽敏感性分析；不覆盖原分数、不重跑生成、不混用两个Q库。

|屏蔽后组/视图|保留任务|有反馈卡|新增卡|有效更新|
|---|---:|---:|---:|---:|
|L0/all_feedback|7|439/1939|3|14|
|L0/cross_family|7|438/1939|2|6|
|L1/all_feedback|7|440/1939|4|21|
|L1/cross_family|7|436/1939|0|6|

屏蔽仅撤销这些题在本轮的新增授信，不重置或重认证继承的436张卡。由于该诊断是事后形成，不拿其子集通过率替代原12题主表。

### smoke_gate.json

```json
{
  "passed": true,
  "checks": {
    "4_runs": true,
    "4_measured": true,
    "no_system_fault": true,
    "2_equal_candidate_pairs": true,
    "budget": true
  }
}
```

### probe_gate.json

```json
{
  "stage": "probe",
  "passed": false,
  "winner": null,
  "absolute": {
    "L0": {
      "12_measured": true,
      "10_final_workflows": true,
      "6_new_cross_cards": false,
      "4_new_anchor_cards": false,
      "8_anchor_queries": true,
      "2_implementation_Joint_families": false,
      "no_system_fault": true,
      "budget": true
    },
    "L1": {
      "12_measured": true,
      "10_final_workflows": true,
      "6_new_cross_cards": false,
      "4_new_anchor_cards": true,
      "8_anchor_queries": true,
      "2_implementation_Joint_families": false,
      "no_system_fault": true,
      "budget": true
    }
  },
  "relative_L1": {
    "3_more_cross_cards": false,
    "F_not_lower": true,
    "Joint_not_lower": true,
    "token_ratio": true
  },
  "interpretation": "coverage/exposure engineering gate, not evidence of Q generation benefit"
}
```

60题与296题阶段未执行，不报告其Joint。

原门保持：每组12题完整测量、至少10题完整流程、新增跨族卡≥6、参照内新增≥4、触及参照任务≥8，且至少两个题族存在新卡采用→代码落实→Joint证据。L1还须比L0多≥3张新增跨族卡、F/Joint不下降、分摊Token≤1.25倍。未达条件不扩大，不把工程门当统计显著性。

## 6. 逐题机制与实现核对

首次共同候选已形成12对核验，查询/候选/余弦一致12对。完整attempt、generation、validation、retrieval_trace及代码保留在运行区；精简逐次表见`attempt_mechanisms.csv`。

|组|题目|尝试|选入数|采用数|流程完整|F/S/Joint|
|---|---|---:|---:|---:|---|---|
|L0|1003|c0|3|1|True|False/False/False|
|L0|1003|c1|3|3|True|False/False/False|
|L0|1008|c0|2|1|True|True/True/True|
|L0|1053|c0|3|0|True|True/False/False|
|L0|1053|c1|3|2|True|True/False/False|
|L0|1216|c0|3|3|True|False/False/False|
|L0|1216|c1|1|1|True|False/False/False|
|L0|1258|c0|3|1|True|False/True/False|
|L0|1258|c1|3|1|True|False/True/False|
|L0|1288|c0|3|3|True|False/True/False|
|L0|1288|c1|3|1|True|False/True/False|
|L0|1299|c0|3|3|True|False/True/False|
|L0|1299|c1|3|1|False|False/True/False|
|L0|1303|c0|2|1|True|False/True/False|
|L0|1303|c1|3|0|True|False/True/False|
|L0|1319|c0|2|0|True|False/True/False|
|L0|1319|c1|2|1|True|False/True/False|
|L0|1338|c0|1|1|True|False/False/False|
|L0|1338|c1|3|2|False|False/False/False|
|L0|1350|c0|3|3|True|True/True/True|
|L0|831|c0|3|2|True|True/True/True|
|L1|1003|c0|3|2|True|False/False/False|
|L1|1003|c1|3|1|True|False/False/False|
|L1|1008|c0|3|3|True|True/True/True|
|L1|1053|c0|2|0|True|True/False/False|
|L1|1053|c1|3|0|True|True/False/False|
|L1|1216|c0|3|3|True|True/False/False|
|L1|1216|c1|3|3|True|True/False/False|
|L1|1258|c0|3|3|True|False/False/False|
|L1|1258|c1|3|2|False|False/False/False|
|L1|1288|c0|3|2|True|False/True/False|
|L1|1288|c1|3|0|True|False/True/False|
|L1|1299|c0|1|1|True|False/True/False|
|L1|1299|c1|3|0|True|False/True/False|
|L1|1303|c0|3|3|True|False/True/False|
|L1|1303|c1|3|1|True|False/True/False|
|L1|1319|c0|3|2|True|False/True/False|
|L1|1319|c1|3|1|True|False/True/False|
|L1|1338|c0|1|1|True|False/False/False|
|L1|1338|c1|3|2|True|False/False/False|
|L1|1350|c0|3|2|True|True/True/True|
|L1|831|c0|3|3|True|True/True/True|

代码落实核对由Codex读取实际卡片建议与生成代码后记录在`implementation_review.json`，与模型声称采用分开。没有核对的条目不能用于通过实现门；该核对不冒称人工金标准。

固定12题中，L0/L1首次选入成员集合变化11/12，首次声明采用集合变化10/12；Joint救回0题、损失0题。这是一次双臂观测，未通过重复选择实验排除模型自身波动，不能把所有成员变化都解释为纯顺序因果效应。

已核对全部6份Joint成功尝试的实际采用ID、436卡起点访问标记及来源关系：符合“基线未学习且跨题族”的采用卡为0张。因此实现门的0有直接记录依据，不是漏填复核。L1题1008虽采用一张新增正反馈卡，但它来自同题族。

### 本轮新增的公开契约问题

以下缺口在固定题单执行期间被实际失败暴露。题面和提示未中途修改，未换题、未重跑；与原81题修复前的资格问题分开。

- 题1258（public_return_representation_underspecified）：公开说明为“list of HTML tags; brackets not specified”；参考/夹具为“captured inner tag text, excluding angle brackets”。证据：both final implementations include brackets; reference uses a capturing group。
- 题1288（public_argument_type_conflicts_with_fixture）：公开说明为“password: str”；参考/夹具为“password: bytes; reference directly hashes bytes”。证据：both final implementations encode presumed str; raw bytes supplied by original fixture。
- 题1299（missing_runtime_callable_and_exception_contract_conflict）：公开说明为“returns data argument after signature validation; raise ConnectionError on reception failure; no receive_data_packet interface”；参考/夹具为“calls receive_data_packet(device_id), returns fetched packet; catches ConnectionError and returns None”。证据：native task ground_truth and setup declare receive_data_packet, but public context lists only TRUSTED_DEVICE_SIGNATURES; both final codes also overwrite that supplied mapping。
- 题1319（required_default_argument_not_declared_publicly）：公开说明为“two inputs data_bytes and format_string; no default value or optional argument declaration”；参考/夹具为“reference format_string defaults to json; capability tests omit format_string”。证据：both final functions require format_string, consistently with the public two-input description; original capability group also exercises one-argument calls。
- 题1003（template_placeholder_schema_not_explicit）：公开说明为“USER_POST_FORMAT described as a template with placeholders for username, title, body and tags; exact tags placeholder not listed”；参考/夹具为“existing template requires tags_html; reference passes tags_html”。证据：L0 escapes content and uses supplied template but passes tags, not tags_html; L1 also overwrites the supplied template。

参考正对照和漏洞负对照通过只确认参考可执行，不能证明公开题面已经完整。未解决契约阻止扩大；原协议反馈保留为待资格审查结果，不能直接作为可信的新Q库投入后续测试。

### 模型实现错误与Q机制的区别

- 1299两组重定义已提供的签名映射为空字典；1303的L1把已有CSRF配置和数据库清空；1003的L1重定义已有模板。这些是实际代码对公开运行绑定的破坏，不能归因于Q值排序。
- 1303两组还猜测嵌套字段和数据库形状，1319未保留未公开的默认参数，1258卡片建议在局部正则上被落实也未满足参考返回形状。即使声明采用，也可能在其他接口处失败。
- 原P7修复反馈仅含许可的F/S状态和错误类别；未把隐藏输入或期望输出补给模型。因此它无法从状态反馈直接知道bytes/str、tags/tags_html等缺口，不能把c1未救回写成Q没有发挥排序作用。
- 本轮未让Q效用数值参与排序，检验的是如何获得更多可信反馈。整份代码失败给采用卡共享−1，仍无法识别单卡是否导致失败；契约不清时更会把题目问题写进卡级分数。

最小后续工作应先澄清并修订已暴露的公开类型、默认值、外部调用与模板字段，统一“使用已有运行绑定、不得重定义”的公开实现约束；另开协议后再做小对照。当前不追加学习轮数、不启动D_gate或全量测试。


## 7. 调用、Token与成本

|项目|逻辑请求|Token|失败|缺usage|
|---|---:|---:|---:|---:|
|LLM合计|198|1660321|0|0|
|其中共享初析|12|16867|0|0|
|L0其余P7调用|93|832908|0|0|
|L1其余P7调用|93|810546|0|0|
|Embedding新增请求|30|33239|0|0|

共享初析总账只计一次，12题比较时给每组分摊一半。逐次请求账保存数值usage与状态，不保存凭据或原始prompt。原请求器内部HTTP重试不完全可见，因此逻辑请求不当成精确物理请求数；实付金额未知，不沿用旧单价冒充账单。

## 8. 证据边界与下一步

若门未过，结论仅限当前起点、曝光策略、预算与题单未达到扩大条件；不证明Q普遍无用。若覆盖增加，仍需未来另获授权的冻结前向对照才能证明Q的生成收益。本轮不启动D_gate或Base/Plus。

## 9. 产物与复现

- 入口：`methods/cle_ablation/run_memory_q_dinit_coverage.py`，prepare/run --stage smoke/probe/60/296/report/gates。
- 原件：`translation_work/diagnostics/20261020/cle_dinit_q_coverage_v3/`；含冻结配置、来源/源码身份、同题初析、请求用量、原生结果、两种Q事件和独立冻结库。
- 精简统计：`results/curated/cle_dinit_q_coverage_20261020/`；配置与原门：`configs/cle_dinit_q_coverage_design_20261020_v3/`。
- 新入口必要离线验证：29项通过，覆盖实际采用/跨族边界、共同候选、三卡限制、原生参数、门失败阻断付费与请求账。

付费阶段墙钟合计1106.8秒（不含入口开发和离线整理）；smoke约180.2秒、补足probe约926.7秒。198次LLM逻辑请求、1,660,321个LLM Token与30次Embedding/33,239 Token均在本阶段预算内。实际执行60题命令的门阻断检查已确认在任何新付费请求前拒绝，未执行60题本身。
