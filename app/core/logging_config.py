# 导入 logging 模块，用于配置和使用日志记录器。
import logging
# 导入 os 模块，用于访问环境变量。
import os
# 导入 sys 模块，用于访问标准输出 (stdout)。
import sys

# 定义配置日志系统的函数。
def configure_logging():
    # 从环境变量 "LOG_LEVEL" 获取日志级别，如果未设置，则默认为 "INFO"。
    # .upper()确保级别字符串是大写的 (例如 "INFO", "DEBUG")。
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()

    # 将字符串日志级别转换为 logging 模块对应的整数级别。
    # getattr 获取 logging 模块中名为 log_level_str 的属性值。
    # 如果获取失败 (例如，LOG_LEVEL 设置为无效值)，则默认为 logging.INFO。
    log_level = getattr(logging, log_level_str, logging.INFO)

    # 创建一个控制台处理器 (StreamHandler)，将日志输出到标准输出 (sys.stdout)。
    console_handler = logging.StreamHandler(sys.stdout)

    # 定义日志格式。
    # %(asctime)s: 日志记录时间。
    # %(name)s: 日志记录器的名称 (通常是模块名)。
    # %(levelname)s: 日志级别 (例如 INFO, WARNING, ERROR)。
    # %(message)s: 实际的日志消息。
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # 将定义的格式器应用到控制台处理器。
    console_handler.setFormatter(formatter)

    # 获取根日志记录器。
    root_logger = logging.getLogger()
    # 设置根日志记录器的级别。只有等于或高于此级别的日志才会被处理。
    root_logger.setLevel(log_level)

    # 清除根日志记录器中任何已存在的处理器。
    # 这可以防止在多次调用 configure_logging (例如在测试中) 时重复添加处理器。
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 将新配置的控制台处理器添加到根日志记录器。
    root_logger.addHandler(console_handler)

    # 为特定的第三方库设置日志级别，以控制其日志输出的详细程度。
    # 例如，SQLAlchemy 的日志可能非常冗长，在 INFO 级别下可以将其设置为 WARNING。
    # 如果应用本身的日志级别是 DEBUG，则可能希望看到更详细的库日志。

    # 如果应用日志级别为 INFO，则将 sqlalchemy.engine 的日志级别设置为 WARNING，以减少不必要的输出。
    # 否则 (例如应用级别为 DEBUG)，则将 sqlalchemy.engine 的日志级别设置为 INFO，以获取更详细的数据库操作日志。
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING if log_level_str == "INFO" else logging.INFO)

    # 类似地，为 RQ (Redis Queue) 库设置日志级别。
    # 如果应用日志级别为 INFO，则将 rq 的日志级别设置为 INFO。
    # 否则 (例如应用级别为 DEBUG)，则将 rq 的日志级别设置为 DEBUG，以获取更详细的队列操作日志。
    logging.getLogger("rq").setLevel(logging.INFO if log_level_str == "INFO" else logging.DEBUG)

    # 可以在此处为其他库添加类似的配置
    # logging.getLogger("another_library").setLevel(logging.WARNING)

    # 打印一条日志消息，确认日志系统已配置 (可选，主要用于调试)。
    # logging.info(f"日志系统已配置。当前日志级别: {log_level_str}")
