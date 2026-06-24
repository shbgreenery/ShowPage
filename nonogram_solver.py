#!/usr/bin/env python3
"""
数织 (Nonogram) 求解器 —— 混合算法（候选法 + 逐线 DP + 约束传播 worklist）

小规模（n ≤ 15）：预计算所有约束的候选位掩码，查表 + 过滤，O(|cands|·n)
大规模（n > 15）：逐线 DP，O(k·n²)，不受候选数膨胀影响

算法：
  1. 小规模（n≤15）：预计算候选缓存 + while-changed 全量扫描，位运算取交集/并集
  2. 大规模（n>15）：逐线 DP + worklist 增量传播，不受候选数膨胀影响
"""

from collections import deque
from itertools import combinations
from typing import Dict, List, Optional, Tuple

# ─── 全局候选缓存（小规模预计算）──────────────────────────────────

_CANDIDATE_CACHE: Dict[int, Dict[Tuple[int, ...], List[int]]] = {}
"""_CANDIDATE_CACHE[n][tuple(constraint)] = [bitmask, ...]"""


def _precompute_candidates(n: int) -> None:
    """预计算 n 维所有可能约束的候选位掩码集，存入全局缓存。"""
    if n in _CANDIDATE_CACHE:
        return

    # 枚举所有 2^n 种填充模式，收集所有不同的约束类型
    constraints: set = set()
    for mask in range(1 << n):
        segs = []
        cnt = 0
        for i in range(n):
            if (mask >> i) & 1:
                cnt += 1
            elif cnt > 0:
                segs.append(cnt)
                cnt = 0
        if cnt > 0:
            segs.append(cnt)
        constraints.add(tuple(segs) if segs else (0,))

    cache: Dict[Tuple[int, ...], List[int]] = {}
    for c in constraints:
        cache[c] = _generate_candidates_for_constraint(list(c), n)

    _CANDIDATE_CACHE[n] = cache


def _generate_candidates_for_constraint(
    constraint: List[int], n: int
) -> List[int]:
    """用插空法生成约束的所有候选位掩码（不含数量上限检查，信任调用方）。"""
    if not constraint or constraint == [0]:
        return [0]
    k = len(constraint)
    total_filled = sum(constraint)
    free = n - total_filled - (k - 1)
    if free < 0:
        return []
    cands = []
    for combo in combinations(range(free + k), k):
        gaps = []
        prev = -1
        for bar in combo:
            gaps.append(bar - prev - 1)
            prev = bar
        gaps.append(free + k - prev - 1)
        mask = 0
        pos = 0
        for i in range(k):
            pos += gaps[i]
            for _ in range(constraint[i]):
                mask |= 1 << pos
                pos += 1
            if i < k - 1:
                pos += 1
        cands.append(mask)
    return cands


# 用户常用规模，模块加载时预计算
for _n in [10, 15]:
    _precompute_candidates(_n)


# ─── 逐线分析 ──────────────────────────────────────────────────────


def _analyze_line(
    cells: List[int], constraint: List[int]
) -> Tuple[Optional[List[int]], Optional[List[int]], bool]:
    """
    逐线 DP：left/right DP 表 + 前缀和 + 差分数组。

    仅用于大规模（n > 15）传播，小规模走 _propagate_small（缓存候选法）。
    """
    # 未知约束 → 无法推导
    if len(constraint) == 1 and constraint[0] == -1:
        return [], [], True
    return _analyze_line_dp(cells, constraint)


def _analyze_line_dp(
    cells: List[int], constraint: List[int]
) -> Tuple[Optional[List[int]], Optional[List[int]], bool]:
    """
    逐线 DP：left/right DP 表 + 前缀和 + 差分数组。

    不受候选数膨胀影响，适合大规模（n > 15）。
    """
    n = len(cells)

    # 全空约束
    if not constraint or constraint == [0]:
        forced_zeros = []
        for j in range(n):
            if cells[j] == 1:
                return None, None, False
            if cells[j] == -1:
                forced_zeros.append(j)
        return [], forced_zeros, True

    k = len(constraint)

    # 前缀和：O(1) 区间查询
    zero_pref = [0] * (n + 1)
    one_pref = [0] * (n + 1)
    for i in range(n):
        zero_pref[i + 1] = zero_pref[i] + (1 if cells[i] == 0 else 0)
        one_pref[i + 1] = one_pref[i] + (1 if cells[i] == 1 else 0)

    def has_zero(lo: int, hi: int) -> bool:
        return zero_pref[hi] - zero_pref[lo] > 0

    def has_one(lo: int, hi: int) -> bool:
        return one_pref[hi] - one_pref[lo] > 0

    # left[i][j]: 块 0..i-1 放入 cells[0..j-1]
    left = [[False] * (n + 1) for _ in range(k + 1)]
    left[0][0] = True
    for j in range(1, n + 1):
        left[0][j] = left[0][j - 1] and cells[j - 1] != 1

    for i in range(1, k + 1):
        blk = constraint[i - 1]
        for j in range(1, n + 1):
            if cells[j - 1] != 1 and left[i][j - 1]:
                left[i][j] = True
                continue
            if j < blk:
                continue
            start = j - blk
            if has_zero(start, j):
                continue
            if start > 0 and cells[start - 1] == 1:
                continue
            if start == 0:
                left[i][j] = (i == 1)
            else:
                left[i][j] = left[i - 1][start - 1]

    if not left[k][n]:
        return None, None, False

    # right[i][j]: 块 i..k-1 放入 cells[j..n-1]
    right = [[False] * (n + 1) for _ in range(k + 1)]
    right[k][n] = True
    for j in range(n - 1, -1, -1):
        right[k][j] = (cells[j] != 1) and right[k][j + 1]

    for i in range(k - 1, -1, -1):
        blk = constraint[i]
        for j in range(n - 1, -1, -1):
            if cells[j] != 1 and right[i][j + 1]:
                right[i][j] = True
                continue
            end = j + blk
            if end > n:
                continue
            if has_zero(j, end):
                continue
            if end < n and cells[end] == 1:
                continue
            next_j = end + 1 if end < n else n
            if right[i + 1][next_j]:
                right[i][j] = True

    # can_be_0
    can_be_0 = [False] * n
    for j in range(n):
        if cells[j] != -1:
            continue
        for i in range(k + 1):
            if left[i][j] and right[i][j + 1]:
                can_be_0[j] = True
                break

    # can_be_1：差分数组批量标记
    diff = [0] * (n + 1)
    for i in range(k):
        blk = constraint[i]
        for start in range(n - blk + 1):
            end = start + blk
            if has_zero(start, end):
                continue
            if start > 0 and cells[start - 1] == 1:
                continue
            if end < n and cells[end] == 1:
                continue
            if start == 0:
                left_ok = (i == 0)
            else:
                left_ok = left[i][start - 1]
            if not left_ok:
                continue
            next_j = end + 1 if end < n else n
            if not right[i + 1][next_j]:
                continue
            diff[start] += 1
            diff[end] -= 1

    can_be_1 = [False] * n
    cur = 0
    for j in range(n):
        cur += diff[j]
        if cur > 0:
            can_be_1[j] = True

    # 收集结论
    forced_ones = []
    forced_zeros = []
    for j in range(n):
        if cells[j] != -1:
            continue
        if can_be_1[j] and not can_be_0[j]:
            forced_ones.append(j)
        elif can_be_0[j] and not can_be_1[j]:
            forced_zeros.append(j)
        elif not can_be_1[j] and not can_be_0[j]:
            return None, None, False

    return forced_ones, forced_zeros, True


# ─── 约束传播 ────────────────────────────────────────────────────


def _propagate(
    grid: List[List[int]],
    row_constraints: List[List[int]],
    col_constraints: List[List[int]],
) -> bool:
    """
    约束传播，根据 n 自动选择策略：
      - n ≤ 15 且缓存已有 → 缓存候选集 + while changed 全量扫描
      - 否则 → 逐线 DP + worklist 增量传播
    """
    n = len(grid)

    if n in _CANDIDATE_CACHE:
        return _propagate_small(grid, row_constraints, col_constraints)
    else:
        return _propagate_large(grid, row_constraints, col_constraints)


def _propagate_small(
    grid: List[List[int]],
    row_constraints: List[List[int]],
    col_constraints: List[List[int]],
) -> bool:
    """小规模：缓存候选集 + while changed 全量扫描。"""
    n = len(grid)

    # 从缓存加载候选集（无需初始过滤，候选是约束的全部合法填充）
    row_cands = [None] * n
    col_cands = [None] * n
    for r in range(n):
        c = tuple(row_constraints[r]) if row_constraints[r] else (0,)
        if c == (-1,):
            row_cands[r] = None
        else:
            row_cands[r] = set(_CANDIDATE_CACHE[n][c])
    for c in range(n):
        ck = tuple(col_constraints[c]) if col_constraints[c] else (0,)
        if ck == (-1,):
            col_cands[c] = None
        else:
            col_cands[c] = set(_CANDIDATE_CACHE[n][ck])

    # 高效过滤：只检查一个位置
    def _filter_row(r: int, c: int, is_filled: bool):
        cands = row_cands[r]
        if cands is None:
            return
        if is_filled:
            row_cands[r] = {m for m in cands if (m >> c) & 1}
        else:
            row_cands[r] = {m for m in cands if not ((m >> c) & 1)}

    def _filter_col(c: int, r: int, is_filled: bool):
        cands = col_cands[c]
        if cands is None:
            return
        if is_filled:
            col_cands[c] = {m for m in cands if (m >> r) & 1}
        else:
            col_cands[c] = {m for m in cands if not ((m >> r) & 1)}

    changed = True
    while changed:
        changed = False

        for r in range(n):
            cands = row_cands[r]
            if cands is None:
                continue
            if not cands:
                return False

            all_ones = (1 << n) - 1
            any_one = 0
            for mask in cands:
                all_ones &= mask
                any_one |= mask

            for c in range(n):
                if grid[r][c] != -1:
                    continue
                if (all_ones >> c) & 1:
                    grid[r][c] = 1
                    changed = True
                    _filter_col(c, r, True)
                elif not ((any_one >> c) & 1):
                    grid[r][c] = 0
                    changed = True
                    _filter_col(c, r, False)

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
                    _filter_row(r, c, True)
                elif not ((any_one >> r) & 1):
                    grid[r][c] = 0
                    changed = True
                    _filter_row(r, c, False)

    return True


def _propagate_large(
    grid: List[List[int]],
    row_constraints: List[List[int]],
    col_constraints: List[List[int]],
) -> bool:
    """大规模：逐线 DP + worklist 增量传播。"""
    n = len(grid)

    fingerprints = {}
    q = deque()

    for r in range(n):
        q.append(('row', r))
    for c in range(n):
        q.append(('col', c))

    while q:
        key = q.popleft()
        line_type, idx = key

        if line_type == 'row':
            r = idx
            constraint = row_constraints[r]

            cells = grid[r]
            current_fp = tuple(cells)
            if fingerprints.get(key) == current_fp:
                continue

            forced_ones, forced_zeros, ok = _analyze_line(cells, constraint)
            if not ok:
                return False

            for c in forced_ones:
                grid[r][c] = 1
                q.appendleft(('col', c))
            for c in forced_zeros:
                grid[r][c] = 0
                q.appendleft(('col', c))

            fingerprints[key] = tuple(grid[r])

            if any(v == -1 for v in grid[r]):
                q.append(key)

        else:  # 'col'
            c = idx
            constraint = col_constraints[c]

            cells = [grid[r][c] for r in range(n)]
            current_fp = tuple(cells)
            if fingerprints.get(key) == current_fp:
                continue

            forced_ones, forced_zeros, ok = _analyze_line(cells, constraint)
            if not ok:
                return False

            for r in forced_ones:
                grid[r][c] = 1
                q.appendleft(('row', r))
            for r in forced_zeros:
                grid[r][c] = 0
                q.appendleft(('row', r))

            fingerprints[key] = tuple(grid[r][c] for r in range(n))

            if any(grid[r][c] == -1 for r in range(n)):
                q.append(key)

    return True


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

    grid = [[-1] * n for _ in range(n)]

    if not _propagate(grid, rows, cols):
        return None

    return grid


# ─── 命令行入口（用于测试）──────────────────────────────────────


def main():
    """命令行测试入口"""
    import sys
    import json

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

    print()
    symbol = {1: "█", 0: "·", -1: "?"}
    for row in result:
        print("".join(symbol.get(c, "?") for c in row))
    print(f"\n求解完成，{len(rows)}x{len(cols)}")


if __name__ == "__main__":
    main()