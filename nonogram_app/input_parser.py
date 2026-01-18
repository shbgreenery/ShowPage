"""
输入解析器
"""

from typing import List, Tuple, Tuple


class InputParser:
    """解析数织约束输入"""

    @staticmethod
    def parse_constraints(text: str) -> List[List[int]]:
        """
        解析约束输入

        Args:
            text: 输入文本，每行代表一个约束，数字间用空格分隔
                  使用 '?' 表示未确定的约束

        Returns:
            约束列表，每个约束是一个整数列表
        """
        if not text or not text.strip():
            return []

        lines = text.strip().split('\n')
        result = []

        for line in lines:
            tokens = line.strip().split()
            row = []
            for token in tokens:
                if token == '?':
                    row.append(-1)
                elif token.lstrip('-').isdigit():
                    row.append(int(token))
            if row:
                result.append(row)

        return result

    @staticmethod
    def validate_constraints(rows: List[List[int]], cols: List[List[int]]) -> Tuple[bool, str]:
        """
        验证约束是否有效

        Args:
            rows: 行约束
            cols: 列约束

        Returns:
            (是否有效, 错误消息)
        """
        if not rows or not cols:
            return False, "请输入有效的行和列约束"

        if len(rows) > 20 or len(cols) > 20:
            return False, "行数和列数不能超过20"

        if len(rows) != len(cols):
            return False, "行数和列数必须相等"

        return True, ""