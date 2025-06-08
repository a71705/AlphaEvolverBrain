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
from sqlalchemy.orm import Session # 用于类型提示 db_session
from rq.job import Job # 用于类型提示 job 参数
# from typing import Optional # Optional 已在之前导入
import random # 用于示意性地更新 random_seed
# from datetime import datetime # datetime 已在之前导入
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


def _report_progress(
    job: Optional[Job],
    db_session: Session,
    experiment_id: int,
    current_depth: int,
    current_iteration: int,
    message: str
):
    """
    辅助函数，用于更新 RQ 作业的元数据和数据库中实验的进度。

    参数:
        job (Optional[Job]): 当前 RQ 作业对象。如果任务不是通过 RQ 执行，则可能为 None。
        db_session (Session): SQLAlchemy 数据库会话。
        experiment_id (int): 当前实验的 ID。
        current_depth (int): 遗传算法当前的深度。
        current_iteration (int): 当前深度下的迭代次数。
        message (str): 关于当前进度的描述性消息。
    """
    try:
        # 1. 更新 RQ Job Meta
        if job:
            if job.meta is None: # job.meta 可能在第一次设置前是 None
                job.meta = {}

            job.meta['progress'] = {
                'depth': current_depth,
                'iteration': current_iteration,
                'message': message,
                'timestamp': datetime.utcnow().isoformat() # 添加时间戳
            }
            job.save_meta() # 保存元数据变更 (对于 RQ >= 1.0)
            # 对于旧版本 RQ (0.x)，可能是 job.save() 或直接修改 job.meta 就被持久化了。
            # 任务描述中是 job.save()，但 save_meta() 更精确。这里采用 save_meta() 并添加注释。
            # 如果严格遵循 job.save()，则替换为 job.save()。
            # logger.debug(f"实验 {experiment_id}: RQ 作业元数据已更新 - {job.meta['progress']}")
        else:
            logger.debug(f"实验 {experiment_id}: 非 RQ 作业上下文，跳过更新作业元数据。")

        # 2. 更新数据库中的 Experiment 模型
        experiment = db_session.query(Experiment).filter(Experiment.id == experiment_id).first()
        if experiment:
            experiment.current_depth = current_depth
            experiment.current_iteration = current_iteration
            # 根据任务描述，更新 random_seed。
            # 这是一个示意性的更新，实际的随机状态管理可能更复杂。
            experiment.random_seed = random.randint(0, 2**32 - 1)

            # experiment.status 应该由主任务逻辑（run_genetic_algorithm_task）在关键转换点更新，
            # _report_progress 主要负责 current_depth/iteration/seed。
            # 如果需要，也可以在这里更新一个更细粒度的状态，例如 experiment.progress_message = message

            db_session.add(experiment) # 将更改添加到会话
            db_session.commit()      # 提交更改到数据库
            logger.info(f"实验 {experiment_id}: 数据库进度已更新 - 深度 {current_depth}, 迭代 {current_iteration}, 随机种子 {experiment.random_seed}。消息: {message}")
        else:
            logger.warning(f"实验 {experiment_id}: 在数据库中未找到对应的实验记录，无法更新进度。")

    except Exception as e:
        logger.error(f"实验 {experiment_id}: 更新进度时发生错误 (_report_progress): {e}", exc_info=True)
        # 不应在此处关闭 db_session 或重新抛出异常，让主任务的 finally 和 except 块处理。
        # 但如果 db_session commit 失败，可能需要 rollback。
        try:
            db_session.rollback() # 如果 commit 失败，尝试回滚以保持会话清洁
            logger.info(f"实验 {experiment_id}: 数据库会话已回滚，由于更新进度时发生错误。")
        except Exception as rb_err:
            logger.error(f"实验 {experiment_id}: 在回滚数据库会话时发生额外错误: {rb_err}", exc_info=True)


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
    （已更新以包含进度报告和断点续传逻辑）
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

    db: Session = SessionLocal()
    brain_api: Optional[BrainApiSession] = None # 初始化为 None
    experiment: Optional[Experiment] = None

    # 初始化进度变量，稍后会从数据库加载
    current_depth_from_db = 0
    current_iteration_from_db = 0
    # ga_config 中的参数通常用于整个实验，但也可以有特定于阶段的设置
    # 例如，每个深度的最大迭代次数
    # max_iterations_per_depth = ga_config.get("max_iterations_per_depth", {}).get(str(current_depth_from_db), 10) # 示例

    try:
        # --- 获取 Brain API 凭据并初始化会话 ---
        brain_email = os.environ.get("BRAIN_CREDENTIAL_EMAIL")
        brain_password = os.environ.get("BRAIN_CREDENTIAL_PASSWORD")
        if not brain_email or not brain_password:
            error_msg = "Brain API 凭据未在环境变量中配置。任务无法继续。"
            logger.error(f"实验 {experiment_id}: {error_msg}")
            # 尝试更新数据库中的实验状态
            temp_exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
            if temp_exp:
                temp_exp.status = "FAILED"
                temp_exp.error_message = error_msg
                temp_exp.end_time = datetime.utcnow()
                db.add(temp_exp)
                db.commit()
            raise ValueError(error_msg) # 抛出异常以标记RQ作业失败

        brain_api = BrainApiSession(email=brain_email, password=brain_password)

        # --- 加载实验并处理断点续传 ---
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment:
            logger.error(f"实验 {experiment_id}: 在数据库中未找到。任务终止。")
            raise ValueError(f"实验ID {experiment_id} 不存在。")

        if experiment.status == "COMPLETED":
            logger.info(f"实验 {experiment.name} (ID: {experiment_id}) 已标记为 COMPLETED。任务将不会重新运行。")
            return # 直接退出，不重新执行已完成的实验

        if experiment.status == "RUNNING":
             logger.warning(f"实验 {experiment.name} (ID: {experiment_id}) 当前状态为 RUNNING，可能表示之前的任务异常中断。将尝试从保存的进度恢复。")
             # 如果需要更复杂的逻辑，例如检查上次心跳时间来判断是否真的中断，可以在此添加

        # 加载已保存的进度用于断点续传
        current_depth_from_db = experiment.current_depth if experiment.current_depth is not None else 0
        current_iteration_from_db = experiment.current_iteration if experiment.current_iteration is not None else 0

        if experiment.random_seed is not None:
            logger.info(f"实验 {experiment_id}: 从数据库恢复随机种子: {experiment.random_seed}。")
            random.seed(experiment.random_seed)
        else:
            # 如果没有保存的种子，可以生成一个新的并立即保存一次进度，或者在首次 _report_progress 时保存
            new_seed = random.randint(0, 2**32 - 1)
            random.seed(new_seed)
            logger.info(f"实验 {experiment_id}: 生成了新的随机种子: {new_seed} (将在首次进度报告时保存到数据库)。")


        logger.info(f"实验 {experiment.name} (ID: {experiment_id}): 状态从 {experiment.status} 更新为 RUNNING。尝试从深度 {current_depth_from_db}，迭代 {current_iteration_from_db} 继续。")
        experiment.status = "RUNNING"
        if experiment.start_time is None: # 仅在首次启动时设置开始时间
             experiment.start_time = datetime.utcnow()
        experiment.error_message = None # 清除之前的错误信息
        db.add(experiment)
        db.commit()

        # 首次报告进度，包含了初始（或恢复的）随机种子
        _report_progress(job, db, experiment_id, current_depth_from_db, current_iteration_from_db, "任务启动/恢复，状态设为RUNNING")


        # --- 调用遗传算法的各个阶段函数 ---
        # 这里的逻辑需要根据 current_depth_from_db 和 current_iteration_from_db 来调整
        # 以便能够跳过已完成的阶段或迭代。
        # 为简单起见，占位符函数目前不真正处理这些“起始点”参数，
        # 但 run_genetic_algorithm_task 会按顺序调用它们，并传递当前进度。
        # 实际的GA循环需要更复杂的逻辑来管理迭代和深度。

        # 假设 ga_config 中有总深度数, 例如 ga_config.get('total_depths', 3)
        # 并且每个 best_dX_alphas 对应一个深度。

        # 阶段/深度 1 (假设 current_depth 0 代表 d1)
        if current_depth_from_db <= 0: # 如果未开始或在深度0
            logger.info(f"实验 {experiment_id}: 开始/继续 best_d1_alphas (深度0)。当前迭代（从数据库加载）: {current_iteration_from_db if current_depth_from_db == 0 else 0}")
            # 实际的 best_d1_alphas 可能需要 current_iteration_from_db 作为参数以从特定迭代恢复
            d1_results = best_d1_alphas(brain_api, db, experiment_id, ga_config) # 传递当前迭代等
            current_depth_from_db = 0 # 标记当前完成的深度
            current_iteration_from_db = ga_config.get("iterations_at_depth_0", 10) # 假设完成此深度的所有迭代
            _report_progress(job, db, experiment_id, current_depth_from_db, current_iteration_from_db, "best_d1_alphas 完成")
            logger.info(f"实验 {experiment_id}: best_d1_alphas 完成。")
        else:
            logger.info(f"实验 {experiment_id}: 跳过 best_d1_alphas (深度0)，因已从深度 {current_depth_from_db} 恢复。")


        # 阶段/深度 2 (假设 current_depth 1 代表 d2)
        if current_depth_from_db <= 1:
            # 如果是从深度0过来的，重置迭代计数器；如果是从深度1恢复，则使用 current_iteration_from_db
            iter_start_d2 = current_iteration_from_db if current_depth_from_db == 1 else 0
            logger.info(f"实验 {experiment_id}: 开始/继续 best_d2_alphas (深度1)。起始迭代: {iter_start_d2}")
            # 假设 d1_results 需要从数据库或其他地方重新加载，如果任务是恢复的
            # 为简单，这里假设 d1_results 仍然可用或 best_d2_alphas 能处理
            # 实际中，可能需要查询数据库获取上一阶段的优秀个体
            if 'd1_results' not in locals(): # 如果跳过了d1阶段
                # d1_results = load_alphas_from_db(db, experiment_id, depth=0, criteria="best") # 示意性
                logger.warning(f"实验 {experiment_id}: d1_results 未定义，可能需要从数据库加载以用于 best_d2_alphas。占位符将使用空列表。")
                d1_results = []
            d2_results = best_d2_alphas(brain_api, db, experiment_id, ga_config, previous_generation_alphas=d1_results) # 传递迭代
            current_depth_from_db = 1
            current_iteration_from_db = ga_config.get("iterations_at_depth_1", 10)
            _report_progress(job, db, experiment_id, current_depth_from_db, current_iteration_from_db, "best_d2_alphas 完成")
            logger.info(f"实验 {experiment_id}: best_d2_alphas 完成。")
        else:
            logger.info(f"实验 {experiment_id}: 跳过 best_d2_alphas (深度1)，因已从深度 {current_depth_from_db} 恢复。")


        # 阶段/深度 3 (假设 current_depth 2 代表 d3)
        if current_depth_from_db <= 2:
            iter_start_d3 = current_iteration_from_db if current_depth_from_db == 2 else 0
            logger.info(f"实验 {experiment_id}: 开始/继续 best_d3_alpha (深度2)。起始迭代: {iter_start_d3}")
            if 'd2_results' not in locals():
                logger.warning(f"实验 {experiment_id}: d2_results 未定义，可能需要从数据库加载以用于 best_d3_alpha。占位符将使用空列表。")
                d2_results = []
            d3_results = best_d3_alpha(brain_api, db, experiment_id, ga_config, previous_generation_alphas=d2_results) # 传递迭代
            current_depth_from_db = 2
            current_iteration_from_db = ga_config.get("iterations_at_depth_2", 10)
            _report_progress(job, db, experiment_id, current_depth_from_db, current_iteration_from_db, "best_d3_alpha 完成")
            logger.info(f"实验 {experiment_id}: best_d3_alpha 完成。")
        else:
            logger.info(f"实验 {experiment_id}: 跳过 best_d3_alpha (深度2)，因已从深度 {current_depth_from_db} 恢复。")


        # --- 所有阶段成功完成 ---
        logger.info(f"实验 {experiment.name} (ID: {experiment_id}): 所有遗传算法阶段成功完成。状态更新为 COMPLETED。")
        experiment.status = "COMPLETED"
        experiment.end_time = datetime.utcnow()
        # experiment.error_message = None # 已在启动时清除
        db.add(experiment)
        db.commit()

        if job:
             logger.info(f"RQ 作业 {job.id}: run_genetic_algorithm_task 成功完成，实验ID: {experiment_id}。")

    except Exception as e:
        logger.error(f"实验 {experiment_id}: 在执行 run_genetic_algorithm_task 过程中发生严重错误: {e}", exc_info=True)
        if experiment:
            logger.error(f"实验 {experiment.name} (ID: {experiment_id}): 因错误将状态更新为 FAILED。")
            experiment.status = "FAILED"
            if experiment.end_time is None: # 只有当之前未设置过（例如，不是在COMPLETED后又失败）才设置
                experiment.end_time = datetime.utcnow()
            experiment.error_message = f"任务执行失败: {str(e)[:450]}" # 截断以适应可能的字段长度
            db.add(experiment)
            try:
                db.commit()
            except Exception as db_err:
                logger.error(f"实验 {experiment_id}: 更新实验状态为 FAILED 时数据库提交失败: {db_err}", exc_info=True)
                db.rollback()

        if job:
            logger.error(f"RQ 作业 {job.id}: run_genetic_algorithm_task 执行失败，实验ID: {experiment_id}。")
        raise

    finally:
        if db:
            db.close()
            logger.debug(f"实验 {experiment_id}: 数据库会话已关闭。")

# 确保所有必要的导入 (datetime, random, Optional, Session, Job, Experiment, BrainApiSession, _report_progress, best_dX_alphas)
# 都在 app/tasks.py 的文件顶部。
