
import json
import argparse
from pathlib import Path

from bugcatcher_constants import JSONKeys

class BugCatcherSolver:
    """
    田地捉虫 (Star Battle) 求解器
    使用回溯算法来解决基于约束的谜题。
    """

    def __init__(self, puzzle_data):
        """
        初始化求解器

        Args:
            puzzle_data (dict): 从 result.json 加载的谜题数据
        """
        self.rows = puzzle_data[JSONKeys.GRID_INFO][JSONKeys.ROWS]
        self.cols = puzzle_data[JSONKeys.GRID_INFO][JSONKeys.COLS]
        self.color_matrix = puzzle_data[JSONKeys.COLOR_MATRIX]

        # 棋盘状态: 0=空, 1=虫子
        self.board = [[0] * self.cols for _ in range(self.rows)]
        self.solution = []

    def is_valid(self, r, c):
        """
        检查在 (r, c) 位置放置虫子是否有效。
        只检查与已经放置的虫子的冲突。

        Args:
            r (int): 行
            c (int): 列

        Returns:
            bool: 是否有效
        """
        # 1. 检查相邻位置 (包括对角线)
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols and self.board[nr][nc] == 1:
                    return False
        return True

    def solve(self):
        """
        启动回溯求解过程
        """
        # 记录已使用的列和颜色区域
        self.used_cols = [False] * self.cols
        self.used_regions = {} # color_id -> bool

        if self._backtrack(0):
            print("✓ 成功找到解决方案！")
            self.solution = []
            for r in range(self.rows):
                for c in range(self.cols):
                    if self.board[r][c] == 1:
                        self.solution.append((r, c))
            return self.solution
        else:
            print("❌ 未能找到解决方案。")
            return None

    def _backtrack(self, r):
        """
        回溯核心函数，尝试在第 r 行放置一个虫子
        """
        # 如果所有行都已成功放置，说明找到解
        if r == self.rows:
            return True

        # 遍历当前行的所有列
        for c in range(self.cols):
            color_id = self.color_matrix[r][c]

            # 剪枝: 检查列约束、区域约束和相邻约束
            if not self.used_cols[c] and not self.used_regions.get(color_id, False) and self.is_valid(r, c):

                # 做出选择
                self.board[r][c] = 1
                self.used_cols[c] = True
                self.used_regions[color_id] = True

                # 进入下一行决策
                if self._backtrack(r + 1):
                    return True

                # 撤销选择 (回溯)
                self.board[r][c] = 0
                self.used_cols[c] = False
                self.used_regions[color_id] = False

        # 如果当前行的所有列都无法放置，则返回False
        return False

def solve_puzzle(puzzle_data):
    """主逻辑封装，接收一个 puzzle_data 字典进行求解"""
    print("\n正在加载谜题数据...")

    solver = BugCatcherSolver(puzzle_data)
    solution = solver.solve()

    if solution:
        print("\n虫子位置坐标 (行, 列):")
        solution.sort()
        for pos in solution:
            print(f"- {pos}")

        print("\n解决方案棋盘视图 ( B 表示虫子):")
        board_view = [['.' for _ in range(solver.cols)] for _ in range(solver.rows)]
        for r, c in solution:
            board_view[r][c] = 'B'
        for row_view in board_view:
            print(' '.join(row_view))

        return solution
    return None

def main():
    parser = argparse.ArgumentParser(description='田地捉虫 (Star Battle) 求解器')
    parser.add_argument('input_file', nargs='?', default='result.json', help='包含谜题数据的JSON文件路径 (默认: result.json)')
    args = parser.parse_args()

    puzzle_path = Path(args.input_file)
    if not puzzle_path.exists():
        print(f"错误: 输入文件不存在 -> {puzzle_path}")
        return

    # 为了保持命令行可用，这里读取文件并传递数据
    with open(puzzle_path, 'r', encoding='utf-8') as f:
        puzzle_data = json.load(f)

    solve_puzzle(puzzle_data)

if __name__ == '__main__':
    main()
