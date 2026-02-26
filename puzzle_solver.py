#!/usr/bin/env python3
"""
拼图暴力求解器 - Python 版本
直接调用 ADB 命令，无需 HTTP 代理，性能最优
"""

import subprocess
import time
from io import BytesIO
from PIL import Image
from datetime import datetime
from typing import List, Tuple, Optional

# 目标颜色（RGB），允许误差 10
TARGET_COLOR = (36, 138, 114)
COLOR_TOLERANCE = 10

# 拖动和点击的坐标
SWIPE_START = (100, 1720)
TAP_COORD = (1050, 400)


class PuzzleSolver:
    def __init__(self):
        self.current_round = 0
        self.is_solving = False
        self.all_points = self._generate_points()
        self.filtered_points: List[Tuple[int, int]] = []
        self.current_index = 0

    def log(self, message: str, level: str = 'info'):
        """输出日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        prefix = {
            'info': 'ℹ️',
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
        }.get(level, 'ℹ️')
        print(f"[{timestamp}] {prefix} {message}")

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
                self.log(f'截图获取失败: {result.stderr.decode()}', 'error')
                return None

            if not result.stdout:
                self.log('截图数据为空', 'error')
                return None

            # 直接从字节流创建图片
            image = Image.open(BytesIO(result.stdout))
            self.log(f'✓ 截图获取成功，尺寸: {image.size}', 'success')
            return image

        except subprocess.TimeoutExpired:
            self.log('截图请求超时', 'error')
            return None
        except Exception as e:
            self.log(f'截图处理异常: {e}', 'error')
            return None

    def get_pixel_color(self, image: Image.Image, x: int, y: int) -> Tuple[int, int, int]:
        """获取指定坐标的像素颜色"""
        # 确保坐标在图片范围内
        if 0 <= x < image.width and 0 <= y < image.height:
            pixel = image.getpixel((x, y))
            # 处理 RGBA 或 RGB
            if isinstance(pixel, tuple):
                return pixel[:3]
            else:
                return (pixel, pixel, pixel)
        return (0, 0, 0)

    def color_matches(self, color: Tuple[int, int, int]) -> bool:
        """检查颜色是否匹配目标颜色"""
        diff = (
            abs(color[0] - TARGET_COLOR[0]) +
            abs(color[1] - TARGET_COLOR[1]) +
            abs(color[2] - TARGET_COLOR[2])
        )
        return diff <= COLOR_TOLERANCE

    def filter_points_by_color(self, image: Image.Image) -> List[Tuple[int, int]]:
        """根据颜色过滤点位"""
        self.log('📸 开始进行颜色过滤...', 'info')
        filtered = []
        matched_count = 0

        for i, (x, y) in enumerate(self.all_points):
            try:
                color = self.get_pixel_color(image, x, y)
                if self.color_matches(color):
                    filtered.append((x, y))
                    matched_count += 1

                # 每处理 10 个点输出一次进度
                if (i + 1) % 10 == 0:
                    progress = (i + 1) / len(self.all_points) * 100
                    self.log(
                        f'已检查 {i + 1}/{len(self.all_points)} 个点 ({progress:.1f}%), '
                        f'找到 {matched_count} 个匹配点',
                        'info'
                    )

            except Exception as e:
                self.log(f'检查点 ({x}, {y}) 时出错: {e}', 'error')

        self.log(
            f'✓ 颜色过滤完成！从 {len(self.all_points)} 个点中筛选出 {len(filtered)} 个有效点',
            'success'
        )
        return filtered

    def perform_swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: int = 300) -> bool:
        """执行拖动操作 - 使用 motionevent 模拟"""
        try:
            # 计算中点
            mid_x, mid_y = 100, 1500

            # 构建事件序列
            events = [f'input motionevent DOWN {start_x} {start_y}']

            # 从起点到中点的移动事件
            distance_to_mid = abs(mid_x - start_x) + abs(mid_y - start_y)
            steps_to_mid = max(2, (distance_to_mid + 99) // 100)

            for i in range(1, steps_to_mid + 1):
                progress = i / steps_to_mid
                curr_x = int(start_x + (mid_x - start_x) * progress)
                curr_y = int(start_y + (mid_y - start_y) * progress)
                events.append(f'input motionevent MOVE {curr_x} {curr_y}')

            # 从中点到终点的移动事件
            distance_to_end = abs(end_x - mid_x) + abs(end_y - mid_y)
            steps_to_end = max(2, (distance_to_end + 99) // 100)

            for i in range(1, steps_to_end + 1):
                progress = i / steps_to_end
                curr_x = int(mid_x + (end_x - mid_x) * progress)
                curr_y = int(mid_y + (end_y - mid_y) * progress)
                events.append(f'input motionevent MOVE {curr_x} {curr_y}')

            # 抬起事件
            events.append(f'input motionevent UP {end_x} {end_y}')

            # 执行事件序列
            shell_script = '\n'.join(events)
            result = subprocess.run(
                ['adb', 'shell', shell_script],
                capture_output=True,
                timeout=10
            )

            if result.returncode != 0:
                self.log(f'拖动操作失败: {result.stderr.decode()}', 'error')
                return False

            return True

        except subprocess.TimeoutExpired:
            self.log('拖动操作超时', 'error')
            return False
        except Exception as e:
            self.log(f'拖动操作异常: {e}', 'error')
            return False

    def perform_tap(self, x: int, y: int) -> bool:
        """执行点击操作"""
        try:
            result = subprocess.run(
                ['adb', 'shell', f'input tap {x} {y}'],
                capture_output=True,
                timeout=10
            )

            if result.returncode != 0:
                self.log(f'点击操作失败: {result.stderr.decode()}', 'error')
                return False

            return True

        except subprocess.TimeoutExpired:
            self.log('点击操作超时', 'error')
            return False
        except Exception as e:
            self.log(f'点击操作异常: {e}', 'error')
            return False

    def solve_point(self, x: int, y: int, index: int, total: int) -> bool:
        """求解单个点位"""
        self.log(f'🎯 处理第 {index} 个点: ({x}, {y})', 'info')

        # 第一步：拖动
        swipe_success = self.perform_swipe(SWIPE_START[0], SWIPE_START[1], x, y + 300, 300)

        if not swipe_success:
            self.log('拖动操作失败，停止本次求解', 'error')
            return False

        # 极短延迟，让 ADB 命令完成
        time.sleep(0.05)

        # 第二步：点击
        tap_success = self.perform_tap(TAP_COORD[0], TAP_COORD[1])

        if not tap_success:
            self.log('点击操作失败，停止本次求解', 'error')
            return False

        self.log(f'✓ 第 {index}/{total} 个点完成', 'success')
        return True

    def solve_round(self) -> bool:
        """执行一轮求解"""
        if not self.filtered_points:
            self.log('⚠️ 没有可处理的点位', 'error')
            return False

        total_points = len(self.filtered_points)
        self.log(f'🚀 开始第 {self.current_round + 1} 轮求解，共 {total_points} 个点', 'info')

        for index, (x, y) in enumerate(self.filtered_points, 1):
            if not self.solve_point(x, y, index, total_points):
                return False

            # 短延迟避免过快
            time.sleep(0.01)

        self.current_round += 1
        self.log(f'🎉 第 {self.current_round} 轮完成！', 'success')
        return True

    def start_solving(self, max_rounds: Optional[int] = None):
        """启动求解"""
        self.is_solving = True
        round_count = 0

        try:
            while self.is_solving:
                # 检查轮次限制
                if max_rounds and round_count >= max_rounds:
                    self.log(f'✓ 已完成 {max_rounds} 轮求解，停止', 'success')
                    break

                # 获取截图
                screenshot = self.get_screenshot()
                if not screenshot:
                    self.log('截图获取失败，停止求解', 'error')
                    break

                # 颜色过滤
                self.filtered_points = self.filter_points_by_color(screenshot)

                if not self.filtered_points:
                    self.log('⚠️ 没有找到匹配颜色的点，停止求解', 'error')
                    break

                # 求解这一轮
                if not self.solve_round():
                    break

                # 轮次间延迟
                time.sleep(0.05)
                round_count += 1

        except KeyboardInterrupt:
            self.log('\n⏹️ 用户中止求解', 'info')
        except Exception as e:
            self.log(f'求解过程中出错: {e}', 'error')
        finally:
            self.is_solving = False
            self.log(f'求解已停止，共完成 {self.current_round} 轮', 'info')


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

    # 显示所有点位信息
    print(f"📍 已生成 {len(solver.all_points)} 个点位")
    print(f"   示例: {solver.all_points[:5]}")
    print()

    # 询问轮次限制
    max_rounds = None
    try:
        user_input = input("请输入求解轮次 (回车为无限循环): ").strip()
        if user_input:
            max_rounds = int(user_input)
            print(f"✓ 将执行 {max_rounds} 轮求解\n")
    except ValueError:
        print("❌ 输入无效，使用无限循环模式\n")

    # 启动求解
    print("💡 按 Ctrl+C 可以停止求解\n")
    time.sleep(1)

    try:
        solver.start_solving(max_rounds=max_rounds)
    except KeyboardInterrupt:
        pass

    print("\n" + "=" * 60)
    print(f"📊 求解统计")
    print(f"   完成轮数: {solver.current_round}")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    main()
