# WallpaperEngineFix

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
