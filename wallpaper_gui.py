"""Windows desktop frontend. Run with python wallpaper_gui.py."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import workshop_service as service

APP_VERSION = "1.1.0"
GAMES = {"全部创意工坊": 0, "Wallpaper Engine": 431960, "Garry's Mod": 4000, "Left 4 Dead 2": 550}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"WallpaperEngineFix · 工坊清单修复  {APP_VERSION}")
        self.geometry("1080x760")
        self.minsize(920, 660)
        self.configure(bg="#f3f6fa")
        self.events = queue.Queue()
        self.rows = {}
        self.busy = False
        self.root_path = tk.StringVar()
        self.game = tk.StringVar(value="Wallpaper Engine")
        self.custom_id = tk.StringVar()
        self.status = tk.StringVar(value="准备就绪 · 扫描不会修改文件")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f3f6fa")
        style.configure("TLabel", background="#f3f6fa", foreground="#24334a", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 24, "bold"))
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(14, 9))
        style.configure("Accent.TButton", background="#2563eb", foreground="white")
        style.map("Accent.TButton", background=[("active", "#1d4ed8"), ("disabled", "#aab9d1")])
        style.configure("Treeview", rowheight=34, font=("Microsoft YaHei UI", 10), background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"), padding=8)
        self._layout()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.poll)

    def _layout(self):
        main = ttk.Frame(self, padding=26)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="找回工坊的安装记录", style="Title.TLabel").pack(anchor="w")
        ttk.Label(main, text="WallpaperEngineFix  /  先诊断，再补全。保留你的壁纸与模组文件。", padding=(0, 8, 0, 18)).pack(anchor="w")
        form = ttk.Frame(main)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Steam / 库目录").grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.path_entry = ttk.Entry(form, textvariable=self.root_path)
        self.path_entry.grid(row=0, column=1, sticky="ew")
        self.browse = ttk.Button(form, text="选择目录", command=self.choose)
        self.browse.grid(row=0, column=2, padx=(10, 0))
        ttk.Label(form, text="留空自动检测；手动选择的目录需包含 steamapps。", foreground="#68768a").grid(row=1, column=1, sticky="w", pady=(4, 12))
        ttk.Label(form, text="扫描范围").grid(row=2, column=0, sticky="w")
        filters = ttk.Frame(form)
        filters.grid(row=2, column=1, columnspan=2, sticky="ew")
        self.game_box = ttk.Combobox(filters, textvariable=self.game, values=list(GAMES) + ["自定义 AppID"], state="readonly", width=25)
        self.game_box.pack(side="left")
        self.game_box.bind("<<ComboboxSelected>>", self.filter_changed)
        self.id_entry = ttk.Entry(filters, textvariable=self.custom_id, width=12, state="disabled")
        self.id_entry.pack(side="left", padx=10)
        ttk.Label(filters, text="仅检查 Steam 清单，不修复游戏内验证。", foreground="#68768a").pack(side="left")
        actions = ttk.Frame(main, padding=(0, 18, 0, 14))
        actions.pack(fill="x")
        self.scan_button = ttk.Button(actions, text="①  只读扫描", style="Accent.TButton", command=self.scan)
        self.scan_button.pack(side="left")
        self.repair_button = ttk.Button(actions, text="②  修复选中项", command=self.repair, state="disabled")
        self.repair_button.pack(side="left", padx=10)
        ttk.Button(actions, text="导出日志", command=self.export).pack(side="right")
        table_frame = ttk.Frame(main)
        table_frame.pack(fill="both", expand=True)
        columns = ("game", "status", "installed", "details", "folders", "add")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse", height=6)
        for col, label, width in zip(columns, ("应用 / AppID", "诊断结果", "已安装", "详情记录", "本地目录", "可补全"), (250, 160, 100, 100, 100, 100)):
            self.table.heading(col, text=label)
            self.table.column(col, width=width, minwidth=65, anchor="w" if col in ("game", "status") else "center")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.table.bind("<<TreeviewSelect>>", self.selection_changed)
        self.detail = ttk.Label(main, text="选择扫描结果查看诊断与路径。", wraplength=970, foreground="#68768a", padding=(0, 10))
        self.detail.pack(fill="x")
        ttk.Label(main, text="运行日志").pack(anchor="w")
        log_frame = ttk.Frame(main)
        log_frame.pack(fill="both", pady=(6, 10))
        self.log_text = tk.Text(log_frame, height=7, wrap="word", bg="#152238", fg="#dbe6f7", font=("Microsoft YaHei UI", 9), relief="flat", padx=12, pady=10, state="disabled")
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")
        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 8))
        ttk.Label(main, textvariable=self.status).pack(anchor="w")

    def choose(self):
        path = filedialog.askdirectory(title="选择包含 steamapps 的目录")
        if path:
            self.root_path.set(path)

    def filter_changed(self, event=None):
        self.id_entry.configure(state="normal" if self.game.get() == "自定义 AppID" else "disabled")

    def log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def selection_changed(self, event=None):
        selected = self.table.selection()
        row = self.rows.get(selected[0]) if selected else None
        self.repair_button.configure(state="normal" if row and row["candidates"] and not self.busy else "disabled")
        if row:
            self.detail.configure(text=f"{row['reason']}\n{row['path']}")

    def start(self, job):
        self.busy = True
        for control in (self.scan_button, self.browse, self.path_entry, self.game_box, self.id_entry, self.repair_button):
            control.configure(state="disabled")
        self.progress.start(12)
        self.status.set("处理中，请稍候…")
        def run():
            try:
                job()
            except Exception as exc:
                self.events.put(("error", str(exc)))
            finally:
                self.events.put(("done", None))
        threading.Thread(target=run, daemon=True).start()

    def scan(self):
        try:
            aid = int(self.custom_id.get()) if self.game.get() == "自定义 AppID" else GAMES[self.game.get()]
            if aid < 0 or (self.game.get() == "自定义 AppID" and aid == 0):
                raise ValueError()
        except ValueError:
            messagebox.showerror("AppID 无效", "请输入正整数 AppID。")
            return
        root = self.root_path.get().strip()
        self.table.delete(*self.table.get_children())
        self.rows.clear()
        self.detail.configure(text="正在读取工坊清单…")
        self.log("\n开始只读扫描，不修改文件。")
        self.start(lambda: self.events.put(("rows", service.scan(root, aid, lambda msg: self.events.put(("log", msg))))))

    def repair(self):
        selected = self.table.selection()
        if not selected:
            return
        row = self.rows[selected[0]]
        if not messagebox.askokcancel("确认补全安装记录", f"将补全 {len(row['candidates'])} 条记录，并先在原目录备份清单。\n\n目录存在不代表内容完整，请确认这些内容曾完整下载。\n请先完全退出 Steam。下载/更新标记将保留。\n\n{row['path']}"):
            return
        self.start(lambda: self.events.put(("repaired", (selected[0], service.repair(row)))))

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="WallpaperEngineFix-log.txt", filetypes=[("文本日志", "*.txt")])
        if path:
            try:
                Path(path).write_text(self.log_text.get("1.0", "end-1c"), encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("导出失败", str(exc))

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "log":
                    self.log(data)
                elif kind == "rows":
                    for index, row in enumerate(data):
                        key = str(index)
                        self.rows[key] = row
                        name = next((name for name, aid in GAMES.items() if aid == row["appid"]), "其他应用")
                        self.table.insert("", "end", iid=key, values=(f"{name} / {row['appid']}", row["status"], len(row["installed"]), len(row["details"]), len(row["folders"]), len(row["candidates"])))
                    self.log(f"扫描完成：{len(data)} 个清单。" if data else "没有找到符合范围的工坊清单，可更换目录或扫描范围。")
                    self.detail.configure(text=f"扫描完成：{len(data)} 个清单。选择一项查看详情。")
                elif kind == "repaired":
                    key, result = data
                    self.rows[key]["candidates"] = []
                    self.table.set(key, "status", "已补全，请重扫")
                    self.table.set(key, "add", 0)
                    self.log(f"补全成功：{result['added']} 条。\n备份：{result['backup']}")
                    messagebox.showinfo("补全完成", f"已补全 {result['added']} 条安装记录。\n备份：{result['backup']}\n\n可重启 Steam 检查；本工具未验证内容完整性。")
                elif kind == "error":
                    self.log("失败：" + data)
                    messagebox.showerror("操作未完成", data)
                elif kind == "done":
                    self.busy = False
                    self.progress.stop()
                    for control in (self.scan_button, self.browse, self.path_entry):
                        control.configure(state="normal")
                    self.game_box.configure(state="readonly")
                    self.filter_changed()
                    self.selection_changed()
                    self.status.set("操作结束 · 详细结果请查看日志")
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo("正在处理", "请等待当前操作完成后再关闭窗口。")
        else:
            self.destroy()


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, AttributeError, OSError):
        pass
    App().mainloop()


if __name__ == "__main__":
    main()
