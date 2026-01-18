"""
数织求解算法
"""

import json
from typing import List, Set

from .constants import UNKNOWN, FILLED, EMPTY


class NonogramSolver:
    """数织求解算法"""

    def __init__(self, rows: List[List[int]], cols: List[List[int]]):
        """
        初始化求解器

        Args:
            rows: 行约束列表
            cols: 列约束列表
        """
        self.rows = rows
        self.cols = cols
        self.n = len(rows)
        if self.n != len(cols):
            raise ValueError("行数和列数不一致")

    def solve(self) -> List[List[int]]:
        """
        求解数织谜题

        Returns:
            求解结果网格，每个格子为 UNKNOWN, FILLED 或 EMPTY
        """
        n = self.n
        ans = [[UNKNOWN for _ in range(n)] for _ in range(n)]

        # 创建所有可能状态的映射
        cs = self._create_state_mapping(n)

        # 初始化行和列的可能状态集合
        prow = [set() for _ in range(n)]
        pcol = [set() for _ in range(n)]

        self._initialize_possible_states(prow, pcol, cs, n)

        # 迭代直到没有变化
        while True:
            change = False

            # 处理行
            for i in range(n):
                if self._process_row(ans, prow, pcol, i, n):
                    change = True

            # 处理列
            for i in range(n):
                if self._process_column(ans, prow, pcol, i, n):
                    change = True

            if not change:
                break

        return ans

    def _create_state_mapping(self, n: int) -> dict:
        """创建所有可能状态的映射"""
        cs = {}
        for state in range(1 << n):
            str_state = self._int2str(state, n)
            arr_state = self._str2arr(str_state)

            arr_key = json.dumps(arr_state)
            if arr_key not in cs:
                cs[arr_key] = []
            cs[arr_key].append(str_state)

            # 为未确定的线索添加所有状态
            unmarked_key = json.dumps([-1])
            if unmarked_key not in cs:
                cs[unmarked_key] = []
            cs[unmarked_key].append(str_state)

        return cs

    def _initialize_possible_states(self, prow: List[Set[str]], pcol: List[Set[str]],
                                    cs: dict, n: int):
        """初始化行和列的可能状态集合"""
        for i in range(n):
            row_key = json.dumps(self.rows[i])
            if row_key in cs:
                prow[i].update(cs[row_key])

            col_key = json.dumps(self.cols[i])
            if col_key in cs:
                pcol[i].update(cs[col_key])

    def _process_row(self, ans: List[List[int]], prow: List[Set[str]],
                     pcol: List[Set[str]], i: int, n: int) -> bool:
        """处理一行"""
        ps = prow[i]
        cnt = [0] * n

        for p in ps:
            for j in range(n):
                if p[j] == '1':
                    cnt[j] += 1

        change = False
        for j in range(n):
            if ans[i][j] == EMPTY and cnt[j] == len(ps):
                raise ValueError(f"冲突在位置 ({i}, {j})")
            if ans[i][j] == UNKNOWN and cnt[j] == len(ps):
                self._f1(ans, i, j, prow, pcol)
                change = True
            if ans[i][j] == FILLED and cnt[j] == 0:
                raise ValueError(f"冲突在位置 ({i}, {j})")
            if ans[i][j] == UNKNOWN and cnt[j] == 0:
                self._f0(ans, i, j, prow, pcol)
                change = True

        return change

    def _process_column(self, ans: List[List[int]], prow: List[Set[str]],
                        pcol: List[Set[str]], i: int, n: int) -> bool:
        """处理一列"""
        ps = pcol[i]
        cnt = [0] * n

        for p in ps:
            for j in range(n):
                if p[j] == '1':
                    cnt[j] += 1

        change = False
        for j in range(n):
            if ans[j][i] == EMPTY and cnt[j] == len(ps):
                raise ValueError(f"冲突在位置 ({j}, {i})")
            if ans[j][i] == FILLED and cnt[j] == 0:
                raise ValueError(f"冲突在位置 ({j}, {i})")
            if ans[j][i] == UNKNOWN and cnt[j] == len(ps):
                self._f1(ans, j, i, prow, pcol)
                change = True
            if ans[j][i] == UNKNOWN and cnt[j] == 0:
                self._f0(ans, j, i, prow, pcol)
                change = True

        return change

    @staticmethod
    def _int2str(i: int, n: int) -> str:
        """将整数转换为二进制字符串"""
        si = bin(i)[2:]
        return '0' * (n - len(si)) + si

    @staticmethod
    def _str2arr(s: str) -> List[int]:
        """将二进制字符串转换为数组"""
        tmp = []
        for i, c in enumerate(s):
            if c == '1':
                if i == 0 or s[i - 1] == '0':
                    tmp.append(1)
                else:
                    tmp[-1] += 1
        return tmp

    def _f1(self, ans: List[List[int]], i: int, j: int,
            prow: List[Set[str]], pcol: List[Set[str]]):
        """设置格子为填充"""
        ans[i][j] = FILLED
        for p in list(prow[i]):
            if p[j] == '0':
                prow[i].remove(p)
        for p in list(pcol[j]):
            if p[i] == '0':
                pcol[j].remove(p)

    def _f0(self, ans: List[List[int]], i: int, j: int,
            prow: List[Set[str]], pcol: List[Set[str]]):
        """设置格子为空白"""
        ans[i][j] = EMPTY
        for p in list(prow[i]):
            if p[j] == '1':
                prow[i].remove(p)
        for p in list(pcol[j]):
            if p[i] == '1':
                pcol[j].remove(p)