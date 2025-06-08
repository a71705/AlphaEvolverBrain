# app/tasks.py
# 此文件用于定义 RQ (Redis Queue) 的后台任务函数。

import logging  # Python 标准日志库
import time     # 用于模拟耗时操作，例如 time.sleep()
import os       # 用于访问环境变量 (如果任务需要)

from rq import get_current_job  # 从 RQ 库导入函数以获取当前正在执行的任务对象

# (为未来更复杂的任务预留导入，当前 test_task 不需要它们)
# from app.database import SessionLocal  # 用于在任务中访问数据库
# from app.core.brain_api import BrainApiSession # 用于在任务中调用 Brain API

# 获取当前模块的 logger 实例
# 日志将以 "app.tasks" 的名称记录
logger = logging.getLogger(__name__)

def test_task(name: str) -> str:
    """
    一个简单的 RQ 测试任务。
    它会记录一些信息，暂停一段时间模拟工作，然后返回一个问候字符串。

    Args:
        name (str): 要在问候中使用的名字。

    Returns:
        str: 包含名字的问候字符串。
    """
    job = get_current_job() # 获取当前 RQ 任务对象，可以访问其属性如 id

    # 在任务开始时记录日志，包含任务ID和输入参数
    # 注意：日志级别 (INFO, DEBUG 等) 和输出位置由 DEV-004 中配置的日志系统决定
    logger.info(f"开始执行 test_task，任务 ID: {job.id if job else 'Unknown_JobID'}, 参数 name: '{name}'")

    # 模拟一些耗时的工作，例如5秒
    try:
        logger.info(f"test_task ({job.id if job else 'N/A'}): 正在模拟工作...")
        time.sleep(5)
        result = f"你好, {name}! RQ 任务 (ID: {job.id if job else 'N/A'}) 已成功执行。"
        logger.info(f"test_task ({job.id if job else 'N/A'}): 模拟工作完成。")
    except Exception as e:
        logger.error(f"test_task ({job.id if job else 'N/A'}) 执行期间发生错误: {e}", exc_info=True)
        # 在实际应用中，根据错误类型和重试策略，可能需要重新抛出异常
        # 或者返回一个表示失败的特定结果
        result = f"任务 (ID: {job.id if job else 'N/A'}) 执行失败: {e}"
        # raise # 如果希望 RQ 将任务标记为 failed 并根据配置进行重试

    # 在任务结束时记录日志
    logger.info(f"test_task ({job.id if job else 'Unknown_JobID'}) 执行完毕。")

    return result

# 以后可以在此文件定义更多复杂的后台任务，例如：
# def run_genetic_algorithm_task(experiment_id: int, ga_config: dict): # experiment_id 应该是整数（如果对应DB ID）
#     logger.info(f"开始执行遗传算法任务，实验ID: {experiment_id}")
#     # ... 具体的遗传算法逻辑 ...
#     # db = SessionLocal()
#     # try:
#     #     experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
#     #     if not experiment:
#     #         logger.error(f"实验 {experiment_id} 未找到。")
#     #         return {"status": "error", "message": "Experiment not found"}
#     #     # ... 更新实验状态 ...
#     #     # ... 执行GA ...
#     #     # ... 保存结果 ...
#     # finally:
#     #     db.close()
#     # ... 可能需要调用 Brain API (BrainApiSession) ...
#     logger.info(f"遗传算法任务 {experiment_id} 完成。")
#     return {"status": "completed", "experiment_id": experiment_id}
