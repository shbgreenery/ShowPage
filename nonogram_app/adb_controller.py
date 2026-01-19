"""
ADB 控制器
"""

import subprocess
from typing import Tuple, Optional


class ADBController:
    """ADB 设备控制器"""

    def __init__(self):
        self.connected = False
        self.device_serial: Optional[str] = None

    def check_devices(self) -> Tuple[bool, str]:
        """
        检查连接的设备

        Returns:
            (是否成功, 消息)
        """
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
        """
        执行点击命令

        Args:
            x: 屏幕X坐标
            y: 屏幕Y坐标

        Returns:
            (是否成功, 消息)
        """
        if not self.device_serial:
            return False, "设备未连接"

        try:
            result = subprocess.run(
                ['adb', 'shell', 'input', 'tap', str(x), str(y)],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return False, f"命令执行失败: {result.stderr or result.stdout}"

            return True, "点击成功"

        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, f"点击失败: {str(e)}"

    def batch_tap(self, coordinates: list, progress_callback=None) -> Tuple[int, int]:
        """
        批量点击

        Args:
            coordinates: 坐标列表 [(row, col, x, y), ...]
            progress_callback: 进度回调函数 (current, total, message)

        Returns:
            (成功数, 失败数)
        """
        success_count = 0
        fail_count = 0

        for i, (r, c, x, y) in enumerate(coordinates):
            if progress_callback:
                progress_callback(i + 1, len(coordinates),
                                  f"正在点击 ({r + 1}, {c + 1})...")

            success, _ = self.execute_tap(x, y)
            if success:
                success_count += 1
            else:
                fail_count += 1

            # 延迟避免点击过快
            import time
            time.sleep(0.01)

        return success_count, fail_count

    def screenshot(self, output_path: str = "screenshot.png") -> Tuple[bool, str]:
        """
        截取手机屏幕

        Args:
            output_path: 截图保存路径

        Returns:
            (是否成功, 消息)
        """
        if not self.device_serial:
            return False, "设备未连接"

        try:
            result = subprocess.run(
                ['adb', 'shell', 'screencap', '-p', '/sdcard/screenshot.png'],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return False, f"截图失败: {result.stderr or result.stdout}"

            # 拉取截图到本地
            result = subprocess.run(
                ['adb', 'pull', '/sdcard/screenshot.png', output_path],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return False, f"拉取截图失败: {result.stderr or result.stdout}"

            return True, output_path

        except subprocess.TimeoutExpired:
            return False, "截图命令执行超时"
        except Exception as e:
            return False, f"截图失败: {str(e)}"
