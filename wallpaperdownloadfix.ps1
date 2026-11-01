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
