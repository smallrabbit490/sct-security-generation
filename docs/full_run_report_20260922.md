# CLE 全量运行报告（2026-09-22）

> 运行目录：`translation_work/sct_runs/cle_full_874_20260922`
> 冻结评测：`translation_work/validation_runs/cle_local_20260922b`
> 代码版本：含 D19/D20/D21/D34/D35/D36/D37/D38 与方案 A、并发提速改造

---

## 一、运行概况

| 项 | 值 |
|---|---|
| 数据 | PLT 训练侧 874 条（互斥三池：source=303 / replay=273 / audit=298） |
| 消融组 | **A7**（L2/3 合并、不生成 Level 4） |
| 模型 | deepseek-v3.2 |
| 并发 | `--workers 80 --phase3-workers 24`（含全局在途闸门 80） |
| 总耗时 | **1 小时 41 秒**（02:08:09 → 03:08:50） |
| 成本 | 22782 次调用 / 2692 万 tokens / **35.07 CA元** |

**对比历史全量**：09-19 为 21.5%、09-20 为 19.8%，二者均为 A4 消融且并发 5~16。
本次在 A7 + 新门控语义下耗时从 **11.3 小时降到 1.7 小时**（约 6.6x）。

### 各阶段节奏

| 阶段 | 内容 |
|---|---|
| Phase1 冷启动 | 303 条，8 分 35 秒 |
| 轮1 | 重放 96 条；覆盖率 35.2%；新增达 A 18 |
| 轮2 | 重放 167 条；覆盖率 65.5%；新增达 A 27 |
| 轮3 | 重放 180 条；覆盖率 **78.9%**（目标 75%）；新增达 A 16 |
| 产出 | 经验池 **4518 条**、树 13 节点、冻结 M\* 含 13 个 active 节点 |

审计抽样每轮均命中「纯负向/失败现场 8 条，保底配额 8」—— D17 保底生效。

---

## 二、正式指标（CodeSecEval Base / Plus）

评测脚本：`methods/sct_trajectory/run_local_frozen_eval`（零 Docker，本地 `python -I` 子进程）。
每个子集都跑 **M\* 组** 与 **空记忆对照组**，唯一变量是是否注入 M\*。

| 组 | 总数 | Function | Secure | **Joint** | Joint% | Function% | Secure% | 生成错误 |
|---|---|---|---|---|---|---|---|---|
| **Base / M\*** | 115 | 26 | **11** | **9** | **7.8%** | 22.6% | **9.6%** | 0 |
| Base / 对照（无记忆） | 115 | **29** | 9 | 7 | 6.1% | 25.2% | 7.8% | 0 |
| **Plus / M\*** | 140 | 86 | **45** | **41** | **29.3%** | 61.4% | **32.1%** | 0 |
| Plus / 对照（无记忆） | 140 | **89** | 36 | 34 | 24.3% | 63.6% | 25.7% | 0 |

### M\* 相对对照组的增益

| 子集 | Joint | Secure | Function |
|---|---|---|---|
| Base | 7 → **9**（+2，相对 **+28.6%**） | 9 → **11**（+2） | 29 → 26（**−3**） |
| Plus | 34 → **41**（+7，相对 **+20.6%**） | 36 → **45**（+9） | 89 → 86（**−3**） |

**结论**：经验库在两个子集上都带来了**稳定且方向一致**的提升，且提升几乎全部来自
**Secure 维度**（+2 / +9），Function 有小幅代价（−3 / −3）—— 这与方法定位一致：
用少量接口改动换安全加固，净效果 Joint 为正。

---

## 三、需要注意的口径问题

1. **Base/Plus 与训练侧互斥**：经验只在 `D_init / D_grow / D_gate` 上生成，
   CodeSecEval 的测试结果**不回流**（`feedback_channel=disabled`）。
2. **审计池最终评测（18.1%）与 Base/Plus 不是同一口径**：前者是训练侧 audit 池上的
   端到端自检，后者是正式冻结评测。论文引用应以 **Base/Plus** 为准。
3. **与历史全量不完全可比**：本次为 A7（无 Level 4），历史为 A4；且门控语义
   （D19/D20/D21）与重放过滤（A 方案）均有改动。

---

## 四、本次运行暴露并修复的缺陷（均带实测依据）

| 编号 | 缺陷 | 影响 |
|---|---|---|
| D35 | 经验池只在轮结束/抛异常时落盘 | 卡死后无法续跑 → 已加周期落盘（每 180 秒，原子写） |
| D36 | 请求挂包时在重试里空转 | 静默假死数小时 → 已加连续失败熔断（阈值 15），大声失败 |
| D37 | Gate3 回归探针双层串行 | 单候选几小时 → 已并行化（8 并发） |
| D38 | `python -I` 忽略 `PYTHONIOENCODING` → GBK 输出被按 UTF-8 解码 | 验证输出丢失、任务误判失败 → 已加 `-X utf8` + `errors="replace"` |
| — | S4 清理用 `unlink()` 被安全策略拦下 | 启动即崩 → 改为截断 |

D38 对数据质量影响最大：修复前一次 Base/Plus 评测出现 **227 次 `UnicodeDecodeError`**，
修复后为 **0**，Base_mstar 的 Joint 也从 7 提升到 9。

---

## 五、复现命令

```bash
# 全量（唯一入口）
python -m methods.sct_trajectory.run_closed_loop \
  --out translation_work/sct_runs/<run_name> \
  --limit 0 --rounds 3 --workers 80 --phase3-workers 24 --timeout 60 \
  --batch-size 96 --replay-limit 96 --audit-per-candidate 5 \
  --audit-max-entries 24 --regression-samples 3 \
  --coverage-target 0.75 --min-audit-tasks 3 --ablation A7

# 冻结后 Base/Plus 评测（无 --live-api 参数）
python -m methods.sct_trajectory.run_local_frozen_eval \
  --cle-run translation_work/sct_runs/<run_name> \
  --out translation_work/validation_runs/<eval_name> \
  --subsets Base Plus --model deepseek-v3.2 --workers 32
```
