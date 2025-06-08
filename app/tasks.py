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

# 新增/确认的导入
from sqlalchemy.orm import Session # 用于类型提示数据库会话
from typing import Optional # 用于类型提示
from datetime import datetime # 用于时间戳

# 导入数据库相关的模块
from app.database import SessionLocal # 用于创建数据库会话
# from app.database import create_tables # 通常表已由 FastAPI 应用启动时创建

# 导入模型 (用于查询和更新 Experiment 对象)
from app.models import Experiment # 假设 Experiment 模型定义在 app.models 中

# 导入 Brain API 会话管理器
from app.core.brain_api import BrainApiSession

# 导入遗传算法核心阶段函数 (当前是占位符)
from app.core.gp_algo import best_d1_alphas, best_d2_alphas, best_d3_alpha


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


def run_genetic_algorithm_task(experiment_id: int, ga_config: dict):
    """
    执行遗传算法的主任务函数 (在 RQ Worker 中运行)。

    此任务负责：
    1. 初始化数据库会话和 Brain API 会话。
    2. 查询并更新实验（Experiment）的状态。
    3. 按顺序调用遗传算法的各个阶段函数（目前是占位符）。
    4. 处理执行过程中的异常，并相应地更新实验状态。
    5. 确保资源（如数据库会话）得到正确关闭。

    参数:
        experiment_id (int): 要运行的实验的 ID。
        ga_config (dict): 包含遗传算法所有配置参数的字典。
                           例如：种群大小、迭代次数、变异率、交叉率、
                           模拟参数、适应度评估标准等。
    """
    job = get_current_job()
    if job:
        logger.info(f"RQ 作业 {job.id}: 开始执行 run_genetic_algorithm_task，实验ID: {experiment_id}。")
    else:
        logger.info(f"直接调用 run_genetic_algorithm_task (非RQ上下文)，实验ID: {experiment_id}。")

    # 初始化数据库会话和 Brain API 会话
    db: Session = SessionLocal() # mypy 可能需要显式 Session 类型提示

    # 从环境变量获取 Brain API 凭据
    # 这些环境变量应该在 worker 服务的 docker-compose.yml 中设置
    brain_email = os.environ.get("BRAIN_CREDENTIAL_EMAIL")
    brain_password = os.environ.get("BRAIN_CREDENTIAL_PASSWORD")

    if not brain_email or not brain_password:
        logger.error(f"实验 {experiment_id}: Brain API 凭据未在环境变量中配置。任务无法继续。")
        # 更新实验状态为 FAILED (如果可以获取实验对象)
        experiment_obj = db.query(Experiment).filter(Experiment.id == experiment_id).first() # Renamed to avoid conflict
        if experiment_obj:
            experiment_obj.status = "FAILED"
            experiment_obj.error_message = "Brain API 凭据缺失导致任务失败。" # 假设 Experiment 模型有 error_message 字段
            db.add(experiment_obj)
            db.commit()
        db.close()
        # 抛出异常，让 RQ 知道任务失败
        raise ValueError("Brain API 凭据缺失，无法执行遗传算法任务。")

    brain_api = BrainApiSession(email=brain_email, password=brain_password)

    current_experiment: Optional[Experiment] = None # 类型提示, changed name from experiment to current_experiment
    try:
        # 1. 查询实验对象并更新状态为 RUNNING
        current_experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not current_experiment:
            logger.error(f"实验 {experiment_id}: 在数据库中未找到。任务终止。")
            # 无需更新状态，因为实验记录本身不存在
            raise ValueError(f"实验ID {experiment_id} 不存在。")

        logger.info(f"实验 {current_experiment.name} (ID: {experiment_id}): 状态从 {current_experiment.status} 更新为 RUNNING。")
        current_experiment.status = "RUNNING"
        # start_time 应该在实验创建时或首次提交到队列时设置，这里假设它可能已设置，
        # 或者如果GA任务是实验生命周期的开始，则在这里设置是合适的。
        if current_experiment.start_time is None: # 仅当尚未设置时才设置
             current_experiment.start_time = datetime.utcnow()
        db.add(current_experiment)
        db.commit()

        # 2. 调用遗传算法的各个阶段函数 (当前是占位符)
        # 这些函数应接收 brain_api, db, experiment_id/current_experiment, ga_config 等
        # 并负责内部的Alpha生成、模拟、评估、存储。

        logger.info(f"实验 {experiment_id}: 开始调用 best_d1_alphas...")
        d1_results = best_d1_alphas(brain_api, db, experiment_id, ga_config)
        logger.info(f"实验 {experiment_id}: best_d1_alphas 完成，返回 {len(d1_results)} 个结果 (占位符)。")
        # 可以在此处理 d1_results，例如选择优秀的进入下一阶段

        logger.info(f"实验 {experiment_id}: 开始调用 best_d2_alphas...")
        d2_results = best_d2_alphas(brain_api, db, experiment_id, ga_config, previous_generation_alphas=d1_results)
        logger.info(f"实验 {experiment_id}: best_d2_alphas 完成，返回 {len(d2_results)} 个结果 (占位符)。")

        logger.info(f"实验 {experiment_id}: 开始调用 best_d3_alpha...")
        d3_results = best_d3_alpha(brain_api, db, experiment_id, ga_config, previous_generation_alphas=d2_results)
        logger.info(f"实验 {experiment_id}: best_d3_alpha 完成，返回 {len(d3_results)} 个结果 (占位符)。")

        # 3. 如果所有阶段成功完成，更新实验状态为 COMPLETED
        logger.info(f"实验 {current_experiment.name} (ID: {experiment_id}): 所有遗传算法阶段成功完成。状态更新为 COMPLETED。")
        current_experiment.status = "COMPLETED"
        current_experiment.end_time = datetime.utcnow()
        current_experiment.error_message = None # 清除之前的错误信息（如果有）
        db.add(current_experiment)
        db.commit()

        if job:
             logger.info(f"RQ 作业 {job.id}: run_genetic_algorithm_task 成功完成，实验ID: {experiment_id}。")

    except Exception as e:
        logger.error(f"实验 {experiment_id}: 在执行 run_genetic_algorithm_task 过程中发生严重错误: {e}", exc_info=True)
        if current_experiment: # 如果实验对象已加载
            logger.error(f"实验 {current_experiment.name} (ID: {experiment_id}): 因错误将状态更新为 FAILED。")
            current_experiment.status = "FAILED"
            current_experiment.end_time = datetime.utcnow()
            current_experiment.error_message = str(e)[:500] # 限制错误信息长度以适应数据库字段
            db.add(current_experiment)
            try:
                db.commit()
            except Exception as db_err:
                logger.error(f"实验 {experiment_id}: 更新实验状态为 FAILED 时数据库提交失败: {db_err}", exc_info=True)
                db.rollback() # 回滚失败的提交尝试

        if job:
            logger.error(f"RQ 作业 {job.id}: run_genetic_algorithm_task 执行失败，实验ID: {experiment_id}。")

        raise # 重新抛出异常，RQ会将作业标记为失败

    finally:
        # 确保数据库会话总是被关闭
        if db:
            db.close()
            logger.debug(f"实验 {experiment_id}: 数据库会话已关闭。")

# 后续将在此文件定义具体的 RQ 任务函数，例如 test_task。
# 以及将来更复杂的任务，如 run_genetic_algorithm_task。
