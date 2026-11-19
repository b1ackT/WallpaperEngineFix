# WallpaperEngineFix 桌面版 1.1.0

Windows x64 独立程序：`dist/WallpaperEngineFix.exe`，无需安装 Python。

1. 打开 EXE，选择游戏。默认只检查 Wallpaper Engine；也可选择全部、GMod、L4D2 或自定义 AppID。
2. Steam 目录留空自动探测；也可选择包含 `steamapps` 的库目录。
3. 点击「只读扫描」，选择一条结果查看详情。
4. 对于「可补全记录」的清单，确认相关内容曾完整下载、完全退出 Steam 后点击「修复选中项」。
5. 程序先保存原始备份，再原子替换清单并读回校验。备份路径显示在日志中。

详情数大于安装数不一定是损坏。GUI 只补全同时有本地目录、有效正数 manifest 和详情的缺失记录，保留现有安装条目与下载/更新标记。目录存在不等于文件完整，无法保证避免所有重复下载，也不修复游戏内验证、模组冲突或损坏的实际内容。缺少完整安装段的清单会拒绝自动修复。

GUI 使用独立的保守补全流程 `workshop_service.py`；原 PowerShell / CLI 修复流程保持原有行为。建议使用 GUI。

## 备份恢复

完全退出 Steam，将日志所示的 `appworkshop_backup_<appid>_<时间>_<随机值>.acf` 复制为同目录的 `appworkshop_<appid>.acf`，覆盖修复后的清单。保留备份以便再次排查。

## 源码与构建

源码启动：`python wallpaper_gui.py`（Windows，Python 3.10+，含 Tkinter）。

构建：`powershell -ExecutionPolicy Bypass -File build_gui.ps1`。脚本创建 `.venv`、安装固定版本 PyInstaller、运行回归测试，并构建无控制台单文件 EXE。产物未做代码签名。

测试：`python -m unittest discover -s tests -v`。测试仅使用临时模拟 Steam 文件，不修改真实库。
