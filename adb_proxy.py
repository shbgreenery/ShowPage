#!/usr/bin/env python3
"""
ADB 代理服务器
接收来自网页的 ADB 命令请求，通过本地 ADB 执行
"""

import nonogram_recognizer
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import json
import sys
import base64
import os
import tempfile
from pathlib import Path
import logging

# 添加当前目录到 path 以便导入模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bugcatcher_recognizer import recognize_bugs
from bugcatcher_solver import solve_puzzle
from bugcatcher_constants import JSONKeys
from logger_config import setup_logger

# 初始化日志记录器
logger = logging.getLogger(__name__)


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
        """处理 GET 请求"""
        if self.path == '/health':
            self.send_json_response({
                'status': 'ok',
                'message': 'ADB 代理服务器运行中'
            })
        elif self.path == '/devices':
            self._handle_get_devices()
        elif self.path == '/screenshot':
            self._handle_get_screenshot()
        elif self.path == '/analyze-nonogram':
            self._handle_analyze_nonogram()
        elif self.path == '/solve-bugcatcher':
            self._handle_solve_bugcatcher()
        else:
            self.send_error(HttpCode.NOT_FOUND, "Endpoint not found")

    def _handle_get_devices(self):
        try:
            result = subprocess.run(
                ADBCommand.DEVICES, capture_output=True, text=True, timeout=Config.DEVICE_TIMEOUT
            )
            devices = []
            for line in result.stdout.strip().split('\n')[1:]:
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        devices.append({'serial': parts[0], 'status': parts[1]})
            self.send_json_response({'status': Status.OK, 'devices': devices})
        except Exception as e:
            logger.error(f"获取设备列表失败: {e}", exc_info=True)
            self.send_json_response({'status': Status.ERROR, 'message': str(e)}, HttpCode.SERVER_ERROR)

    def _handle_get_screenshot(self):
        try:
            logger.info("开始获取设备截图")
            base64_data = self._capture_screenshot()
            self.send_json_response({
                'status': Status.OK,
                'data': base64_data,
                'format': 'png',
                'size': len(base64.b64decode(base64_data))
            })
            logger.info(f"截图获取成功")
        except Exception as e:
            logger.error(f"截图处理异常: {e}", exc_info=True)
            self.send_json_response({'status': Status.ERROR, 'message': str(e)}, HttpCode.SERVER_ERROR)

    def _handle_analyze_nonogram(self):
        try:
            logger.info("开始分析数织游戏约束")
            image_base64 = self._capture_screenshot()
            constraints = self._analyze_nonogram_constraints(image_base64)
            response_data = {'status': Status.OK, 'row': constraints.get('row', ''), 'col': constraints.get('col', '')}
            if 'gameArea' in constraints:
                response_data['gameArea'] = constraints['gameArea']
            self.send_json_response(response_data)
            logger.info("数织游戏约束分析成功")
        except Exception as e:
            logger.error(f"数织分析失败: {str(e)}", exc_info=True)
            self.send_json_response({'status': Status.ERROR, 'message': str(e)}, HttpCode.SERVER_ERROR)

    def _handle_solve_bugcatcher(self):
        logger.info("开始“田地捉虫”自动化流程")
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                image_base64 = self._capture_screenshot()
                tmp_file.write(base64.b64decode(image_base64))
                temp_path = tmp_file.name
            logger.info(f"截图已临时保存到 {temp_path}")

            puzzle_data, _ = recognize_bugs(str(temp_path), output_path=None, debug=False)
            if not puzzle_data:
                raise Exception("图像识别返回空数据")
            logger.info("图像识别成功")

            solution = solve_puzzle(puzzle_data)
            if not solution:
                raise Exception("谜题求解失败")
            logger.info(f"谜题求解成功，找到 {len(solution)} 个虫子。")

            solution_set = set(solution)
            taps = [
                (cell[JSONKeys.X] + cell[JSONKeys.W] // 2, cell[JSONKeys.Y] + cell[JSONKeys.H] // 2)
                for cell in puzzle_data[JSONKeys.CELLS]
                if (cell[JSONKeys.ROW], cell[JSONKeys.COL]) not in solution_set
            ]

            if taps:
                logger.info(f"准备点击 {len(taps)} 个非虫子单元格")
                self._batch_tap(taps)
                logger.info("点击命令发送成功")

            self.send_json_response({
                'status': Status.OK,
                'message': '“田地捉虫”自动化流程执行成功！',
                'solution_size': len(solution),
                'taps_performed': len(taps)
            })
        except Exception as e:
            logger.error(f"“田地捉虫”自动化流程失败: {str(e)}", exc_info=True)
            self.send_json_response({'status': Status.ERROR, 'message': str(e)}, HttpCode.SERVER_ERROR)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
                logger.info(f"临时截图 {temp_path} 已删除")

    def do_POST(self):
        """处理 POST 请求"""
        if self.path == '/tap':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
                taps_coords = [(tap.get('x', 0), tap.get('y', 0)) for tap in post_data.get('taps', [])]

                if not taps_coords:
                    self.send_json_response({'status': Status.OK, 'total': 0, 'success': 0, 'failed': 0})
                    return

                logger.info(f'批量执行 {len(taps_coords)} 个点击命令')
                self._batch_tap(taps_coords)
                self.send_json_response({'status': Status.OK, 'total': len(taps_coords), 'success': len(taps_coords), 'failed': 0})

            except Exception as e:
                logger.error(f"点击处理失败: {e}", exc_info=True)
                self.send_json_response({'status': Status.ERROR, 'message': str(e)}, HttpCode.SERVER_ERROR)
        else:
            self.send_error(HttpCode.NOT_FOUND, "Endpoint not found")

    def _capture_screenshot(self) -> str:
        """截取手机屏幕，返回 base64 编码的图片数据"""
        try:
            result = subprocess.run(
                ADBCommand.SCREENCAP, capture_output=True, timeout=Config.DEFAULT_TIMEOUT, check=True
            )
            return base64.b64encode(result.stdout).decode('utf-8')
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            error_msg = e.stderr.decode() if hasattr(e, 'stderr') and e.stderr else str(e)
            raise Exception(f'截图失败: {error_msg}')

    def _batch_tap(self, taps: list[tuple[int, int]]):
        """批量执行点击操作"""
        tap_commands = [f"input tap {x} {y}" for x, y in taps]
        shell_script = '\n'.join(tap_commands)
        try:
            subprocess.run(
                ['adb', 'shell', shell_script], capture_output=True, text=True,
                timeout=Config.DEFAULT_TIMEOUT, check=True
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"点击命令可能部分失败: {e.stderr}")

    def _analyze_nonogram_constraints(self, image_base64: str) -> dict:
        """使用本地识别器分析数织游戏的行约束和列约束"""
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                tmp_file.write(base64.b64decode(image_base64))
                temp_path = tmp_file.name

            logger.info("开始使用本地识别器分析数织约束")
            result = nonogram_recognizer.recognize_from_image(temp_path)
            pos = result.get('pos')
            game_area = None
            if pos and len(pos) == 2:
                x1, y1 = pos[0]
                x2, y2 = pos[1]
                game_area = {'startX': x1, 'startY': y1, 'gridWidth': x2 - x1, 'gridHeight': y2 - y1}
                logger.debug(f"识别到游戏区域: 起点({x1},{y1}), 尺寸({x2-x1}x{y2-y1})")

            data = {'row': result.get('row', '').replace('\n', '\\n'), 'col': result.get('col', '').replace('\n', '\\n')}
            if game_area: data['gameArea'] = game_area
            logger.info(f"本地识别成功: row={data['row'][:30]}..., col={data['col'][:30]}...")
            return data

        except Exception as e:
            raise Exception(f'本地识别失败: {str(e)}')
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    def send_json_response(self, data, status_code=200):
        """发送 JSON 响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format_string, *args):
        """重写基类的日志方法，将其重定向到我们的 logger"""
        logger.info("%s - %s" % (self.address_string(), format_string % args))


def main():
    # 配置日志
    setup_logger()

    port = Config.DEFAULT_PORT
    server_address = ('', port)

    logger.info(f"🚀 ADB 代理服务器启动在 http://localhost:{port}")
    logger.info("📱 请确保手机已连接并开启 USB 调试")
    logger.info("📡 支持的 API:")
    logger.info("   GET  /health            - 健康检查")
    logger.info("   GET  /devices           - 获取设备列表")
    logger.info("   GET  /screenshot        - 获取设备截图")
    logger.info("   GET  /analyze-nonogram  - 分析数织游戏约束")
    logger.info("   GET  /solve-bugcatcher  - 自动化“田地捉虫”流程")
    logger.info("   POST /tap               - 执行点击操作")
    logger.info("💡 按 Ctrl+C 停止服务器")

    try:
        httpd = ThreadingHTTPServer(server_address, ADBProxyHandler)
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("\n👋 服务器已停止")
        httpd.server_close()
        sys.exit(0)
    except OSError as e:
        if e.errno == 48:  # Address already in use
            logger.error(f"❌ 端口 {port} 已被占用，请先关闭其他服务")
        else:
            logger.error(f"❌ 启动失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()