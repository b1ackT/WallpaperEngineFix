# WallpaperEngineFix

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
