# CLE 细粒度消融矩阵

本目录把 CLE 拆成冷启动建库 C1、多 Agent 演化 C2、门控冻结 C3 三层，并要求每个臂重跑自己的训练过程、生成自己的经验池、通过冻结资格检查后才进入最终评测。

## 固定数据边界

| 池 | 条数 | 用途 |
|---|---:|---|
| `D_init` | 270 | C1 冷启动建库 |
| `D_grow` | 240 | C2 回放和演化 |
| `D_gate` | 64 | C3 训练侧门控诊断 |
| `H_pass` | 300 | 最终 CLE 留出评测 |

分池以 `family_id` 为原子单位。`H_pass` 不进入生成、检索、蒸馏、门控或经验更新。Base 115 条、Plus 140 条也只在冻结后评测，反馈通道固定为 disabled。

## 运行

先生成清单和每个臂的可审计命令，不启动 API：

```powershell
python -m methods.cle_ablation_matrix.run_training_matrix `
  --out translation_work/sct_runs/cle_ablation_matrix_20260929 `
  --arms C1-1 C1-2 C1-3 C2-0 C2-1 C2-2 C2-3 C2-4 C2-5
```

确认 `matrix_plan.json` 后，加入 `--execute`。运行后，用冻结评测入口执行 Base、Plus 和 H_pass：

```powershell
python -m methods.cle_ablation_matrix.run_frozen_matrix `
  --matrix-root translation_work/sct_runs/cle_ablation_matrix_20260929 `
  --pool-manifest translation_work/sct_runs/cle_ablation_matrix/pool_manifest.json `
  --arms C2-0 C2-1 C2-2 C2-3 C2-4 C2-5 --execute
```

最后汇总：

```powershell
python -m methods.cle_ablation_matrix.report_matrix `
  --matrix-root translation_work/sct_runs/cle_ablation_matrix_20260929
```

`C2-B*`、`C2-R*`、`C2-E*`、`C2-I*`、`C2-A*` 和 `C2-T*` 是对主链最佳 C2 臂的辅助策略矩阵，不与全部主链进行笛卡尔积。

## 冻结验收和汇报

`freeze_policy.py` 对没有底层冻结产物的独立池执行严格资格冻结：要求候选 ID 唯一、至少有一个 `active` 节点，并保存经验池和 `m_star.jsonl` 的 SHA-256。底层 `run_closed_loop` 已自动写出的 `frozen/m_star.jsonl` 则由矩阵编排器执行快照审计：它按 CLE 的“经验池全量快照”契约允许 `provisional`/`consolidated`，只拒绝空快照、重复 ID、缺失产物或哈希不一致。C3 的 active、质量、独立有效性和 `H_pass` 回归门控仍由严格资格路径单独检查，不能用快照审计替代。

报告必须覆盖：每臂唯一变量和上游链、经验状态和来源阶段、C1/C2/C3 中间过程、Base/Plus/H_pass 的 Function/Secure/Joint、缺测与环境错误、调用/token、C2 与 C3 的相邻配对比较及 Holm 校正。没有统计检验支持时，只报告观测差异，不声明提升。
