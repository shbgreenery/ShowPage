#!/usr/bin/env python3
"""
ADB 工具函数库
封装常用的 ADB 命令操作
"""

import subprocess
import base64
from typing import List, Dict, Tuple


class ADBError(Exception):
    """ADB 命令执行错误"""
    pass


class ADBUtil:
    """ADB 工具类，封装常用的 ADB 命令"""

    # ADB 命令常量
    CMD_DEVICES = ['adb', 'devices']
    CMD_SCREENCAP = ['adb', 'exec-out', 'screencap', '-p']
    CMD_SHELL = ['adb', 'shell']

    # 默认超时时间（秒）
    DEFAULT_TIMEOUT = 30
    DEVICE_TIMEOUT = 5

    @staticmethod
    def get_devices() -> List[Dict[str, str]]:
        """
        获取已连接的设备列表

        Returns:
            List[Dict]: 设备列表，每个设备包含 'serial' 和 'status' 字段

        Raises:
            ADBError: ADB 命令执行失败
        """
        try:
            result = subprocess.run(
                ADBUtil.CMD_DEVICES,
                capture_output=True,
                text=True,
                timeout=ADBUtil.DEVICE_TIMEOUT
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

            return devices

        except subprocess.TimeoutExpired:
            raise ADBError('获取设备列表超时')
        except Exception as e:
            raise ADBError(f'获取设备列表失败: {str(e)}')

    @staticmethod
    def capture_screenshot() -> bytes:
        """
        截取设备屏幕

        Returns:
            bytes: PNG 格式的图片数据

        Raises:
            ADBError: 截图失败
        """
        try:
            result = subprocess.run(
                ADBUtil.CMD_SCREENCAP,
                capture_output=True,
                timeout=ADBUtil.DEFAULT_TIMEOUT
            )

            if result.returncode == 0 and result.stdout:
                return result.stdout
            else:
                error_msg = result.stderr.decode() if result.stderr else '未知错误'
                raise ADBError(f'截图失败: {error_msg}')

        except subprocess.TimeoutExpired:
            raise ADBError('截图超时')
        except ADBError:
            raise
        except Exception as e:
            raise ADBError(f'截图异常: {str(e)}')

    @staticmethod
    def capture_screenshot_base64() -> str:
        """
        截取设备屏幕并返回 base64 编码

        Returns:
            str: Base64 编码的 PNG 图片数据

        Raises:
            ADBError: 截图失败
        """
        png_data = ADBUtil.capture_screenshot()
        return base64.b64encode(png_data).decode('utf-8')

    @staticmethod
    def batch_tap(taps: List[Dict[str, int]]) -> Tuple[int, int]:
        """
        批量执行点击操作
        将所有点击命令合并为一个 shell 脚本执行，提高效率

        Args:
            taps: 点击坐标列表，每个元素包含 'x' 和 'y' 字段

        Returns:
            Tuple[int, int]: (成功数量, 失败数量)

        Raises:
            ADBError: 批量点击失败
        """
        if not taps:
            return (0, 0)

        try:
            # 构建批量点击命令
            tap_commands = [
                f"input tap {tap.get('x', 0)} {tap.get('y', 0)}"
                for tap in taps
            ]
            shell_script = '\n'.join(tap_commands)

            # 执行批量命令
            result = subprocess.run(
                ADBUtil.CMD_SHELL + [shell_script],
                capture_output=True,
                text=True,
                timeout=ADBUtil.DEFAULT_TIMEOUT
            )

            if result.returncode == 0:
                return (len(taps), 0)
            else:
                return (0, len(taps))

        except subprocess.TimeoutExpired:
            raise ADBError('批量点击超时')
        except Exception as e:
            raise ADBError(f'批量点击失败: {str(e)}')


# 便捷函数
def get_devices() -> List[Dict[str, str]]:
    """获取设备列表"""
    return ADBUtil.get_devices()


def capture_screenshot() -> bytes:
    """截取屏幕（PNG格式）"""
    return ADBUtil.capture_screenshot()


def capture_screenshot_base64() -> str:
    """截取屏幕（Base64编码）"""
    return ADBUtil.capture_screenshot_base64()


def batch_tap(taps: List[Dict[str, int]]) -> Tuple[int, int]:
    """批量点击"""
    return ADBUtil.batch_tap(taps)


if __name__ == '__main__':
    # 测试代码
    print("ADB 工具库测试")
    print("=" * 50)

    try:
        # 测试获取设备列表
        devices = get_devices()
        print(f"✓ 已连接设备: {len(devices)} 台")
        for device in devices:
            print(f"  - {device['serial']}: {device['status']}")

        if devices:
            # 测试截图
            print("\n测试截图...")
            png_data = capture_screenshot()
            print(f"✓ 截图成功，大小: {len(png_data)} 字节")

            # 测试 base64 编码
            base64_data = capture_screenshot_base64()
            print(f"✓ Base64 编码成功，长度: {len(base64_data)}")

    except ADBError as e:
        print(f"✗ 错误: {e}")
    except Exception as e:
        print(f"✗ 异常: {e}")