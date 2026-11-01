# wallpaperdownloadfix — 完整仓库交付包

> 这份文件包含**一个完整可发布的 GitHub 仓库的全部内容**。
> 把下面每个代码块按标注的路径保存成文件，就是一个可以直接 push 的仓库。

---

## 一、仓库信息（建仓时照着填）

| 字段 | 值 |
|---|---|
| Repository name | `wallpaperdownloadfix` |
| Description | `Repair a corrupted Steam Workshop manifest so Steam stops re-downloading content you already have.` |
| Visibility | Public |
| License | MIT |
| Topics | `steam` `steam-workshop` `wallpaper-engine` `steam-bug-fix` `powershell` `python` `cli-tool` |

### 这个项目解决什么问题

Steam 某天开始把**已经下载好的**创意工坊内容当成缺失，全部重新下载，
`steamapps/workshop/downloads` 涨到几十 GB 把盘塞满，然后 Steam 自己卡死。

根因是 `appworkshop_<appid>.acf` 里的 `WorkshopItemsInstalled` 段在磁盘写满时被写坏。
本工具用同一文件里仍然完好的 `WorkshopItemDetails` 段（含每个条目的真实 manifest ID）
配合磁盘上文件夹的实际大小，重建损坏的段。

**只重写 `.acf` 这一个文本文件，不碰任何壁纸内容。**

---

## 二、文件清单

| # | 路径 | 说明 |
|---:|---|---|
| 1 | `README.md` | 英文说明（GitHub 首页） |
| 2 | `README.zh-CN.md` | 中文说明 |
| 3 | `wallpaperdownloadfix.ps1` | Windows 主程序（537 行，零依赖） |
| 4 | `wallpaperdownloadfix.py` | 跨平台版（626 行，纯标准库） |
| 5 | `run.cmd` | 双击运行的一键入口 |
| 6 | `LICENSE` | MIT 许可证 |
| 7 | `.gitignore` | 忽略规则 |
| 8 | `.gitattributes` | 行尾规范化 |
| 9 | `publish.ps1` | 发布到 GitHub 的辅助脚本 |

---

## 三、文件内容

### 1. `README.md`

````markdown
# Wallpaper Download Fix

**Repair a corrupted Steam Workshop manifest so Steam stops re-downloading content you already have.**

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)](#requirements)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[中文说明 →](README.zh-CN.md)

---

## The problem

One day Steam decides that thousands of Workshop items you already downloaded are
*missing*, and starts downloading them all over again. `steamapps/workshop/downloads`
balloons to tens of gigabytes, the drive fills up, and Steam stalls because it has
nowhere left to write.

## Why it happens

`steamapps/workshop/appworkshop_<appid>.acf` is where Steam records which Workshop
items are installed. When the disk fills up mid-write, that file gets **truncated** —
specifically the `WorkshopItemsInstalled` section:

```
broken :  WorkshopItemsInstalled = 4 entries      SizeOnDisk = 354 MB
correct:  WorkshopItemsInstalled = 2078 entries   SizeOnDisk = 118.26 GB
```

Steam now believes you have 4 wallpapers totalling 338 MB, so the remaining ~118 GB
looks like it needs downloading. And it becomes a loop:

> disk full → manifest corrupted → Steam thinks nothing is installed → re-downloads
> 118 GB → disk fills faster → manifest corrupted again

## The fix

The **`WorkshopItemDetails`** section of the *same file* usually survives intact and
still holds every item's real `manifest` ID.

This tool rebuilds `WorkshopItemsInstalled` from those IDs plus the **actual on-disk
size** of each content folder. Afterwards Steam recognises everything as installed,
`NeedsDownload` goes to `0`, and the re-downloading stops.

**No wallpaper files are touched. Only the `.acf` text file is rewritten.**

---

## Requirements

| | |
|---|---|
| PowerShell version | Windows, PowerShell 5.1+ (built in on Win10/11) |
| Python version | Python 3.8+, Windows / Linux / macOS |

Use whichever you prefer — both do exactly the same thing.

## Usage

### 1. Fully quit Steam

Right-click the Steam tray icon → **Exit**.

> Closing the window is not enough — Steam keeps running in the background.
> The tool detects this and refuses to run.

### 2. Run it

**Windows (PowerShell)**

```powershell
.\wallpaperdownloadfix.ps1 -DryRun     # analyse only, change nothing
.\wallpaperdownloadfix.ps1             # repair everything broken
```

Or just double-click `run.cmd`.

**Any platform (Python)**

```bash
python wallpaperdownloadfix.py --dry-run
python wallpaperdownloadfix.py
```

### 3. Start Steam again

It should now accept all installed content and stop re-downloading.

---

## Options

| PowerShell | Python | Meaning |
|---|---|---|
| `-DryRun` | `--dry-run` | Analyse and print the plan, modify nothing |
| `-AppId 431960` | `--appid 431960` | Only handle one appid (default: all found) |
| `-SteamRoot "D:\Steam"` | `--steam-root "D:\Steam"` | Force a Steam install location |
| `-Force` | `--force` | Continue even if Steam is running (not recommended) |
| `-NoBackup` | `--no-backup` | Skip the backup file (not recommended) |

## What it detects automatically

- **Steam install location** — Windows registry (`HKCU`/`HKLM`), then common paths;
  `~/.steam/steam`, `~/.local/share/Steam` and `~/Library/Application Support/Steam`
  on Linux/macOS
- **Every Steam library** — parsed from `steamapps/libraryfolders.vdf`, so multiple
  drives are handled
- **Every Workshop app** — every `appworkshop_*.acf` found across all libraries
- **Whether it is actually broken** — compares the installed-entry count against the
  details-entry count; only broken manifests are touched

## Safety

| Guarantee | How |
|---|---|
| Never deletes content | Only the `.acf` file is rewritten |
| Always backs up first | `appworkshop_backup_<timestamp>.acf` next to the original |
| Never shrinks the manifest | If the rebuild would produce fewer entries than before, it refuses and reports why |
| Verifies after writing | Re-reads the file and re-counts entries |
| Will not fight Steam | Aborts if Steam is running |

### Restoring a backup

```powershell
Copy-Item '.\appworkshop_backup_20260101_120000.acf' `
          '<Steam>/steamapps/workshop/appworkshop_431960.acf' -Force
```

## Output example

```
> 3 / 4  Diagnose
    [BROKEN] appid 431960
        installed 4 / details 2078 / 2083 folders on disk
        SizeOnDisk 0.35 GB / NeedsDownload 1
        reason: installed section has only 4 entries, details section has 2078

> 4 / 4  Repair
    [+] appid 431960 repaired: 2078 entries, 118.26 GB
        verify: installed 2078 / NeedsDownload 0 / SizeOnDisk 118.26 GB
        backup -> appworkshop_backup_20260101_120000.acf
```

## FAQ

**It says `WorkshopItemDetails` is unusable — now what?**
The file is damaged beyond local repair. In Steam, unsubscribe from the Workshop
items you do not need, then delete the `.acf` and restart Steam so it rebuilds from
scratch.

**Will this happen again?**
Only if the drive fills up again mid-write. Keeping headroom on the drive — and
unsubscribing from Workshop items you no longer use — is the real fix.

**Does it work for Garry's Mod / other games?**
Yes. Workshop manifests are per-app, and the format is identical.
`--appid 4000` for Garry's Mod, or just run it with no arguments to scan everything.

## License

[MIT](LICENSE)
````

### 2. `README.zh-CN.md`

````markdown
# Wallpaper Download Fix

**修复损坏的 Steam 创意工坊清单，让 Steam 不再重复下载你已经有的内容。**

[English →](README.md)

---

## 问题现象

某天开始，Steam 突然把几千个**已经下载好**的创意工坊内容当成"缺失"，全部重新下载。
`steamapps/workshop/downloads` 暂存目录迅速涨到几十 GB，把整块盘塞满，
然后 Steam 自己卡死——因为没地方可写了。

## 为什么会这样

`steamapps/workshop/appworkshop_<appid>.acf` 是 Steam 记录"哪些工坊条目已安装"的清单。
当磁盘在写入过程中被写满，这个文件会被**截断**，具体是 `WorkshopItemsInstalled` 段：

```
损坏时：WorkshopItemsInstalled = 4 条          SizeOnDisk = 354 MB
正常应：WorkshopItemsInstalled = 2078 条       SizeOnDisk = 118.26 GB
```

Steam 以为你只装了 4 个壁纸、总共 338 MB，于是剩下 118 GB 全被当成"缺失"要下载。
而且会形成死循环：

> 盘满 → 清单写坏 → Steam 以为没装 → 重下 118 GB → 更快满盘 → 清单再写坏

## 怎么修

**同一个文件里的 `WorkshopItemDetails` 段通常还是完好的**，里面保存着每个条目的
真实 `manifest` ID。

本工具用这些 manifest ID，配合磁盘上各内容文件夹的**实际大小**，
重建损坏的 `WorkshopItemsInstalled` 段。修完之后 Steam 会认下全部已装内容，
`NeedsDownload` 归零，不再重复下载。

**不会动任何壁纸文件，只重写 `.acf` 这一个文本文件。**

---

## 环境要求

| | |
|---|---|
| PowerShell 版 | Windows，PowerShell 5.1+（Win10/11 自带） |
| Python 版 | Python 3.8+，Windows / Linux / macOS |

两个版本功能完全一致，用哪个都行。

## 使用方法

### 第一步：完全退出 Steam

右键任务栏托盘里的 Steam 图标 → **退出**。

> 只关窗口不算退出，Steam 还在后台跑。工具检测到会拒绝执行。

### 第二步：运行

**Windows（PowerShell）**

```powershell
.\wallpaperdownloadfix.ps1 -DryRun     # 只看诊断，不改任何东西
.\wallpaperdownloadfix.ps1             # 修复所有损坏的清单
```

或者直接双击 `run.cmd`。

**任意平台（Python）**

```bash
python wallpaperdownloadfix.py --dry-run
python wallpaperdownloadfix.py
```

### 第三步：重新启动 Steam

它应该会认下全部已装内容，不再重复下载。

---

## 参数说明

| PowerShell | Python | 含义 |
|---|---|---|
| `-DryRun` | `--dry-run` | 只分析并打印计划，不修改任何文件 |
| `-AppId 431960` | `--appid 431960` | 只处理指定 appid（默认处理全部） |
| `-SteamRoot "D:\Steam"` | `--steam-root "D:\Steam"` | 手动指定 Steam 安装目录 |
| `-Force` | `--force` | 即使 Steam 在运行也继续（不推荐） |
| `-NoBackup` | `--no-backup` | 不生成备份（不推荐） |

## 自动检测的东西

- **Steam 安装位置** —— Windows 读注册表（`HKCU`/`HKLM`），再扫常见路径；
  Linux/macOS 读 `~/.steam/steam`、`~/.local/share/Steam`、
  `~/Library/Application Support/Steam`
- **所有 Steam 库** —— 解析 `steamapps/libraryfolders.vdf`，多硬盘也能处理
- **所有工坊 app** —— 遍历全部库里的 `appworkshop_*.acf`
- **是否真的损坏** —— 比较"已安装段条目数"和"详情段条目数"，只修有问题的

## 安全性

| 保证 | 做法 |
|---|---|
| 绝不删内容 | 只重写 `.acf` 文件 |
| 一定先备份 | 原文件旁边生成 `appworkshop_backup_<时间戳>.acf` |
| 绝不缩小清单 | 重建后条目数若少于原来，直接拒绝并说明原因 |
| 写完必校验 | 读回文件重新统计条目数 |
| 不跟 Steam 抢文件 | 检测到 Steam 在运行就中止 |

### 还原备份

```powershell
Copy-Item '.\appworkshop_backup_20260101_120000.acf' `
          '<Steam>/steamapps/workshop/appworkshop_431960.acf' -Force
```

## 输出示例

```
> 3 / 4  诊断
    [损坏] appid 431960
        已安装段 4 条 / 详情段 2078 条 / 磁盘 2083 个文件夹
        SizeOnDisk 0.35 GB / NeedsDownload 1
        原因：已安装段只有 4 条，但详情段有 2078 条

> 4 / 4  修复
    [+] appid 431960 修复完成：2078 条，118.26 GB
        校验：已安装段 2078 条 / NeedsDownload 0 / SizeOnDisk 118.26 GB
        备份 -> appworkshop_backup_20260101_120000.acf
```

## 常见问题

**提示 `WorkshopItemDetails` 段也不可用，怎么办？**
说明文件损坏得更彻底，本地无法重建。处理办法：在 Steam 里退订不需要的工坊内容，
然后删掉这个 `.acf`，重启 Steam 让它重新生成。

**以后还会再坏吗？**
只要磁盘再次在写入时被写满就可能复发。根治办法是别让盘长期处于满的状态，
以及退订不需要的工坊内容。

**支持 Garry's Mod 之类的其它游戏吗？**
支持。工坊清单是按 app 分的，格式完全一样。Garry's Mod 用 `--appid 4000`，
或者不带参数直接扫描全部。

## 许可证

[MIT](LICENSE)
````

### 3. `wallpaperdownloadfix.ps1`

> ⚠️ **必须保存为 UTF-8 with BOM** —— 否则 PowerShell 5.1 会把中文按 GBK 读，注释里的字节可能被误读成反引号导致行继续、脚本行为异常。

```powershell
<#
.SYNOPSIS
    Wallpaper Download Fix - 修复 Steam 创意工坊清单损坏导致的重复下载。

.DESCRIPTION
    Steam 反复把「已经下载好的」创意工坊内容当成缺失并重新下载，把磁盘塞满。
    原因通常是 appworkshop_<appid>.acf 里的 "WorkshopItemsInstalled" 段被写坏
    （磁盘写满时写入中断），Steam 以为只装了极少数内容。

    同一文件里的 "WorkshopItemDetails" 段通常仍完好，保存着每个条目的真实
    manifest ID。本工具用这些 manifest ID + 磁盘上文件夹的实际大小，
    重建损坏的 "WorkshopItemsInstalled" 段。

    支持：
      - 自动探测 Steam 安装位置（注册表 + 常见路径）
      - 自动遍历所有 Steam 库（libraryfolders.vdf），多硬盘也支持
      - 任意 appid（Wallpaper Engine / Garry's Mod / 其它）
      - 自动判断「是否损坏」，只修有问题的
      - 始终先备份；重建结果比原来少就拒绝执行

.PARAMETER AppId
    只处理指定 appid。省略则扫描并处理所有能找到的工坊清单。

.PARAMETER SteamRoot
    手动指定 Steam 安装目录。省略则自动探测。

.PARAMETER DryRun
    只分析、只打印计划，不修改任何文件。

.PARAMETER Force
    即使检测到 Steam 正在运行也继续（不推荐，Steam 可能覆盖写回）。

.PARAMETER NoBackup
    不生成备份文件（不推荐）。

.EXAMPLE
    .\wallpaperdownloadfix.ps1 -DryRun

.EXAMPLE
    .\wallpaperdownloadfix.ps1

.EXAMPLE
    .\wallpaperdownloadfix.ps1 -AppId 431960
#>
[CmdletBinding()]
param(
    [int]$AppId = 0,
    [string]$SteamRoot = '',
    [switch]$DryRun,
    [switch]$Force,
    [switch]$NoBackup
)

$ErrorActionPreference = 'Stop'
$script:Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$script:Version = '1.0.0'

# ==================================================================
#  输出辅助
# ==================================================================
function Write-Title([string]$text) {
    Write-Host ''
    Write-Host ('=' * 64) -ForegroundColor DarkGray
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host ('=' * 64) -ForegroundColor DarkGray
}
function Write-Step([string]$text) {
    Write-Host ''
    Write-Host "  > $text" -ForegroundColor Cyan
    Write-Host ('  ' + ('-' * 60)) -ForegroundColor DarkGray
}
function Write-Ok([string]$text)    { Write-Host "    [+] $text" -ForegroundColor Green }
function Write-Warn2([string]$text) { Write-Host "    [!] $text" -ForegroundColor Yellow }
function Write-Err([string]$text)   { Write-Host "    [x] $text" -ForegroundColor Red }
function Write-Info([string]$text)  { Write-Host "        $text" -ForegroundColor Gray }

# ==================================================================
#  VDF 解析（Steam 的 KeyValues 文本格式）
# ==================================================================
function Unescape-Vdf([string]$s) {
    # VDF 字符串里 \\ -> \ ，\" -> "
    $r = $s
    $r = $r.Replace('\\', '\')
    $r = $r.Replace('\"', '"')
    return $r
}

function Get-LibraryPaths([string]$steamRoot) {
    # 返回该 Steam 安装下所有库目录（含自身），大小写不敏感去重
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $libs = New-Object System.Collections.Generic.List[string]

    $add = {
        param($p)
        if (-not $p) { return }
        $p = $p.TrimEnd('\', '/')
        if (-not $p) { return }
        try { $full = [System.IO.Path]::GetFullPath($p) } catch { return }
        if ($seen.Add($full)) { [void]$libs.Add($full) }
    }

    if (Test-Path -LiteralPath (Join-Path $steamRoot 'steamapps')) { & $add $steamRoot }

    $vdf = Join-Path $steamRoot 'steamapps\libraryfolders.vdf'
    if (Test-Path -LiteralPath $vdf) {
        try {
            $t = [System.IO.File]::ReadAllText($vdf, $script:Utf8NoBom)
            foreach ($m in [regex]::Matches($t, '"path"\s+"((?:[^"\\]|\\.)*)"')) {
                $p = Unescape-Vdf $m.Groups[1].Value
                if (Test-Path -LiteralPath $p) { & $add $p }
            }
        } catch { }
    }

    if ($libs.Count -eq 0) { [void]$libs.Add($steamRoot) }
    return $libs
}

function Find-SteamRoots([string]$explicit) {
    $roots = New-Object System.Collections.Generic.List[string]
    $seen  = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)

    if ($explicit) {
        try { $full = (Get-Item -LiteralPath $explicit).FullName } catch { return $roots }
        if (Test-Path -LiteralPath (Join-Path $full 'steamapps')) { [void]$roots.Add($full) }
        return $roots
    }

    $cands = New-Object System.Collections.Generic.List[string]
    foreach ($rk in 'HKCU:\Software\Valve\Steam',
                    'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam',
                    'HKLM:\SOFTWARE\Valve\Steam') {
        try {
            $v = Get-ItemProperty -Path $rk -ErrorAction SilentlyContinue
            if ($v) {
                if ($v.SteamPath)   { [void]$cands.Add($v.SteamPath) }
                if ($v.InstallPath) { [void]$cands.Add($v.InstallPath) }
            }
        } catch { }
    }
    foreach ($d in 'C:\Program Files (x86)\Steam', 'C:\Program Files\Steam',
                   'D:\Steam', 'D:\SteamLibrary', 'E:\Steam', 'E:\steam',
                   'F:\Steam', 'G:\Steam') {
        [void]$cands.Add($d)
    }

    foreach ($c in $cands) {
        if (-not $c) { continue }
        $full = $null
        try { $full = (Get-Item -LiteralPath $c).FullName } catch { continue }
        if (-not $full) { continue }
        if (-not (Test-Path -LiteralPath (Join-Path $full 'steamapps'))) { continue }
        if ($seen.Add($full)) { [void]$roots.Add($full) }
    }
    return $roots
}

# ==================================================================
#  ACF 解析（KeyValues 文本，花括号配平）
# ==================================================================
function Get-BlockRange([string]$text, [string]$key) {
    $ki = $text.IndexOf($key)
    if ($ki -lt 0) { return $null }
    $ob = $text.IndexOf('{', $ki)
    if ($ob -lt 0) { return $null }
    $depth = 0
    for ($p = $ob; $p -lt $text.Length; $p++) {
        $ch = $text[$p]
        if ($ch -eq '{') { $depth++ }
        elseif ($ch -eq '}') {
            $depth--
            if ($depth -eq 0) {
                return [pscustomobject]@{
                    Start = $ki
                    Open  = $ob
                    Close = $p
                    Body  = $text.Substring($ki, $p - $ki + 1)
                }
            }
        }
    }
    return $null
}

function Get-FieldValue([string]$text, [string]$name) {
    $m = [regex]::Match($text, '"' + [regex]::Escape($name) + '"\s+"([^"]*)"')
    if ($m.Success) { return $m.Groups[1].Value }
    return $null
}

function Get-ItemBlocks([string]$blockBody) {
    # 逐个条目块解析：id -> 块内文本。字段顺序无关。
    $result = @{}
    $rx = [regex]'"(\d{6,})"\s*\{'
    foreach ($m in $rx.Matches($blockBody)) {
        $id = $m.Groups[1].Value
        if ($result.ContainsKey($id)) { continue }
        $ob = $blockBody.IndexOf('{', $m.Index)
        if ($ob -lt 0) { continue }
        $depth = 0; $cb = -1
        for ($p = $ob; $p -lt $blockBody.Length; $p++) {
            $ch = $blockBody[$p]
            if ($ch -eq '{') { $depth++ }
            elseif ($ch -eq '}') { $depth--; if ($depth -eq 0) { $cb = $p; break } }
        }
        if ($cb -lt 0) { continue }
        $result[$id] = $blockBody.Substring($ob, $cb - $ob + 1)
    }
    return $result
}

function Get-DetailsMap([string]$text) {
    # 从 WorkshopItemDetails 段解析 id -> {Manifest, TimeUpdated}，字段顺序无关
    $map = @{}
    $blk = Get-BlockRange $text '"WorkshopItemDetails"'
    if (-not $blk) { return $map }
    $blocks = Get-ItemBlocks $blk.Body
    foreach ($id in $blocks.Keys) {
        $inner = $blocks[$id]
        $mf = [regex]::Match($inner, '"manifest"\s+"(-?\d+)"')
        if (-not $mf.Success) { continue }
        $tu = [regex]::Match($inner, '"timeupdated"\s+"(\d+)"')
        $map[$id] = [pscustomobject]@{
            Manifest    = $mf.Groups[1].Value
            TimeUpdated = $(if ($tu.Success) { $tu.Groups[1].Value } else { '0' })
        }
    }
    return $map
}

function Measure-Content([string]$contentDir) {
    $sizes = @{}
    if (-not (Test-Path -LiteralPath $contentDir)) { return $sizes }
    foreach ($d in Get-ChildItem -LiteralPath $contentDir -Force -Directory -ErrorAction SilentlyContinue) {
        $sum = 0
        try {
            $sum = (Get-ChildItem -LiteralPath $d.FullName -Recurse -Force -File -ErrorAction SilentlyContinue |
                    Measure-Object Length -Sum).Sum
            if ($null -eq $sum) { $sum = 0 }
        } catch { $sum = 0 }
        $sizes[$d.Name] = [long]$sum
    }
    return $sizes
}

# ==================================================================
#  诊断
# ==================================================================
function Test-AcfHealth([string]$acfPath, [string]$contentDir) {
    $txt = [System.IO.File]::ReadAllText($acfPath, $script:Utf8NoBom)

    $inst    = Get-BlockRange $txt '"WorkshopItemsInstalled"'
    $details = Get-DetailsMap $txt

    $installedCount = 0
    if ($inst) { $installedCount = ([regex]::Matches($inst.Body, '"(\d{6,})"\s*\{')).Count }

    $folderCount = 0
    if (Test-Path -LiteralPath $contentDir) {
        $folderCount = @(Get-ChildItem -LiteralPath $contentDir -Force -Directory -ErrorAction SilentlyContinue).Count
    }

    $broken = $false
    $reason = ''
    $rebuildable = $false

    if (-not $inst) {
        $broken = $true
        $reason = '缺少 WorkshopItemsInstalled 段'
    } elseif ($details.Count -gt 0 -and $installedCount -lt ($details.Count * 0.9)) {
        $broken = $true
        $reason = "已安装段只有 $installedCount 条，但详情段有 $($details.Count) 条"
    }

    if ($broken) {
        if ($details.Count -eq 0 -and $folderCount -gt 0) {
            $rebuildable = $false
            $reason = $reason + '；且详情段不可用，无法从本地重建'
        } elseif ($details.Count -ge ($installedCount * 0.9)) {
            # 关键保险：重建不会让条目变少才允许
            $rebuildable = $true
        } else {
            $rebuildable = $false
            $reason = $reason + '；详情段条目比已安装段还少，重建会丢数据，已拒绝'
        }
    }

    return [pscustomobject]@{
        Path           = $acfPath
        ContentDir     = $contentDir
        Text           = $txt
        InstalledCount = $installedCount
        DetailsCount   = $details.Count
        FolderCount    = $folderCount
        SizeOnDisk     = (Get-FieldValue $txt 'SizeOnDisk')
        NeedsDownload  = (Get-FieldValue $txt 'NeedsDownload')
        Broken         = $broken
        Reason         = $reason
        Rebuildable    = $rebuildable
        Inst           = $inst
        Details        = $details
    }
}

# ==================================================================
#  修复
# ==================================================================
function Repair-Acf($diag, [switch]$NoBackup) {
    $txt     = $diag.Text
    $details = $diag.Details
    $sizes   = Measure-Content $diag.ContentDir

    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('"WorkshopItemsInstalled"' + "`r`n`t{`r`n")
    $built = 0
    $totalBytes = [long]0
    foreach ($id in ($details.Keys | Sort-Object)) {
        if (-not $sizes.ContainsKey($id)) { continue }
        if ([string]::IsNullOrEmpty($details[$id].Manifest)) { continue }
        $sz = $sizes[$id]
        $totalBytes += $sz
        $built++
        [void]$sb.Append("`t`t`"$id`"`r`n`t`t{`r`n")
        [void]$sb.Append("`t`t`t`"size`"`t`t`"$sz`"`r`n")
        [void]$sb.Append("`t`t`t`"timeupdated`"`t`t`"$($details[$id].TimeUpdated)`"`r`n")
        [void]$sb.Append("`t`t`t`"manifest`"`t`t`"$($details[$id].Manifest)`"`r`n")
        [void]$sb.Append("`t`t}`r`n")
    }
    [void]$sb.Append("`t}")
    $newBlock = $sb.ToString()

    if ($built -eq 0) { return $null }
    # 硬性保险：不允许比原来更少
    if ($built -lt $diag.InstalledCount) {
        return [pscustomobject]@{ Refused = $true; Built = $built; Was = $diag.InstalledCount }
    }

    $orphan = @($sizes.Keys | Where-Object { -not $details.ContainsKey($_) })

    $backupPath = $null
    if (-not $NoBackup) {
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $dir = Split-Path -Parent $diag.Path
        $backupPath = Join-Path $dir ("appworkshop_backup_{0}.acf" -f $stamp)
        Copy-Item -LiteralPath $diag.Path -Destination $backupPath -Force
    }

    $inst = $diag.Inst
    $out = $txt.Substring(0, $inst.Start) + $newBlock + $txt.Substring($inst.Close + 1)
    $out = [regex]::Replace($out, '("SizeOnDisk"\s*")[\d]+(")',    '${1}' + $totalBytes + '${2}')
    $out = [regex]::Replace($out, '("NeedsDownload"\s*")[\d]+(")', '${1}0${2}')
    $out = [regex]::Replace($out, '("NeedsUpdate"\s*")[\d]+(")',   '${1}0${2}')

    [System.IO.File]::WriteAllText($diag.Path, $out, $script:Utf8NoBom)

    $v  = [System.IO.File]::ReadAllText($diag.Path, $script:Utf8NoBom)
    $vi = Get-BlockRange $v '"WorkshopItemsInstalled"'
    $vc = 0
    if ($vi) { $vc = ([regex]::Matches($vi.Body, '"(\d{6,})"\s*\{')).Count }

    return [pscustomobject]@{
        Refused    = $false
        Built      = $built
        TotalBytes = $totalBytes
        Orphan     = $orphan.Count
        Backup     = $backupPath
        Verified   = $vc
        NeedsDown  = (Get-FieldValue $v 'NeedsDownload')
        SizeNow    = (Get-FieldValue $v 'SizeOnDisk')
    }
}

# ==================================================================
#  主流程
# ==================================================================
Write-Title "Wallpaper Download Fix  v$script:Version"
if ($DryRun) { Write-Host '  mode: DryRun (analyze only)' -ForegroundColor Yellow }

# ---- 1 ----
Write-Step '1 / 4  检查 Steam 进程'
$procs = @(Get-Process -Name steam, steamwebhelper, steamservice -ErrorAction SilentlyContinue)
if ($procs.Count -gt 0) {
    if ($DryRun) {
        Write-Warn2 "Steam 正在运行（$($procs.Count) 个进程）—— DryRun 不写入，可以继续"
    } elseif ($Force) {
        Write-Warn2 "Steam 正在运行（$($procs.Count) 个进程）—— -Force 强制继续，Steam 可能覆盖写回"
    } else {
        Write-Err "Steam 正在运行（$($procs.Count) 个进程）"
        Write-Info '请右键任务栏托盘里的 Steam 图标 -> 退出（只关窗口不算退出）'
        Write-Info '然后重新运行。已中止，未修改任何文件。'
        exit 1
    }
} else {
    Write-Ok 'Steam 未运行'
}

# ---- 2 ----
Write-Step '2 / 4  探测 Steam 安装与库目录'
$roots = Find-SteamRoots $SteamRoot
if ($roots.Count -eq 0) {
    Write-Err '没找到 Steam 安装目录'
    Write-Info '用 -SteamRoot 手动指定，例如： -SteamRoot "D:\Steam"'
    exit 1
}

$acfSeen  = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$acfFiles = New-Object System.Collections.Generic.List[object]

foreach ($r in $roots) {
    Write-Ok "Steam: $r"
    foreach ($lib in (Get-LibraryPaths $r)) {
        $ws = Join-Path $lib 'steamapps\workshop'
        if (-not (Test-Path -LiteralPath $ws)) { continue }
        $found = @(Get-ChildItem -LiteralPath $ws -Force -File -Filter 'appworkshop_*.acf' -ErrorAction SilentlyContinue)
        if ($found.Count -eq 0) { continue }
        Write-Info ("库 {0} -> {1} 个工坊清单" -f $lib, $found.Count)
        foreach ($f in $found) {
            if ($f.Name -match 'backup') { continue }
            $m = [regex]::Match($f.Name, '^appworkshop_(\d+)\.acf$')
            if (-not $m.Success) { continue }
            $aid = [int]$m.Groups[1].Value
            if ($AppId -gt 0 -and $aid -ne $AppId) { continue }
            if (-not $acfSeen.Add($f.FullName)) { continue }
            $acfFiles.Add([pscustomobject]@{
                AppId      = $aid
                Acf        = $f.FullName
                ContentDir = Join-Path $ws "content\$aid"
            })
        }
    }
}

if ($acfFiles.Count -eq 0) {
    Write-Warn2 '没有找到可处理的工坊清单文件'
    if ($AppId -gt 0) { Write-Info "（已按 -AppId $AppId 过滤）" }
    exit 0
}
Write-Ok "共 $($acfFiles.Count) 个工坊清单待检查"

# ---- 3 ----
Write-Step '3 / 4  诊断'
$rows = New-Object System.Collections.Generic.List[object]
foreach ($item in $acfFiles) {
    try {
        $d = Test-AcfHealth $item.Acf $item.ContentDir
        $d | Add-Member -NotePropertyName AppId -NotePropertyValue $item.AppId -Force
        $rows.Add($d)

        $color = if ($d.Broken) { 'Red' } else { 'Green' }
        $tag   = if ($d.Broken) { '损坏' } else { '正常' }
        Write-Host ("    [{0}] appid {1}" -f $tag, $item.AppId) -ForegroundColor $color
        Write-Info ("已安装段 {0} 条 / 详情段 {1} 条 / 磁盘 {2} 个文件夹" -f `
                    $d.InstalledCount, $d.DetailsCount, $d.FolderCount)
        if ($d.SizeOnDisk) {
            Write-Info ("SizeOnDisk {0:N2} GB / NeedsDownload {1}" -f ([double]$d.SizeOnDisk / 1GB), $d.NeedsDownload)
        }
        if ($d.Broken) { Write-Warn2 ('原因：' + $d.Reason) }
    } catch {
        Write-Err ("读取失败 {0}: {1}" -f $item.Acf, $_.Exception.Message)
    }
}

$broken = @($rows | Where-Object { $_.Broken })
Write-Host ''
if ($broken.Count -eq 0) {
    Write-Ok '全部正常，无需修复'
    exit 0
}
Write-Warn2 ("发现 {0} 个损坏的清单" -f $broken.Count)

$rebuildable = @($broken | Where-Object { $_.Rebuildable })
$hopeless    = @($broken | Where-Object { -not $_.Rebuildable })

# ---- 4 ----
Write-Step '4 / 4  修复'

if ($DryRun) {
    foreach ($d in $rebuildable) {
        $willBuild = @($d.Details.Keys | Where-Object {
            Test-Path -LiteralPath (Join-Path $d.ContentDir $_)
        }).Count
        Write-Info ("appid {0}：将重建 {1} 条（原 {2} 条）" -f $d.AppId, $willBuild, $d.InstalledCount)
    }
    foreach ($d in $hopeless) {
        Write-Warn2 ("appid {0}：无法本地重建 —— {1}" -f $d.AppId, $d.Reason)
    }
    Write-Host ''
    Write-Host '  去掉 -DryRun 即可真正执行。' -ForegroundColor Yellow
    exit 0
}

$okCount = 0
$failCount = 0

foreach ($d in $rebuildable) {
    try {
        $r = Repair-Acf $d -NoBackup:$NoBackup
        if ($null -eq $r) {
            Write-Err ("appid {0}：没有可重建条目，跳过" -f $d.AppId)
            $failCount++
            continue
        }
        if ($r.Refused) {
            Write-Err ("appid {0}：重建后只有 {1} 条，少于原有 {2} 条 —— 已拒绝（会丢数据）" -f `
                       $d.AppId, $r.Built, $r.Was)
            $failCount++
            continue
        }
        Write-Ok ("appid {0} 修复完成：{1} 条，{2:N2} GB" -f $d.AppId, $r.Built, ($r.TotalBytes / 1GB))
        Write-Info ("校验：已安装段 {0} 条 / NeedsDownload {1} / SizeOnDisk {2:N2} GB" -f `
                    $r.Verified, $r.NeedsDown, ([double]$r.SizeNow / 1GB))
        if ($r.Orphan -gt 0) {
            Write-Info ("另有 {0} 个磁盘文件夹没有 manifest 记录，Steam 会重新下载它们" -f $r.Orphan)
        }
        if ($r.Backup) { Write-Info ('备份 -> ' + $r.Backup) }
        $okCount++
    } catch {
        Write-Err ("appid {0} 修复失败：{1}" -f $d.AppId, $_.Exception.Message)
        $failCount++
    }
}

foreach ($d in $hopeless) {
    Write-Err ("appid {0}：无法本地重建" -f $d.AppId)
    Write-Info ('原因：' + $d.Reason)
    Write-Info '处理办法：在 Steam 里退订不需要的工坊内容，再删除该 acf，重启 Steam 让它重建'
    $failCount++
}

Write-Title '完成'
Write-Host ("  修复成功 {0} 个，失败 {1} 个" -f $okCount, $failCount) -ForegroundColor $(if ($failCount -eq 0) { 'Green' } else { 'Yellow' })
if ($okCount -gt 0) {
    Write-Host ''
    Write-Host '  现在可以启动 Steam 了。' -ForegroundColor Cyan
    Write-Host '  它应该会认下全部已装内容，不再重复下载。' -ForegroundColor Cyan
}
Write-Host ''
```

### 4. `wallpaperdownloadfix.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wallpaper Download Fix - 修复 Steam 创意工坊清单损坏导致的重复下载。

跨平台版本（Windows / Linux / macOS）。

问题：Steam 反复把「已经下载好的」创意工坊内容当成缺失并重新下载，把磁盘塞满。
原因：appworkshop_<appid>.acf 的 "WorkshopItemsInstalled" 段被写坏
      （磁盘写满时写入中断），Steam 以为只装了极少数内容。

修复：同一文件里的 "WorkshopItemDetails" 段通常仍完好，保存着每个条目的
      manifest ID。用它 + 磁盘上文件夹的实际大小，重建损坏的段。

用法：
    python wallpaperdownloadfix.py --dry-run      # 只诊断
    python wallpaperdownloadfix.py                # 修复
    python wallpaperdownloadfix.py --appid 431960 # 只处理某个 appid
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

VERSION = "1.0.0"

# ---------------------------------------------------------------- 输出


def _enable_ansi() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        k = ctypes.windll.kernel32
        k.SetConsoleMode(k.GetStdHandle(-11), 7)
    except Exception:
        pass


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    return True


_COLOR = _supports_color()


def c(text: str, code: str) -> str:
    if not _COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def title(t: str) -> None:
    print()
    print(c("=" * 64, "90"))
    print("  " + c(t, "96"))
    print(c("=" * 64, "90"))


def step(t: str) -> None:
    print()
    print("  " + c("> " + t, "96"))
    print(c("  " + "-" * 60, "90"))


def ok(t: str) -> None:
    print("    " + c("[+] ", "92") + t)


def warn(t: str) -> None:
    print("    " + c("[!] ", "93") + t)


def err(t: str) -> None:
    print("    " + c("[x] ", "91") + t)


def info(t: str) -> None:
    print("        " + c(t, "90"))


def human(n: int) -> str:
    gb = n / (1024 ** 3)
    if gb >= 1:
        return f"{gb:.2f} GB"
    return f"{n / (1024 ** 2):.2f} MB"


# ---------------------------------------------------------------- VDF


def unescape_vdf(s: str) -> str:
    return s.replace("\\\\", "\\").replace('\\"', '"')


def library_paths(steam_root: Path) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []

    def add(p: Path) -> None:
        try:
            full = str(p.resolve())
        except Exception:
            return
        key = full.lower()
        if key not in seen:
            seen.add(key)
            out.append(Path(full))

    if (steam_root / "steamapps").is_dir():
        add(steam_root)

    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    if vdf.is_file():
        try:
            t = vdf.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'"path"\s+"((?:[^"\\]|\\.)*)"', t):
                p = Path(unescape_vdf(m.group(1)))
                if p.is_dir():
                    add(p)
        except Exception:
            pass

    if not out:
        out.append(steam_root)
    return out


def find_steam_roots(explicit: str | None) -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        if not (p / "steamapps").is_dir():
            return
        try:
            full = str(p.resolve())
        except Exception:
            return
        if full.lower() not in seen:
            seen.add(full.lower())
            roots.append(Path(full))

    if explicit:
        add(Path(explicit))
        return roots

    cands: list[Path] = []

    if os.name == "nt":
        try:
            import winreg

            for hive, key in (
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
            ):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        for name in ("SteamPath", "InstallPath"):
                            try:
                                v, _ = winreg.QueryValueEx(k, name)
                                if v:
                                    cands.append(Path(v))
                            except OSError:
                                pass
                except OSError:
                    pass
        except Exception:
            pass
        for d in (
            r"C:\Program Files (x86)\Steam",
            r"C:\Program Files\Steam",
        ):
            cands.append(Path(d))
    else:
        home = Path.home()
        cands += [
            home / ".steam" / "steam",
            home / ".local" / "share" / "Steam",
            home / "Library" / "Application Support" / "Steam",
        ]

    for p in cands:
        add(p)
    return roots


# ---------------------------------------------------------------- ACF


def block_range(text: str, key: str):
    """返回 (start, close_index, body) 或 None；花括号配平。"""
    ki = text.find(key)
    if ki < 0:
        return None
    ob = text.find("{", ki)
    if ob < 0:
        return None
    depth = 0
    for p in range(ob, len(text)):
        ch = text[p]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return ki, p, text[ki : p + 1]
    return None


def field_value(text: str, name: str) -> str | None:
    m = re.search(r'"' + re.escape(name) + r'"\s+"([^"]*)"', text)
    return m.group(1) if m else None


def item_blocks(body: str) -> dict[str, str]:
    """把一段内容按 'id { ... }' 切开，字段顺序无关。"""
    out: dict[str, str] = {}
    for m in re.finditer(r'"(\d{6,})"\s*\{', body):
        ident = m.group(1)
        if ident in out:
            continue
        ob = body.find("{", m.start())
        if ob < 0:
            continue
        depth = 0
        cb = -1
        for p in range(ob, len(body)):
            ch = body[p]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    cb = p
                    break
        if cb < 0:
            continue
        out[ident] = body[ob : cb + 1]
    return out


def details_map(text: str) -> dict[str, dict[str, str]]:
    """解析 WorkshopItemDetails: id -> {manifest, timeupdated}"""
    out: dict[str, dict[str, str]] = {}
    blk = block_range(text, '"WorkshopItemDetails"')
    if not blk:
        return out
    for ident, inner in item_blocks(blk[2]).items():
        # manifest 可能是 -1（老条目），所以允许负号
        mf = re.search(r'"manifest"\s+"(-?\d+)"', inner)
        if not mf:
            continue
        tu = re.search(r'"timeupdated"\s+"(\d+)"', inner)
        out[ident] = {
            "manifest": mf.group(1),
            "timeupdated": tu.group(1) if tu else "0",
        }
    return out


def measure_content(content_dir: Path) -> dict[str, int]:
    sizes: dict[str, int] = {}
    if not content_dir.is_dir():
        return sizes
    for d in content_dir.iterdir():
        if not d.is_dir():
            continue
        total = 0
        try:
            for root, _dirs, files in os.walk(d):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
        except Exception:
            total = 0
        sizes[d.name] = total
    return sizes


# ---------------------------------------------------------------- 诊断


def diagnose(acf_path: Path, content_dir: Path) -> dict:
    # 按字节读取再解码，避免通用换行把 \r\n 归一成 \n
    text = acf_path.read_bytes().decode("utf-8", errors="replace")

    inst = block_range(text, '"WorkshopItemsInstalled"')
    details = details_map(text)

    installed_count = len(re.findall(r'"(\d{6,})"\s*\{', inst[2])) if inst else 0
    folder_count = (
        sum(1 for d in content_dir.iterdir() if d.is_dir()) if content_dir.is_dir() else 0
    )

    broken = False
    reason = ""
    rebuildable = False

    if not inst:
        broken = True
        reason = "缺少 WorkshopItemsInstalled 段"
    elif details and installed_count < len(details) * 0.9:
        broken = True
        reason = f"已安装段只有 {installed_count} 条，但详情段有 {len(details)} 条"

    if broken:
        if not details and folder_count > 0:
            reason += "；且详情段不可用，无法从本地重建"
        elif len(details) >= installed_count * 0.9:
            rebuildable = True
        else:
            reason += "；详情段条目比已安装段还少，重建会丢数据，已拒绝"

    size_on_disk = field_value(text, "SizeOnDisk")
    return {
        "path": acf_path,
        "content_dir": content_dir,
        "text": text,
        "installed": installed_count,
        "details": details,
        "details_count": len(details),
        "folders": folder_count,
        "size_on_disk": int(size_on_disk) if size_on_disk and size_on_disk.isdigit() else 0,
        "needs_download": field_value(text, "NeedsDownload"),
        "broken": broken,
        "reason": reason,
        "rebuildable": rebuildable,
        "inst_block": inst,
    }


# ---------------------------------------------------------------- 修复


def repair(d: dict, backup: bool = True):
    text = d["text"]
    details = d["details"]
    sizes = measure_content(d["content_dir"])

    lines = ['"WorkshopItemsInstalled"', "\t{"]
    built = 0
    total_bytes = 0
    for ident in sorted(details):
        if ident not in sizes:
            continue
        mf = details[ident]["manifest"]
        if mf == "":
            continue
        sz = sizes[ident]
        total_bytes += sz
        built += 1
        lines += [
            f'\t\t"{ident}"',
            "\t\t{",
            f'\t\t\t"size"\t\t"{sz}"',
            f'\t\t\t"timeupdated"\t\t"{details[ident]["timeupdated"]}"',
            f'\t\t\t"manifest"\t\t"{mf}"',
            "\t\t}",
        ]
    lines.append("\t}")
    new_block = "\r\n".join(lines)

    if built == 0:
        return None
    if built < d["installed"]:
        return {"refused": True, "built": built, "was": d["installed"]}

    orphans = [k for k in sizes if k not in details]

    backup_path = None
    if backup:
        from datetime import datetime

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = d["path"].parent / f"appworkshop_backup_{stamp}.acf"
        backup_path.write_bytes(d["path"].read_bytes())

    start, close, _body = d["inst_block"]
    out = text[:start] + new_block + text[close + 1 :]
    out = re.sub(r'("SizeOnDisk"\s*")[\d]+(")', rf"\g<1>{total_bytes}\g<2>", out)
    out = re.sub(r'("NeedsDownload"\s*")[\d]+(")', r"\g<1>0\g<2>", out)
    out = re.sub(r'("NeedsUpdate"\s*")[\d]+(")', r"\g<1>0\g<2>", out)

    d["path"].write_bytes(out.encode("utf-8"))

    v = d["path"].read_bytes().decode("utf-8", errors="replace")
    vi = block_range(v, '"WorkshopItemsInstalled"')
    verified = len(re.findall(r'"(\d{6,})"\s*\{', vi[2])) if vi else 0

    return {
        "refused": False,
        "built": built,
        "total_bytes": total_bytes,
        "orphans": len(orphans),
        "backup": backup_path,
        "verified": verified,
        "needs_download": field_value(v, "NeedsDownload"),
    }


# ---------------------------------------------------------------- main


def steam_running() -> int:
    """返回 Steam 相关进程数（尽力而为）。"""
    n = 0
    try:
        if os.name == "nt":
            import subprocess

            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq steam.exe", "/NH"],
                capture_output=True,
                text=True,
                errors="replace",
            ).stdout
            n += out.lower().count("steam.exe")
        else:
            for pid in os.listdir("/proc"):
                if not pid.isdigit():
                    continue
                try:
                    with open(f"/proc/{pid}/comm") as f:
                        if "steam" in f.read().lower():
                            n += 1
                except OSError:
                    pass
    except Exception:
        pass
    return n


def main() -> int:
    ap = argparse.ArgumentParser(
        description="修复 Steam 创意工坊清单损坏导致的重复下载。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--appid", type=int, default=0, help="只处理指定 appid（默认全部）")
    ap.add_argument("--steam-root", default=None, help="手动指定 Steam 安装目录")
    ap.add_argument("--dry-run", action="store_true", help="只诊断，不修改任何文件")
    ap.add_argument("--force", action="store_true", help="即使 Steam 正在运行也继续")
    ap.add_argument("--no-backup", action="store_true", help="不生成备份")
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = ap.parse_args()

    title(f"Wallpaper Download Fix  v{VERSION}")
    if args.dry_run:
        print("  " + c("mode: DryRun (analyze only)", "93"))

    # 1
    step("1 / 4  检查 Steam 进程")
    nproc = steam_running()
    if nproc > 0:
        if args.dry_run:
            warn(f"Steam 正在运行（{nproc} 个进程）—— DryRun 不写入，可以继续")
        elif args.force:
            warn(f"Steam 正在运行 —— --force 强制继续，Steam 可能覆盖写回")
        else:
            err(f"Steam 正在运行（{nproc} 个进程）")
            info("请完全退出 Steam（含托盘图标 / 后台进程），然后重新运行。")
            info("已中止，未修改任何文件。")
            return 1
    else:
        ok("Steam 未运行")

    # 2
    step("2 / 4  探测 Steam 安装与库目录")
    roots = find_steam_roots(args.steam_root)
    if not roots:
        err("没找到 Steam 安装目录")
        info('用 --steam-root 手动指定，例如： --steam-root "D:\\Steam"')
        return 1

    acf_files: list[tuple[int, Path, Path]] = []
    seen: set[str] = set()

    for r in roots:
        ok(f"Steam: {r}")
        for lib in library_paths(r):
            ws = lib / "steamapps" / "workshop"
            if not ws.is_dir():
                continue
            found = sorted(ws.glob("appworkshop_*.acf"))
            if not found:
                continue
            info(f"库 {lib} -> {len(found)} 个工坊清单")
            for f in found:
                if "backup" in f.name:
                    continue
                m = re.match(r"^appworkshop_(\d+)\.acf$", f.name)
                if not m:
                    continue
                aid = int(m.group(1))
                if args.appid and aid != args.appid:
                    continue
                key = str(f).lower()
                if key in seen:
                    continue
                seen.add(key)
                acf_files.append((aid, f, ws / "content" / str(aid)))

    if not acf_files:
        warn("没有找到可处理的工坊清单文件")
        if args.appid:
            info(f"（已按 --appid {args.appid} 过滤）")
        return 0
    ok(f"共 {len(acf_files)} 个工坊清单待检查")

    # 3
    step("3 / 4  诊断")
    rows = []
    for aid, acf, content in acf_files:
        try:
            d = diagnose(acf, content)
            d["appid"] = aid
            rows.append(d)
            tag = c("损坏", "91") if d["broken"] else c("正常", "92")
            print(f"    [{tag}] appid {aid}")
            info(
                f"已安装段 {d['installed']} 条 / 详情段 {d['details_count']} 条 "
                f"/ 磁盘 {d['folders']} 个文件夹"
            )
            if d["size_on_disk"]:
                info(
                    f"SizeOnDisk {human(d['size_on_disk'])} "
                    f"/ NeedsDownload {d['needs_download']}"
                )
            if d["broken"]:
                warn("原因：" + d["reason"])
        except Exception as exc:  # noqa: BLE001
            err(f"读取失败 {acf}: {exc}")

    broken = [r for r in rows if r["broken"]]
    print()
    if not broken:
        ok("全部正常，无需修复")
        return 0
    warn(f"发现 {len(broken)} 个损坏的清单")

    rebuildable = [r for r in broken if r["rebuildable"]]
    hopeless = [r for r in broken if not r["rebuildable"]]

    # 4
    step("4 / 4  修复")
    if args.dry_run:
        for d in rebuildable:
            will = sum(
                1 for k in d["details"] if (d["content_dir"] / k).is_dir()
            )
            info(f"appid {d['appid']}：将重建 {will} 条（原 {d['installed']} 条）")
        for d in hopeless:
            warn(f"appid {d['appid']}：无法本地重建 —— {d['reason']}")
        print()
        print("  " + c("去掉 --dry-run 即可真正执行。", "93"))
        return 0

    okc = 0
    failc = 0
    for d in rebuildable:
        try:
            r = repair(d, backup=not args.no_backup)
            if r is None:
                err(f"appid {d['appid']}：没有可重建条目，跳过")
                failc += 1
                continue
            if r["refused"]:
                err(
                    f"appid {d['appid']}：重建后只有 {r['built']} 条，少于原有 "
                    f"{r['was']} 条 —— 已拒绝（会丢数据）"
                )
                failc += 1
                continue
            ok(
                f"appid {d['appid']} 修复完成：{r['built']} 条，"
                f"{human(r['total_bytes'])}"
            )
            info(
                f"校验：已安装段 {r['verified']} 条 "
                f"/ NeedsDownload {r['needs_download']}"
            )
            if r["orphans"]:
                info(f"另有 {r['orphans']} 个磁盘文件夹没有 manifest 记录，Steam 会重新下载")
            if r["backup"]:
                info(f"备份 -> {r['backup']}")
            okc += 1
        except Exception as exc:  # noqa: BLE001
            err(f"appid {d['appid']} 修复失败：{exc}")
            failc += 1

    for d in hopeless:
        err(f"appid {d['appid']}：无法本地重建")
        info("原因：" + d["reason"])
        info("处理办法：在 Steam 里退订不需要的工坊内容，再删除该 acf，重启 Steam 让它重建")
        failc += 1

    title("完成")
    print(f"  修复成功 {okc} 个，失败 {failc} 个")
    if okc:
        print()
        print("  现在可以启动 Steam 了。它应该会认下全部已装内容，不再重复下载。")
    print()
    return 0 if failc == 0 else 2


if __name__ == "__main__":
    _enable_ansi()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
```

### 5. `run.cmd`

```bat
@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Wallpaper Download Fix

echo.
echo   ==========================================================
echo     Wallpaper Download Fix
echo     Repair a corrupted Steam Workshop manifest
echo   ==========================================================
echo.
echo   Steam MUST be fully quit before running this
echo   (right-click the tray icon - Exit).
echo.
echo   Running in DRY-RUN mode first (nothing will be changed)...
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0wallpaperdownloadfix.ps1" -DryRun

echo.
echo   ----------------------------------------------------------
echo   Dry run finished. Apply the repair now? [Y/N]
echo   ----------------------------------------------------------
set /p ANSWER=  ^> 
if /i not "%ANSWER%"=="Y" (
    echo.
    echo   Cancelled. Nothing was changed.
    goto :end
)

echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0wallpaperdownloadfix.ps1"

:end
echo.
echo   Press any key to close...
pause >nul
```

### 6. `LICENSE`

```text
MIT License

Copyright (c) 2026 wallpaperdownloadfix contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### 7. `.gitignore`

```gitignore
# --- Steam workshop manifests (never commit these) ---
appworkshop_*.acf
appworkshop_backup_*.acf
*.acf
!*.example.acf

# --- Python ---
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
build/
dist/

# --- Editors / OS ---
.vs/
.vscode/
.idea/
*.swp
.DS_Store
Thumbs.db
desktop.ini

# --- Local test output ---
*.log
```

### 8. `.gitattributes`

```gitattributes
# Normalize line endings per file type; keep the PowerShell script CRLF
# (its UTF-8 BOM lives in the content and is preserved either way).
* text=auto

*.ps1  text eol=crlf
*.cmd  text eol=crlf
*.py   text eol=lf
*.md   text eol=lf
LICENSE text eol=lf
*.yml  text eol=lf
*.yaml text eol=lf
```

### 9. `publish.ps1`

```powershell
# 把本地仓库发布到 GitHub（仓库名 wallpaperdownloadfix）
#
# 用法：
#   .\publish.ps1              # 公开仓库
#   .\publish.ps1 -Private     # 私有仓库
#   .\publish.ps1 -Name myrepo # 换个仓库名
#
# 会自动用登录的 GitHub 账号配置 git 身份和 noreply 邮箱，
# 并把已有提交的作者改写为你自己。

param(
    [string]$Name = 'wallpaperdownloadfix',
    [switch]$Private
)

$ErrorActionPreference = 'Stop'

# 新装的 gh 需要刷新 PATH
$env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
            [System.Environment]::GetEnvironmentVariable('Path', 'User')

function Write-Ok([string]$t)   { Write-Host "  [+] $t" -ForegroundColor Green }
function Write-Err([string]$t)  { Write-Host "  [x] $t" -ForegroundColor Red }
function Write-Warn([string]$t) { Write-Host "  [!] $t" -ForegroundColor Yellow }
function Write-Dim([string]$t)  { Write-Host "      $t" -ForegroundColor Gray }

$repo = 'E:\wallpaperdownloadfix'
if (-not (Test-Path (Join-Path $repo '.git'))) {
    Write-Err "找不到 git 仓库：$repo"
    exit 1
}
Set-Location $repo

# ---------- 1. gh 可用性 ----------
$gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $gh) {
    Write-Err 'gh CLI 未安装。安装： winget install --id GitHub.cli'
    exit 1
}

# ---------- 2. 登录状态 ----------
gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Warn 'gh 尚未登录 GitHub'
    Write-Dim '运行下面这条命令完成授权（会打开浏览器）：'
    Write-Host '      gh auth login --hostname github.com --git-protocol https --web' -ForegroundColor Cyan
    exit 1
}

$login = (gh api user --jq '.login' 2>$null)
$uid   = (gh api user --jq '.id' 2>$null)
$dname = (gh api user --jq '.name // .login' 2>$null)
if (-not $login) { Write-Err '拿不到 GitHub 账号信息'; exit 1 }
Write-Ok "已登录：$login (id $uid)"

# ---------- 3. 用 GitHub 身份配置 git ----------
$curName  = git config user.name
$curEmail = git config user.email
if ($curName -eq 'Your Name' -or $curEmail -eq 'you@example.com' -or -not $curName -or -not $curEmail) {
    $email = if ($dname) { $dname } else { $login }
    git config user.name  $login
    git config user.email "$uid+$login@users.noreply.github.com"
    Write-Ok "已配置 git 身份：$login <$uid+$login@users.noreply.github.com>"
    # 把已有提交的作者改写为本人
    git rev-parse --verify HEAD *> $null
    if ($LASTEXITCODE -eq 0) {
        git commit --amend --reset-author --no-edit *> $null
        Write-Ok '已把初始提交的作者改写为你的 GitHub 身份'
    }
} else {
    Write-Ok "git 身份：$curName <$curEmail>"
}

# ---------- 4. 必须有提交 ----------
git rev-parse --verify HEAD *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Err '仓库里还没有任何提交'
    exit 1
}

# ---------- 5. 创建远程仓库并推送 ----------
$remoteExists = $false
gh repo view "$login/$Name" *> $null
if ($LASTEXITCODE -eq 0) { $remoteExists = $true }

if ($remoteExists) {
    Write-Warn "远程仓库 $login/$Name 已存在，只做推送"
    $origin = git remote get-url origin 2>$null
    if (-not $origin) { git remote add origin "https://github.com/$login/$Name.git" }
    git push -u origin main
} else {
    Write-Ok "创建仓库 $login/$Name ..."
    $vis = if ($Private) { '--private' } else { '--public' }
    gh repo create $Name $vis --source=. --remote=origin `
        --description 'Repair a corrupted Steam Workshop manifest so Steam stops re-downloading content you already have.' `
        --push
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ''
    Write-Ok "发布完成 -> https://github.com/$login/$Name"
} else {
    Write-Err '推送失败，检查上面的报错'
    exit 1
}
```

---

## 四、发布步骤

```bash
git init -b main
git add -A
git commit -m "feat: initial release - repair corrupted Steam workshop manifests"
git remote add origin https://github.com/<你的用户名>/wallpaperdownloadfix.git
git push -u origin main
```

或者用 gh CLI 一步到位（会自动建仓并推送）：

```bash
gh repo create wallpaperdownloadfix --public --source=. --remote=origin \
  --description "Repair a corrupted Steam Workshop manifest so Steam stops re-downloading content you already have." \
  --push
```

---

## 五、关键注意事项

1. **`wallpaperdownloadfix.ps1` 必须保存为 UTF-8 with BOM。**
   PowerShell 5.1 读取无 BOM 的 UTF-8 文件时会按 GBK 解释，中文注释里的字节可能被误读成反引号 `` ` ``，
   造成「行继续」——变量不赋值、行为诡异。这是本项目踩过的坑。

2. **`.gitattributes` 不要删。** 它保证 `.ps1`/`.cmd` 检出时为 CRLF、`.py`/`.md` 为 LF。

3. **代码逻辑上的三个关键点**（改代码时别踩）：

   - `libraryfolders.vdf` 里的路径是转义过的（`E:\\steam`），解析后必须还原成 `E:\steam`，
     并且去重要**大小写不敏感**，否则同一个库会被扫两遍。
   - `"manifest"` 的值可能是 `-1`（老工坊条目），正则必须写成 `(-?\d+)`，
     只写 `(\d+)` 会漏掉这些条目 —— 曾导致「已安装 131 条 / 详情 4 条」的误判，
     如果照着去修会把 131 条削成 4 条。
   - **重建后条目数少于原有的一律拒绝执行。** 这是防止数据损坏的最后一道保险。

4. **Python 版读文件要用 `read_bytes().decode()`，不能用 `read_text()`。**
   后者会做通用换行转换，把 `\r\n` 归一成 `\n`，写回时整个文件的换行符都被改掉。

---

## 六、自测方法（无需真的损坏文件）

```powershell
# 只诊断，不改任何文件
.\wallpaperdownloadfix.ps1 -DryRun
```

```bash
python wallpaperdownloadfix.py --dry-run
```

正常输出形如：

```
[正常] appid 431960
    已安装段 2078 条 / 详情段 2078 条 / 磁盘 2083 个文件夹
    SizeOnDisk 118.26 GB / NeedsDownload 0
```

