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
