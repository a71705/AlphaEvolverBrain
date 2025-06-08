# app/tasks.py
# 此文件用于定义 RQ (Redis Queue) 的后台任务函数。

import logging  # Python 标准日志库
import time     # 用于模拟耗时操作，例如 time.sleep()
import os       # 用于访问环境变量 (如果任务需要)
from datetime import datetime # 用于更新时间戳
from typing import Dict, Any, Optional, List # 类型提示

from rq import get_current_job  # 从 RQ 库导入函数以获取当前正在执行的任务对象
from sqlalchemy.orm import Session # 用于类型提示 db_session

from app.database import SessionLocal # 用于创建数据库会话
from app.models import Experiment, Alpha # Alpha 模型也可能需要
from app.core.brain_api import BrainApiSession, AuthenticationError, PersonaLoginError # Brain API交互
# 从 gp_algo 导入核心GA执行函数和初始种群生成函数
from app.core.gp_algo import (
    generate_initial_population,
    _run_ga_generation,
    Node # Node 类型也需要被导入，因为 current_population_nodes 是 List[Node]
    # tree_to_alpha, # 仅在需要直接调用时导入，目前主要在 _run_ga_generation 内部使用
    # alpha_to_tree, # 仅在需要直接调用时导入 (例如，从DB恢复时)
)


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
    job = get_current_job()
    logger.info(f"开始执行 test_task，任务 ID: {job.id if job else 'Unknown_JobID'}, 参数 name: '{name}'")
    try:
        logger.info(f"test_task ({job.id if job else 'N/A'}): 正在模拟工作...")
        time.sleep(5)
        result = f"你好, {name}! RQ 任务 (ID: {job.id if job else 'N/A'}) 已成功执行。"
        logger.info(f"test_task ({job.id if job else 'N/A'}): 模拟工作完成。")
    except Exception as e:
        logger.error(f"test_task ({job.id if job else 'N/A'}) 执行期间发生错误: {e}", exc_info=True)
        result = f"任务 (ID: {job.id if job else 'N/A'}) 执行失败: {e}"
    logger.info(f"test_task ({job.id if job else 'Unknown_JobID'}) 执行完毕。")
    return result


def run_genetic_algorithm_task(experiment_id: int, ga_config: Dict[str, Any]):
    """
    执行遗传算法的主任务。
    此任务由 RQ worker 调用。

    Args:
        experiment_id (int): 要运行的实验的 ID。
        ga_config (Dict[str, Any]): 遗传算法的配置参数字典。
                                   例如: generations, population_size, max_initial_depth,
                                         num_parents_to_select, crossover_rate, mutation_rate,
                                         selection_method, simulation_settings, etc.
    """
    job = get_current_job()
    task_job_id = job.id if job else 'N/A'
    logger.info(f"开始执行 run_genetic_algorithm_task (任务ID: {task_job_id}) for 实验ID: {experiment_id}")
    logger.debug(f"GA 配置: {ga_config}")

    db: Optional[Session] = None
    brain_api: Optional[BrainApiSession] = None
    experiment: Optional[Experiment] = None # 确保 experiment 在 try 块外可访问（用于 finally 或后续错误处理）

    try:
        db = SessionLocal()

        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment:
            logger.error(f"实验ID {experiment_id} 未在数据库中找到。任务终止。")
            return {"status": "error", "message": f"Experiment ID {experiment_id} not found."}

        try:
            brain_api = BrainApiSession()
            logger.info("BrainApiSession 初始化成功。")
        except (AuthenticationError, PersonaLoginError, ValueError) as auth_exc:
            logger.error(f"BrainApiSession 初始化失败: {auth_exc}", exc_info=True)
            experiment.status = "FAILED"; experiment.end_time = datetime.utcnow()
            # experiment.error_message = f"Brain API Auth Error: {str(auth_exc)[:250]}" # 如果有 error_message 字段
            db.add(experiment); db.commit()
            raise # 重新抛出异常，让 RQ 标记任务失败
        except Exception as e:
            logger.error(f"BrainApiSession 初始化时发生未知错误: {e}", exc_info=True)
            experiment.status = "FAILED"; experiment.end_time = datetime.utcnow()
            # experiment.error_message = f"Brain API Init Error: {str(e)[:250]}"
            db.add(experiment); db.commit()
            raise

        experiment.status = "RUNNING"
        if experiment.start_time is None: experiment.start_time = datetime.utcnow()
        db.add(experiment); db.commit()
        logger.info(f"实验 {experiment_id} 状态更新为 RUNNING。")

        num_generations = ga_config.get("generations", 10)
        population_size = ga_config.get("population_size", 50)
        max_initial_depth = ga_config.get("max_initial_depth", 3)

        current_population_nodes: List[Node] = []

        if experiment.current_iteration == 0:
            logger.info(f"实验 {experiment_id}: 生成初始种群...")
            current_population_nodes = generate_initial_population(
                size=population_size, max_initial_depth=max_initial_depth, config=ga_config
            )
        else:
            # TODO DEV-015: 实现从数据库加载上一代种群的逻辑
            logger.info(f"实验 {experiment_id}: 尝试从第 {experiment.current_iteration} 代继续 (当前简化为重新生成)。")
            current_population_nodes = generate_initial_population(
                size=population_size, max_initial_depth=max_initial_depth, config=ga_config
            )

        if not current_population_nodes:
            logger.error(f"实验 {experiment_id}: 初始种群为空，无法继续。")
            experiment.status = "FAILED"
            # experiment.error_message = "Initial population generation failed."
            experiment.end_time = datetime.utcnow()
            db.add(experiment); db.commit()
            return {"status": "error", "message": "Initial population was empty."}

        for gen_num in range(experiment.current_iteration, num_generations):
            current_gen_display = gen_num + 1 # 用于日志的代数 (从1开始)
            logger.info(f"实验 {experiment_id}: 开始第 {current_gen_display}/{num_generations} 代遗传算法...")

            next_gen_nodes = _run_ga_generation(
                current_population_nodes=current_population_nodes, brain_session=brain_api,
                db_session=db, experiment_id=experiment.id,
                current_iteration=current_gen_display, # 传递当前正在运行的代数
                ga_config=ga_config
            )

            if not next_gen_nodes:
                logger.error(f"实验 {experiment_id}: 第 {current_gen_display} 代未能生成有效后代。终止GA。")
                experiment.status = "FAILED"
                # experiment.error_message = f"Generation {current_gen_display} failed to produce offspring."
                break

            current_population_nodes = next_gen_nodes
            experiment.current_iteration = current_gen_display

            # TODO DEV-015: 实现更详细的进度报告 (例如更新 job.meta)
            db.add(experiment); db.commit()
            logger.info(f"实验 {experiment_id}: 第 {current_gen_display} 代完成。")

        if experiment.status == "RUNNING":
            experiment.status = "COMPLETED"
            experiment.end_time = datetime.utcnow()
            logger.info(f"实验 {experiment_id} 所有代数完成，状态更新为 COMPLETED。")

        db.add(experiment); db.commit()
        return {"status": experiment.status, "experiment_id": experiment.id, "generations_completed": experiment.current_iteration}

    except Exception as e:
        logger.error(f"执行遗传算法任务 (实验ID: {experiment_id}) 时发生严重错误: {e}", exc_info=True)
        if db and experiment:
            try:
                experiment.status = "FAILED"; experiment.end_time = datetime.utcnow()
                # if hasattr(experiment, 'error_message'): experiment.error_message = str(e)[:500]
                db.add(experiment); db.commit()
            except Exception as db_err:
                logger.error(f"在主错误处理中更新实验状态为 FAILED 时再次发生数据库错误: {db_err}", exc_info=True)
        raise

    finally:
        if db: db.close()
        logger.info(f"run_genetic_algorithm_task (任务ID: {task_job_id}) for 实验ID: {experiment_id} 执行流程结束。")
