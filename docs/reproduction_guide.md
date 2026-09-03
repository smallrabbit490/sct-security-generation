# 复现实验指南

1. 克隆仓库，并由 `.env.example` 创建 `.env.local`。
2. 确认 Docker Desktop 已运行并构建验证器镜像。
3. 运行 `python -m compileall src methods tools`。
4. 运行 `python -m unittest discover -s tests -v`。
5. 运行 `python tools/check_repository.py`。
6. 每条方法先跑一个任务，检查 trace 和 Docker 结果。
7. Base 与 Plus 分开运行；最终测试失败不能反向作为经验输入。
8. 大文件输出放在 Git 外部或被忽略的 `translation_work/` 下。

本仓库对“完成”采用保守口径。JSONL 只能证明写入了一行，不能证明编译、功能测试和安全测试均通过。
