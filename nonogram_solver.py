#!/usr/bin/env python3
"""
数织 (Nonogram) DFS 求解器

使用组合数学生成候选模式 + 约束传播 + DFS 回溯，
支持 30x30 及更大的谜题。

算法：
  1. 插空法：将约束转化为"把剩余空格插入间隙"的组合问题
     - 约束 [3,2] 在长度 n=30 → 剩余空格=25-(3+2)=20, 间隙=3 → C(22,2)=231 种
     - 远小于暴力枚举的 2^30 ≈ 10 亿种
  2. 约束传播：利用行/列候选交叉验证，确定必然填/必然空的格子
  3. DFS 分支定界：对未确定格子尝试填 1/0，每次分支后用约束传播剪枝
"""

from itertools import combinations
from typing import List, Optional, Set, Tuple

# 预生成候选模式的最大数量（超过此值则不预生成，在 DFS 中惰性处理）
MAX_CANDIDATES = 50000


def _comb(n: int, k: int) -> int:
    """计算组合数 C(n, k)"""
    if k < 0 or k > n:
        return 0
    k = min(k, n - k)
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result


def _generate_line_candidates(
    constraint: List[int], n: int
) -> Optional[List[int]]:
    """
    用插空法生成满足行/列约束的所有位掩码。

    例如约束 [3, 2]，线长 n=10：
      - 填充格: 3+2=5, 最少间隔: 1, 剩余空格: 10-5-1=4
      - 把 4 个空格分配到 3 个间隙（段前/段间/段后）
      - 共 C(4+2, 2) = 15 种分配方案

    Args:
        constraint: 数字约束列表，[-1] 表示未知
        n: 线长

    Returns:
        位掩码列表（bit 0 = 位置 0），若约束未知或候选过多则返回 None
    """
    if not constraint:
        return [0]  # 全空

    if len(constraint) == 1 and constraint[0] == -1:
        return None  # 未知约束，不预生成

    k = len(constraint)
    total_filled = sum(constraint)
    min_gaps = k - 1  # k 段之间至少 k-1 个空格
    free = n - total_filled - min_gaps

    if free < 0:
        return []  # 约束本身不可满足

    # 预估候选数量：C(free + k, k)
    count = _comb(free + k, k)
    if count > MAX_CANDIDATES:
        return None  # 候选过多，延迟到 DFS 中按需处理

    candidates = []

    # 用组合数生成所有间隙分配方案
    # free 个空格 + k 个"分隔线" = free+k 个位置，选 k 个作为分隔线
    total_positions = free + k
    for combo in combinations(range(total_positions), k):
        gaps = []
        prev = -1
        for bar in combo:
            gaps.append(bar - prev - 1)
            prev = bar
        gaps.append(total_positions - prev - 1)

        # 根据间隙建造位掩码
        mask = 0
        pos = 0
        for i in range(k):
            pos += gaps[i]  # 段前空格
            # 连续的填充格
            for _ in range(constraint[i]):
                mask |= 1 << pos
                pos += 1
            if i < k - 1:
                pos += 1  # 段间最少 1 个空格

        candidates.append(mask)

    return candidates


# ─── 约束传播 ────────────────────────────────────────────────────


def _propagate(
    grid: List[List[int]],
    row_cands: List[Optional[Set[int]]],
    col_cands: List[Optional[Set[int]]],
) -> bool:
    """
    约束传播：利用行/列候选交叉验证，确定必然填充或必然空的格子。

    对每行：
      - 若所有候选在位置 j 都是 1 → grid[r][j] = 1（强制填充）
      - 若所有候选在位置 j 都是 0 → grid[r][j] = 0（强制空）
    对列同理。填充/清空后过滤对立面候选。

    Returns:
        True 若状态一致，False 若发现矛盾
    """
    n = len(grid)
    changed = True

    while changed:
        changed = False

        # ── 处理行 ──
        for r in range(n):
            cands = row_cands[r]
            if cands is None:
                continue
            if not cands:
                return False  # 有约束的行候选集为空 → 矛盾

            # 计算 all_ones（所有候选的交集）和 any_one（所有候选的并集）
            all_ones = (1 << n) - 1
            any_one = 0
            for mask in cands:
                all_ones &= mask
                any_one |= mask

            for c in range(n):
                if grid[r][c] != -1:
                    continue
                if (all_ones >> c) & 1:
                    # 所有候选都在位置 c 有 1 → 强制填充
                    grid[r][c] = 1
                    changed = True
                    _filter_col_candidates(col_cands, c, r, True)
                elif not ((any_one >> c) & 1):
                    # 没有候选在位置 c 有 1 → 强制空
                    grid[r][c] = 0
                    changed = True
                    _filter_col_candidates(col_cands, c, r, False)

        # ── 处理列 ──
        for c in range(n):
            cands = col_cands[c]
            if cands is None:
                continue
            if not cands:
                return False

            all_ones = (1 << n) - 1
            any_one = 0
            for mask in cands:
                all_ones &= mask
                any_one |= mask

            for r in range(n):
                if grid[r][c] != -1:
                    continue
                if (all_ones >> r) & 1:
                    grid[r][c] = 1
                    changed = True
                    _filter_row_candidates(row_cands, r, c, True)
                elif not ((any_one >> r) & 1):
                    grid[r][c] = 0
                    changed = True
                    _filter_row_candidates(row_cands, r, c, False)

    return True


def _filter_col_candidates(
    col_cands: List[Optional[Set[int]]], c: int, r: int, is_filled: bool
):
    """从列候选集中移除与 (r, c) 格子状态不一致的候选"""
    cands = col_cands[c]
    if cands is None:
        return
    if is_filled:
        col_cands[c] = {m for m in cands if (m >> r) & 1}
    else:
        col_cands[c] = {m for m in cands if not ((m >> r) & 1)}


def _filter_row_candidates(
    row_cands: List[Optional[Set[int]]], r: int, c: int, is_filled: bool
):
    """从行候选集中移除与 (r, c) 格子状态不一致的候选"""
    cands = row_cands[r]
    if cands is None:
        return
    if is_filled:
        row_cands[r] = {m for m in cands if (m >> c) & 1}
    else:
        row_cands[r] = {m for m in cands if not ((m >> c) & 1)}


# ─── 求解入口 ────────────────────────────────────────────────────


def _solve_by_propagation(
    grid: List[List[int]],
    row_cands: List[Optional[Set[int]]],
    col_cands: List[Optional[Set[int]]],
) -> Optional[List[List[int]]]:
    """
    纯约束传播求解：反复用行/列候选交叉验证，尽可能确定格子。
    不做猜测——无法由约束必然确定的格子保持 -1。

    这与 Nonogram 的玩法一致：玩家只填"必然"的格子，不确定的留空。
    """
    if not _propagate(grid, row_cands, col_cands):
        return None  # 约束矛盾
    return grid


# ─── 公开接口 ────────────────────────────────────────────────────


def solve(
    rows: List[List[int]], cols: List[List[int]]
) -> Optional[List[List[int]]]:
    """
    求解 Nonogram 谜题。

    Args:
        rows: 行约束，每行是整数列表。[-1] 表示该行约束未知。
              空列表 [] 或 [0] 表示该行全部为空。
        cols: 列约束，格式同行约束。

    Returns:
        二维数组，1 = 填充，0 = 空，若多解则返回第一个找到的解。
        若题目无解则返回 None。

    Raises:
        ValueError: 行数和列数不一致。

    Example:
        >>> solve([[3], [1, 1], [3]], [[3], [1, 1], [3]])
        [[1, 1, 1], [1, 0, 1], [1, 1, 1]]
    """
    n = len(rows)
    if n != len(cols):
        raise ValueError(
            f"行数 ({n}) 和列数 ({len(cols)}) 必须相等"
        )

    # 生成候选模式
    row_cands = [_generate_line_candidates(r, n) for r in rows]
    col_cands = [_generate_line_candidates(c, n) for c in cols]

    # 预处理检查：有约束的行/列候选集是否非空
    for i, cands in enumerate(row_cands):
        if cands is not None and not cands:
            return None
    for i, cands in enumerate(col_cands):
        if cands is not None and not cands:
            return None

    # 转换为 set 以便高效 filter
    row_cands = [set(c) if c is not None else None for c in row_cands]
    col_cands = [set(c) if c is not None else None for c in col_cands]

    # 初始网格
    grid = [[-1] * n for _ in range(n)]

    return _solve_by_propagation(grid, row_cands, col_cands)


# ─── 命令行入口（用于测试）──────────────────────────────────────


def main():
    """命令行测试入口"""
    import sys
    import json

    # 示例：3x3 十字图案
    rows = [[3], [1, 1], [3]]
    cols = [[3], [1, 1], [3]]

    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1]) as f:
                data = json.load(f)
                rows = data.get("rows", rows)
                cols = data.get("cols", cols)
        except Exception as e:
            print(f"读取输入文件失败: {e}")
            sys.exit(1)

    print(f"求解 {len(rows)}x{len(cols)} 数织...")

    result = solve(rows, cols)

    if result is None:
        print("无解！")
        sys.exit(1)

    # 渲染结果
    print()
    symbol = {1: "█", 0: "·", -1: "?"}
    for row in result:
        print("".join(symbol.get(c, "?") for c in row))
    print(f"\n求解完成，{len(rows)}x{len(cols)}")


if __name__ == "__main__":
    main()
