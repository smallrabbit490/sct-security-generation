# `methods/sct_trajectory/` 主流程代码审查报告

> 审查时间：2026-09-21
> 范围：主方法/主流程相关代码（**不含 `dashboard/`**）
> 规模：26 个模块 / 约 7300 行
> 方法：逐模块精读 + `pyflakes` 静态检查 + 与真实运行产物交叉验证

---

## 零、执行流程总览

```
run_closed_loop.main()
  ├─ _load_tasks()            读 PLT 有测试任务（limit=0 为全量 874）
  ├─ assign_families_atomic() 三池原子划分（source / replay / audit，同族不跨池）
  ├─ Phase1  phase1_seed()    source 池 → 提取 seed 经验卡 + 四步流水线 + 动态验证
  │                           → Distillation 按轮提炼 → 统一插入经验池（不直接入树）
  └─ run_evolution_rounds()   每轮：
       ├─ Phase2  phase2_evolve()   规则配额初筛 → LLM 有界筛选 → 强制重放失败任务
       │                            → 并发四步流水线 + 动态验证 → 按轮提炼 → 入池
       ├─ Phase3  phase3_audit()    Gate1 召回探针 / Gate2 ΔJointPass / Gate3 分维度回归
       │                            → supported 入树 / demoted 退休 / unmeasured 降级保留
       └─ 归并（consolidate_family）+ 剪枝（prune_by_utility）
  └─ final_evaluate()         冻结 M* → 在 audit 池全量跑一遍 → JointPass
```

**核心数据结构**：`HskTree`（4 层：CWE → Invariant → TrackRule → LanguageLeaf）
**信号边界**：全部在线信号只来自训练侧 PLT；Base/Plus 永不回流（`__init__.py` 明确声明）

---

## 一、严重问题（4 项）

### S1. `_audit_one` 内存在 `return` 之后的死代码，且引用未定义变量

**位置**：`closed_loop.py:2033-2047`

```python
        return {"candidate_id": cand.invariant_id, "detail": detail,
                "rec": rec.to_dict(), "audit_source": audit_source}
        # ↓↓↓ 以下全部不可达，且 consolidate_max_active / records / targets / audit_detail
        #     在 _audit_one 作用域内**均未定义**（不是形参、不是局部变量）
        merged = 0
        for fam in self.tree.all_families():
            if consolidate_family(fam, ..., max_active=consolidate_max_active) is not None:
                ...
        promoted = sum(1 for r in records if ...)
```

`pyflakes` 报出 5 个未定义名：`consolidate_max_active`、`records`、`targets`、`audit_detail`（2 处）。

这是 `phase3_audit` 尾部"归并 / 剪枝 / 汇总"逻辑的**副本**（正确版本在 `1851-1864`）。

**影响**：
- 当前不可达 → 不报错，但**埋着 `NameError`**：任何人为了加日志/调试删掉那个 `return`，整轮门控立即中断
- 更现实的风险是**改错地方**：维护者看到这段代码以为是归并逻辑所在，改完后运行结果毫无变化，且没有任何提示
- 说明 `_audit_one` 的抽取重构没做完

### S2. `regression_count` 永远是 0 → 效用剪枝机制不可能触发

**位置**：`hsk_tree.py:43-45, 318-325` + 全仓检索

```python
def utility_score(support, regression): return (support + 1) / (regression + 1)
def prune_by_utility(family, *, threshold=UTILITY_PRUNE):   # 0.3
    ... if node.utility < threshold: node.status = "retired"
```

全仓 `regression_count` **只有读取（求和）与初始化为 0，没有任何递增点**：

```
closed_loop.py:827   best.support_count += max(1, node.support_count)   ← 只有 support 增长
closed_loop.py:2069  support_count=sum(...), regression_count=sum(...)  ← 只读
hsk_tree.py:310      best.support_count += node.support_count           ← 只读 regression
```

因此 `utility = (support+1)/1 = support+1 ≥ 1 > 0.3` → **`prune_by_utility` 永不触发**。

**附带语义错位**：`support_count` 只在"被就地吸收"时增加，含义是"被合并了几次"，
而 DOCX 6.3 的本意是"这条经验被验证有效了几次"。两者不是一回事。

**影响**：
- DOCX 6.3 第 4 步（效用 < 0.3 剪枝）形同虚设，树**只增不减**
- 门控算出的 `security_regressions` / `functional_regressions` 从未回写到节点，效用统计与门控证据脱节

### S3. `final_evaluate` 无异常保护 → 长时间运行的产物可能全丢

**位置**：`run_closed_loop.py:391-421`（有保护）vs `:477`（无保护）

```python
    try:
        evo = runner.run_evolution_rounds(...)      # ← 有 try/except，失败也落盘
    except Exception as exc:
        _write_jsonl(out / "error_ledger.jsonl", ...)
        _write_jsonl(out / "experience_pool.jsonl", ...)
        write_status(..., status="failed", ...)
        raise

    ...
    fe = runner.final_evaluate(audit, on_item=on_final_item)   # ← 没有任何保护
```

而 `experience_pool.jsonl`（续跑的唯一前提）、`error_ledger.jsonl`、`tree.json`、
`summary.json` 全都在 `final_evaluate` **之后**才写（`:485-525`）。

**影响**：全量运行约 11 小时，若最终评测阶段一次 API 断连/超时 → 抛异常退出 →
**整个运行的产物一个都没落盘**，且**无法续跑**（续跑强制要求 `experience_pool.jsonl` 存在，
见 `:322` 的 `raise SystemExit`）。

### S4. `--out` 目录复用会静默追加，导致跨运行数据混杂

**位置**：`run_closed_loop.py:275-276, 295, 471`

```python
p1_handle   = open(p1_path, "a", encoding="utf-8")     # 追加
traj_handle = open(traj_path, "a", encoding="utf-8")   # 追加
audit_handle = open(out / "audit_detail.jsonl", "a")   # 追加
fe_handle   = open(out / "final_eval.jsonl", "a")      # 追加
```

而 `status.json` / `run_metadata.json` / `summary.json` 是覆盖写（`write_json_atomic`）。

**影响**：
- 同名目录重跑 → `rows.jsonl` 类文件里**混入两次运行的行**，条数翻倍、统计口径被污染
- 没有任何"目录非空"的检查或警告；`AGENTS.md` 第三节要求"每次运行目录至少包含 rows.jsonl"，
  但没有约束"必须干净"
- 实测中我已因此改用新目录名（`rm -rf` 被工作区批量删除保护拦下时才发现这个隐患）

---

## 二、中等问题（7 项）

### M1. LLM 打分失败 → 经验被静默丢弃

**位置**：`retriever.py:177-178, 334-346`

```python
        except Exception as exc:
            return {"score": 0.0, "reason": "", "error": type(exc).__name__}   # 失败 = 0 分
...
                if sc is None or c.get("_align_error"):
                    # 打分失败：保守丢弃（宁缺毋滥）
                    continue
```

**影响**：
- 一次 API 抖动就直接改变注入内容 → **实验不可复现**，且系统性减少经验注入量
- "丢弃了几条、因为什么"没有任何落盘统计；违反 AGENTS.md 第九节"降级必须显式记录原因"
- 更隐蔽的问题：`score=0.0` 与"真的不相关"不可区分，事后无法从产物里判断哪些是 API 失败

### M2. 检索是两段式漏斗：`recall_k=8` 先按 base_score 截断，再让 LLM 打分

**位置**：`retriever.py:319-328`

```python
ranked = sorted(nodes, key=lambda n: -scorer(n, max_utility))[: self.recall_k]  # 先按 TF-IDF 截到 8
...
for n in ranked:
    scored.append((n, scorer(...), self._llm_score(task, n)))                   # 再让 LLM 打分
```

**影响**：语义上最相关的经验若 base_score 排第 9，**永远没有机会被 LLM 看到**。
这与"用 LLM 做相关性判断"的设计初衷相悖 —— LLM 只被用来给 TF-IDF 的前 8 名排序。

### M3. 中文分词导致相似度退化为"分句精确匹配"

**位置**：`hsk_tree.py:261-273`

```python
return set(re.findall(r"[a-z0-9_\-]+|[\u4e00-\u9fff]+", (text or "").lower()))
```

`[\u4e00-\u9fff]+` 会把**一整段连续中文当作一个 token**。而经验池里的
`high_level_invariant` / `positive_principle` 几乎全是中文。

**影响**（两个方向同时出错）：
- **漏吸收**：同义不同表述的两条经验（"必须校验输入长度" vs "应当限制参数尺寸"）
  相似度 ≈ 0 → 不会被就地吸收，池子重复膨胀
- **过度吸收**：模板化套话（整句完全相同）相似度虚高 → 被误判为重复
- 这恰好解释了实测中"**230 对重叠≥0.6 的重复**"与"**语义检索失效**"并存的现象
- 早先"Phase1 seed 提取改为输出英文"是对同一根因的局部规避，但提炼出的经验仍是中文

### M4. `_load_tasks` 的均衡采样静默不足额，且任务子集固定不变

**位置**：`run_closed_loop.py:108-119`

```python
        for cwe in sorted(by_cwe):
            for r in by_cwe[cwe][:3]:        # 每个 CWE 只取前 3 条
                result.append(r)
                if len(result) >= limit: return result
        return result                         # ← 可能远少于 limit
```

**影响**：
- **静默不足额**：实测 `--limit 60` 只加载到 **54 条**（日志原文"加载训练侧任务 54 条（limit=60）"），
  但没有任何警告；下游按 54 条做统计，与配置不符
- **子集固定**：`sorted(by_cwe)` 按 CWE 编号排序 + `[:3]` → 永远取**编号最小的那些 CWE 的前 3 条**。
  重复运行拿到完全相同的任务（这也解释了三次验证运行的三池划分都是 `source=20 replay=17 audit=17`）
- **覆盖偏差**：小规模实验的 CWE 覆盖被"小编号 CWE"锁死，无法反映真实分布

### M5. 归并阈值仍与实际规模不匹配 → 归并从未触发

**位置**：`hsk_tree.py:343-345` + `run_closed_loop.py:203-205`

```python
    actives = [n for n in family.invariants if n.status == "active"]
    if len(actives) <= max_active: return None      # 需要 ≥ max_active+1 才归并
```

默认 `--consolidate-max-active 3` → 需要同一 CWE 有 **≥4 个 active**。
但实测每个 CWE 的 active 最多 3 个 → 三轮日志全部"归并 **0**"。

**影响**：DOCX 6.3 第 3 步（容量归并）仍未生效；注释虽已说明"原默认 4 导致从未触发"，
但改成 3 依然没触发 —— 说明**没有用实测数据反推阈值**。

### M6. `_requester` 超时后线程泄漏

**位置**：`run_closed_loop.py:73-95`

```python
            th = threading.Thread(target=_run, daemon=True)
            th.start()
            th.join(HARD_TIMEOUT)
            if th.is_alive():
                last_exc = TimeoutError(...)
                continue              # ← 放弃线程，但它仍在跑、仍持有 socket
```

**影响**：超时的线程不会被回收，会继续占用连接直到 socket 层自己超时。
并发 20 workers × 每次检索 8 个打分调用 → 僵死线程可能累积；
11 小时长跑下有内存/连接缓慢增长的风险。

### M7. 门控与最终评测共用同一批任务 → 指标有信息泄漏，需明确披露

**位置**：`run_closed_loop.py:392`（`phase3_audit(audit)`）与 `:477`（`final_evaluate(audit)`）

`phase3_audit` 用 audit 池决定经验**去留**（只有在这批任务上 Δ>0 才 supported），
`final_evaluate` 又在**同一批** audit 任务上测 M* 的端到端表现。

**说明**：这是用户 2026-09-18 明确要求的口径（"最后要做一次这些经验在最后这个审计池当中
全量运行的表现"），**不是实现错误**。但它是"选择性偏差"：被采纳的经验恰恰是"在这批任务上有效"的。

**影响**：
- `JointPass 4/17 = 23.5%` 这类数字**不能当作泛化性能**，只能当作"门控是否自洽"的自检
- 正式指标必须是 Base/Plus 冻结评测（AGENTS.md 第二节的硬约束）
- 建议在报告里显式标注该口径，避免被误读为无偏泛化结果

---

## 三、轻微问题（8 项）

| # | 位置 | 问题 | 影响 |
|---|---|---|---|
| L1 | `trajectory_reflection.py`（119 行） | **整模块无主流程调用方**（仅测试引用） | 死代码，增加理解成本 |
| L2 | `frozen.py` / `frozen_eval.py` | 仅测试引用，主流程未用 | 死代码 |
| L3 | `experience_filter.py`（134 行） | 开关 `filter_experiences` 默认 False 且**从未被传 True** | 模块死代码；且 `run_pipeline` 返回的 `experience_filter` 字段恒为 `{"kept": n, "dropped": 0, "assessments": []}` —— **看起来像"做了筛选"的假报告** |
| L4 | `error_ledger.merge_negative_boundary` | DOCX 5.2 声明的"消费 3"，主流程从未调用 | 归并时不会规避历史盲区 |
| L5 | `four_state.classify_first_state` | "A 直出 Early-Exit"规范，主流程从未调用 | 规范未落地（A 直出靠 `len(states)==1` 判断） |
| L6 | `agent_pipeline.py:419-420` | `prompts["planning"]` 重算时**漏传 `contract_freeze`** | 落盘的 prompt 与实际调用不一致 → 审计误导（"为什么模型还发明前置条件？"因为你看的 prompt 里没有契约冻结） |
| L7 | `closed_loop.py:698/1174/1832`、`distillation.py:477` | 死变量（`task` / `used` / `audit_source` / `failure_types`） | 维护噪音；`used` 是 A 方案重构的残留 |
| L8 | `hsk_tree.tfidf_overlap`、`closed_loop.AblationConfig` | 函数名叫 TF-IDF 实为 Jaccard；`AblationConfig` 未导入（字符串注解） | 命名误导；若有人 `get_type_hints()` 会失败 |

---

## 四、做得好的地方（保持）

- **注释带实测依据**：几乎每处阈值都写了"实测 X/Y"的出处，可追溯
- **`unmeasured` 纪律**：状态缺省一律视为 unmeasured，不冒充 pass（`four_state._evidence_status`）
- **信号边界显式声明**：`__init__.py` 明确写死"Base/Plus 永不回流"
- **异常隔离**：`_joint_pass_rate` 单任务 try/except（有过 8 小时运行被一次超时清零的事故）
- **`_read_jsonl_tolerant`**：续跑时容忍崩溃截断的半行 JSON
- **`write_json_atomic`**：避免看板读到写了一半的状态文件

---

## 五、修复优先级建议

| 优先级 | 项 | 理由 |
|---|---|---|
| **P0（全量前必修）** | S1 死代码 | 埋着 `NameError`，且会误导维护者改错地方 |
| **P0** | S3 final_eval 无保护 | 11 小时运行可能零产物、且不可续跑 |
| **P0** | S4 目录复用追加 | 会静默污染结果文件，重跑即踩 |
| **P1** | S2 效用剪枝死 | 机制失效；需决定是接门控回归数还是删掉该步骤 |
| **P1** | M1 打分失败丢弃 | 影响可复现性，且违反"降级要留痕" |
| **P1** | M4 采样不足额 | 影响实验设计可信度（limit 与实际条数不符） |
| **P2** | M2 / M3 | 影响检索质量，但改动面较大，建议单独实验 |
| **P2** | M5 / M6 / M7 | 配置与披露问题 |
| **P3** | L1–L8 | 清理死代码、修注释与命名 |
