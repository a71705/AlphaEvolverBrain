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
from typing import Optional, Dict, Any # 用于类型提示, Dict, Any 新增
from datetime import datetime, timezone # 用于时间戳, timezone 新增

# 导入数据库相关的模块
from app.database import SessionLocal # 用于创建数据库会话
# from app.database import create_tables # 通常表已由 FastAPI 应用启动时创建

# 导入模型 (用于查询和更新 Experiment 对象)
from app.models import Experiment, Alpha as AlphaModel # 导入 Experiment 和 Alpha 模型

# 导入 Brain API 会话管理器
from app.core.brain_api import BrainApiSession

# 导入遗传算法核心阶段函数 (当前是占位符)
from app.core.gp_algo import best_d1_alphas, best_d2_alphas, best_d3_alpha

# 从 app.core.notifications 导入 send_email 函数 (DEV-033 新增)
from app.core.notifications import send_email


def _report_progress(
    job: Optional[Job],
    db_session: Session,
    experiment_id: str, # 实验ID现在是UUID字符串
    current_depth: int,
    current_iteration: int,
    message: str
):
    """
    辅助函数，用于更新 RQ 作业的元数据和数据库中实验的进度。

    参数:
        job (Optional[Job]): 当前 RQ 作业对象。如果任务不是通过 RQ 执行，则可能为 None。
        db_session (Session): SQLAlchemy 数据库会话。
        experiment_id (str): 当前实验的 ID (UUID字符串)。
        current_depth (int): 遗传算法当前的深度。
        current_iteration (int): 当前深度下的迭代次数。
        message (str): 关于当前进度的描述性消息。
    """
    try:
        # 1. 更新 RQ Job Meta
        if job:
            if job.meta is None:
                job.meta = {}

            job.meta['progress'] = {
                'depth': current_depth,
                'iteration': current_iteration,
                'message': message,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            job.save_meta()
        else:
            logger.debug(f"实验 {experiment_id}: 非 RQ 作业上下文，跳过更新作业元数据。")

        # 2. 更新数据库中的 Experiment 模型
        experiment = db_session.query(Experiment).filter(Experiment.id == experiment_id).first()
        if experiment:
            experiment.current_depth = current_depth
            # experiment.current_iteration = current_iteration # Schema中是 current_iteration_at_depth
            experiment.current_iteration_at_depth = current_iteration

            # experiment.random_seed = random.randint(0, 2**32 - 1) # 随机种子不应在每次进度报告时都更新
                                                                # 应在实验开始时设定，或从配置中读取
            if experiment.ga_config_json and 'random_seed' in experiment.ga_config_json:
                 current_seed = experiment.ga_config_json['random_seed']
            else: # 如果不存在，则生成一个并存入配置（理论上应在实验创建时完成）
                 current_seed = random.randint(0, 2**32 - 1)
                 if experiment.ga_config_json:
                     experiment.ga_config_json['random_seed'] = current_seed
                 # else: # 如果 ga_config_json 为空，则不处理，或者创建一个新的
                 #    experiment.ga_config_json = {'random_seed': current_seed}


            db_session.add(experiment)
            db_session.commit()
            logger.info(f"实验 {experiment_id}: 数据库进度已更新 - 深度 {current_depth}, 迭代 {current_iteration}, 种子 {current_seed}。消息: {message}")
        else:
            logger.warning(f"实验 {experiment_id}: 在数据库中未找到对应的实验记录，无法更新进度。")

    except Exception as e:
        logger.error(f"实验 {experiment_id}: 更新进度时发生错误 (_report_progress): {e}", exc_info=True)
        try:
            db_session.rollback()
            logger.info(f"实验 {experiment_id}: 数据库会话已回滚，由于更新进度时发生错误。")
        except Exception as rb_err:
            logger.error(f"实验 {experiment_id}: 在回滚数据库会话时发生额外错误: {rb_err}", exc_info=True)


def test_task(name: str, delay: int = 5) -> str:
    """
    一个简单的 RQ 测试任务函数。
    ... (原有的docstring) ...
    """
    job = get_current_job()
    if job:
        logger.info(f"开始执行测试任务 test_task。作业ID: {job.id}，参数 name='{name}', delay={delay}秒。")
    else:
        logger.info(f"开始执行测试任务 test_task (非 RQ 作业上下文)。参数 name='{name}', delay={delay}秒。")

    logger.info(f"任务 test_task ({name}): 正在模拟工作，将持续 {delay} 秒...")
    time.sleep(delay)
    result_message = f"你好，{name}！测试任务已在 {delay} 秒后完成。"
    if job:
        logger.info(f"测试任务 test_task ({name}) 完成。作业ID: {job.id}。结果: {result_message}")
    else:
        logger.info(f"测试任务 test_task ({name}) 完成。结果: {result_message}")
    return result_message


def run_genetic_algorithm_task(experiment_id: str, ga_config_override: Optional[Dict[str, Any]] = None) -> str:
    """
    执行遗传算法的主任务。
    ... (原有的docstring) ...
    任务完成（成功或失败）后会发送邮件通知。
    """
    job = get_current_job()
    logger.info(f"开始执行遗传算法任务，实验ID: {experiment_id}, Job ID: {job.id if job else 'N/A'}")

    db: Session = SessionLocal()
    experiment: Optional[Experiment] = None
    brain_api: Optional[BrainApiSession] = None

    task_final_status: str = "未知"
    error_info: str = ""
    best_alpha_details: str = ""

    try:
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment:
            error_msg = f"实验ID {experiment_id} 未找到。"
            logger.error(f"{error_msg} 任务终止。")
            task_final_status = "失败 (配置错误)"
            error_info = error_msg
            # 注意：这里直接抛出异常，finally块会执行邮件发送
            raise ValueError(error_info)

        # 仅当状态不是 FAILED 或 COMPLETED 时才设置为 RUNNING 并重置/设置时间
        if experiment.status not in ["COMPLETED", "FAILED"]:
            experiment.status = "RUNNING"
            if experiment.start_time is None: # 仅在首次启动时设置开始时间
                experiment.start_time = datetime.now(timezone.utc)
            experiment.error_message = None # 清除之前的错误信息
            # end_time 应该在任务真正结束时设置，而不是在开始时清除
            # experiment.end_time = None
            db.add(experiment)
            db.commit()
            logger.info(f"实验 {experiment.name} (ID: {experiment_id}) 状态已更新为 RUNNING。")
        elif experiment.status == "COMPLETED":
            logger.info(f"实验 {experiment.name} (ID: {experiment_id}) 已完成，任务不再执行。")
            task_final_status = "已完成 (未重新执行)"
            return f"实验 {experiment_id} 已完成。" # 直接返回，finally 块仍会执行
        elif experiment.status == "FAILED":
            # 如果允许重试FAILED的任务，则可能需要不同的逻辑。目前假设FAILED任务不自动重试。
            logger.warning(f"实验 {experiment.name} (ID: {experiment_id}) 状态为 FAILED，任务未执行。")
            task_final_status = "失败 (未重新执行)"
            error_info = experiment.error_message or "先前已标记为失败。"
            return f"实验 {experiment_id} 先前已失败。" # 直接返回


        brain_email = os.environ.get("BRAIN_CREDENTIAL_EMAIL")
        brain_password = os.environ.get("BRAIN_CREDENTIAL_PASSWORD")
        if not (brain_email and brain_password):
            error_msg = "Brain API 凭据 (BRAIN_CREDENTIAL_EMAIL, BRAIN_CREDENTIAL_PASSWORD) 未在环境变量中设置。"
            logger.error(error_msg)
            task_final_status = "失败 (配置错误)" # 更新状态以便邮件通知
            error_info = error_msg
            raise EnvironmentError("Brain API 凭据未配置。")

        brain_api = BrainApiSession(email=brain_email, password=brain_password)
        logger.info("BrainApiSession 初始化成功。")

        ga_config = experiment.ga_config_json.copy() if experiment.ga_config_json else {}
        if ga_config_override:
            ga_config.update(ga_config_override)
        logger.info(f"使用的遗传算法配置: {ga_config}")

        # 确保随机种子被设置和记录 (如果需要的话)
        if 'random_seed' not in ga_config or ga_config['random_seed'] is None:
            ga_config['random_seed'] = random.randint(0, 2**32 - 1)
            logger.info(f"为实验 {experiment_id} 生成/设置随机种子: {ga_config['random_seed']}")
            experiment.ga_config_json = ga_config # 保存回数据库
            db.add(experiment)
            db.commit()
        random.seed(ga_config['random_seed'])


        logger.info(f"实验 {experiment_id}: 遗传算法主循环开始...")
        # 【重要】实际的遗传算法调用逻辑应在此处
        # 示例:
        # population_d1 = best_d1_alphas(brain_api_session=brain_api, db_session=db, experiment_id=experiment_id, ga_config=ga_config)
        # population_d2 = best_d2_alphas(brain_api_session=brain_api, db_session=db, experiment_id=experiment_id, ga_config=ga_config, initial_population=population_d1)
        # final_population = best_d3_alpha(brain_api_session=brain_api, db_session=db, experiment_id=experiment_id, ga_config=ga_config, initial_population=population_d2)
        time.sleep(2) # 模拟工作负载从10秒减少到2秒
        logger.info(f"实验 {experiment_id}: 遗传算法主循环完成。")

        experiment.status = "COMPLETED"
        experiment.end_time = datetime.now(timezone.utc)
        db.add(experiment)
        db.commit()
        logger.info(f"实验 {experiment.name} (ID: {experiment_id}) 已成功完成。")
        task_final_status = "成功完成"

        # 查询最佳Alpha信息用于邮件
        best_alpha = db.query(AlphaModel).filter(AlphaModel.experiment_id == experiment_id) \
            .order_by(AlphaModel.fitness_score.desc().nullslast()).first() # fitness_score 来自 AlphaResponse schema
        if best_alpha:
            best_alpha_details = (
                f"最佳Alpha ID: {best_alpha.id}<br>"
                f"表达式: {best_alpha.expression[:100]}{'...' if len(best_alpha.expression) > 100 else ''}<br>"
                f"适应度得分: {best_alpha.fitness_score:.4f if best_alpha.fitness_score is not None else 'N/A'}"
            )
        else:
            best_alpha_details = "未能找到最佳Alpha信息。"

        return f"实验 {experiment_id} 成功完成。"

    except Exception as e:
        logger.error(f"实验 {experiment_id} 的遗传算法任务执行失败: {e}", exc_info=True)
        task_final_status = "执行失败" # 更新状态
        error_info = f"{type(e).__name__}: {str(e)}"
        if experiment: # 确保 experiment 对象存在
            experiment.status = "FAILED"
            if hasattr(experiment, 'error_message'): # 确保模型有 error_message 字段
                experiment.error_message = error_info[:499] # 限制长度以防超出数据库字段限制
            if not experiment.end_time: # 仅当尚未设置结束时间时设置
                experiment.end_time = datetime.now(timezone.utc)
            db.add(experiment)
            db.commit()
        # 此处不应返回，让 finally 块执行邮件发送，然后RQ会自动处理异常并标记作业失败
        raise # 重新抛出异常，以便RQ能捕获并标记作业为失败

    finally:
        # 邮件发送逻辑
        if experiment: # 确保 experiment 对象已加载
            recipient = os.environ.get("DEFAULT_NOTIFICATION_RECIPIENT")
            if recipient:
                exp_name = experiment.name if experiment.name else f"ID {experiment_id}"
                # 确保时间对象存在且有时区信息
                start_time_obj = experiment.start_time
                if start_time_obj and start_time_obj.tzinfo is None:
                    start_time_obj = start_time_obj.replace(tzinfo=timezone.utc)
                exp_start_time_str = start_time_obj.strftime("%Y-%m-%d %H:%M:%S %Z") if start_time_obj else "未知"

                # 结束时间应为当前时间，因为任务到此结束
                current_time_utc = datetime.now(timezone.utc)
                exp_end_time_str = current_time_utc.strftime("%Y-%m-%d %H:%M:%S %Z")

                subject = f"遗传算法实验 '{exp_name}' 执行{task_final_status}"

                html_parts = [
                    "<html><head><style>",
                    "body { font-family: Arial, sans-serif; margin: 20px; color: #333; }",
                    "h1 { color: #2a2f36; border-bottom: 1px solid #eee; padding-bottom: 10px; }",
                    "p { line-height: 1.6; margin-bottom: 10px; }",
                    "strong { color: #555; }",
                    ".status-success { color: #28a745; font-weight: bold; }",
                    ".status-failed { color: #dc3545; font-weight: bold; }",
                    ".status-unknown { color: #ffc107; font-weight: bold; }",
                    ".details-box { background-color: #f8f9fa; border: 1px solid #e9ecef; border-left-width: 6px; padding: 15px; margin-top:15px; border-radius: 4px; }",
                    ".error-details { border-left-color: #f5c6cb; }",
                    ".alpha-details { border-left-color: #b8daff; }",
                    "pre { white-space: pre-wrap; word-wrap: break-word; background-color: #e9ecef; padding: 10px; border-radius: 4px;}",
                    "hr { border: none; border-top: 1px solid #eee; margin: 20px 0; }",
                    ".footer { font-size: 0.9em; color: #777; margin-top: 20px; text-align: center; }",
                    "</style></head><body>",
                    f"<h1>实验执行通知</h1>",
                    f"<p><strong>实验名称:</strong> {exp_name}</p>",
                    f"<p><strong>实验ID:</strong> {experiment_id}</p>"
                ]

                status_class = "status-unknown"
                if task_final_status == "成功完成":
                    status_class = "status-success"
                elif "失败" in task_final_status or "执行失败" in task_final_status:
                    status_class = "status-failed"

                html_parts.append(f"<p><strong>状态:</strong> <span class='{status_class}'>{task_final_status}</span></p>")
                html_parts.append(f"<p><strong>任务计划/实际开始时间:</strong> {exp_start_time_str}</p>")
                html_parts.append(f"<p><strong>通知生成时间 (任务结束):</strong> {exp_end_time_str}</p>")

                if task_final_status == "成功完成":
                    html_parts.append(f"<h2>实验结果摘要:</h2><div class='details-box alpha-details'>{best_alpha_details if best_alpha_details else '任务已顺利完成，无特定Alpha信息。'}</div>")
                elif task_final_status != "未知" and error_info: # 对于失败或配置错误等，且有错误信息
                    html_parts.append(f"<h2>错误详情:</h2><div class='details-box error-details'><pre>{error_info}</pre></div>")

                html_parts.extend([
                    "<hr><p class='footer'>此邮件为WorldQuant Alpha Evolution系统自动发送，请勿回复。</p>",
                    "</body></html>"
                ])
                body_html = "".join(html_parts)

                logger.info(f"准备发送实验 '{exp_name}' 的完成通知邮件至 {recipient}。状态: {task_final_status}")
                if not send_email(recipient, subject, body_html):
                    logger.error(f"发送实验 '{exp_name}' 的通知邮件失败。")
            else:
                logger.warning("DEFAULT_NOTIFICATION_RECIPIENT 未在环境变量中设置，无法发送任务完成邮件。")

        if db:
            db.close()
        logger.info(f"遗传算法任务处理完成，实验ID: {experiment_id}, Job ID: {job.id if job else 'N/A'}")
        # 如果任务因异常退出，RQ 会自动标记作业为 'failed'。
        # 如果正常完成，RQ 会标记为 'finished'。
        # 此处的返回字符串主要用于日志或直接调用时的结果。
        # 如果有异常被重新抛出 (如上面 raise)，则此 return 语句不会执行。

    # 这个 return 语句只会在 try 块中的 return 语句被执行时（即实验之前已完成或失败）才会被执行。
    # 如果 try 块中发生异常并被捕获和重新抛出，或者 try 块成功执行到末尾并返回，
    # 则这个顶层的 return 语句不会被执行。
    # 为了确保函数总有返回值（即使理论上某些路径不会到达），可以保留一个。
    # 但在当前结构下，如果try块成功，它有自己的return；如果失败，它会raise。
    # 如果实验一开始就处于 COMPLETED/FAILED 状态，也会有 return。
    # 所以这个 return 可能永远不会被达到。可以考虑移除或调整逻辑。
    return f"任务处理流程已结束，实验ID: {experiment_id}，最终状态: {task_final_status}"
