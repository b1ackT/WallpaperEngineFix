# 把本地仓库发布到 GitHub（仓库名 WallpaperEngineFix）
#
# 用法：
#   .\publish.ps1              # 公开仓库
#   .\publish.ps1 -Private     # 私有仓库
#   .\publish.ps1 -Name myrepo # 换个仓库名
#
# 会自动用登录的 GitHub 账号配置 git 身份和 noreply 邮箱，
# 并把已有提交的作者改写为你自己。

param(
    [string]$Name = 'WallpaperEngineFix',
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
