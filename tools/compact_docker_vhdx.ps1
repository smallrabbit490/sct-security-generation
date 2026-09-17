# tools/compact_docker_vhdx.ps1
# ============================================================
# 用途：压缩 Docker Desktop 的 WSL2 数据盘 docker_data.vhdx，
#       把"已删除但从未归还 Windows"的块还给 D 盘。
#
# 为什么需要这个脚本：
#   - 验证代码使用 `docker run --rm`，容器结束后其临时层已被删除，
#     块回到 vhdx 内部 ext4 的空闲池（任务级空间已自动回收）；
#   - 但 vhdx 文件本身从不自动缩小，Windows 看到的文件大小停在
#     "历史最高水位"。只有离线 compact 才能把空闲块还给 Windows。
#
# 什么时候运行：
#   - 跑完一批 baseline / 一轮 SCT 之后运行一次即可；
#   - 不需要每个任务后运行（任务级空间已由 --rm 自动回收，
#     且每个任务后都重启 Docker 反而会拖慢整个实验）。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File .\tools\compact_docker_vhdx.ps1 -ReportOnly
#   powershell -ExecutionPolicy Bypass -File .\tools\compact_docker_vhdx.ps1
#   powershell -ExecutionPolicy Bypass -File .\tools\compact_docker_vhdx.ps1 -ThresholdGB 5
#   powershell -ExecutionPolicy Bypass -File .\tools\compact_docker_vhdx.ps1 -Force
#
# 注意：
#   - diskpart 需要管理员权限，脚本会自动以管理员身份重新启动自己；
#   - 压缩期间会退出 Docker Desktop 并执行 wsl --shutdown，
#     压缩完成后自动重新启动 Docker Desktop（可用 -SkipRestart 关闭）；
#   - 检测到有运行中的容器时会拒绝执行（除非 -Force）。
# ============================================================

[CmdletBinding()]
param(
    # 只看报告，不做任何修改
    [switch]$ReportOnly,
    # 跳过交互确认，直接压缩
    [switch]$Force,
    # 预计可回收量小于该值（GB）时跳过压缩
    [int]$ThresholdGB = 3,
    # 压缩完成后不自动重启 Docker Desktop
    [switch]$SkipRestart
)

$ErrorActionPreference = 'Stop'

# ---------- 0. 管理员检查：diskpart 必须在管理员窗口里运行 ----------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[提示] 需要管理员权限，正在重新以管理员身份启动本脚本..." -ForegroundColor Yellow
    # 重新构造命令行参数：带 [CmdletBinding()] 的脚本里 $args 不包含已声明参数，
    # 必须用 $PSBoundParameters 把用户给的开关/数值原样传给提权后的实例
    $relaunch = @()
    foreach ($k in $PSBoundParameters.Keys) {
        $v = $PSBoundParameters[$k]
        if ($v -is [System.Management.Automation.SwitchParameter]) {
            if ($v.IsPresent) { $relaunch += "-$k" }
        } else {
            $relaunch += "-$k"
            $relaunch += [string]$v
        }
    }
    $argStr = ($relaunch | ForEach-Object { '"' + $_ + '"' }) -join ' '
    Start-Process -FilePath 'powershell.exe' -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '" ' + $argStr) -Verb RunAs
    exit 0
}

# ---------- 1. 定位 docker_data.vhdx ----------
# Docker Desktop 的自定义数据目录在 settings-store.json 里，
# 默认是 <安装盘>\DockerDesktopLocal\wsl-data\disk\docker_data.vhdx。
function Get-DockerDataVhdxPath {
    $settingsPath = Join-Path $env:APPDATA 'Docker\settings-store.json'
    if (Test-Path -LiteralPath $settingsPath) {
        try {
            $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
            if ($settings.CustomWslDistroDir) {
                $candidate = Join-Path $settings.CustomWslDistroDir 'disk\docker_data.vhdx'
                if (Test-Path -LiteralPath $candidate) { return $candidate }
            }
        } catch {
            Write-Warning "读取 settings-store.json 失败: $($_.Exception.Message)"
        }
    }
    # 常见兜底路径
    foreach ($p in @(
        'D:\DockerDesktopLocal\wsl-data\disk\docker_data.vhdx',
        "$env:LOCALAPPDATA\Docker\wsl\data\ext4.vhdx",
        "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx"
    )) {
        if (Test-Path -LiteralPath $p) { return $p }
    }
    return $null
}

$vhdx = Get-DockerDataVhdxPath
if (-not $vhdx) {
    Write-Error "找不到 docker_data.vhdx，请手动检查 Docker Desktop 的数据目录后重试。"
    exit 1
}

# ---------- 2. 采集"压缩前"数据 ----------
$fileBefore = (Get-Item -LiteralPath $vhdx).Length
Write-Host "数据盘文件 : $vhdx" -ForegroundColor Cyan
Write-Host ("当前文件大小: {0:N2} GB" -f ($fileBefore / 1GB)) -ForegroundColor Cyan

# 尝试读取 vhdx 内部 ext4 的真实用量（docker 运行时可以读）。
# docker-desktop 发行版是 BusyBox，df 不支持 --output，改用 df -B1 输出精确字节，
# 取 "docker-desktop-disk" 那一行的第 3 列（Used，单位字节）。
$internalUsedBytes = $null
try {
    $dfLines = (& wsl -d docker-desktop -e df -B1 /mnt/docker-desktop-disk 2>$null)
    $dfRow = $dfLines | Where-Object { $_ -match 'docker-desktop-disk' } | Select-Object -Last 1
    if ($dfRow) {
        $tokens = (($dfRow -replace [char]0, '') -split '\s+') | Where-Object { $_ -ne '' }
        if ($tokens.Count -ge 3 -and $tokens[2] -match '^\d+$') {
            $internalUsedBytes = [int64]$tokens[2]
            Write-Host ("内部实际用量: {0:N2} GB" -f ($internalUsedBytes / 1GB)) -ForegroundColor Cyan
        }
    }
} catch {
    Write-Warning "读取内部用量失败（Docker 可能已停止），将按文件大小估算。"
}

if ($internalUsedBytes) {
    $reclaimableGB = ($fileBefore - $internalUsedBytes) / 1GB
    Write-Host ("预计可回收  : {0:N2} GB" -f $reclaimableGB) -ForegroundColor Cyan
} else {
    $reclaimableGB = $null
    Write-Host "预计可回收  : 未知（Docker 未运行，无法读内部用量）" -ForegroundColor DarkYellow
}

if ($ReportOnly) {
    Write-Host "`n[报告模式] 未做任何修改。若预计可回收量较大，去掉 -ReportOnly 再运行即可压缩。" -ForegroundColor Green
    exit 0
}

# ---------- 3. 决策：值不值得压缩 ----------
if ($reclaimableGB -ne $null -and $reclaimableGB -lt $ThresholdGB -and -not $Force) {
    Write-Host ("预计只回收 {0:N2} GB（低于阈值 {1} GB），跳过压缩。" -f $reclaimableGB, $ThresholdGB) -ForegroundColor DarkYellow
    Write-Host "如需强制压缩请加 -Force。" -ForegroundColor DarkYellow
    exit 0
}

# ---------- 4. 安全检查：有运行中的容器则拒绝 ----------
try {
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if ($dockerCmd) {
        $runningContainers = @(& docker ps -q 2>$null)
        if ($runningContainers.Count -gt 0) {
            if ($Force) {
                Write-Warning "检测到 $($runningContainers.Count) 个运行中的容器，-Force 强制继续（数据有丢失风险）。"
            } else {
                Write-Error "检测到 $($runningContainers.Count) 个运行中的容器，请先停止它们再压缩。"
                exit 1
            }
        }
    }
} catch {
    Write-Warning "无法查询容器状态：$($_.Exception.Message)"
}

# ---------- 5. 交互确认 ----------
if (-not $Force) {
    $answer = Read-Host "确认现在退出 Docker Desktop 并压缩数据盘？(yes/no)"
    if ($answer -notmatch '^(y|yes)$') {
        Write-Host "已取消。" -ForegroundColor Yellow
        exit 0
    }
}

# ---------- 6. 停止 Docker Desktop + WSL ----------
Write-Host "正在停止 Docker Desktop 与 WSL..." -ForegroundColor Cyan
Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like 'Docker*' -or $_.Name -like 'com.docker*' -or $_.Name -eq 'vpnkit' } |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
& wsl --shutdown 2>$null
Start-Sleep -Seconds 3
Write-Host "已停止。" -ForegroundColor Green

# ---------- 7. diskpart 压缩 ----------
$diskpartScript = Join-Path $env:TEMP ("compact_vhdx_" + [guid]::NewGuid().ToString('N') + ".txt")
@(
    'select vdisk file="' + $vhdx + '"',
    'attach vdisk readonly',
    'compact vdisk',
    'detach vdisk',
    'exit'
) | Set-Content -LiteralPath $diskpartScript -Encoding ASCII

Write-Host "正在压缩 vhdx（diskpart compact）..." -ForegroundColor Cyan
$dpOut = & diskpart /s $diskpartScript 2>&1
Remove-Item -LiteralPath $diskpartScript -Force -ErrorAction SilentlyContinue
$dpOut | Select-Object -Last 12

$fileAfter = (Get-Item -LiteralPath $vhdx).Length
Write-Host ("压缩后文件大小: {0:N2} GB（回收 {1:N2} GB）" -f ($fileAfter / 1GB), (($fileBefore - $fileAfter) / 1GB)) -ForegroundColor Green

# ---------- 8. 重新启动 Docker Desktop ----------
if (-not $SkipRestart) {
    $dockerExe = 'D:\DockerDesktopLocal\app\Docker Desktop.exe'
    if (-not (Test-Path -LiteralPath $dockerExe)) {
        $dockerExe = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    }
    if (Test-Path -LiteralPath $dockerExe) {
        Write-Host "正在重新启动 Docker Desktop..." -ForegroundColor Cyan
        Start-Process -FilePath $dockerExe
        Write-Host "已启动，等待数秒即可使用。" -ForegroundColor Green
    } else {
        Write-Warning "找不到 Docker Desktop.exe，请手动启动 Docker Desktop。"
    }
}

Write-Host "`n完成。建议把本脚本加入每次实验收尾流程（见 docs/docker_disk_hygiene.md）。" -ForegroundColor Green
exit 0
