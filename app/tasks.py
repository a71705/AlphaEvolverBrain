# app/tasks.py
# 此文件用于定义 RQ (Redis Queue) 的后台任务函数。

import logging  # Python 标准日志库
import time     # 用于模拟耗时操作，例如 time.sleep()
import os       # 用于访问环境变量 (如果任务需要)
import random   # 用于生成随机种子
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
    Node, # Node 类型也需要被导入，因为 current_population_nodes 是 List[Node]
    alpha_to_tree, # 用于从表达式恢复种群树
)


# 获取当前模块的 logger 实例
# 日志将以 "app.tasks" 的名称记录
logger = logging.getLogger(__name__)

def test_task(name: str) -> str:
    """
    一个简单的 RQ 测试任务。
    (详细注释见之前实现)
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

def _report_progress(
    job: Optional[Any],
    db_session: Session,
    experiment_id: int,
    current_iteration: int,
    message: str,
    current_depth: Optional[int] = None
):
    """
    报告 RQ 任务进度，更新 job.meta 并持久化 Experiment 状态到数据库。

    Args:
        job (Optional[Any]): 当前的 RQ Job 对象。
        db_session (Session): SQLAlchemy 数据库会话。
        experiment_id (int): 当前实验的 ID。
        current_iteration (int): 当前完成的迭代/代数。
        message (str): 描述当前进度的消息。
        current_depth (Optional[int]): 实验当前达到的深度。
    """
    logger.debug(f"报告进度: 实验ID {experiment_id}, 代数 {current_iteration}, 消息: '{message}'")

    if job:
        if job.meta is None: job.meta = {}
        job.meta['progress'] = {
            'iteration': current_iteration,
            'depth': current_depth,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        try:
            job.save_meta()
            logger.debug(f"RQ Job (ID: {job.id}) meta data 已更新。")
        except Exception as e:
            logger.warning(f"更新 RQ Job (ID: {job.id}) meta data 失败: {e}", exc_info=True)
    else:
        logger.info("当前任务不在 RQ worker 上下文中运行 (job is None)，跳过 job.meta 更新。")

    try:
        experiment = db_session.query(Experiment).filter(Experiment.id == experiment_id).first()
        if experiment:
            experiment.current_iteration = current_iteration
            if current_depth is not None: experiment.current_depth = current_depth
            experiment.random_seed = random.randint(0, 2**32 - 1) # 为下一次可能的恢复生成新种子
            db_session.add(experiment)
            db_session.commit()
            logger.debug(f"实验 {experiment_id} 数据库进度更新 (代数: {current_iteration}, 种子: {experiment.random_seed})。")
        else:
            logger.error(f"_report_progress: 未找到实验ID {experiment_id}。")
    except Exception as e:
        logger.error(f"更新实验 {experiment_id} 数据库进度时出错: {e}", exc_info=True)
        db_session.rollback()

def run_genetic_algorithm_task(experiment_id: int, ga_config: Dict[str, Any]):
    """
    执行遗传算法的主任务。
    (详细注释见之前实现)
    """
    job = get_current_job()
    task_job_id = job.id if job else 'N/A'
    logger.info(f"开始执行 run_genetic_algorithm_task (任务ID: {task_job_id}) for 实验ID: {experiment_id}")
    logger.debug(f"GA 配置: {ga_config}")

    db: Optional[Session] = None
    brain_api: Optional[BrainApiSession] = None
    experiment: Optional[Experiment] = None

    try:
        db = SessionLocal()

        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment:
            logger.error(f"实验ID {experiment_id} 未在数据库中找到。任务终止。")
            return {"status": "error", "message": f"Experiment ID {experiment_id} not found."}

        # --- 断点续传：加载和设置随机种子 ---
        if experiment.random_seed is not None:
            logger.info(f"实验 {experiment_id}: 从数据库恢复随机种子: {experiment.random_seed}")
            random.seed(experiment.random_seed)
        else:
            initial_seed = random.randint(0, 2**32 - 1)
            logger.info(f"实验 {experiment_id}: 生成初始种子: {initial_seed}")
            random.seed(initial_seed)
            experiment.random_seed = initial_seed
            # 初始种子将在首次报告进度时与 iteration=0 一起保存

        start_iteration = experiment.current_iteration # 已完成的代数
        logger.info(f"实验 {experiment_id}: 将从第 {start_iteration} 代之后开始。")

        try:
            brain_api = BrainApiSession()
            logger.info("BrainApiSession 初始化成功。")
        except (AuthenticationError, PersonaLoginError, ValueError) as auth_exc:
            logger.error(f"BrainApiSession 初始化失败: {auth_exc}", exc_info=True); experiment.status = "FAILED"; experiment.end_time = datetime.utcnow(); db.add(experiment); db.commit(); raise
        except Exception as e:
            logger.error(f"BrainApiSession 初始化时发生未知错误: {e}", exc_info=True); experiment.status = "FAILED"; experiment.end_time = datetime.utcnow(); db.add(experiment); db.commit(); raise

        experiment.status = "RUNNING"
        if experiment.start_time is None: experiment.start_time = datetime.utcnow()
        # 第一次提交状态和可能的初始种子（如果上面没有提交）
        # 注意：_report_progress 内部会 commit
        _report_progress(job, db, experiment.id, start_iteration, "Task started, status set to RUNNING.", experiment.current_depth)
        logger.info(f"实验 {experiment_id} 状态更新为 RUNNING。")

        num_generations = ga_config.get("generations", 10)
        population_size = ga_config.get("population_size", 50)
        max_initial_depth = ga_config.get("max_initial_depth", 3)

        current_population_nodes: List[Node] = []

        if start_iteration > 0:
            logger.info(f"实验 {experiment_id}: 尝试从第 {start_iteration} 代恢复种群。")
            previous_gen_alphas = db.query(Alpha).filter(Alpha.experiment_id == experiment_id, Alpha.iteration == start_iteration).filter(Alpha.calculated_fitness_score != None).order_by(Alpha.calculated_fitness_score.desc()).limit(population_size).all()
            if previous_gen_alphas:
                for alpha_orm in previous_gen_alphas:
                    tree = alpha_to_tree(alpha_orm.expression)
                    if tree: current_population_nodes.append(tree)
                    else: logger.warning(f"恢复种群: Alpha ID {alpha_orm.id} ({alpha_orm.expression}) 无法转回树。")
                if not current_population_nodes or len(current_population_nodes) < population_size // 2 :
                     logger.warning(f"实验 {experiment_id}: 恢复个体数 ({len(current_population_nodes)}) 不足或为零。将重新生成初始种群并将代数重置为0。")
                     start_iteration = 0; experiment.current_iteration = 0 # 重置
                     # _report_progress 会更新DB中的iteration和种子
                     _report_progress(job, db, experiment.id, 0, "Population recovery failed, resetting iteration to 0.", experiment.current_depth)
                     current_population_nodes = [] # 清空，以便下面重新生成
            else:
                logger.warning(f"实验 {experiment_id}: 未找到第 {start_iteration} 代有效Alpha。将重新生成初始种群并将代数重置为0。")
                start_iteration = 0; experiment.current_iteration = 0
                _report_progress(job, db, experiment.id, 0, "No Alphas for recovery, resetting iteration to 0.", experiment.current_depth)


        if not current_population_nodes: # (包含了 start_iteration == 0 的情况，或恢复失败/不足的情况)
            logger.info(f"实验 {experiment_id}: (重新)生成初始种群...")
            current_population_nodes = generate_initial_population(size=population_size, max_initial_depth=max_initial_depth, config=ga_config)
            _report_progress(job, db, experiment.id, 0, "Initial population generated.", experiment.current_depth)
            # 确保 experiment.current_iteration 仍为 0 (或已被 _report_progress 更新为0)

        if not current_population_nodes:
            logger.error(f"实验 {experiment_id}: 初始种群为空，无法继续。"); experiment.status = "FAILED"; experiment.end_time = datetime.utcnow(); db.add(experiment); db.commit()
            return {"status": "error", "message": "Initial population was empty."}

        for gen_idx in range(start_iteration, num_generations):
            current_processing_iteration = gen_idx + 1
            logger.info(f"实验 {experiment_id}: 开始第 {current_processing_iteration}/{num_generations} 代...")

            next_gen_nodes = _run_ga_generation(
                current_population_nodes=current_population_nodes, brain_session=brain_api,
                db_session=db, experiment_id=experiment.id,
                current_iteration=current_processing_iteration, ga_config=ga_config
            )

            if not next_gen_nodes:
                logger.error(f"实验 {experiment_id}: 第 {current_processing_iteration} 代未能生成有效后代。终止GA。"); experiment.status = "FAILED"; break

            current_population_nodes = next_gen_nodes
            # experiment.current_iteration 已在 _run_ga_generation -> evaluate_population -> (如果需要创建Alpha对象时) 设置
            # _report_progress 会再次确认并保存最新的 iteration 和新的 random_seed
            _report_progress(job, db, experiment.id, current_processing_iteration, f"Generation {current_processing_iteration} completed.", experiment.current_depth) # TODO: current_depth 更新
            logger.info(f"实验 {experiment_id}: 第 {current_processing_iteration} 代完成。")

        if experiment.status == "RUNNING":
            experiment.status = "COMPLETED"; experiment.end_time = datetime.utcnow()
            logger.info(f"实验 {experiment_id} 所有代数完成，状态更新为 COMPLETED。")

        db.add(experiment); db.commit() # 最终提交实验状态
        return {"status": experiment.status, "experiment_id": experiment.id, "generations_completed": experiment.current_iteration}

    except Exception as e:
        logger.error(f"执行GA任务 (实验ID: {experiment_id}) 时发生严重错误: {e}", exc_info=True)
        if db and experiment:
            try:
                experiment.status = "FAILED"; experiment.end_time = datetime.utcnow()
                # if hasattr(experiment, 'error_message'): experiment.error_message = str(e)[:500]
                db.add(experiment); db.commit()
            except Exception as db_err: logger.error(f"主错误处理中更新实验状态为FAILED时DB错误: {db_err}", exc_info=True)
        raise
    finally:
        if db: db.close()
        logger.info(f"run_genetic_algorithm_task (任务ID: {task_job_id}) for 实验ID: {experiment_id} 执行流程结束。")
