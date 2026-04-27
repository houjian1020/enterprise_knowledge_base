#================================================================
#日志配置
#================================================================
import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """
    获取一个配置好的日志记录器
    :param name: 通常是 __name__，用于标识日志来源
    :return: 配置好的 Logger 实例
    """
    logger = logging.getLogger(name)

    # 如果已经配置过，直接返回，避免重复配置
    if logger.handlers:
        return logger

    # 设置日志器的总级别
    logger.setLevel(logging.DEBUG)

    # 1. 定义日志格式
    # 格式：时间 - 级别 - 模块名:行号 - 消息
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 2. 配置控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)  # 控制台显示所有级别日志
    console_handler.setFormatter(formatter)

    # 3. 配置文件处理器
    # 将日志写入 app.log 文件
    file_handler = logging.FileHandler("app.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)  # 文件只记录 INFO 及以上级别的重要日志
    file_handler.setFormatter(formatter)

    # 4. 将处理器添加到日志器
    logger.addHandler(console_handler)
    #logger.addHandler(file_handler)  # 写日志到本地磁盘

    return logger