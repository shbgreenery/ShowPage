"""
数织 (Nonogram) 求解器

使用约束传播算法自动求解数织谜题。
通过 ADB 连接 Android 设备，自动识别并点击答案。
"""

import collections
import base64
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from nonogram_recognizer import recognize_from_image
import adbUtil


# 常量定义
UNKNOWN = -1
FILLED = 1
EMPTY = 0


def solve_nonogram(row: List[List[int]], col: List[List[int]]) -> Optional[List[List[int]]]:
    if not row or not col:
        print("❌ 错误: 约束条件为空")
        return None

    n = len(row)
    if len(col) != n:
        print(f"❌ 错误: 行列数量不匹配 (row={n}, col={len(col)})")
        return None

    print(f"🔢 开始求解 {n}x{n} 数织谜题")

    ans = [[UNKNOWN for _ in range(n)] for _ in range(n)]
    def int2str(i: int) -> str:
        s = bin(i)[2:]
        return '0' * (n - len(s)) + s

    def str2arr(s: str) -> List[int]:
        tmp = []
        for i in range(n):
            c = s[i]
            if c == '1':
                if i == 0 or s[i-1] == '0':
                    tmp.append(1)
                else:
                    tmp[-1] += 1
        return tmp

    def mark_filled(i: int, j: int) -> None:
        """标记单元格为填充，并过滤不可能的状态"""
        ans[i][j] = FILLED
        # 过滤行状态
        for state in list(prow[i]):
            if state[j] == '0':
                prow[i].remove(state)
        # 过滤列状态
        for state in list(pcol[j]):
            if state[i] == '0':
                pcol[j].remove(state)

    def mark_empty(i: int, j: int) -> None:
        """标记单元格为空，并过滤不可能的状态"""
        ans[i][j] = EMPTY
        # 过滤行状态
        for state in list(prow[i]):
            if state[j] == '1':
                prow[i].remove(state)
        # 过滤列状态
        for state in list(pcol[j]):
            if state[i] == '1':
                pcol[j].remove(state)

    # 生成所有可能的状态
    cs = collections.defaultdict(list)
    for state in range(1 << n):
        str_state = int2str(state)
        arr_state = str2arr(str_state)
        key = tuple(arr_state)
        cs[key].append(str_state)
        # 未标记的键（用于初始化）
        unmark_key = tuple([-1])
        cs[unmark_key].append(str_state)

    # 初始化行和列的可能状态集合
    prow = [set(cs[tuple(row[i])]) for i in range(n)]
    pcol = [set(cs[tuple(col[i])]) for i in range(n)]

    # 约束传播循环
    while True:
        change = False
        # 处理行约束
        for i in range(n):
            ps = prow[i]
            cnt = [0] * n
            for state in prow[i]:
                for j in range(n):
                    cnt[j] += int(state[j])

            for j in range(n):
                # 所有状态都标记为填充
                if cnt[j] == len(ps) and ans[i][j] == UNKNOWN:
                    mark_filled(i, j)
                    change = True
                # 所有状态都标记为空
                if cnt[j] == 0 and ans[i][j] == UNKNOWN:
                    mark_empty(i, j)
                    change = True
                # 矛盾检测
                if cnt[j] == len(ps) and ans[i][j] == EMPTY:
                    return None
                if cnt[j] == 0 and ans[i][j] == FILLED:
                    return None

        # 处理列约束
        for j in range(n):
            ps = pcol[j]
            cnt = [0] * n
            for state in pcol[j]:
                for i in range(n):
                    cnt[i] += int(state[i])

            for i in range(n):
                # 所有状态都标记为填充
                if cnt[i] == len(ps) and ans[i][j] == UNKNOWN:
                    mark_filled(i, j)
                    change = True
                # 所有状态都标记为空
                if cnt[i] == 0 and ans[i][j] == UNKNOWN:
                    mark_empty(i, j)
                    change = True
                # 矛盾检测
                if cnt[i] == len(ps) and ans[i][j] == EMPTY:
                    return None
                if cnt[i] == 0 and ans[i][j] == FILLED:
                    return None
        # 没有更多变化，退出循环
        if not change:
            break

    return ans


def calculate_cell_center(
    row: int,
    col: int,
    ans: List[List[int]],
    config: Dict[str, Any]
) -> Tuple[int, int]:
    grid_size_x = len(ans[0])
    grid_size_y = len(ans)
    x = round(config["startX"] + (col + 0.5) * config["gridWidth"] / grid_size_x)
    y = round(config["startY"] + (row + 0.5) * config["gridHeight"] / grid_size_y)

    return (x, y)


def batch_fill_cells(ans: List[List[int]], config: Dict[str, Any]) -> bool:
    """
    批量填充所有标记为 FILLED 的单元格

    Args:
        ans: 解答矩阵
        config: ADB 配置字典

    Returns:
        是否所有点击都成功
    """
    if not ans or not ans[0]:
        return False

    taps = []
    for r in range(len(ans)):
        for c in range(len(ans[0])):
            if ans[r][c] == FILLED:
                coords = calculate_cell_center(r, c, ans, config)
                taps.append({"x": coords[0], "y": coords[1]})

    # 处理返回值
    result = adbUtil.batch_tap(taps)

    # 检查是否成功（假设返回 (success_count, failed_count)）
    if isinstance(result, tuple) and len(result) == 2:
        _, failed = result  # success 未使用，用 _ 代替
        if failed > 0:
            print(f"⚠️ 警告: {failed} 个点击失败")
        return failed == 0

    return True


def analyze_from_screenshot() -> Tuple[List[List[int]], List[List[int]], Dict[str, Any]]:
    temp_file = None
    try:
        # 1. 捕获截图
        screenshot_b64 = adbUtil.capture_screenshot_base64()
        if not screenshot_b64:
            raise RuntimeError("ADB 截图捕获失败：返回空数据")

        try:
            screenshot_bytes = base64.b64decode(screenshot_b64)
            if not screenshot_bytes:
                raise RuntimeError("Base64 解码失败：返回空数据")
        except Exception as e:
            raise RuntimeError(f"Base64 解码失败: {e}")

        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
            f.write(screenshot_bytes)
            temp_file = Path(f.name)


        data = recognize_from_image(temp_file, debug=False)
        pos = data["pos"]
        config = {
            'startX': pos[0][0],
            'startY': pos[0][1],
            'gridWidth': pos[1][0] - pos[0][0],
            'gridHeight': pos[1][1] - pos[0][1]
        }


        row = []
        for line_num, r in enumerate(data['row'].split("\n")):
            numbers = [int(x) for x in r.split() if x.strip()]
            if numbers:
                row.append(numbers)
        col = []
        for line_num, c in enumerate(data['col'].split("\n")):
            numbers = [int(x) for x in c.split() if x.strip()]
            if numbers:
                col.append(numbers)
        return row, col, config

    except Exception as e:
        print(f"❌ analyze_from_screenshot 失败: {e}")
        raise
    finally:
        # 清理临时文件
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception as e:
                print(f"⚠️ 清理临时文件失败: {e}")


def main():
    """主函数"""
    try:
        # 分析截图
        row, col, config = analyze_from_screenshot()
        ans = solve_nonogram(row, col)

        if ans is None:
            print("❌ 无解的谜题")
            return 1

        # # 批量填充
        print("\n正在填充单元格...")
        if batch_fill_cells(ans, config):
            print("✅ 填充完成")
        else:
            print("⚠️ 部分填充失败")

        return 0

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
        return 130
    except Exception as e:
        print(f"❌ 错误: {e}")
        return 1


if __name__ == "__main__":
    exit(main())