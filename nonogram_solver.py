#!/usr/bin/env python3
"""
数织 求解器 - Python 桌面版
支持求解、显示和通过 ADB 自动点击
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import subprocess
import threading
import json
import os
from typing import List, Set, Tuple, Optional


# 状态常量
UNKNOWN = -1
FILLED = 1
EMPTY = 0


class NonogramSolver:
    """数织求解算法"""

    def __init__(self, rows: List[List[int]], cols: List[List[int]]):
        self.rows = rows
        self.cols = cols
        self.n = len(rows)
        if self.n != len(cols):
            raise ValueError("行数和列数不一致")

    def solve(self) -> List[List[int]]:
        """求解数织谜题"""
        n = self.n
        ans = [[UNKNOWN for _ in range(n)] for _ in range(n)]

        # 创建所有可能状态的映射
        cs = {}
        for state in range(1 << n):
            str_state = self._int2str(state, n)
            arr_state = self._str2arr(str_state)

            arr_key = json.dumps(arr_state)
            if arr_key not in cs:
                cs[arr_key] = []
            cs[arr_key].append(str_state)

            # 为未确定的线索添加所有状态
            unmarked_key = json.dumps([-1])
            if unmarked_key not in cs:
                cs[unmarked_key] = []
            cs[unmarked_key].append(str_state)

        # 初始化行和列的可能状态集合
        prow = [set() for _ in range(n)]
        pcol = [set() for _ in range(n)]

        for i in range(n):
            row_key = json.dumps(self.rows[i])
            if row_key in cs:
                prow[i].update(cs[row_key])

            col_key = json.dumps(self.cols[i])
            if col_key in cs:
                pcol[i].update(cs[col_key])

        # 迭代直到没有变化
        while True:
            change = False

            # 处理行
            for i in range(n):
                ps = prow[i]
                cnt = [0] * n

                for p in ps:
                    for j in range(n):
                        if p[j] == '1':
                            cnt[j] += 1

                for j in range(n):
                    if ans[i][j] == EMPTY and cnt[j] == len(ps):
                        raise ValueError(f"冲突在位置 ({i}, {j})")
                    if ans[i][j] == UNKNOWN and cnt[j] == len(ps):
                        self._f1(ans, i, j, prow, pcol)
                        change = True
                    if ans[i][j] == FILLED and cnt[j] == 0:
                        raise ValueError(f"冲突在位置 ({i}, {j})")
                    if ans[i][j] == UNKNOWN and cnt[j] == 0:
                        self._f0(ans, i, j, prow, pcol)
                        change = True

            # 处理列
            for i in range(n):
                ps = pcol[i]
                cnt = [0] * n

                for p in ps:
                    for j in range(n):
                        if p[j] == '1':
                            cnt[j] += 1

                for j in range(n):
                    if ans[j][i] == EMPTY and cnt[j] == len(ps):
                        raise ValueError(f"冲突在位置 ({j}, {i})")
                    if ans[j][i] == FILLED and cnt[j] == 0:
                        raise ValueError(f"冲突在位置 ({j}, {i})")
                    if ans[j][i] == UNKNOWN and cnt[j] == len(ps):
                        self._f1(ans, j, i, prow, pcol)
                        change = True
                    if ans[j][i] == UNKNOWN and cnt[j] == 0:
                        self._f0(ans, j, i, prow, pcol)
                        change = True

            if not change:
                break

        return ans

    @staticmethod
    def _int2str(i: int, n: int) -> str:
        """将整数转换为二进制字符串"""
        si = bin(i)[2:]
        return '0' * (n - len(si)) + si

    @staticmethod
    def _str2arr(s: str) -> List[int]:
        """将二进制字符串转换为数组"""
        tmp = []
        for i, c in enumerate(s):
            if c == '1':
                if i == 0 or s[i - 1] == '0':
                    tmp.append(1)
                else:
                    tmp[-1] += 1
        return tmp

    def _f1(self, ans: List[List[int]], i: int, j: int,
            prow: List[Set[str]], pcol: List[Set[str]]):
        """设置格子为填充"""
        ans[i][j] = FILLED
        for p in list(prow[i]):
            if p[j] == '0':
                prow[i].remove(p)
        for p in list(pcol[j]):
            if p[i] == '0':
                pcol[j].remove(p)

    def _f0(self, ans: List[List[int]], i: int, j: int,
            prow: List[Set[str]], pcol: List[Set[str]]):
        """设置格子为空白"""
        ans[i][j] = EMPTY
        for p in list(prow[i]):
            if p[j] == '1':
                prow[i].remove(p)
        for p in list(pcol[j]):
            if p[i] == '1':
                pcol[j].remove(p)


class ADBController:
    """ADB 控制器"""

    def __init__(self):
        self.connected = False
        self.device_serial = None

    def check_devices(self) -> Tuple[bool, str]:
        """检查连接的设备"""
        try:
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=5
            )

            devices = []
            for line in result.stdout.strip().split('\n')[1:]:
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        devices.append({
                            'serial': parts[0],
                            'status': parts[1]
                        })

            if not devices:
                return False, "未检测到设备，请确保手机已连接并开启 USB 调试"

            self.device_serial = devices[0]['serial']
            return True, f"已连接: {devices[0]['serial']} ({devices[0]['status']})"
        except FileNotFoundError:
            return False, "ADB 未安装，请先安装 Android SDK Platform Tools"
        except subprocess.TimeoutExpired:
            return False, "ADB 命令执行超时"
        except Exception as e:
            return False, f"检查设备失败: {str(e)}"

    def execute_tap(self, x: int, y: int) -> Tuple[bool, str]:
        """执行点击命令"""
        if not self.device_serial:
            return False, "设备未连接"

        try:
            result = subprocess.run(
                ['adb', 'shell', 'input', 'tap', str(x), str(y)],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return False, f"命令执行失败: {result.stderr or result.stdout}"

            return True, "点击成功"
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, f"点击失败: {str(e)}"


class NonogramApp(ctk.CTk):
    """数织求解器 GUI 应用"""

    def __init__(self):
        super().__init__()

        self.title("数织 求解器")
        self.geometry("1200x1000")

        # 设置主题
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 数据
        self.rows_input: List[List[int]] = []
        self.cols_input: List[List[int]] = []
        self.grid: Optional[List[List[int]]] = None
        self.cell_size = 30

        # ADB 控制器
        self.adb = ADBController()

        # 创建 UI
        self._create_ui()

        # 加载配置
        self._load_config()

    def _create_ui(self):
        """创建用户界面"""
        # 主框架
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧面板
        left_panel = ctk.CTkFrame(main_frame, width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # 标题
        title_label = ctk.CTkLabel(
            left_panel,
            text="数织求解器",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=10)

        # 行约束输入
        ctk.CTkLabel(left_panel, text="行约束 (Row Hints):",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10)
        self.row_text = ctk.CTkTextbox(left_panel, height=150, width=280)
        self.row_text.pack(padx=10, pady=5)

        # 列约束输入
        ctk.CTkLabel(left_panel, text="列约束 (Column Hints):",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10)
        self.col_text = ctk.CTkTextbox(left_panel, height=150, width=280)
        self.col_text.pack(padx=10, pady=5)

        # 按钮框架
        button_frame = ctk.CTkFrame(left_panel)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ctk.CTkButton(button_frame, text="开始求解",
                      command=self.solve).pack(fill=tk.X, pady=2)
        ctk.CTkButton(button_frame, text="加载示例",
                      command=self.load_sample).pack(fill=tk.X, pady=2)
        ctk.CTkButton(button_frame, text="清空",
                      command=self.clear_constraints).pack(fill=tk.X, pady=2)

        # 状态标签
        self.status_label = ctk.CTkLabel(
            left_panel, text="", text_color="yellow")
        self.status_label.pack(pady=5)

        # ADB 配置面板
        adb_frame = ctk.CTkFrame(left_panel)
        adb_frame.pack(fill=tk.X, padx=10, pady=10)

        ctk.CTkLabel(adb_frame, text="📱 ADB 点击配置",
                     font=ctk.CTkFont(weight="bold")).pack(pady=5)

        # 连接测试
        ctk.CTkButton(adb_frame, text="🧪 测试连接", command=self.test_adb).pack(
            fill=tk.X, padx=10, pady=5)
        self.adb_status_label = ctk.CTkLabel(
            adb_frame, text="未测试连接", font=ctk.CTkFont(size=10))
        self.adb_status_label.pack(pady=5)

        # 坐标配置
        coord_frame = ctk.CTkFrame(adb_frame)
        coord_frame.pack(fill=tk.X, padx=10, pady=5)

        ctk.CTkLabel(coord_frame, text="起始 X:").grid(row=0, column=0, padx=2)
        self.start_x_entry = ctk.CTkEntry(coord_frame, width=80)
        self.start_x_entry.insert(0, "180")
        self.start_x_entry.grid(row=0, column=1, padx=2)

        ctk.CTkLabel(coord_frame, text="起始 Y:").grid(row=1, column=0, padx=2)
        self.start_y_entry = ctk.CTkEntry(coord_frame, width=80)
        self.start_y_entry.insert(0, "890")
        self.start_y_entry.grid(row=1, column=1, padx=2)

        ctk.CTkLabel(coord_frame, text="格子宽度:").grid(row=2, column=0, padx=2)
        self.cell_width_entry = ctk.CTkEntry(coord_frame, width=80)
        self.cell_width_entry.insert(0, "62")
        self.cell_width_entry.grid(row=2, column=1, padx=2)

        ctk.CTkLabel(coord_frame, text="格子高度:").grid(row=3, column=0, padx=2)
        self.cell_height_entry = ctk.CTkEntry(coord_frame, width=80)
        self.cell_height_entry.insert(0, "62")
        self.cell_height_entry.grid(row=3, column=1, padx=2)

        # 自动点击复选框
        self.auto_tap_var = tk.BooleanVar(value=True)
        self.auto_tap_check = ctk.CTkCheckBox(
            adb_frame,
            text="连接成功后自动执行点击",
            variable=self.auto_tap_var,
            command=self._save_config
        )
        self.auto_tap_check.pack(pady=5)

        # 批量点击按钮
        ctk.CTkButton(
            adb_frame,
            text="🎯 批量点击所有填充格子",
            fg_color="#ff9800",
            command=self.batch_tap_all
        ).pack(fill=tk.X, padx=10, pady=5)

        # 右侧显示区域
        right_panel = ctk.CTkFrame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH,
                         expand=True, padx=5, pady=5)

        # 滚动区域
        self.scroll_frame = ctk.CTkScrollableFrame(right_panel)
        self.scroll_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 网格画布
        self.canvas = tk.Canvas(
            self.scroll_frame, bg="white", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

    def _parse_constraints(self, text: str) -> List[List[int]]:
        """解析约束输入"""
        if not text or not text.strip():
            return []

        lines = text.strip().split('\n')
        result = []

        for line in lines:
            tokens = line.strip().split()
            row = []
            for token in tokens:
                if token == '?':
                    row.append(-1)
                elif token.lstrip('-').isdigit():
                    row.append(int(token))
            if row:
                result.append(row)

        return result

    def solve(self):
        """求解数织"""
        try:
            # 解析输入
            self.rows_input = self._parse_constraints(
                self.row_text.get("1.0", tk.END))
            self.cols_input = self._parse_constraints(
                self.col_text.get("1.0", tk.END))

            if not self.rows_input or not self.cols_input:
                messagebox.showerror("错误", "请输入有效的行和列约束")
                return

            if len(self.rows_input) > 20 or len(self.cols_input) > 20:
                messagebox.showerror("错误", "行数和列数不能超过20")
                return

            if len(self.rows_input) != len(self.cols_input):
                messagebox.showerror("错误", "行数和列数必须相等")
                return

            # 求解
            solver = NonogramSolver(self.rows_input, self.cols_input)
            self.grid = solver.solve()

            # 渲染
            self._render_grid()
            self.status_label.configure(text="求解成功！", text_color="green")
            self._save_config()

        except ValueError as e:
            messagebox.showerror("错误", str(e))
            self.status_label.configure(text=f"错误: {str(e)}", text_color="red")
        except Exception as e:
            messagebox.showerror("错误", f"求解失败: {str(e)}")
            self.status_label.configure(text=f"错误: {str(e)}", text_color="red")

    def _render_grid(self):
        """渲染网格"""
        if not self.grid:
            return

        self.canvas.delete("all")

        n = len(self.grid)
        cell_size = self.cell_size

        # 计算画布大小
        canvas_width = (n + 1) * cell_size + 100
        canvas_height = (n + 1) * cell_size + 100
        self.canvas.configure(width=canvas_width, height=canvas_height)

        offset_x = 80
        offset_y = 80

        # 绘制列提示
        for c in range(n):
            hints = self.cols_input[c]
            hint_text = '\n'.join(
                [str(h) if h != -1 else '?' for h in hints[::-1]])
            self.canvas.create_text(
                offset_x + c * cell_size + cell_size // 2,
                offset_y - 10,
                text=hint_text,
                fill="#555",
                font=("Arial", 9)
            )

        # 绘制行提示
        for r in range(n):
            hints = self.rows_input[r]
            hint_text = ' '.join([str(h) if h != -1 else '?' for h in hints])
            self.canvas.create_text(
                offset_x - 10,
                offset_y + r * cell_size + cell_size // 2,
                text=hint_text,
                fill="#555",
                font=("Arial", 9),
                anchor="e"
            )

        # 绘制格子
        for r in range(n):
            for c in range(n):
                x1 = offset_x + c * cell_size
                y1 = offset_y + r * cell_size
                x2 = x1 + cell_size
                y2 = y1 + cell_size

                # 绘制背景
                value = self.grid[r][c]
                if value == FILLED:
                    color = "#333"
                elif value == EMPTY:
                    color = "#fff"
                else:
                    color = "#f0f0f0"

                self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill=color, outline="#ddd")

                # 绘制标记
                if value == EMPTY:
                    self.canvas.create_text(
                        x1 + cell_size // 2,
                        y1 + cell_size // 2,
                        text="×",
                        fill="#ccc",
                        font=("Arial", 14)
                    )
                elif value == UNKNOWN:
                    self.canvas.create_text(
                        x1 + cell_size // 2,
                        y1 + cell_size // 2,
                        text="?",
                        fill="#666",
                        font=("Arial", 12)
                    )

                # 绘制粗边框
                if (c + 1) % 5 == 0 and c != n - 1:
                    self.canvas.create_line(
                        x2, y1, x2, y2, width=2, fill="#aaa")
                if (r + 1) % 5 == 0 and r != n - 1:
                    self.canvas.create_line(
                        x1, y2, x2, y2, width=2, fill="#aaa")

        # 绘制外边框
        self.canvas.create_rectangle(
            offset_x, offset_y,
            offset_x + n * cell_size,
            offset_y + n * cell_size,
            width=2,
            outline="#333"
        )

    def _on_canvas_click(self, event):
        """处理画布点击事件"""
        if not self.grid:
            return

        # 计算点击的格子
        offset_x = 80
        offset_y = 80
        cell_size = self.cell_size

        col = (event.x - offset_x) // cell_size
        row = (event.y - offset_y) // cell_size

        n = len(self.grid)
        if 0 <= row < n and 0 <= col < n:
            value = self.grid[row][col]

            # 计算屏幕坐标
            try:
                start_x = int(self.start_x_entry.get())
                start_y = int(self.start_y_entry.get())
                cell_width = int(self.cell_width_entry.get())
                cell_height = int(self.cell_height_entry.get())

                screen_x = start_x + col * cell_width + cell_width // 2
                screen_y = start_y + row * cell_height + cell_height // 2

                if self.adb.connected and self.auto_tap_var.get():
                    # 执行点击
                    success, msg = self.adb.execute_tap(screen_x, screen_y)
                    if success:
                        self.adb_status_label.configure(
                            text=f"✓ 已点击 ({row + 1}, {col + 1})",
                            text_color="green"
                        )
                    else:
                        messagebox.showerror("点击失败", msg)
                else:
                    # 显示命令
                    cmd = f"adb shell input tap {screen_x} {screen_y}"
                    messagebox.showinfo(
                        "ADB 命令",
                        f"坐标: ({row + 1}, {col + 1})\n状态: {'填充' if value == FILLED else '空白' if value == EMPTY else '未知'}\n\n命令:\n{cmd}"
                    )
            except ValueError:
                messagebox.showerror("错误", "请输入有效的坐标配置")

    def test_adb(self):
        """测试 ADB 连接"""
        self.adb_status_label.configure(text="正在测试连接...", text_color="yellow")

        def test_thread():
            connected, msg = self.adb.check_devices()
            self.adb.connected = connected

            def update_ui():
                if connected:
                    self.adb_status_label.configure(
                        text=msg, text_color="green")
                else:
                    self.adb_status_label.configure(text=msg, text_color="red")

            self.after(0, update_ui)

        threading.Thread(target=test_thread, daemon=True).start()

    def batch_tap_all(self):
        """批量点击所有填充格子"""
        if not self.grid:
            messagebox.showwarning("警告", "请先求解数织！")
            return

        if not self.adb.connected:
            messagebox.showwarning("警告", "请先测试 ADB 连接！")
            return

        # 收集填充格子
        filled_cells = []
        try:
            start_x = int(self.start_x_entry.get())
            start_y = int(self.start_y_entry.get())
            cell_width = int(self.cell_width_entry.get())
            cell_height = int(self.cell_height_entry.get())

            for r in range(len(self.grid)):
                for c in range(len(self.grid[r])):
                    if self.grid[r][c] == FILLED:
                        screen_x = start_x + c * cell_width + cell_width // 2
                        screen_y = start_y + r * cell_height + cell_height // 2
                        filled_cells.append((r, c, screen_x, screen_y))
        except ValueError:
            messagebox.showerror("错误", "请输入有效的坐标配置")
            return

        if not filled_cells:
            messagebox.showinfo("提示", "没有填充的格子！")
            return

        if not messagebox.askyesno("确认", f"准备批量点击 {len(filled_cells)} 个填充格子，确定继续吗？"):
            return

        # 批量点击
        def batch_tap_thread():
            success_count = 0
            fail_count = 0

            for i, (r, c, x, y) in enumerate(filled_cells):
                def update_status(msg, color):
                    self.after(0, lambda: self.adb_status_label.configure(
                        text=msg, text_color=color))

                update_status(
                    f"正在点击 ({r + 1}, {c + 1})... ({i + 1}/{len(filled_cells)})", "yellow")

                success, _ = self.adb.execute_tap(x, y)
                if success:
                    success_count += 1
                else:
                    fail_count += 1

                # 延迟避免点击过快
                import time
                time.sleep(0.1)

            def final_update():
                if fail_count == 0:
                    self.adb_status_label.configure(
                        text=f"✓ 批量点击完成！成功 {success_count} 个",
                        text_color="green"
                    )
                else:
                    self.adb_status_label.configure(
                        text=f"⚠ 批量点击完成！成功 {success_count} 个，失败 {fail_count} 个",
                        text_color="orange"
                    )

            self.after(0, final_update)

        threading.Thread(target=batch_tap_thread, daemon=True).start()

    def load_sample(self):
        """加载示例"""
        sample_rows = "-1\n1 1\n3"
        sample_cols = "-1\n1 1\n3"

        self.row_text.delete("1.0", tk.END)
        self.row_text.insert("1.0", sample_rows)

        self.col_text.delete("1.0", tk.END)
        self.col_text.insert("1.0", sample_cols)

        self.solve()

    def clear_constraints(self):
        """清空约束"""
        self.row_text.delete("1.0", tk.END)
        self.col_text.delete("1.0", tk.END)
        self.canvas.delete("all")
        self.grid = None
        self.status_label.configure(text="")

    def _save_config(self):
        """保存配置"""
        config = {
            "startX": self.start_x_entry.get(),
            "startY": self.start_y_entry.get(),
            "cellWidth": self.cell_width_entry.get(),
            "cellHeight": self.cell_height_entry.get(),
            "autoTap": self.auto_tap_var.get()
        }

        with open("config.json", "w") as f:
            json.dump(config, f)

    def _load_config(self):
        """加载配置"""
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    config = json.load(f)

                # 获取配置值，如果为空则使用默认值
                start_x = config.get("startX", "180") or "180"
                start_y = config.get("startY", "890") or "890"
                cell_width = config.get("cellWidth", "62") or "62"
                cell_height = config.get("cellHeight", "62") or "62"
                auto_tap = config.get("autoTap", True)

                self.start_x_entry.delete(0, tk.END)
                self.start_x_entry.insert(0, start_x)
                self.start_y_entry.delete(0, tk.END)
                self.start_y_entry.insert(0, start_y)
                self.cell_width_entry.delete(0, tk.END)
                self.cell_width_entry.insert(0, cell_width)
                self.cell_height_entry.delete(0, tk.END)
                self.cell_height_entry.insert(0, cell_height)
                self.auto_tap_var.set(auto_tap)
            except Exception as e:
                print(f"加载配置失败: {e}")


def main():
    """主函数"""
    app = NonogramApp()
    app.mainloop()


if __name__ == "__main__":
    main()
