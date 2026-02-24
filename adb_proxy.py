#!/usr/bin/env python3
"""
ADB 代理服务器
接收来自网页的 ADB 命令请求，通过本地 ADB 执行
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import json
import sys
import base64


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
                self.send_json_response({
                    'status': 'ok',
                    'devices': devices
                })
            except Exception as e:
                self.send_json_response({
                    'status': 'error',
                    'message': str(e)
                }, 500)
        elif self.path == '/screenshot':
            # 获取设备截图
            try:
                self.log_message("开始获取设备截图")
                result = subprocess.run(
                    ['adb', 'exec-out', 'screencap', '-p'],
                    capture_output=True,
                    timeout=10
                )

                if result.returncode == 0 and result.stdout:
                    # 将 PNG 数据编码为 Base64
                    base64_data = base64.b64encode(
                        result.stdout).decode('utf-8')
                    self.send_json_response({
                        'status': 'ok',
                        'data': base64_data,
                        'format': 'png',
                        'size': len(result.stdout)
                    })
                    self.log_message(f"截图获取成功，大小: {len(result.stdout)} 字节")
                else:
                    self.log_message(
                        f"截图失败，返回码: {result.returncode}, 错误: {result.stderr.decode()}")
                    self.send_json_response({
                        'status': 'error',
                        'message': '截图失败，请确保设备已连接且锁屏已解除'
                    }, 500)
            except subprocess.TimeoutExpired:
                self.log_message("截图请求超时")
                self.send_json_response({
                    'status': 'error',
                    'message': '截图请求超时'
                }, 500)
            except Exception as e:
                self.log_message(f"截图异常: {str(e)}")
                self.send_json_response({
                    'status': 'error',
                    'message': f'截图异常: {str(e)}'
                }, 500)
        else:
            self.send_response(404)
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
                        'status': 'ok',
                        'total': 0,
                        'success': 0,
                        'failed': 0
                    })
                    return

                success_count = 0
                for i, tap in enumerate(taps):
                    x = tap.get('x', 0)
                    y = tap.get('y', 0)
                    command = f'input tap {x} {y}'
                    self.log_message(f'执行点击 [{i+1}/{len(taps)}]：{command}')

                    # 执行 ADB 命令
                    result = subprocess.run(
                        ['adb', 'shell', command],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    if result.returncode == 0:
                        success_count += 1

                self.send_json_response({
                    'status': 'ok',
                    'total': len(taps),
                    'success': success_count,
                    'failed': len(taps) - success_count
                })

            except subprocess.TimeoutExpired:
                self.send_json_response({
                    'status': 'error',
                    'message': '命令执行超时'
                }, 500)
            except Exception as e:
                self.send_json_response({
                    'status': 'error',
                    'message': str(e)
                }, 500)
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
                mid_x = 100
                mid_y = 1500

                self.log_message(
                    f'执行手指拖动：({start_x}, {start_y}) → ({mid_x}, {mid_y}) → ({end_x}, {end_y})')

                # 构建简化的 motionevent 事件序列
                # DOWN 事件 - 手指按下
                down_event = f'input motionevent DOWN {start_x} {start_y}'

                # MOVE 事件 - 移动到中间点（分几步移动）
                move_events = []
                steps = 5  # 分5步移动到中间点
                for i in range(1, steps + 1):
                    progress = i / steps
                    curr_x = int(start_x + (mid_x - start_x) * progress)
                    curr_y = int(start_y + (mid_y - start_y) * progress)
                    move_events.append(
                        f'input motionevent MOVE {curr_x} {curr_y}')

                # 继续移动到终点（分几步移动）
                for i in range(1, steps + 1):
                    progress = i / steps
                    curr_x = int(mid_x + (end_x - mid_x) * progress)
                    curr_y = int(mid_y + (end_y - mid_y) * progress)
                    move_events.append(
                        f'input motionevent MOVE {curr_x} {curr_y}')

                # UP 事件 - 手指抬起
                up_event = f'input motionevent UP {end_x} {end_y}'

                # 构建完整的事件序列
                all_events = [down_event] + move_events + [up_event]

                # 直接执行事件序列，不添加延迟
                shell_script = '\n'.join(all_events)

                self.log_message(f'执行 motionevent 手指拖动：{len(all_events)} 个事件')

                result = subprocess.run(
                    ['adb', 'shell', shell_script],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    self.send_json_response({
                        'status': 'ok',
                        'message': '手指拖动执行成功',
                        'path': f'({start_x},{start_y}) → ({mid_x},{mid_y}) → ({end_x},{end_y})'
                    })
                else:
                    self.log_message(
                        f"motionevent 拖动失败，返回码: {result.returncode}, 错误: {result.stderr}")
                    self.send_json_response({
                        'status': 'error',
                        'message': '拖动执行失败'
                    }, 500)

            except subprocess.TimeoutExpired:
                self.send_json_response({
                    'status': 'error',
                    'message': '拖动命令执行超时'
                }, 500)
            except Exception as e:
                self.send_json_response({
                    'status': 'error',
                    'message': str(e)
                }, 500)
        else:
            self.send_response(404)
            self.end_headers()

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
    port = 8085
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
        httpd = HTTPServer(server_address, ADBProxyHandler)
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
