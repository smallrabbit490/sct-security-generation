# CLE 契约主线与条件Q接续

## 本次状态

用户于2026-10-23明确选择“保持暂停，交付本轮结果”。本轮以零API阶段成果收尾，192次P7契约双臂筛查未获授权、不启动；旧实验、Q学习、全量D_gate和Base/Plus继续暂停。

从PR #5提交 `21d21c0af571579df1aa83a12a534c8b008e82fe` 接续到本地分支 `fjy/cle-contract-conditional-q-20261023`。用户提供的路线图原文保存在 `research_request.md`；其中的网页附件引用标记不冒充本机证据。

已完成零API38例交叉分析、条件Q接线、共享suite及首次初析、固定48题与972反馈卡快照预检、5题URL夹具原样恢复、48/48参考实现正对照。相关离线测试220项通过。

主交叉表未过提案门，当前 `route_policy.json` 为 `enabled=false`，不根据这38例反复寻找有利阈值。条件Q臂会被入口明确移除，不重复执行与契约-only完全相同的臂。当前有效设计为48题×2臂×2重复＝192次P7，尚未付费执行。

## 原生执行入口

新选项复用 `methods.cle_ablation.run_joint_contract`：

- `--candidate-order similarity|q`：仅对新消费者重排，必须保持 `semantic_llm`；LLM仍自主选至多三张，不能与直接数值选卡的 `semantic_q` 混称。
- `--conditional-q-policy`：只允许公开契约、候选相似度、冻结Q与visits形成的六项事前特征。无规则或结果字段不能用于开启路由。
- `--shared-public-suite`：每题×重复先生成一次公开用例集并保存；新臂共用c0初析，首次查询、候选、余弦也须相同。修复轮仍随各臂代码和公开反馈独立。
- `--max-embedding-http-attempts`：另设1000次embedding上限，仍同时服从总请求预算；实际预算保守预留不能当实付费用。

以下不含 `--run`，只做预检；输出目录必须全新：

```powershell
python -m methods.cle_ablation.run_joint_contract `
  --dataset PLT `
  --tasks translation_work/diagnostics/20261023/cle_contract_q/tasks_D_gate_48_restored_urls_v2.json `
  --memory translation_work/diagnostics/20261020/cle_q_online_v1/D_grow/frozen/m_star_q.jsonl `
  --arms P7 P7_public_contract_v1 P7_public_contract_q_conditional_v1 `
  --candidate-order similarity `
  --conditional-q-policy configs/cle_contract_q_20261023/route_policy.json `
  --shared-public-suite --limit 48 --repeats 2 `
  --max-http-attempts 4500 --max-total-tokens 40000000 `
  --max-embedding-http-attempts 1000 `
  --out translation_work/diagnostics/20261023/cle_contract_q/another_preflight
```

付费筛查须在用户单独确认后，将输出目录改为全新的运行目录并显式加 `--run`。附件把48题筛查列为“未授权、不得自动执行”，且旧实验仍暂停，本次未自行越过此边界。

## 数据与复现

1. `python -m configs.cle_contract_q_20261023.prepare`：只连接既有逐题CSV和PR #5静态报告；从D_gate按字符串题号排序、CWE轮转，每family至多一题，固定48题。题号及family在 `manifest.json`，不按新生成成绩挑题。
2. `python -m configs.cle_contract_q_20261023.restore_urls`：从项目已采用的上游固定提交恢复5题受损URL测试字段；不替换题目，不修改公开题面、参考代码、setup或历史成绩，另存v2。已有v2拒绝覆盖。
3. `python -m configs.cle_contract_q_20261023.calibrate --restored-v2`：原参考实现的零API环境校准，保留原验证器；不是CLE模型成绩，已有输出不覆盖。

上述准备操作已在本机执行；再次复现请使用独立目录或先读取现成产物，不应覆盖已保存证据。更早原始记录仍按上一版项目Release恢复；本次新增的48题v2和参考校准证据在 `translation_work/diagnostics/20261023/cle_contract_q/`。

## 门槛与停止

- 当前条件Q路线：关闭，不学习全局Q，不继续D_grow刷覆盖，不启动Base/Plus或全量D_gate。
- 若以后授权契约双臂：完整可测后比较当次配对Joint；契约-only相对旧P7至少+3个百分点、两次重复方向不冲突才通过工程筛选门；不大于0则STOP；0至3个百分点或不完整，记不确定且不扩大。
- 只有另有可复现事前路由依据并重新锁定规则，才有理由启用第三臂。届时Q增量对契约-only须至少+5个百分点、两重复均正、按family重采样80%区间下界大于0；否则停止或记不确定，不扩全量。
- 最多288次P7、576份代码、4500次总HTTP保守预留、4000万保守Token上界、1000次embedding；当前关闭第三臂后最多192次P7及384份代码。总HTTP上限包含embedding，比路线图的分项上限更保守。

原P7与新消费者比较的是整个契约消费者包，不能把所有变化归因于某个单组件；D_gate已有历史暴露，开发门通过也不是独立最终验证。
