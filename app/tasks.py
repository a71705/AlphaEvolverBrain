# 导入 logging 模块，用于在任务函数中记录日志。
import logging
# 导入 time 模块，例如用于在测试任务中模拟耗时操作。
import time
# 导入 os 模块，用于访问环境变量（如果任务需要配置）。
import os

# 从 rq 包导入 get_current_job，用于在任务执行时获取当前作业的相关信息。
from rq import get_current_job

# 导入数据库会话管理和表创建函数（尽管简单测试任务可能不直接使用，但为后续复杂任务做准备）。
# from app.database import SessionLocal, create_tables # 暂时注释，如果test_task简单则不需要
# 导入 BrainApiSession（同样为后续复杂任务做准备）。
# from app.core.brain_api import BrainApiSession # 暂时注释

# 获取一个日志记录器实例，通常以当前模块名命名。
logger = logging.getLogger(__name__)

def test_task(name: str, delay: int = 5) -> str:
    """
    一个简单的 RQ 测试任务函数。

    此任务接收一个名称和一个可选的延迟时间，模拟执行一些工作，
    并记录相关信息，然后返回一个问候字符串。

    参数:
        name (str): 要在问候语中使用的名称。
        delay (int): 模拟工作所需的秒数。默认为 5 秒。

    返回:
        str: 一个包含问候语的字符串，例如 "你好，[name]！任务已完成。"
    """
    # 获取当前正在执行的 RQ 作业对象
    job = get_current_job()
    if job:
        logger.info(f"开始执行测试任务 test_task。作业ID: {job.id}，参数 name='{name}', delay={delay}秒。")
    else:
        # 如果任务不是通过 RQ worker 执行的（例如直接调用），job 可能为 None
        logger.info(f"开始执行测试任务 test_task (非 RQ 作业上下文)。参数 name='{name}', delay={delay}秒。")

    # 模拟耗时的工作
    logger.info(f"任务 test_task ({name}): 正在模拟工作，将持续 {delay} 秒...")
    time.sleep(delay)

    result_message = f"你好，{name}！测试任务已在 {delay} 秒后完成。"

    if job:
        logger.info(f"测试任务 test_task ({name}) 完成。作业ID: {job.id}。结果: {result_message}")
    else:
        logger.info(f"测试任务 test_task ({name}) 完成。结果: {result_message}")

    return result_message

# 示例：如果直接运行此文件进行测试（非标准用法，通常由 worker 调用）
# if __name__ == '__main__':
#     # 配置日志以便在控制台看到输出
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     logger.info("直接调用 test_task 进行测试...")
#     output = test_task("开发者", delay=2)
#     logger.info(f"直接调用结果: {output}")

# 后续将在此文件定义具体的 RQ 任务函数，例如 test_task。
# 以及将来更复杂的任务，如 run_genetic_algorithm_task。
