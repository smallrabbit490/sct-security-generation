# Docker 数据盘膨胀与压缩指南

## 问题现象

跑完一批 baseline / 一轮 SCT 后，D 盘剩余空间明显变少，即使删除了容器和临时文件，空间也不会回来。

## 原因（两层空间，回收难度不同）

验证器使用 `docker run --rm` 在容器里编译运行 C++/Go/Python 代码：

1. **任务级空间（容器可写层）**：`--rm` 会在容器结束后自动删除其临时层，块回到 vhdx 内部 ext4 的空闲池。**这一层已经自动回收，不需要任何操作。**
2. **文件级空间（`docker_data.vhdx` 文件本身）**：ext4 里的空闲块不会主动通知 Windows。vhdx 文件是动态扩展且非稀疏的，Windows 看到的文件大小停在"历史最高水位"，只有离线压缩才能把空闲块还给 Windows。

**因此：压缩只能在 Docker 完全退出后执行**（`diskpart compact` 要求文件不被占用）。合理的粒度是"每跑完一批压缩一次"，而不是每个任务后压缩——后者需要反复重启 Docker，反而拖慢实验，且没有必要（任务级空间已经自动回收了）。

## 本机实测（2026-09-15）

- 数据盘：`D:\DockerDesktopLocal\wsl-data\disk\docker_data.vhdx`（`settings-store.json` 中 `CustomWslDistroDir`）
- 文件 14.9 GB，内部实际用量 12.2 GB，其中镜像约 11.5 GB → 可回收约 2.7 GB
- 镜像 9 个 tag / 11.47 GB，容器 0 个，悬空镜像 0 个
- `docker system df` 显示"95% 可回收"是误导：那是因为容器数为 0，**不要执行 `docker system prune -a`**，否则会删掉全部验证器镜像（secevo-*、safecoder-*、gosec、semgrep 等），下次运行需重建

## 一键压缩脚本

`tools/compact_docker_vhdx.ps1`（需管理员权限，脚本会自动请求提权）：

```powershell
# 只看报告，不做修改
powershell -ExecutionPolicy Bypass -File .\tools\compact_docker_vhdx.ps1 -ReportOnly

# 正常压缩（预计可回收量低于 3 GB 会自动跳过）
powershell -ExecutionPolicy Bypass -File .\tools\compact_docker_vhdx.ps1

# 指定阈值 / 强制压缩
powershell -ExecutionPolicy Bypass -File .\tools\compact_docker_vhdx.ps1 -ThresholdGB 5
powershell -ExecutionPolicy Bypass -File .\tools\compact_docker_vhdx.ps1 -Force
```

脚本做的事：

1. 定位 `docker_data.vhdx`（优先读 `settings-store.json` 的 `CustomWslDistroDir`）；
2. 报告当前文件大小、内部实际用量、预计可回收量；
3. 有运行中容器时拒绝执行（除非 `-Force`）；
4. 退出 Docker Desktop → `wsl --shutdown` → `diskpart` 只读挂载并 `compact vdisk`；
5. 重新启动 Docker Desktop，报告回收了多少。

## 建议纳入实验收尾流程

每跑完一批（baseline run / SCT round）后运行一次压缩脚本。可选地，在运行脚本的收尾阶段追加：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\compact_docker_vhdx.ps1 -ReportOnly
```

先看预计可回收量，大于阈值再真正压缩。

## 其他可选的预防措施（按需）

- 给 Docker Desktop 数据盘设虚拟容量上限（设置里磁盘大小 / `settings-store.json` 的 `diskSizeMiB`），避免极端情况下吃干 D 盘；
- 大批量运行前先检查 D 盘剩余空间（不足时提前中止，避免写到一半 ENOSPC）；
- 压缩收益集中在"大批量运行后"；日常小任务运行不需要频繁压缩。
