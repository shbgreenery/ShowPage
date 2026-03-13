#!/usr/bin/env python3
"""
拼图暴力求解器 - Python 版本
直接调用 ADB 命令，无需 HTTP 代理，性能最优

优化特性：
- 动态线程池：根据 CPU 核心数自动调整（4-16 线程）
- 批量 ADB 命令执行：将多个操作合并到单个 shell 脚本中
- 优化延迟时间：减少不必要的等待
"""

import subprocess
import time
import os
from io import BytesIO
from PIL import Image
from typing import List, Tuple, Optional
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# 目标颜色（RGB），允许误差 10
TARGET_COLOR = (36, 138, 114)
COLOR_TOLERANCE = 10

# 拖动和点击的坐标
SWIPE_START = (100, 1720)
TAP_COORD = (1050, 400)
SWIPE_MID_POINT = (100, 1650)


class LogLevel(Enum):
    """日志级别枚举"""
    INFO = 'ℹ️'
    SUCCESS = '✅'
    ERROR = '❌'
    WARNING = '⚠️'


class PuzzleSolver:
    def __init__(self):
        self.current_round = 0
        self.all_points = self._generate_points()
        self.filtered_points: List[Tuple[int, int]] = self.all_points[:]
        # 动态设置线程池大小：CPU 核心数，最少 4，最多 16
        self.thread_pool_size = max(4, min(16, os.cpu_count() or 1))

    def log(self, message: str, level: LogLevel = LogLevel.INFO):
        """输出日志"""
        from time import strftime
        timestamp = strftime('%H:%M:%S')
        print(f"[{timestamp}] {level.value} {message}")

    def _generate_points(self) -> List[Tuple[int, int]]:
        """从 HTML 中移植的点位生成逻辑"""
        points = []
        for row in range(19):
            y = 580 + row * 54
            sx = 110 if row % 2 == 0 else 200
            cols = 6 - (row % 2)
            for col in range(cols):
                x = sx + col * 185
                points.append((x, y))
        return points

    def get_screenshot(self) -> Optional[Image.Image]:
        """获取设备截图"""
        try:
            result = subprocess.run(
                ['adb', 'exec-out', 'screencap', '-p'],
                capture_output=True,
                timeout=10
            )

            if result.returncode != 0:
                self.log(f'截图获取失败: {result.stderr.decode()}', LogLevel.ERROR)
                return None

            if not result.stdout:
                self.log('截图数据为空', LogLevel.ERROR)
                return None

            # 直接从字节流创建图片
            image = Image.open(BytesIO(result.stdout))
            self.log(f'✓ 截图获取成功，尺寸: {image.size}', LogLevel.SUCCESS)
            return image

        except subprocess.TimeoutExpired:
            self.log('截图请求超时', LogLevel.ERROR)
            return None
        except Exception as e:
            self.log(f'截图处理异常: {e}', LogLevel.ERROR)
            return None

    def get_pixel_color(self, image: Image.Image, x: int, y: int) -> Tuple[int, int, int]:
        """获取指定坐标的像素颜色

        注意：_generate_points 生成的坐标是固定的且在安全范围内，
        因此直接访问而不进行越界检查是安全的。
        """
        pixel = image.getpixel((x, y))
        if isinstance(pixel, tuple):
            return pixel[:3]
        else:
            return (pixel, pixel, pixel)

    def color_matches(self, color: Tuple[int, int, int]) -> bool:
        """检查颜色是否匹配目标颜色"""
        diff = (
            abs(color[0] - TARGET_COLOR[0]) +
            abs(color[1] - TARGET_COLOR[1]) +
            abs(color[2] - TARGET_COLOR[2])
        )
        return diff <= COLOR_TOLERANCE

    def _check_single_point(self, pixels, point: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """检查单个点位是否匹配目标颜色（线程安全版本）"""
        x, y = point
        try:
            # 从像素数据数组中获取颜色
            color = pixels[x, y]
            if self.color_matches(color):
                return point
            return None
        except Exception:
            return None

    def filter_points_by_color(self, image: Image.Image, candidate_points: Optional[List[Tuple[int, int]]] = None) -> List[Tuple[int, int]]:
        """根据颜色过滤点位（并行处理以提高性能）

        Args:
            image: 截图图像
            candidate_points: 候选点列表，如果为 None 则使用 self.all_points
        """
        # 使用候选点（如果提供），否则使用全部点位
        points_to_check = candidate_points if candidate_points is not None else self.all_points
        self.log(f'📸 开始进行颜色过滤...', LogLevel.INFO)

        # 加载图片数据到内存并获取线程安全的像素访问器
        pixels = image.load()

        with ThreadPoolExecutor(max_workers=self.thread_pool_size) as executor:
            results = list(executor.map(
                lambda p: self._check_single_point(pixels, p),
                points_to_check
            ))

        filtered = [r for r in results if r is not None]

        self.log(
            f'✓ 颜色过滤完成！从 {len(points_to_check)} 个候选点中筛选出 {len(filtered)} 个有效点',
            LogLevel.SUCCESS
        )
        return filtered

    def _build_swipe_commands(self, x: int, y: int) -> List[str]:
        """构建单个点的拖动命令序列"""
        sx, sy = SWIPE_START
        mid_x, mid_y = SWIPE_MID_POINT
        target_y = y + 300

        return [
            f'input motionevent DOWN {sx} {sy}',
            f'input motionevent MOVE {mid_x} {mid_y}',
            f'input motionevent MOVE {x} {target_y}',
            f'input motionevent UP {x} {target_y}',
            f'input tap {TAP_COORD[0]} {TAP_COORD[1]}',
            # f'input keyevent sleep 10'  # 10ms 短暂延迟
        ]

    def solve_round(self) -> bool:
        """执行一轮求解（批量执行 ADB 命令以提升性能）"""
        if not self.filtered_points:
            self.log('⚠️ 没有可处理的点位', LogLevel.ERROR)
            return False

        total_points = len(self.filtered_points)
        self.log(
            f'🚀 开始第 {self.current_round + 1} 轮求解，共 {total_points} 个点', LogLevel.INFO)

        # 使用进度条显示处理进度
        with tqdm(total=len(self.filtered_points),
                  desc=f'  轮次 {self.current_round + 1}',
                  unit='点', leave=True) as pbar:

            # 分批执行，避免单次 shell 脚本过大
            batch_size = 20  # 每批处理 20 个点
            for i in range(0, len(self.filtered_points), batch_size):
                batch_end = min(i + batch_size, len(self.filtered_points))
                batch_points = self.filtered_points[i:batch_end]

                # 构建批量命令
                batch_commands = []
                for x, y in batch_points:
                    batch_commands.extend(self._build_swipe_commands(x, y))

                shell_script = '\n'.join(batch_commands)

                try:
                    result = subprocess.run(
                        ['adb', 'shell', shell_script],
                        capture_output=True,
                        timeout=30
                    )

                    if result.returncode != 0:
                        self.log(
                            f'批量操作失败: {result.stderr.decode()}', LogLevel.ERROR)
                        return False

                except subprocess.TimeoutExpired:
                    self.log('批量操作超时', LogLevel.ERROR)
                    return False
                except Exception as e:
                    self.log(f'批量操作异常: {e}', LogLevel.ERROR)
                    return False

                # 更新进度条
                pbar.update(len(batch_points))

                # 批次间极短延迟
                time.sleep(0.02)

        self.current_round += 1
        print(f'✓ 第 {self.current_round} 轮完成！', flush=True)
        return True

    def start_solving(self):
        """启动求解"""
        round_count = 0

        try:
            while True:
                # 获取截图
                if round_count % 2 == 0:
                    screenshot = self.get_screenshot()
                    if not screenshot:
                        self.log('截图获取失败，停止求解', LogLevel.ERROR)
                        break

                    self.filtered_points = self.filter_points_by_color(
                        screenshot, candidate_points=self.filtered_points)

                    if not self.filtered_points:
                        self.log('⚠️ 没有找到匹配颜色的点，停止求解', LogLevel.ERROR)
                        break

                # 求解这一轮
                if not self.solve_round():
                    break

                # 轮次间延迟（优化：减少延迟时间）
                # time.sleep(0.02)
                round_count += 1

        except KeyboardInterrupt:
            self.log('\n⏹️ 用户中止求解', LogLevel.INFO)
        except Exception as e:
            self.log(f'求解过程中出错: {e}', LogLevel.ERROR)
        finally:
            self.log(f'求解已停止，共完成 {self.current_round} 轮', LogLevel.INFO)


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🧩 拼图暴力求解器 - Python 版本（直接 ADB）")
    print("=" * 60)
    print(f"📱 使用 ADB 直接操作，无 HTTP 代理开销")
    print(f"🎯 目标颜色: RGB{TARGET_COLOR} (允许误差 ±{COLOR_TOLERANCE})")
    print(f"⚙️ 操作: 拖动 {SWIPE_START} → (x, y+300) → 点击 {TAP_COORD}")
    print("=" * 60 + "\n")

    solver = PuzzleSolver()

    # 显示配置信息
    print(f"🔧 线程池大小: {solver.thread_pool_size} (基于 CPU 核心: {os.cpu_count()})")
    print(f"📍 已生成 {len(solver.all_points)} 个点位")
    print(f"   示例: {solver.all_points[:5]}")
    print()
    # 启动求解
    print("💡 按 Ctrl+C 可以停止求解\n")

    try:
        solver.start_solving()
    except KeyboardInterrupt:
        pass

    print("\n" + "=" * 60)
    print(f"📊 求解统计")
    print(f"   完成轮数: {solver.current_round}")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    main()
