"""Conservative repair path shared by the desktop UI and its tests."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import wallpaperdownloadfix as core


def steam_running() -> bool:
    # Fail closed: a process-query failure must never authorize a write.
    result = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
        text=True, errors="replace", check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return bool(re.search(r'"(?:steam|steamwebhelper|steamservice)\.exe"', result.stdout, re.I))


def inspect(acf: Path, content: Path, appid: int) -> dict:
    raw = acf.read_bytes()
    text = raw.decode("utf-8-sig", errors="strict")
    block = core.block_range(text, '"WorkshopItemsInstalled"')
    details = core.details_map(text)
    installed = core.item_blocks(block[2]) if block else {}
    folders = {p.name for p in content.iterdir() if p.is_dir()} if content.is_dir() else set()
    candidates = sorted(
        ident for ident in details.keys() & folders - installed.keys()
        if details[ident]["manifest"].isdigit() and int(details[ident]["manifest"]) > 0
    )
    if not block:
        status, reason = "无法修复", "安装段缺失或括号不完整；请保留原文件进行人工排查。"
        candidates = []
    elif not details:
        status, reason = "无法判断", "没有可用的条目详情。"
        candidates = []
    elif candidates:
        status, reason = "可补全记录", f"{len(candidates)} 个本地目录有详情记录，但没有安装记录。请确认曾完整下载。"
    elif details.keys() - installed.keys():
        status, reason = "无需补全", "详情比安装记录多，但没有可补全的本地条目，可能尚未下载。"
    else:
        status, reason = "无需补全", "未发现可补全的安装记录。"
    return dict(path=acf, content=content, appid=appid, raw=raw, text=text,
                digest=hashlib.sha256(raw).hexdigest(), block=block,
                installed=installed, details=details, folders=folders,
                candidates=candidates, status=status, reason=reason)


def scan(root: str = "", appid: int = 0, log=lambda message: None) -> list[dict]:
    roots = core.find_steam_roots(root or None)
    if not roots:
        raise ValueError("未找到 Steam。请手动选择包含 steamapps 的 Steam 安装目录或库目录。")
    rows, seen = [], set()
    for steam in roots:
        log(f"Steam：{steam}")
        for library in core.library_paths(steam):
            log(f"检查库：{library}")
            ws = library / "steamapps" / "workshop"
            for acf in sorted(ws.glob("appworkshop_*.acf")):
                match = re.fullmatch(r"appworkshop_(\d+)\.acf", acf.name)
                if not match or str(acf.resolve()).lower() in seen:
                    continue
                aid = int(match[1])
                if appid and aid != appid:
                    continue
                seen.add(str(acf.resolve()).lower())
                try:
                    row = inspect(acf, ws / "content" / str(aid), aid)
                    rows.append(row)
                    log(f"{aid} · {row['status']}：{row['reason']}\n  {acf}")
                except Exception as exc:
                    log(f"读取失败：{acf} — {exc}")
    return rows


def repair(row: dict, process_check=steam_running) -> dict:
    if process_check():
        raise RuntimeError("请完全退出 Steam（包括托盘和后台进程），再执行修复。")
    acf = row["path"]
    current = inspect(acf, row["content"], row["appid"])
    if current["digest"] != row["digest"]:
        raise RuntimeError("清单在扫描后发生变化，请重新扫描。")
    if not current["candidates"] or not current["block"]:
        raise ValueError("没有可安全补全的安装记录。")
    sizes = core.measure_content(current["content"])
    installed = dict(current["installed"])
    for ident in current["candidates"]:
        size = sizes.get(ident, 0)
        if size <= 0:
            raise ValueError(f"条目 {ident} 目录为空或无法读取，未修改清单。")
        detail = current["details"][ident]
        installed[ident] = ('{\r\n'
            f'\t\t\t"size"\t\t"{size}"\r\n'
            f'\t\t\t"timeupdated"\t\t"{detail["timeupdated"]}"\r\n'
            f'\t\t\t"manifest"\t\t"{detail["manifest"]}"\r\n\t\t' + '}')
    block = '"WorkshopItemsInstalled"\r\n\t{\r\n' + ''.join(
        f'\t\t"{ident}"\r\n\t\t{body}\r\n' for ident, body in installed.items()
    ) + '\t}'
    start, end, _ = current["block"]
    text = current["text"][:start] + block + current["text"][end + 1:]
    # Preserve pending download/update flags: folder existence is not integrity verification.
    total = sum(int(core.field_value(body, "size") or 0) for body in installed.values())
    text = re.sub(r'("SizeOnDisk"\s*")\d+(")', rf'\g<1>{total}\g<2>', text)
    parsed = core.item_blocks(core.block_range(text, '"WorkshopItemsInstalled"')[2])
    if parsed != installed:
        raise RuntimeError("重建结果校验失败，未写入。")
    backup = acf.with_name(f"appworkshop_backup_{row['appid']}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.acf")
    with backup.open("xb") as stream:
        stream.write(current["raw"])
    raw = text.encode("utf-8")
    if current["raw"].startswith(b"\xef\xbb\xbf"):
        raw = b"\xef\xbb\xbf" + raw
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=acf.parent, prefix=".wefix-", delete=False) as stream:
            temp = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if process_check() or acf.read_bytes() != current["raw"]:
            raise RuntimeError("Steam 已启动或清单发生变化，已取消写入。")
        os.replace(temp, acf)
        if acf.read_bytes() != raw:
            raise RuntimeError(f"写入后校验失败。原始备份：{backup}")
    finally:
        if temp and temp.exists():
            temp.unlink()
    return dict(added=len(current["candidates"]), backup=backup)
