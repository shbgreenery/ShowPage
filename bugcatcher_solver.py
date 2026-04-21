import json
import argparse
from pathlib import Path
import logging

from bugcatcher_constants import JSONKeys
from logger_config import setup_logger

logger = logging.getLogger(__name__)


class BugCatcherSolver:
    """
    田地捉虫 (Star Battle) 求解器
    使用回溯算法来解决基于约束的谜题。
    """

    def __init__(self, puzzle_data):
        self.rows = puzzle_data[JSONKeys.GRID_INFO][JSONKeys.ROWS]
        self.cols = puzzle_data[JSONKeys.GRID_INFO][JSONKeys.COLS]
        self.color_matrix = puzzle_data[JSONKeys.COLOR_MATRIX]
        self.board = [[0] * self.cols for _ in range(self.rows)]
        self.solution = []

    def is_valid(self, r, c):
        """
        检查在 (r, c) 位置放置虫子是否有效。
        只检查与已经放置的虫子的冲突。
        """
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
        self.used_cols = [False] * self.cols
        self.used_regions = {}

        if self._backtrack(0):
            logger.info("成功找到解决方案！")
            self.solution = [(r, c) for r in range(self.rows) for c in range(self.cols) if self.board[r][c] == 1]
            return self.solution
        else:
            logger.warning("未能找到解决方案。")
            return None

    def _backtrack(self, r):
        """
        回溯核心函数，尝试在第 r 行放置一个虫子
        """
        if r == self.rows:
            return True

        for c in range(self.cols):
            color_id = self.color_matrix[r][c]

            if not self.used_cols[c] and not self.used_regions.get(color_id, False) and self.is_valid(r, c):
                self.board[r][c] = 1
                self.used_cols[c] = True
                self.used_regions[color_id] = True

                if self._backtrack(r + 1):
                    return True

                self.board[r][c] = 0
                self.used_cols[c] = False
                self.used_regions[color_id] = False

        return False

def solve_puzzle(puzzle_data):
    """主逻辑封装，接收一个 puzzle_data 字典进行求解"""
    logger.debug("开始求解“田地捉虫”谜题...")

    solver = BugCatcherSolver(puzzle_data)
    solution = solver.solve()

    if solution:
        solution.sort()
        logger.debug(f"解决方案包含 {len(solution)} 个虫子，位置 (行, 列): {solution}")

        if logger.isEnabledFor(logging.DEBUG):
            board_view = [['.' for _ in range(solver.cols)] for _ in range(solver.rows)]
            for r, c in solution:
                board_view[r][c] = 'B'
            board_str = "\n" + "\n".join([' '.join(row) for row in board_view])
            logger.debug(f"解决方案棋盘视图 (B 表示虫子):{board_str}")

        return solution
    return None

def main():
    parser = argparse.ArgumentParser(description='田地捉虫 (Star Battle) 求解器')
    parser.add_argument('input_file', nargs='?', default='result.json', help='包含谜题数据的JSON文件路径 (默认: result.json)')
    parser.add_argument('--debug', action='store_true', help='开启调试模式，显示详细日志')
    args = parser.parse_args()

    setup_logger(args.debug)

    puzzle_path = Path(args.input_file)
    if not puzzle_path.exists():
        logger.error(f"输入文件不存在 -> {puzzle_path}")
        return

    logger.info(f"从 {puzzle_path} 加载谜题数据...")
    with open(puzzle_path, 'r', encoding='utf-8') as f:
        puzzle_data = json.load(f)

    solve_puzzle(puzzle_data)

if __name__ == '__main__':
    main()
