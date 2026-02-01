#!/usr/bin/env python3
"""
ADB 代理服务器
接收来自网页的 ADB 命令请求，通过本地 ADB 执行
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import json
import urllib.parse
import sys
import base64
import io

# PIL依赖检查
try:
    from PIL import Image
except ImportError:
    print("❌ 错误: 需要安装Pillow库")
    print("请运行: pip install Pillow")
    sys.exit(1)


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
        if self.path == '/execute':
            try:
                # 读取请求体
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                command = data.get('command', '')
                if not command:
                    raise ValueError('缺少 command 参数')

                # 安全检查：只允许 input tap 命令
                if not command.startswith('input tap '):
                    raise ValueError('只允许 input tap 命令')

                self.log_message(f'执行命令：{command}')

                # 执行 ADB 命令
                result = subprocess.run(
                    ['adb', 'shell', command],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                self.send_json_response({
                    'status': 'ok',
                    'command': command,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode
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
        elif self.path == '/screenshot':
            try:
                # 执行ADB截图命令
                result = subprocess.run(
                    ['adb', 'shell', 'screencap', '-p'],
                    capture_output=True,
                    timeout=10
                )

                if result.returncode != 0:
                    raise ValueError(f'截图失败: {result.stderr.decode()}')

                # 将PNG数据编码为base64
                screenshot_b64 = base64.b64encode(result.stdout).decode('utf-8')

                self.send_json_response({
                    'status': 'ok',
                    'screenshot': screenshot_b64
                })
            except Exception as e:
                self.send_json_response({
                    'status': 'error',
                    'message': str(e)
                }, 500)
        elif self.path == '/get-color':
            try:
                # 读取请求体
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                x = int(data.get('x', 0))
                y = int(data.get('y', 0))
                # 获取请求中的白色阈值（可选）
                white_threshold = int(data.get('white_threshold', 240))

                # 执行ADB截图
                result = subprocess.run(
                    ['adb', 'shell', 'screencap', '-p'],
                    capture_output=True,
                    timeout=10
                )

                if result.returncode != 0:
                    raise ValueError(f'截图失败: {result.stderr.decode()}')

                # 使用PIL解析图像
                image = Image.open(io.BytesIO(result.stdout))
                pixel_color = image.getpixel((x, y))

                # 如果是RGB模式，确保返回3个值
                if len(pixel_color) == 4:  # RGBA
                    pixel_color = pixel_color[:3]

                r, g, b = pixel_color
                is_white = (r > white_threshold and g > white_threshold and b > white_threshold)  # 判断是否为白色

                self.send_json_response({
                    'status': 'ok',
                    'x': x,
                    'y': y,
                    'color': {'r': r, 'g': g, 'b': b},
                    'is_white': is_white
                })

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
