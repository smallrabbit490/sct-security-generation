# v4.1 Flash 1017完整CLE三集基准

**已撤销：该文将用户需求误解为重新训练经验。用户已纠正为P3无经验Agent仅做题，且要求先审阅方案、暂不执行。原进程已停止，禁止按本文启动或续跑；当前以 [无经验Agent方案](CLE_无经验Agent换模基准方案_20261024.md) 为准。以下仅保留误解发生时的方案记录。**

2026年10月24日新增执行授权：单次加法控制通过后，用同一密钥和 `deepseek-v4.1-flash-1017` 重新完成原CLE，不复用旧冻结卡库。该授权接续单次测试，覆盖下列固定流程；旧Q、B/C机制实验和其他模型任务不恢复。

## 范围和经验流

| 阶段 | 固定数据 | 操作与产物 |
|---|---|---|
| 技术控制 | 原单user加法提示，一次HTTP | 两项加法运行通过，返回模型字段与指定模型一致 |
| PLT Phase1 | D_init 303题 | 从空经验池开始，重新提取种子经验、生成/修复、验证、提炼；不读取旧1939卡或冻结Q |
| PLT Phase2 | D_grow 273题，三轮演化 | 原主动回放及覆盖调度；新经验持续入本轮池，保留逐轮状态与采用记录 |
| PLT Phase3 | D_gate 298题 | 原全池无经验/有经验/过滤后对照、移除归因和门控，产生本轮新M* |
| Base | Python 115题 | 原常驻Docker验证器，完整CLE，固定两次前向、交付末次代码 |
| Plus | Python 140题 | Base结束后串行执行，规则同Base |

PLT参与全流程的任务总数874。**PLT主表是D_gate 298题开发成绩，不能把三个阶段不同用途的874题混为一个独立准确率。** D_init、D_grow成绩和复播覆盖另表报告。既有family分组不变；这些数据有历史研究暴露，换模型不产生新的全局未见测试集。

“不用冻结经验卡”在本次执行中指不拿旧库直接消费：新库在PLT中重新建立和演化。Base/Plus只读这次学得的新M*，其隐藏测试结果不进入模型修复、选卡、门控或经验更新。Base/Plus不在线学习，不能把最终测试集变成训练材料。

## 参数与原入口

完整参数在运行根的 `protocol.json`。已从用户提供ZIP中的 `cle_full_deepseek32_20260924_full/run_metadata.json` 读取原全量历史参数：4096输出上限、三轮、单分支、一次修复、semantic_llm、A7、全局门控、context_pipeline、internal_checks、inject_prev_evidence。保留原回放窗口874、batch80、coverage0.75及门控设置；Q关闭，最多三张经验卡。

本次模型为v4.1 Flash 1017，thinking disabled、temperature=0、流式org接入点，修正客户端标识。workers/max_inflight由历史80降为4，phase3_workers由16降为4；选择器并发4。传输复用180秒socket、300秒hard、600秒排队，原客户端最多三次HTTP尝试；训练每题的修复次数仍为一次。物理重试逐次记录，不能与逻辑调用混算。

这些工程及当前验证边界与9月历史运行的差异必须披露；本次建立新模型基准，不据此宣称只有模型一个变量改变。

- PLT：`methods/sct_trajectory/run_closed_loop.py`，新增只读 `--tasks-file` 接收当次完整快照，默认行为不变。
- Base/Plus：`methods/sct_trajectory/run_plus_frozen_comparison.py`，新增 `--only-cle` 和 `--data-root`；默认行为不变。
- 基准启动：`configs/cle_model_baseline_20261024/launch.py`。
- 快照内阶段执行：`configs/cle_model_baseline_20261024/execute.py`。

按北京时间，仅周一至周五09:00–12:00及14:00–18:00禁止派发新模型请求；其他时段及周末允许。运行遇到禁用窗口在请求边界等待，已有在途请求自然结束；时段等待不记为做题失败。原客户端仍在发送前复查。

## 保存与回放

运行根：`D:/Agent/sct-security-generation/translation_work/sct_runs/cle_full_v41flash1017_20261024/`。当前D盘可用约242GB，准备前要求至少20GB，不自动清理旧材料。

- `source_bundle/`：实际执行的源码、原始数据和完整PLT任务/分池快照；不复制凭据。
- `protocol.json / source_manifest.json / state.json / launch.json`：协议、源码版本、运行阶段与进程身份。
- `journals/<stage>/requests/`：每次精确提示、参数、返回正文、usage、耗时和未决状态。同提示第N次采样保留独立响应。
- `wire/<stage>/`：每次实际HTTP的请求正文、原始响应字节/流式片段、HTTP状态和耗时；不保存Authorization头。
- `validation_events/<stage>/`：每次被验证的完整代码、题目/测试、后端参数与原始结果，包括公开内部测试与正式F/S。
- `source_bundle/translation_work/baseline/<stage>/segment_001/`：原生阶段产物。PLT保留phase1_results、trajectories、pool_snapshots、experience_pool、门控事件、frozen/m_star、final_eval及summary；Base/Plus保留rows、generation/cards/retrieval_trace、验证和校准。
- `cost_<stage>.json`位于 `cost_/` 目录，记录逻辑调用实际usage；物理尝试数从wire核对。缺usage记未知，实际货币费用在没有账单和当前单价时不填。

准备（零API；新根拒绝覆盖）：

```powershell
& 'D:/Agent/sct-security-generation/translation_work/temp/cle_memory_q_env/Scripts/python.exe' -B -X utf8 -m configs.cle_model_baseline_20261024.prepare
```

监控在控制通过、允许时段且无运行进程时调用 `python -B -X utf8 -m configs.cle_model_baseline_20261024.launch`。每个子进程使用source_bundle中的实际源码；Base/Plus各自包裹原watchdog，严格串行。

回放有两种模式：

1. **完整事件回放与代码重验**：快照中的 `replay.py --run-root <运行根>` 生成按时间的精确输入/输出/验证索引；加 `--revalidate` 从保存代码与原测试重执行，始终禁止模型和Embedding网络。不会重生成代码或覆盖旧成绩。
2. **严格请求回放**：快照中的 `execute.py --run-root <运行根> --stage PLT --mode replay`（或Base/Plus）从保存响应执行原编排，不读取密钥、不发HTTP。并发调度若产生未记录提示，明确停止并报告分歧，不能默认为可付费补齐。完整事件和验证回放不依赖此调度一致性。

中断后保留未决响应。`--mode resume`只允许消费同输入的已保存完成前缀后续跑；未决、失败或前缀分歧均停止，不自动重发、不换模型。监控不得启动重复进程或按低正确率重跑。

## 当前环境与完成要求

Docker服务可响应，但原 `safecoder-python-validator:local` 及父镜像 `porta-bench-runtime-python3:latest` 均不在本机；原Dockerfile需要该父镜像。用户ZIP未包含可恢复该镜像的镜像归档。**Base/Plus在原环境补齐前为未执行，不改用普通Python镜像冒充原结果。** PLT本地python -I不依赖此镜像，可独立推进。

48项记录/时段/控制相关检查及30项原门控/冻结消费检查通过。这里是离线实现验收，不是三集真实实验通过。

最终报告分别给出PLT各阶段与D_gate三组、Base、Plus的F/S/Joint、完整测量、代码/环境/请求错误、经验数及生命周期、实际采用、调用/Token/缓存、耗时与时段等待。检查原生分母、同题唯一性、三池互斥、Base/Plus记忆不变；明确未执行部分和历史暴露。全部完成后暂停监控；技术未决时保留现场并汇报具体停止原因。
