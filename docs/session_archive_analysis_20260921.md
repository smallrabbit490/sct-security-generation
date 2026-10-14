# agents 会话归档分析（`dsh-session-941683a9`）

> 来源：`agents工具会话集合/dsh-session-session-941683a9-cfc4-4964-b5de-74f35b21e9ea.zip`
> 分析时间：2026-09-21 16:30 ~ 16:50
> 归档范围：**2026-09-15 15:18 → 2026-09-21 16:29**（7 天，120 轮对话，2266 步工具调用）

---

## 一、归档内容

| 文件 | 大小 | 说明 |
|---|---|---|
| `session.v3.jsonl` | 37.2 MB / 12236 行 | 主会话全量事件流 |
| `subagents/session-e73dafea-.../session.v3.jsonl` | 36.8 MB / 12077 行 | 同源分叉会话（内容到 09-21 14:39 为止，非独立工作） |
| `files/7e/7e810dbb.../面向安全代码生成的经验自进化方法（最终）.docx` | 53 KB | 方法正式规范原件 |
| `media/sha256_*.png` ×2 | 24 KB / 51 KB | 用户贴的报错截图与方案截图 |

主会话 `cwd = D:\thecourceofdasi\sct-security-generation`，`parentSession = session-03eb5662-...`，
`agentPreset = standard`，模型主力 `chatanywhere-backup/deepseek-v4-flash` → `deepseek-v4.1-flash`。
会话被导出时**正在运行中**（最后事件 16:29:27，且有一个 Phase1 任务在跑）。

---

## 二、七天工作主线（十个会话段）

| # | 时间 | 会话标题 | 主要工作 |
|---|---|---|---|
| 1 | 09-15 15:40 | 分析问题原因 | Docker Desktop `docker_data.vhdx` 从 14.9 GB 涨到 67.7 GB。根因：每任务 `docker run --rm` + 中途强杀留孤儿容器 |
| 2 | 09-15 20:02 | 分析新的计划（王老师） | 引入常驻容器池执行层（`persistent_container.py`），VHDX 不再增长；确立"每跑完一个任务回收空间"的纪律 |
| 3 | 09-15 20:22 | 分析新的计划（王老师）(1) | 把 CLE 新方案落进 `methods/sct_trajectory/`，要求"每阶段必须产出可验证结果、分步实施、需拍板处必须询问" |
| 4 | 09-16 10:00 | 分析新的计划（王老师）(1) | 逐阶段实现 B/C/阶段 4；受控主动回放两阶段调度（规则配额 + LLM 有界筛选） |
| 5 | 09-16 18:24 | — | goal：在 PLT 874 条可验证样本上跑通 CLE 完整闭环（Phase1→2→3），落盘 `sct_runs/cle_full_*` |
| 6 | 09-17 15:20 | 分析第一次全量实验 | 人工 check 各阶段产物；Phase3 真实门控（修 Gate1 召回探针）、Phase2 多轮回放、明细落盘 |
| 7 | 09-17 ~ 09-18 | — | 架构归一化：Phase1/Phase2 经验**一视同仁**只做"插入"，门控统一在 Phase3；检索底层逻辑对比实验（TF-IDF 排序 vs LLM 直接挑选） |
| 8 | 09-18 10:30 | 做好任务看板 | 网页看板：实时/历史监控自进化流程、三阶段可视化、ABCD 四态统计、树成长轨迹、失败案例对比、精确成本 |
| 9 | 09-18 17:53 → 09-19 | — | HSK-Tree **四层结构**（CWE → Invariant → … → LanguageLeaf 多语言）+ 6 组消融（A1~A6）；门控 LLM 任务选择器；反过度防御 |
| 10 | 09-20 ~ 09-21 | 做好任务看板(2) | 全量运行两次失败与断点续跑；重放强度/覆盖率专项；经验质量与"失败现场"改造 |

### 关键指标演进

| 运行 | JointPass | 备注 |
|---|---|---|
| `cle_full_874_20260919`（第一次全量） | **21.5%** | 暴露六大问题：门控 Δ 全 0、21/24 零证据晋升、Phase2 覆盖仅 3.3% |
| `cle_full_874_v2_resumed_20260920`（第二次全量续跑） | **19.8%** | 反而降 1.7pt，原因未定论 |
| `per_round_test_20260921`（60 任务小规模） | 23.5%（4/17） | 状态变化率 64%、经验池 457 条 |

---

## 三、会话中断点：当前正在做什么

**最后一条用户指令（09-21 15:56）**：
> "确认是A方案，然后你还要确定失败案例中的轨迹和具体的报错信息都要加入，并且这些经验可以被经验选择器（llm）选中"

**中断时的待办清单**（09-21 15:57 写入）：

| 编号 | 待办 | 中断时状态 |
|---|---|---|
| A1 | 重放候选排除"已达 A"任务（按 CWE 保底） | in_progress |
| A2 | 重放候选排除"上一轮已选"任务 | pending |
| A3 | 覆盖率口径改为"未通过任务 75%" | pending |
| B1 | 失败轨迹 + 具体报错写入经验（可被检索） | pending |
| B2 | 验证经验选择器能选中这些失败经验 | pending |
| — | 小规模验证：覆盖率 / 状态变化 / 经验可选中 | pending |
| — | 验证通过后启动全量 | pending |

**中断时最后一步动作**（16:29）：写 `patch_B_render.py`，把 `root_cause` / `fix_directive`
渲染进 Planning 用的经验文本（`agent_pipeline.dual_track_text`）。该补丁已生效、文件可编译。

**中断前已启动的运行**：`translation_work/sct_runs/afilter_test_20260921`
（60 任务 / 3 轮 / workers=20，标签"验证：A方案过滤 + 失败现场可见"）。

---

## 四、接手后的处置（本次）

### 4.1 A 方案核查：**已落地，逻辑正确**

`methods/sct_trajectory/closed_loop.py` 中 `passed_ids` / `prev_round_chosen` /
CWE 保底 / 覆盖率新口径 / 强制重放均已实现。

### 4.2 B 方案核查：**发现 4 处静默丢字段，已修**

提炼层（`distill_each_round`）确实产出了 `root_cause` / `fix_directive` /
`prev_fix_assessment`（Phase1 20 个任务产出 37 条按轮经验），
但**入池环节逐层丢弃**，导致实测 457 条池子里 `prev_fix_assessment` 全空、
`round_*` 按轮经验一条不剩。这正是用户"感觉你没有提取有效的经验"的根因。

四处缺陷与修法见 `docs/architecture_and_experiment_history.md` 第八节。
修复后实测：**36 条按轮经验中 34 条成功入池**（含 root_cause 34、prev_fix_assessment 16、round_index 34），
未入池的 2 条被"成功描述过滤"正常拦下。

### 4.3 处置动作

1. 停掉 `afilter_test_20260921`（B 缺陷未修，跑完也无法验证 B）。
2. 应用 4 处修复 + 1 处日志口径修复；`py_compile` 通过；单测 **294 passed / 2 skipped**。
3. 启动合并验证运行 `translation_work/sct_runs/ab_verify_20260921`。
4. 新增两个可复用验证脚本（对旧运行已做**反向校验**，确认不是橡皮图章）。

---

## 五、遗留与风险

| 项 | 说明 |
|---|---|
| `prev_fix_assessment` 覆盖率偏低 | 修复后 36 条中仅 16 条非空——首轮本来就该为空，但修复轮填充率仍需观察 |
| 全量耗时 ~11.3 小时 | Phase2 rollout ×3 轮占 71%；已识别"跳过小池子基线筛选"等提速项，**尚未实施** |
| 两次全量结果反降（21.5% → 19.8%） | 原因未定论，本次全量需与历史同 task_id 配对比较 |
| 九条 baseline 未达标 | 4 Prompt FAIL / 5 Agent BLOCKED（09-04 审计结论，仍未解决） |
| 代码大量未提交 | `git status`：19 改 + 15 新增 |
