# secodeplt_eval：官方 SeCodePLT 评测方式本地移植

本目录把官方论文仓库 `ucsb-mlsec/SeCodePLT`（[arXiv 2410.11096](https://arxiv.org/html/2410.11096)，
本地快照在 `data/external/secodeplt_github/`）的 **Python 评测方式**移植到本仓库，
用于对 PLT 任务做与官方一致的 capability（功能）/ safety（安全）动态单测。

## 文件索引

| 文件 | 主要负责什么 |
|---|---|
| `schemas.py` | 与官方数据结构对齐的 dataclass（TaskDescription / CWEData / TestCodeParams / TestCodeOutput），零外部依赖 |
| `template.py` | 官方 `unittest_template` 模板 + `## START ... ##` 占位符注入逻辑 + Windows 兼容（`signal.alarm` 降级） |
| `executor.py` | 执行器：本地 `python -I` 子进程（默认）与常驻 Docker 容器（可选，官方模式） |
| `scoring.py` | 官方打分语义：capability/safety 平均分 + 联合通过判定（全过才算） |
| `README.md` | 本文件 |

## 评测语义（与官方一致）

- 每个测试用例 `(arguments, expected)`：调用被测函数 `__func(**arguments)`，
  `str(output) == str(expected)` 判对；期望值是异常类型时检查是否抛出。
- 用例结果：`1`=通过，`-1`=运行错误，`-2`=超时（模板按用例 `signal.alarm(10s)`；
  Windows 无 SIGALRM 时降级，由外层 subprocess 超时兜底）。
- 打分：`capability_score` / `safety_score` = 各自组内通过数 / 组内总数（负分钳 0）。
- 联合通过 `joint_pass`：**功能与安全两组都必须全过**（对应官方 generate_table
  的「capability 不是平均而是全过才算 1，且 capability 不过时 safety 直接记 0」），
  与本项目 `trajectory_runner.joint_pass` 口径一致。

## 用法

```powershell
python -m compileall methods\secodeplt_eval
python -m unittest discover -s tests -p "test_secodeplt_eval.py" -v

# 对一条 PLT 任务记录(raw_data 为 data.json 的一行)评测生成代码
python -c "
import json
from pathlib import Path
from methods.secodeplt_eval import testcase_evaluation, joint_pass
rows = json.loads(Path('data/external/secodeplt/secodeplt/data.json').read_text(encoding='utf-8'))
row = rows[0]
truth = row['ground_truth']
full = truth['code_before'] + truth['patched_code'] + truth['code_after']  # 黄金修复函数
ev = testcase_evaluation(full, row)
print(ev)
print('joint_pass:', joint_pass(ev))
"
```

## 与官方/VHDX 有关的说明：为什么官方评测不会让 Docker 虚拟盘（VHDX）变大

### 官方的执行模式（`executor_docker/server/`）

1. **镜像只构建一次，评测期间从不 build**：`python:3.11-alpine` 基础镜像 +
   几行依赖，`Dockerfile` 仅 4 步；评测前 `docker build/pull` 一次，之后全程不重建。
2. **常驻单容器**：服务启动时 `containers.run(...)` 创建**一个**容器，评测结束才
   `container.remove(force=True)`。每个任务只在这个容器上 `exec_run`：
   往 `/tmp` 写输入 JSON（几十 KB）→ 执行 `run_test.py` → `cat` 取回输出 →
   `rm -f` 删除临时文件。
3. **输出极小且清理**：结果只是 capability/safety 的 int 列表，KB 级，用完即删。

### 为什么这样就不会让 VHDX 膨胀

Docker Desktop（WSL2 后端）的数据盘是 `%LOCALAPPDATA%\Docker\wsl\data\ext4.vhdx`，
一个**稀疏虚拟盘**。它的两个特性决定了「变大」的本质：

- **写入即增长、删除不回收**：镜像层、容器可写层、BuildKit 缓存都写在这个
  vhdx 里；即使 `docker rm` / `docker image prune` 删除了数据，**vhdx 文件
  本身不会自动收缩**（必须 `wsl --shutdown` 后 compact 或 `Optimize-VHD`）。
- 因此「VHDX 变大」= **写入量累积且永不回收**。

官方把所有「每次评测」的写入压到 KB 级（常驻容器 + 临时文件即写即删 + 不
build），于是即便 vhdx 不回收，增长也可忽略。而常见膨胀来源——**反复
`docker build` 产生的新镜像层与 BuildKit 缓存（几百 MB ~ 数 GB）**——官方
评测期间完全不存在。

### 本项目的对比与建议

- `src/translation_pipeline/validators.py` / `python_validator.py`：每条记录
  `docker run` 新建容器、验证后 `docker rm -f`。容器层会删，但**镜像层与
  build cache 仍留在 vhdx**；若频繁 `docker build`，层会持续累积。
- PLT 训练侧已用本地 `python -I`（本模块默认后端同款），本身不膨胀；膨胀主要
  来自 Base/Plus Docker 验证与反复 build。
- 建议：a) 大评测用「常驻容器 + exec_run」模式替代逐任务 `docker run`
  （本模块 `run_testcases_docker` 已按该模式实现）；b) 镜像稳定后不要反复
  build；c) 需要回收空间时 `wsl --shutdown` 后 compact `ext4.vhdx`。

## 边界

- 本地后端忽略 `install_requires`（安装依赖有副作用且数据中多为空）；需要依赖
  时请用 Docker 后端（准备含依赖的 python 镜像）。
- 空 `testcases` 的 10 个 CWE（22/78/120/281/295/338/367/400/611/732）在官方
  走 LLM 规则评审（`rule` 字段），本模块只做动态单测，不含 llm_judge。
- Docker 后端测试在无 Docker / 无法拉镜像时自动跳过。
