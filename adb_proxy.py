#!/usr/bin/env python3
"""
ADB 代理服务器
接收来自网页的 ADB 命令请求，通过本地 ADB 执行
"""

from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import subprocess
import json
import sys
import base64
import os
import tempfile
from datetime import datetime

# 添加当前目录到 path 以便导入模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nonogram_recognizer


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
                self.send_json_response({
                    'status': Status.OK,
                    'row': constraints.get('row', ''),
                    'col': constraints.get('col', '')
                })
                self.log_message("数织游戏约束分析成功")
            except Exception as e:
                self.log_message(f"分析失败: {str(e)}")
                self.send_json_response({
                    'status': Status.ERROR,
                    'message': str(e)
                }, HttpCode.SERVER_ERROR)
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
            data = {
                'row': result.get('row', '').replace('\n', '\\n'),
                'col': result.get('col', '').replace('\n', '\\n')
            }

            self.log_message(f"本地识别成功: row={data['row'][:50]}..., col={data['col'][:50]}...")
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
