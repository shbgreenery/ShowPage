#!/usr/bin/env python3
"""
ADB 代理服务器
接收来自网页的 ADB 命令请求，通过本地 ADB 执行
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import json
import sys


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
