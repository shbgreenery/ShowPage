"""
网格渲染器
"""

import tkinter as tk
from typing import List, Optional, Callable

from .constants import UNKNOWN, FILLED, EMPTY, DEFAULT_CELL_SIZE


class GridRenderer:
    """网格渲染器"""

    def __init__(self, canvas: tk.Canvas, cell_size: int = DEFAULT_CELL_SIZE):
        """
        初始化渲染器

        Args:
            canvas: 画布对象
            cell_size: 格子大小
        """
        self.canvas = canvas
        self.cell_size = cell_size
        self.grid: Optional[List[List[int]]] = None
        self.row_hints: Optional[List[List[int]]] = None
        self.col_hints: Optional[List[List[int]]] = None
        self.click_callback: Optional[Callable] = None

        # 渲染参数
        self.offset_x = 80
        self.offset_y = 80

    def set_click_callback(self, callback: Callable):
        """设置点击回调函数"""
        self.click_callback = callback
        self.canvas.bind("<Button-1>", self._on_click)

    def render(self, grid: List[List[int]], row_hints: List[List[int]],
               col_hints: List[List[int]]):
        """
        渲染网格

        Args:
            grid: 网格数据
            row_hints: 行提示
            col_hints: 列提示
        """
        self.grid = grid
        self.row_hints = row_hints
        self.col_hints = col_hints

        self.canvas.delete("all")

        n = len(grid)
        cell_size = self.cell_size

        # 计算画布大小
        canvas_width = (n + 1) * cell_size + 100
        canvas_height = (n + 1) * cell_size + 100
        self.canvas.configure(width=canvas_width, height=canvas_height)

        # 绘制列提示
        self._draw_col_hints(col_hints, n, cell_size)

        # 绘制行提示
        self._draw_row_hints(row_hints, n, cell_size)

        # 绘制格子
        self._draw_cells(grid, n, cell_size)

        # 绘制外边框
        self._draw_border(n, cell_size)

    def _draw_col_hints(self, col_hints: List[List[int]], n: int, cell_size: int):
        """绘制列提示"""
        for c in range(n):
            hints = col_hints[c]
            hint_text = '\n'.join([str(h) if h != -1 else '?' for h in hints[::-1]])
            self.canvas.create_text(
                self.offset_x + c * cell_size + cell_size // 2,
                self.offset_y - 10,
                text=hint_text,
                fill="#555",
                font=("Cascadia Code", 9)
            )

    def _draw_row_hints(self, row_hints: List[List[int]], n: int, cell_size: int):
        """绘制行提示"""
        for r in range(n):
            hints = row_hints[r]
            hint_text = ' '.join([str(h) if h != -1 else '?' for h in hints])
            self.canvas.create_text(
                self.offset_x - 10,
                self.offset_y + r * cell_size + cell_size // 2,
                text=hint_text,
                fill="#555",
                font=("Cascadia Code", 9),
                anchor="e"
            )

    def _draw_cells(self, grid: List[List[int]], n: int, cell_size: int):
        """绘制格子"""
        for r in range(n):
            for c in range(n):
                x1 = self.offset_x + c * cell_size
                y1 = self.offset_y + r * cell_size
                x2 = x1 + cell_size
                y2 = y1 + cell_size

                # 绘制背景
                value = grid[r][c]
                if value == FILLED:
                    color = "#333"
                elif value == EMPTY:
                    color = "#fff"
                else:
                    color = "#f0f0f0"

                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="#ddd")

                # 绘制标记
                self._draw_cell_marker(x1, y1, cell_size, value)

                # 绘制粗边框
                self._draw_cell_borders(x1, y1, x2, y2, cell_size, r, c, n)

    def _draw_cell_marker(self, x1: int, y1: int, cell_size: int, value: int):
        """绘制格子标记"""
        if value == EMPTY:
            self.canvas.create_text(
                x1 + cell_size // 2,
                y1 + cell_size // 2,
                text="×",
                fill="#ccc",
                font=("Cascadia Code", 14)
            )
        elif value == UNKNOWN:
            self.canvas.create_text(
                x1 + cell_size // 2,
                y1 + cell_size // 2,
                text="?",
                fill="#666",
                font=("Cascadia Code", 12)
            )

    def _draw_cell_borders(self, x1: int, y1: int, x2: int, y2: int,
                          cell_size: int, r: int, c: int, n: int):
        """绘制格子边框"""
        if (c + 1) % 5 == 0 and c != n - 1:
            self.canvas.create_line(x2, y1, x2, y2, width=2, fill="#aaa")
        if (r + 1) % 5 == 0 and r != n - 1:
            self.canvas.create_line(x1, y2, x2, y2, width=2, fill="#aaa")

    def _draw_border(self, n: int, cell_size: int):
        """绘制外边框"""
        self.canvas.create_rectangle(
            self.offset_x, self.offset_y,
            self.offset_x + n * cell_size,
            self.offset_y + n * cell_size,
            width=2,
            outline="#333"
        )

    def _on_click(self, event):
        """处理点击事件"""
        if not self.grid or not self.click_callback:
            return

        # 计算点击的格子
        col = (event.x - self.offset_x) // self.cell_size
        row = (event.y - self.offset_y) // self.cell_size

        n = len(self.grid)
        if 0 <= row < n and 0 <= col < n:
            self.click_callback(row, col, self.grid[row][col])

    def clear(self):
        """清空画布"""
        self.canvas.delete("all")
        self.grid = None
        self.row_hints = None
        self.col_hints = None