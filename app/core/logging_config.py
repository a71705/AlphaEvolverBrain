# app/core/logging_config.py
# 导入 logging 模块用于日志记录
import logging
# 导入 os 模块以访问环境变量
import os
# 导入 sys 模块以访问 stdout
import sys

# 定义配置日志记录的函数
def configure_logging():
    # 从环境变量 "LOG_LEVEL" 获取日志级别，如果未设置，则默认为 "INFO"
    # .upper()确保级别字符串是大写的 (例如 "INFO", "DEBUG")
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()

    # 将字符串日志级别转换为 logging 模块对应的整数值
    # getattr(logging, log_level_str, logging.INFO) 会尝试获取 logging.DEBUG, logging.INFO 等
    # 如果字符串无效，则默认为 logging.INFO
    log_level = getattr(logging, log_level_str, logging.INFO)

    # 创建一个日志处理器 (Handler)，用于将日志记录发送到标准输出 (控制台)
    console_handler = logging.StreamHandler(sys.stdout)

    # 创建一个日志格式化器 (Formatter)
    # 定义日志输出的格式：时间 - Logger名称 - 日志级别 - 日志消息
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 将格式化器设置给控制台处理器
    console_handler.setFormatter(formatter)

    # 获取根 Logger
    # logging.getLogger() 不带参数时返回根 logger
    root_logger = logging.getLogger()

    # 设置根 Logger 的日志级别
    # 只有等于或高于此级别的日志消息才会被处理
    root_logger.setLevel(log_level)

    # 清除所有已存在的处理器，以避免重复输出或冲突
    # 这对于在应用重新加载或多次调用此配置函数时特别重要
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 将新配置的控制台处理器添加到根 Logger
    root_logger.addHandler(console_handler)

    # 为特定的第三方库 Logger 设置更精细的日志级别控制
    # 目的是减少在常规 INFO 级别下这些库产生的过多日志输出

    # SQLAlchemy Engine Logger:
    # 如果应用日志级别是 DEBUG，则将 SQLAlchemy Engine 的日志级别设置为 INFO (显示SQL查询)
    # 否则 (例如 INFO, WARNING, ERROR)，将其设置为 WARNING，以减少其输出
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO if log_level == logging.DEBUG else logging.WARNING)

    # RQ (Redis Queue) Logger:
    # 如果应用日志级别是 DEBUG，则将 RQ 的日志级别设置为 DEBUG
    # 否则 (例如 INFO, WARNING, ERROR)，将其设置为 INFO
    # logging.getLogger("rq").setLevel(logging.DEBUG if log_level == logging.DEBUG else logging.INFO)
    # logging.getLogger("rq.worker").setLevel(logging.DEBUG if log_level == logging.DEBUG else logging.INFO)
    # 更正后的逻辑：如果应用主日志级别 (log_level) 为 INFO 或更低 (如 DEBUG)，则 RQ 日志也应相应调整
    # 当主日志级别为 INFO 时，RQ 日志为 INFO
    # 当主日志级别为 DEBUG 时，RQ 日志为 DEBUG
    rq_log_level = logging.DEBUG if log_level == logging.DEBUG else logging.INFO
    logging.getLogger("rq").setLevel(rq_log_level)
    logging.getLogger("rq.worker").setLevel(rq_log_level)


    # 可以在此处添加一个测试日志消息，以验证配置是否生效
    # logging.info(f"日志系统已配置，当前日志级别: {log_level_str} ({log_level})")
