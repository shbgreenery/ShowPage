"""
数织求解器主应用
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading
from typing import List

from .constants import (
    UNKNOWN, FILLED, EMPTY,
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT, DEFAULT_CELL_SIZE
)
from .solver import NonogramSolver
from .adb_controller import ADBController
from .config_manager import ConfigManager
from .grid_renderer import GridRenderer
from .input_parser import InputParser
from .image_analyzer import ImageAnalyzer


class NonogramApp(ctk.CTk):
    """数织求解器 GUI 应用"""

    def __init__(self):
        super().__init__()

        # 初始化组件
        self.config_manager = ConfigManager()
        self.adb_controller = ADBController()
        self.input_parser = InputParser()
        self.image_analyzer = ImageAnalyzer()
        self.grid_renderer = None

        # 数据
        self.rows_input = []
        self.cols_input = []
        self.grid = None

        # 设置窗口
        self._setup_window()

        # 创建 UI
        self._create_ui()

        # 加载配置
        self._load_config()

    def _setup_window(self):
        """设置窗口"""
        self.title("数织 (Nonogram) 求解器")
        self.geometry(f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}")

        # 设置主题
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

    def _create_ui(self):
        """创建用户界面"""
        # 主框架
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧面板
        left_panel = self._create_left_panel(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # 右侧面板
        right_panel = self._create_right_panel(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH,
                         expand=True, padx=5, pady=5)

    def _create_left_panel(self, parent) -> ctk.CTkFrame:
        """创建左侧面板"""
        panel = ctk.CTkFrame(parent, width=300)

        # 标题
        title_label = ctk.CTkLabel(
            panel,
            text="数织求解器",
            font=ctk.CTkFont(size=24, weight="bold", family="Cascadia Code")
        )
        title_label.pack(pady=10)

        # 约束输入区域
        self._create_constraint_inputs(panel)

        # 按钮区域
        self._create_action_buttons(panel)

        # 状态标签
        self.status_label = ctk.CTkLabel(panel, text="", text_color="yellow")
        self.status_label.pack(pady=5)

        # ADB 配置区域
        self._create_adb_config(panel)

        return panel

    def _create_constraint_inputs(self, parent):
        """创建约束输入区域"""
        # 行约束
        ctk.CTkLabel(parent, text="行约束 (Row Hints):", font=ctk.CTkFont(
            weight="bold", family="Cascadia Code")).pack(anchor="w", padx=10)
        self.row_text = ctk.CTkTextbox(parent, height=150, width=280)
        self.row_text.pack(padx=10, pady=5)

        # 列约束
        ctk.CTkLabel(parent, text="列约束 (Column Hints):", font=ctk.CTkFont(
            weight="bold", family="Cascadia Code")).pack(anchor="w", padx=10)
        self.col_text = ctk.CTkTextbox(parent, height=150, width=280)
        self.col_text.pack(padx=10, pady=5)

    def _create_action_buttons(self, parent):
        """创建操作按钮"""
        button_frame = ctk.CTkFrame(parent)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ctk.CTkButton(button_frame, text="开始求解",
                      command=self.solve).pack(fill=tk.X, pady=2)
        ctk.CTkButton(button_frame, text="加载示例",
                      command=self.load_sample).pack(fill=tk.X, pady=2)
        ctk.CTkButton(button_frame, text="清空",
                      command=self.clear_constraints).pack(fill=tk.X, pady=2)

    def _create_adb_config(self, parent):
        """创建 ADB 配置区域"""
        adb_frame = ctk.CTkFrame(parent)
        adb_frame.pack(fill=tk.X, padx=10, pady=10)

        ctk.CTkLabel(adb_frame, text="📱 ADB 点击配置", font=ctk.CTkFont(
            weight="bold", family="Cascadia Code")).pack(pady=5)

        # 连接测试
        ctk.CTkButton(adb_frame, text="🧪 测试连接", command=self.test_adb).pack(
            fill=tk.X, padx=10, pady=5)
        self.adb_status_label = ctk.CTkLabel(
            adb_frame, text="未测试连接", font=ctk.CTkFont(size=10, family="Cascadia Code"))
        self.adb_status_label.pack(pady=5)

        # 坐标配置
        coord_frame = self._create_coord_input_frame(adb_frame)
        coord_frame.pack(fill=tk.X, padx=10, pady=5)

        # 自动点击复选框
        self.auto_tap_var = tk.BooleanVar(value=True)
        self.auto_tap_check = ctk.CTkCheckBox(
            adb_frame,
            text="连接成功后自动执行点击",
            variable=self.auto_tap_var,
            command=self._save_config
        )
        self.auto_tap_check.pack(pady=5)

        # 截图分析按钮
        ctk.CTkButton(
            adb_frame,
            text="📸 截图并分析约束",
            fg_color="#2196f3",
            command=self.capture_and_analyze
        ).pack(fill=tk.X, padx=10, pady=5)

        # 批量点击按钮
        ctk.CTkButton(
            adb_frame,
            text="🎯 批量点击所有填充格子",
            fg_color="#ff9800",
            command=self.batch_tap_all
        ).pack(fill=tk.X, padx=10, pady=5)

    def _create_coord_input_frame(self, parent) -> ctk.CTkFrame:
        """创建坐标输入框"""
        frame = ctk.CTkFrame(parent)

        # 起始 X
        ctk.CTkLabel(frame, text="起始 X:").grid(row=0, column=0, padx=2)
        self.start_x_entry = ctk.CTkEntry(frame, width=80)
        self.start_x_entry.insert(0, "180")
        self.start_x_entry.grid(row=0, column=1, padx=2)

        # 起始 Y
        ctk.CTkLabel(frame, text="起始 Y:").grid(row=1, column=0, padx=2)
        self.start_y_entry = ctk.CTkEntry(frame, width=80)
        self.start_y_entry.insert(0, "890")
        self.start_y_entry.grid(row=1, column=1, padx=2)

        # 格子宽度
        ctk.CTkLabel(frame, text="格子宽度:").grid(row=2, column=0, padx=2)
        self.cell_width_entry = ctk.CTkEntry(frame, width=80)
        self.cell_width_entry.insert(0, "62")
        self.cell_width_entry.grid(row=2, column=1, padx=2)

        # 格子高度
        ctk.CTkLabel(frame, text="格子高度:").grid(row=3, column=0, padx=2)
        self.cell_height_entry = ctk.CTkEntry(frame, width=80)
        self.cell_height_entry.insert(0, "62")
        self.cell_height_entry.grid(row=3, column=1, padx=2)

        return frame

    def _create_right_panel(self, parent) -> ctk.CTkFrame:
        """创建右侧面板"""
        panel = ctk.CTkFrame(parent)

        # 滚动区域
        scroll_frame = ctk.CTkScrollableFrame(panel)
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建画布
        canvas = tk.Canvas(scroll_frame, bg="white", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        # 创建网格渲染器
        self.grid_renderer = GridRenderer(canvas, DEFAULT_CELL_SIZE)
        self.grid_renderer.set_click_callback(self._on_grid_click)

        return panel

    def solve(self):
        """求解数织"""
        try:
            # 解析输入
            self.rows_input = self.input_parser.parse_constraints(
                self.row_text.get("1.0", tk.END))
            self.cols_input = self.input_parser.parse_constraints(
                self.col_text.get("1.0", tk.END))

            # 验证约束
            is_valid, error_msg = self.input_parser.validate_constraints(
                self.rows_input, self.cols_input)
            if not is_valid:
                messagebox.showerror("错误", error_msg)
                return

            # 在后台线程中求解
            self.status_label.configure(text="正在求解...", text_color="yellow")

            def solve_thread():
                try:
                    # 求解
                    solver = NonogramSolver(self.rows_input, self.cols_input)
                    self.grid = solver.solve()

                    # 在主线程中更新 UI
                    def update_ui():
                        self.grid_renderer.render(
                            self.grid, self.rows_input, self.cols_input)
                        self.status_label.configure(
                            text="求解成功！", text_color="green")
                        self._save_config()

                    self.after(0, update_ui)

                except ValueError as e:
                    def show_error():
                        messagebox.showerror("错误", str(e))
                        self.status_label.configure(
                            text=f"错误: {str(e)}", text_color="red")
                    self.after(0, show_error)
                except Exception as e:
                    def show_error():
                        messagebox.showerror("错误", f"求解失败: {str(e)}")
                        self.status_label.configure(
                            text=f"错误: {str(e)}", text_color="red")
                    self.after(0, show_error)

            threading.Thread(target=solve_thread, daemon=True).start()

        except Exception as e:
            messagebox.showerror("错误", f"求解失败: {str(e)}")
            self.status_label.configure(text=f"错误: {str(e)}", text_color="red")

    def _on_grid_click(self, row: int, col: int, value: int):
        """处理网格点击"""
        if not self.grid:
            return

        # 计算屏幕坐标
        try:
            start_x = int(self.start_x_entry.get())
            start_y = int(self.start_y_entry.get())
            cell_width = int(self.cell_width_entry.get())
            cell_height = int(self.cell_height_entry.get())

            screen_x = start_x + col * cell_width + cell_width // 2
            screen_y = start_y + row * cell_height + cell_height // 2

            if self.adb_controller.connected and self.auto_tap_var.get():
                # 在后台线程中执行点击
                def tap_thread():
                    self.adb_status_label.configure(
                        text=f"正在点击 ({row + 1}, {col + 1})...",
                        text_color="yellow"
                    )

                    success, msg = self.adb_controller.execute_tap(
                        screen_x, screen_y)

                    def update_status():
                        if success:
                            self.adb_status_label.configure(
                                text=f"✓ 已点击 ({row + 1}, {col + 1})",
                                text_color="green"
                            )
                        else:
                            messagebox.showerror("点击失败", msg)
                            self.adb_status_label.configure(
                                text=f"✗ 点击失败",
                                text_color="red"
                            )

                    self.after(0, update_status)

                threading.Thread(target=tap_thread, daemon=True).start()
            else:
                # 显示命令
                cmd = f"adb shell input tap {screen_x} {screen_y}"
                status_text = "填充" if value == FILLED else "空白" if value == EMPTY else "未知"
                messagebox.showinfo(
                    "ADB 命令",
                    f"坐标: ({row + 1}, {col + 1})\n状态: {status_text}\n\n命令:\n{cmd}"
                )
        except ValueError:
            messagebox.showerror("错误", "请输入有效的坐标配置")

    def test_adb(self):
        """测试 ADB 连接"""
        self.adb_status_label.configure(text="正在测试连接...", text_color="yellow")

        def test_thread():
            try:
                connected, msg = self.adb_controller.check_devices()
                self.adb_controller.connected = connected

                def update_ui():
                    if connected:
                        self.adb_status_label.configure(
                            text=msg, text_color="green")
                    else:
                        self.adb_status_label.configure(
                            text=msg, text_color="red")

                self.after(0, update_ui)

            except Exception as e:
                def show_error():
                    self.adb_status_label.configure(
                        text=f"测试失败: {str(e)}", text_color="red")

                self.after(0, show_error)

        threading.Thread(target=test_thread, daemon=True).start()

    def batch_tap_all(self):
        """批量点击所有填充格子"""
        if not self.grid:
            messagebox.showwarning("警告", "请先求解数织！")
            return

        if not self.adb_controller.connected:
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
            def progress_callback(current, total, msg):
                def update():
                    self.adb_status_label.configure(
                        text=f"{msg} ({current}/{total})", text_color="yellow")
                self.after(0, update)

            success_count, fail_count = self.adb_controller.batch_tap(
                filled_cells, progress_callback)

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

    def capture_and_analyze(self):
        """截图并分析约束"""
        if not self.adb_controller.connected:
            messagebox.showwarning("警告", "请先测试 ADB 连接！")
            return

        self.adb_status_label.configure(text="正在截图...", text_color="yellow")

        def analyze_thread():
            # 截图
            success, result = self.adb_controller.screenshot("screenshot.png")

            if not success:
                def show_error():
                    messagebox.showerror("截图失败", result)
                    self.adb_status_label.configure(
                        text="截图失败", text_color="red")
                self.after(0, show_error)
                return

            def update_status():
                self.adb_status_label.configure(
                    text="正在分析图片...", text_color="yellow")
            self.after(0, update_status)

            # 分析图片
            my_grid = (180, 890, 940, 940)
            row_hints, col_hints, error_msg = self.image_analyzer.analyze_screenshot(
                result, manual_grid=my_grid)

            def update_ui():
                if error_msg:
                    messagebox.showerror("分析失败", error_msg)
                    self.adb_status_label.configure(
                        text="分析失败", text_color="red")
                    return

                # 填充约束到界面
                self._fill_constraints(row_hints, col_hints)

                self.adb_status_label.configure(
                    text=f"✓ 成功提取 {len(row_hints)} 行 {len(col_hints)} 列约束", text_color="green")

            self.after(0, update_ui)

        threading.Thread(target=analyze_thread, daemon=True).start()

    def _fill_constraints(self, row_hints: List[List[int]], col_hints: List[List[int]]):
        """
        将约束填充到界面

        Args:
            row_hints: 行约束
            col_hints: 列约束
        """
        # 填充行约束
        row_text = "\n".join(" ".join(str(num) for num in row)
                             for row in row_hints)
        self.row_text.delete("1.0", tk.END)
        self.row_text.insert("1.0", row_text)

        # 填充列约束
        col_text = "\n".join(" ".join(str(num) for num in col)
                             for col in col_hints)
        self.col_text.delete("1.0", tk.END)
        self.col_text.insert("1.0", col_text)

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

        if self.grid_renderer:
            self.grid_renderer.clear()
        self.grid = None
        self.status_label.configure(text="")

    def _save_config(self):
        """保存配置"""
        entries = {
            "startX": self.start_x_entry,
            "startY": self.start_y_entry,
            "cellWidth": self.cell_width_entry,
            "cellHeight": self.cell_height_entry
        }
        self.config_manager.save_from_entries(entries)
        self.config_manager.update("autoTap", self.auto_tap_var.get())
        self.config_manager.save()

    def _load_config(self):
        """加载配置"""
        entries = {
            "startX": self.start_x_entry,
            "startY": self.start_y_entry,
            "cellWidth": self.cell_width_entry,
            "cellHeight": self.cell_height_entry
        }
        self.config_manager.load_to_entries(entries)
        self.auto_tap_var.set(self.config_manager.get("autoTap", True))
