#!/usr/bin/env python3
"""
数织求解器 - 主入口
"""

from nonogram_app import NonogramApp


def main():
    """主函数"""
    app = NonogramApp()
    app.mainloop()


if __name__ == "__main__":
    main()