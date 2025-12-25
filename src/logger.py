import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import os
import config

def setup_logger(name=__name__, log_dir=config.log_dir):

    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 获取logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 避免重复添加处理器
    if not logger.handlers:
        # 设置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s:%(message)s\n',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 按时间轮转的文件处理器（每天轮转）
        file_handler = TimedRotatingFileHandler(
            filename=log_path / config.log_name,
            when="midnight",  # 每天午夜轮转
            interval=1,  # 每天一次
            backupCount=config.log_backup_num,  # 保留14天
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)

        # 添加处理器
        logger.addHandler(file_handler)

    return logger

log = setup_logger()
