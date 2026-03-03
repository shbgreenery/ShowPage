#!/usr/bin/env python3
"""
ADB 代理服务器
接收来自网页的 ADB 命令请求，通过本地 ADB 执行
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import subprocess
import json
import sys
import base64


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
    DEFAULT_TIMEOUT = 10
    SWIPE_MID_X = 100
    SWIPE_MID_Y = 1660
    STEP_PIXEL_SIZE = 100
    MIN_STEPS = 2


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
        elif self.path == '/swipe':
            try:
                # 读取请求体
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                start_x = data.get('startX', 0)
                start_y = data.get('startY', 0)
                end_x = data.get('endX', 0)
                end_y = data.get('endY', 0)

                # 使用 motionevent 模拟手指拖动
                mid_x = Config.SWIPE_MID_X
                mid_y = Config.SWIPE_MID_Y

                self.log_message(
                    f'执行手指拖动：({start_x}, {start_y}) → ({mid_x}, {mid_y}) → ({end_x}, {end_y})')

                # 构建事件序列
                all_events = []
                all_events.append(
                    f'input motionevent DOWN {start_x} {start_y}')
                all_events.append(
                    f'input motionevent MOVE {mid_x} {mid_y}')
                all_events.append(
                    f'input motionevent MOVE {end_x} {end_y}')
                all_events.append(f'input motionevent UP {end_x} {end_y}')

                shell_script = '\n'.join(all_events)

                self.log_message(f'执行 motionevent 手指拖动：{len(all_events)} 个事件')

                result = subprocess.run(
                    ['adb', 'shell', shell_script],
                    capture_output=True,
                    text=True,
                    timeout=Config.DEFAULT_TIMEOUT
                )

                if result.returncode == 0:
                    self.send_json_response({
                        'status': Status.OK,
                        'message': '手指拖动执行成功',
                        'path': f'({start_x},{start_y}) → ({mid_x},{mid_y}) → ({end_x},{end_y})'
                    })
                else:
                    self.log_message(
                        f"motionevent 拖动失败，返回码: {result.returncode}, 错误: {result.stderr}")
                    self.send_json_response({
                        'status': Status.ERROR,
                        'message': '拖动执行失败'
                    }, HttpCode.SERVER_ERROR)

            except subprocess.TimeoutExpired:
                self.send_json_response({
                    'status': Status.ERROR,
                    'message': '拖动命令执行超时'
                }, HttpCode.SERVER_ERROR)
            except Exception as e:
                self.send_json_response({
                    'status': Status.ERROR,
                    'message': str(e)
                }, HttpCode.SERVER_ERROR)
        else:
            self.send_response(HttpCode.NOT_FOUND)
            self.end_headers()

    def _generate_move_events(self, from_x: int, from_y: int, to_x: int, to_y: int) -> list[str]:
        """生成从起点到终点的移动事件序列"""
        distance = abs(to_x - from_x) + abs(to_y - from_y)
        steps = max(Config.MIN_STEPS, (distance +
                    Config.STEP_PIXEL_SIZE - 1) // Config.STEP_PIXEL_SIZE)
        events = []

        for i in range(1, steps + 1):
            progress = i / steps
            curr_x = int(from_x + (to_x - from_x) * progress)
            curr_y = int(from_y + (to_y - from_y) * progress)
            events.append(f'input motionevent MOVE {curr_x} {curr_y}')

        return events

    def send_json_response(self, data, status_code=200):
        """发送 JSON 响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[ADB Proxy] {format % args}")


def main():
    port = Config.DEFAULT_PORT
    server_address = ('', port)

    print(f"🚀 ADB 代理服务器启动在 http://localhost:{port}")
    print(f"📱 请确保手机已连接并开启 USB 调试")
    print(f"📡 支持的 API:")
    print(f"   GET  /health    - 健康检查")
    print(f"   GET  /devices   - 获取设备列表")
    print(f"   GET  /screenshot - 获取设备截图")
    print(f"   POST /tap       - 执行点击操作")
    print(f"   POST /swipe     - 执行拖动操作")
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
