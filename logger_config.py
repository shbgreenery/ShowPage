import logging
import sys

def setup_logger(debug=False):
    """
    配置全局日志记录器
    """
    level = logging.DEBUG if debug else logging.INFO

    # 获取根日志记录器
    logger = logging.getLogger()
    logger.setLevel(level)

    # 如果已经有处理器，则先移除，防止重复添加
    if logger.hasHandlers():
        logger.handlers.clear()

    # 创建一个流处理器，将日志输出到控制台
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # 创建一个格式化器
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    # 将处理器添加到日志记录器
    logger.addHandler(handler)
