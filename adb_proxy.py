#!/usr/bin/env python3
"""
ADB 代理服务器
接收来自网页的 ADB 命令请求，通过本地 ADB 执行
"""

import nonogram_recognizer
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import subprocess
import json
import sys
import base64
import os
import tempfile
from datetime import datetime
from pathlib import Path

# 添加当前目录到 path 以便导入模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bugcatcher_recognizer import recognize_bugs
from bugcatcher_solver import solve_puzzle
from bugcatcher_constants import JSONKeys



# 常量定义
class Status:
    OK = 'ok'
    ERROR = 'error'


class HttpCode:
    OK = 200
    NOT_FOUND = 404
    SERVER_ERROR = 500


class Config:
    DEFAULT_PORT = 8085
    DEVICE_TIMEOUT = 5
    DEFAULT_TIMEOUT = 30


class ADBCommand:
    DEVICES = ['adb', 'devices']
    SCREENCAP = ['adb', 'exec-out', 'screencap', '-p']


class ADBProxyHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """处理 GET 请求 - 测试连接"""
        if self.path == '/health':
            self.send_json_response({
                'status': 'ok',
                'message': 'ADB 代理服务器运行中'
            })
        elif self.path == '/devices':
            # 获取连接的设备列表
            try:
                result = subprocess.run(
                    ADBCommand.DEVICES,
                    capture_output=True,
                    text=True,
                    timeout=Config.DEVICE_TIMEOUT
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
                self.send_json_response({
                    'status': Status.OK,
                    'devices': devices
                })
            except Exception as e:
                self.send_json_response({
                    'status': Status.ERROR,
                    'message': str(e)
                }, HttpCode.SERVER_ERROR)
        elif self.path == '/screenshot':
            # 获取设备截图
            try:
                self.log_message("开始获取设备截图")
                result = subprocess.run(
                    ADBCommand.SCREENCAP,
                    capture_output=True,
                    timeout=Config.DEFAULT_TIMEOUT
                )

                if result.returncode == 0 and result.stdout:
                    # 将 PNG 数据编码为 Base64
                    base64_data = base64.b64encode(
                        result.stdout).decode('utf-8')
                    self.send_json_response({
                        'status': Status.OK,
                        'data': base64_data,
                        'format': 'png',
                        'size': len(result.stdout)
                    })
                    self.log_message(f"截图获取成功，大小: {len(result.stdout)} 字节")
                else:
                    self.log_message(
                        f"截图失败，返回码: {result.returncode}, 错误: {result.stderr.decode()}")
                    self.send_json_response({
                        'status': Status.ERROR,
                        'message': '截图失败，请确保设备已连接且锁屏已解除'
                    }, HttpCode.SERVER_ERROR)
            except subprocess.TimeoutExpired:
                self.log_message("截图请求超时")
                self.send_json_response({
                    'status': Status.ERROR,
                    'message': '截图请求超时'
                }, HttpCode.SERVER_ERROR)
            except Exception as e:
                self.log_message(f"截图异常: {str(e)}")
                self.send_json_response({
                    'status': Status.ERROR,
                    'message': f'截图异常: {str(e)}'
                }, HttpCode.SERVER_ERROR)
        elif self.path == '/analyze-nonogram':
            # 分析数织游戏约束
            try:
                self.log_message("开始分析数织游戏约束")
                # 1. 截取屏幕
                image_base64 = self._capture_screenshot()
                # 2. 用 AI 分析约束
                constraints = self._analyze_nonogram_constraints(image_base64)
                # 3. 构造响应（包含约束数据和游戏区域）
                response_data = {
                    'status': Status.OK,
                    'row': constraints.get('row', ''),
                    'col': constraints.get('col', '')
                }
                # 添加识别到的游戏区域信息
                game_area = constraints.get('gameArea')
                if game_area:
                    response_data['gameArea'] = game_area
                    self.log_message(
                        f"游戏区域: 起点({game_area['startX']},{game_area['startY']}), 尺寸({game_area['gridWidth']}x{game_area['gridHeight']})")
                self.send_json_response(response_data)
                self.log_message("数织游戏约束分析成功")
            except Exception as e:
                self.log_message(f"分析失败: {str(e)}")
                self.send_json_response({
                    'status': Status.ERROR,
                    'message': str(e)
                }, HttpCode.SERVER_ERROR)
        elif self.path == '/solve-bugcatcher':
            self.log_message("开始“田地捉虫”自动化流程")
            temp_path = None
            try:
                # 1. 获取截图并保存到临时文件
                image_base64 = self._capture_screenshot()
                image_data = base64.b64decode(image_base64)

                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    tmp_file.write(image_data)
                    temp_path = tmp_file.name

                self.log_message(f"截图已临时保存到 {temp_path}")

                # 2. 图像识别 (不再保存JSON文件)
                puzzle_data, _ = recognize_bugs(str(temp_path), output_path=None, debug=False)
                if not puzzle_data:
                    raise Exception("图像识别失败。")

                self.log_message("图像识别成功")

                # 3. 谜题求解
                solution = solve_puzzle(puzzle_data)
                if not solution:
                    raise Exception("谜题求解失败。")

                self.log_message(f"谜题求解成功，找到 {len(solution)} 个虫子。")

                # 4. 点击非虫子单元格
                solution_set = set(solution)
                taps_to_perform = [
                    {
                        "x": cell[JSONKeys.X] + cell[JSONKeys.W] // 2,
                        "y": cell[JSONKeys.Y] + cell[JSONKeys.H] // 2
                    }
                    for cell in puzzle_data[JSONKeys.CELLS]
                    if (cell[JSONKeys.ROW], cell[JSONKeys.COL]) not in solution_set
                ]

                if taps_to_perform:
                    self.log_message(f"准备点击 {len(taps_to_perform)} 个非虫子单元格")
                    tap_commands = [f"input tap {tap['x']} {tap['y']}" for tap in taps_to_perform]
                    shell_script = '\n'.join(tap_commands)

                    result = subprocess.run(
                        ['adb', 'shell', shell_script],
                        capture_output=True,
                        text=True,
                        timeout=Config.DEFAULT_TIMEOUT
                    )
                    if result.returncode != 0:
                        self.log_message(f"点击命令可能部分失败: {result.stderr.decode()}")

                self.log_message("点击命令发送成功")

                self.send_json_response({
                    'status': Status.OK,
                    'message': '“田地捉虫”自动化流程执行成功！',
                    'solution_size': len(solution),
                    'taps_performed': len(taps_to_perform)
                })

            except Exception as e:
                import traceback
                self.log_message(f"“田地捉虫”自动化流程失败: {str(e)}\n{traceback.format_exc()}")
                self.send_json_response({
                    'status': Status.ERROR,
                    'message': str(e)
                }, HttpCode.SERVER_ERROR)
            finally:
                # 清理临时截图文件
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                    self.log_message(f"临时截图 {temp_path} 已删除")
        else:
            self.send_response(HttpCode.NOT_FOUND)
            self.end_headers()

    def do_POST(self):
        """处理 POST 请求 - 执行 ADB 命令"""
        if self.path == '/tap':
            try:
                # 读取请求体
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                taps = data.get('taps', [])
                if not taps:
                    self.send_json_response({
                        'status': Status.OK,
                        'total': 0,
                        'success': 0,
                        'failed': 0
                    })
                    return

                # 批量执行点击：将所有命令合并为一个 shell 脚本
                tap_commands = [
                    f"input tap {tap.get('x', 0)} {tap.get('y', 0)}" for tap in taps]
                shell_script = '\n'.join(tap_commands)

                self.log_message(f'批量执行 {len(taps)} 个点击命令')

                result = subprocess.run(
                    ['adb', 'shell', shell_script],
                    capture_output=True,
                    text=True,
                    timeout=Config.DEFAULT_TIMEOUT
                )

                success_count = len(taps) if result.returncode == 0 else 0
                failed_count = len(taps) - success_count

                self.send_json_response({
                    'status': Status.OK,
                    'total': len(taps),
                    'success': success_count,
                    'failed': failed_count
                })

            except subprocess.TimeoutExpired:
                self.send_json_response({
                    'status': Status.ERROR,
                    'message': '命令执行超时'
                }, HttpCode.SERVER_ERROR)
            except Exception as e:
                self.send_json_response({
                    'status': Status.ERROR,
                    'message': str(e)
                }, HttpCode.SERVER_ERROR)
        else:
            self.send_response(HttpCode.NOT_FOUND)
            self.end_headers()

    def _capture_screenshot(self) -> str:
        """截取手机屏幕，返回 base64 编码的图片数据"""
        result = subprocess.run(
            ADBCommand.SCREENCAP,
            capture_output=True,
            timeout=Config.DEFAULT_TIMEOUT
        )
        if result.returncode == 0 and result.stdout:
            return base64.b64encode(result.stdout).decode('utf-8')
        raise Exception('截图失败')

    def _analyze_nonogram_constraints(self, image_base64: str) -> dict:
        """使用本地识别器分析数织游戏的行约束和列约束"""

        # 1. 将 base64 图片保存到临时文件
        image_data = base64.b64decode(image_base64)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_file.write(image_data)
            temp_path = tmp_file.name

        try:
            # 调用本地识别器
            self.log_message("开始使用本地识别器分析数织约束")
            result = nonogram_recognizer.recognize_from_image(temp_path)

            # 提取结果并格式化
            # 识别器返回的 pos 是 ((x1, y1), (x2, y2))
            # (x1, y1): 行数字区域的右边界 (行提示结束位置)
            # (x2, y2): 列数字区域的下边界 (列提示结束位置)
            # 游戏网格从 (x1, y2) 开始
            pos = result.get('pos')  # ((x1, y1), (x2, y2))
            game_area = None
            if pos and len(pos) == 2:
                x1, y1 = pos[0]
                x2, y2 = pos[1]
                game_area = {
                    'startX': x1,
                    'startY': y1,
                    'gridWidth': x2 - x1,
                    'gridHeight': y2 - y1
                }
                self.log_message(
                    f"识别到游戏区域: 起点({x1},{y1}), 尺寸({x2-x1}x{y2-y1})")

            data = {
                'row': result.get('row', '').replace('\n', '\\n'),
                'col': result.get('col', '').replace('\n', '\\n')
            }
            if game_area:
                data['gameArea'] = game_area

            self.log_message(
                f"本地识别成功: row={data['row'][:50]}..., col={data['col'][:50]}...")
            return data

        except Exception as e:
            self.log_message(f"本地识别失败: {str(e)}")
            raise Exception(f'本地识别失败: {str(e)}')
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def send_json_response(self, data, status_code=200):
        """发送 JSON 响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        """自定义日志格式"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [ADB Proxy] {format % args}")


def main():
    port = Config.DEFAULT_PORT
    server_address = ('', port)

    print(f"🚀 ADB 代理服务器启动在 http://localhost:{port}")
    print(f"📱 请确保手机已连接并开启 USB 调试")
    print(f"📡 支持的 API:")
    print(f"   GET  /health            - 健康检查")
    print(f"   GET  /devices           - 获取设备列表")
    print(f"   GET  /screenshot        - 获取设备截图")
    print(f"   GET  /analyze-nonogram  - 分析数织游戏约束")
    print(f"   GET  /solve-bugcatcher  - 自动化“田地捉虫”流程")
    print(f"   POST /tap               - 执行点击操作")
    print(f"💡 按 Ctrl+C 停止服务器")

    try:
        # 使用 ThreadingHTTPServer 支持并发请求
        httpd = ThreadingHTTPServer(server_address, ADBProxyHandler)
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
        httpd.server_close()
        sys.exit(0)
    except OSError as e:
        if e.errno == 48:
            print(f"❌ 端口 {port} 已被占用，请先关闭其他服务")
        else:
            print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
