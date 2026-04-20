
import argparse
from pathlib import Path
import sys
import requests
import time
import base64
import json
import os

# 将当前目录添加到系统路径，以便导入其他模块
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

from bugcatcher_recognizer import recognize_bugs
from bugcatcher_solver import solve_puzzle
from bugcatcher_constants import ProxyConfig, FileConfig, JSONKeys

def get_screenshot_from_proxy():
    """从adb_proxy获取截图，并处理Base64编码的JSON响应"""
    print(f"\n尝试从 {ProxyConfig.SCREENSHOT_ENDPOINT} 获取截图...")
    try:
        response = requests.get(ProxyConfig.SCREENSHOT_ENDPOINT, timeout=ProxyConfig.TIMEOUT_GENERAL)
        response.raise_for_status()  # 如果HTTP请求失败则抛出异常

        json_data = response.json()
        if json_data.get(JSONKeys.STATUS) != JSONKeys.STATUS_OK or JSONKeys.DATA not in json_data:
            print(f"❌ 截图失败: 代理返回错误 -> {json_data.get(JSONKeys.MESSAGE, '未知错误')}")
            return None

        image_data = base64.b64decode(json_data[JSONKeys.DATA])
        if not image_data:
            print("❌ 截图失败: 获取到的图像数据为空。")
            return None

        screenshot_path = Path.cwd() / f"autocapture_{int(time.time())}.png"
        with open(screenshot_path, 'wb') as f:
            f.write(image_data)
            f.flush()
            os.fsync(f.fileno())

        if not screenshot_path.exists() or screenshot_path.stat().st_size == 0:
            print(f"❌ 截图保存失败: 文件未能正确创建或为空 -> {screenshot_path}")
            return None

        print(f"✓ 截图成功，已保存为 {screenshot_path}")
        return screenshot_path

    except requests.exceptions.RequestException as e:
        print(f"❌ 获取截图失败: {e}")
        print("请确保 adb_proxy.py 服务正在运行，并且设备已通过ADB连接。")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ 截图失败: 无法解析来自代理的响应 -> {e}")
        return None

def tap_non_bug_cells(puzzle_data, solution_coords):
    """点击所有非虫子单元格"""
    print("\n--- 步骤 3: 自动点击非虫子单元格 ---")

    solution_set = set(solution_coords)
    taps_to_perform = [
        {
            JSONKeys.X: cell[JSONKeys.X] + cell[JSONKeys.W] // 2,
            JSONKeys.Y: cell[JSONKeys.Y] + cell[JSONKeys.H] // 2
        }
        for cell in puzzle_data[JSONKeys.CELLS]
        if (cell[JSONKeys.ROW], cell[JSONKeys.COL]) not in solution_set
    ]

    if not taps_to_perform:
        print("没有需要点击的单元格。")
        return

    print(f"准备点击 {len(taps_to_perform)} 个非虫子单元格...")
    payload = {"taps": taps_to_perform}

    try:
        response = requests.post(ProxyConfig.TAP_ENDPOINT, json=payload, timeout=ProxyConfig.TIMEOUT_TAP)
        response.raise_for_status()

        result = response.json()
        if result.get(JSONKeys.STATUS) == JSONKeys.STATUS_OK:
            print(f"✓ 成功发送点击命令: 总计 {result.get(JSONKeys.TOTAL, 0)}, 成功 {result.get(JSONKeys.SUCCESS, 0)}")
        else:
            print(f"❌ 点击命令失败: {result.get(JSONKeys.MESSAGE, '未知错误')}")

    except requests.exceptions.RequestException as e:
        print(f"❌ 发送点击命令失败: {e}")
        print("请确保 adb_proxy.py 服务正在运行。")

def main():
    """自动化 田地捉虫 从识别到求解的全过程"""
    parser = argparse.ArgumentParser(description='自动化“田地捉虫”识别与求解')
    parser.add_argument('image', nargs='?', default=None, help='游戏截图文件路径 (如果留空，则会尝试从手机自动截图)')
    parser.add_argument('--output', default=FileConfig.DEFAULT_OUTPUT_JSON, help='识别结果的临时JSON文件名')
    parser.add_argument('--debug', action='store_true', help='为识别过程保存调试图像')
    args = parser.parse_args()

    image_to_process = args.image
    if not image_to_process:
        image_to_process = get_screenshot_from_proxy()
        if not image_to_process:
            print("无法获取截图，流程中止。")
            return

    print("\n--- 步骤 1: 图像识别 ---")
    try:
        puzzle_data, _ = recognize_bugs(str(image_to_process), output_path=args.output, debug=args.debug)
        if not puzzle_data:
            print("图像识别失败，流程中止。")
            return
    except Exception as e:
        print(f"图像识别过程中发生严重错误: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n--- 步骤 2: 谜题求解 ---")
    try:
        solution = solve_puzzle(puzzle_data)
        if not solution:
            print("求解失败，流程中止。")
            return

        # 步骤 3: 自动点击
        tap_non_bug_cells(puzzle_data, solution)

    except Exception as e:
        print(f"谜题求解或点击过程中发生严重错误: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n=========================================")
    print("🎉 自动化流程执行成功！")
    print("=========================================")

if __name__ == '__main__':
    main()
