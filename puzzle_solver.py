#!/usr/bin/env python3
"""
拼图暴力求解器 - Python 版本
直接调用 ADB 命令，无需 HTTP 代理，性能最优
"""

import subprocess
import time
import os
from io import BytesIO
from PIL import Image
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import argparse
import logging

from logger_config import setup_logger

logger = logging.getLogger(__name__)

# ============================================================
# 配置常量
# ============================================================
TARGET_COLOR = (36, 138, 114)
COLOR_TOLERANCE = 10
SWIPE_START = (100, 1720)
TAP_COORD = (1050, 400)
SWIPE_MID_POINT = (100, 1650)


class PuzzleSolver:
    def __init__(self):
        self.current_round = 0
        self.all_points = self._generate_points()
        self.filtered_points: List[Tuple[int, int]] = self.all_points[:]
        self.thread_pool_size = max(4, min(16, os.cpu_count() or 1))

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
                capture_output=True, timeout=10, check=True
            )
            image = Image.open(BytesIO(result.stdout))
            logger.debug(f'截图获取成功，尺寸: {image.size}')
            return image
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            error_msg = e.stderr.decode() if hasattr(e, 'stderr') and e.stderr else str(e)
            logger.error(f'截图失败: {error_msg}', exc_info=True)
            return None
        except Exception as e:
            logger.error(f'截图处理异常: {e}', exc_info=True)
            return None

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
            color = pixels[x, y][:3]
            if self.color_matches(color):
                return point
            return None
        except IndexError:
            return None # 坐标越界，安全返回

    def filter_points_by_color(self, image: Image.Image, candidate_points: Optional[List[Tuple[int, int]]] = None) -> List[Tuple[int, int]]:
        """根据颜色过滤点位（并行处理）"""
        points_to_check = candidate_points if candidate_points is not None else self.all_points
        logger.info(f'开始进行颜色过滤，检查 {len(points_to_check)} 个点...')

        pixels = image.load()

        with ThreadPoolExecutor(max_workers=self.thread_pool_size) as executor:
            results = list(executor.map(lambda p: self._check_single_point(pixels, p), points_to_check))

        filtered = [r for r in results if r is not None]

        # 逻辑简化：如果候选点无匹配，则重新扫描所有点
        if not filtered and candidate_points is not None and len(candidate_points) < len(self.all_points):
            logger.warning("在候选点中未找到匹配项，将重新扫描所有点位...")
            return self.filter_points_by_color(image, self.all_points)

        logger.info(f'颜色过滤完成！找到 {len(filtered)} 个有效点')
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
        ]

    def solve_round(self) -> bool:
        """执行一轮求解（批量执行 ADB 命令）"""
        if not self.filtered_points:
            logger.error('没有可处理的点位')
            return False

        total_points = len(self.filtered_points)
        logger.info(f'开始第 {self.current_round + 1} 轮求解，共 {total_points} 个点')

        batch_size = 20  # 每批处理 20 个点
        with tqdm(total=total_points, desc=f'  轮次 {self.current_round + 1}', unit='点', leave=True) as pbar:
            for i in range(0, total_points, batch_size):
                batch_points = self.filtered_points[i:i + batch_size]
                batch_commands = [cmd for p in batch_points for cmd in self._build_swipe_commands(p[0], p[1])]
                shell_script = '\n'.join(batch_commands)

                try:
                    subprocess.run(
                        ['adb', 'shell', shell_script], capture_output=True, timeout=30, check=True
                    )
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                    error_msg = e.stderr.decode() if hasattr(e, 'stderr') and e.stderr else str(e)
                    logger.error(f'批量操作失败: {error_msg}', exc_info=True)
                    return False

                pbar.update(len(batch_points))
                time.sleep(0.02)

        self.current_round += 1
        logger.info(f'第 {self.current_round} 轮完成！')
        return True

    def start_solving(self):
        """启动求解循环"""
        try:
            while True:
                screenshot = self.get_screenshot()
                if not screenshot:
                    logger.error('截图获取失败，停止求解')
                    break

                self.filtered_points = self.filter_points_by_color(screenshot, self.filtered_points)

                if not self.filtered_points:
                    logger.warning('没有找到匹配颜色的点，刷新所有点再试一次')
                    self.filtered_points = self.all_points # 重置为所有点
                    continue # 直接进入下一轮，重新截图和过滤

                if not self.solve_round():
                    break

        except KeyboardInterrupt:
            logger.info('\n用户中止求解')
        except Exception as e:
            logger.error(f'求解过程中出错: {e}', exc_info=True)
        finally:
            logger.info(f'求解已停止，共完成 {self.current_round} 轮')

def main():
    parser = argparse.ArgumentParser(description='拼图暴力求解器 - Python 版本（直接 ADB）')
    parser.add_argument('--debug', action='store_true', help='开启调试模式，显示详细日志')
    args = parser.parse_args()

    setup_logger(args.debug)

    logger.info("=" * 60)
    logger.info("🧩 拼图暴力求解器 - Python 版本（直接 ADB）")
    logger.info("=" * 60)
    logger.info(f"📱 使用 ADB 直接操作，无 HTTP 代理开销")
    logger.info(f"🎯 目标颜色: RGB{TARGET_COLOR} (允许误差 ±{COLOR_TOLERANCE})")

    solver = PuzzleSolver()
    logger.info(f"🔧 线程池大小: {solver.thread_pool_size} (基于 CPU 核心: {os.cpu_count()})")
    logger.info(f"📍 已生成 {len(solver.all_points)} 个点位")
    logger.debug(f"   示例: {solver.all_points[:5]}")
    logger.info("💡 按 Ctrl+C 可以停止求解\n")

    solver.start_solving()

    logger.info("\n" + "=" * 60)
    logger.info("📊 求解统计")
    logger.info(f"   完成轮数: {solver.current_round}")
    logger.info("=" * 60 + "\n")

if __name__ == '__main__':
    main()
