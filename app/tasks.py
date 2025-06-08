# 导入 logging 模块，用于在任务函数中记录日志。
import logging
# 导入 time 模块，例如用于在测试任务中模拟耗时操作。
import time
# 导入 os 模块，用于访问环境变量（如果任务需要配置）。
import os

# 从 rq 包导入 get_current_job，用于在任务执行时获取当前作业的相关信息。
from rq import get_current_job
import requests # DEV-046: 导入 requests 用于捕获其异常

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
    (Implementation from DEV-033, assumes experiment_id is str for consistency with task)
    """
    try:
        if job:
            if job.meta is None: job.meta = {}
            job.meta['progress'] = {
                'depth': current_depth, 'iteration': current_iteration,
                'message': message, 'timestamp': datetime.now(timezone.utc).isoformat()
            }
            job.save_meta()

        experiment = db_session.query(Experiment).filter(Experiment.id == experiment_id).first()
        if experiment:
            experiment.current_depth = current_depth
            experiment.current_iteration_at_depth = current_iteration # Corrected field name

            current_seed_in_config = experiment.ga_config_json.get('random_seed') if experiment.ga_config_json else None
            if current_seed_in_config is None and experiment.ga_config_json is not None : # if ga_config_json exists but no seed
                 new_seed = random.randint(0, 2**32 - 1)
                 experiment.ga_config_json['random_seed'] = new_seed # Store seed if not present
                 logger.info(f"实验 {experiment_id}: 新随机种子 {new_seed} 已存入ga_config_json。")


            db_session.add(experiment)
            db_session.commit()
            logger.info(f"实验 {experiment_id}: 数据库进度更新 - 深度 {current_depth}, 迭代 {current_iteration}。消息: {message}")
        else:
            logger.warning(f"实验 {experiment_id}: 更新进度时未找到实验记录。")
    except Exception as e:
        logger.error(f"实验 {experiment_id}: 更新进度错误 (_report_progress): {e}", exc_info=True)
        try: db_session.rollback()
        except Exception as rb_err: logger.error(f"实验 {experiment_id}: 回滚错误: {rb_err}", exc_info=True)


def test_task(name: str, delay: int = 5) -> str:
    # ... (Unchanged from DEV-033) ...
    job = get_current_job()
    if job: logger.info(f"开始测试任务 test_task. Job ID: {job.id}, name='{name}', delay={delay}s.")
    else: logger.info(f"开始测试任务 test_task (非RQ). name='{name}', delay={delay}s.")
    logger.info(f"任务 test_task ({name}): 模拟工作 {delay}s...")
    time.sleep(delay)
    result_message = f"你好，{name}！测试任务 {delay}s 后完成。"
    if job: logger.info(f"测试任务 test_task ({name}) 完成. Job ID: {job.id}. 结果: {result_message}")
    else: logger.info(f"测试任务 test_task ({name}) 完成. 结果: {result_message}")
    return result_message


def run_genetic_algorithm_task(experiment_id: str, ga_config_override: Optional[Dict[str, Any]] = None) -> str:
    job = get_current_job()
    logger.info(f"开始遗传算法任务，实验ID: {experiment_id}, Job ID: {job.id if job else 'N/A'}")

    db: Session = SessionLocal()
    experiment: Optional[Experiment] = None
    brain_api: Optional[BrainApiSession] = None

    task_final_status: str = "未知"
    error_info: str = ""
    best_alpha_details: str = ""
    oos_results_summary_for_email: str = "" # DEV-046: For OOS summary in email

    try:
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment:
            error_msg = f"实验ID {experiment_id} 未找到。"
            logger.error(f"{error_msg} 任务终止。")
            task_final_status = "失败 (配置错误)"
            error_info = error_msg
            raise ValueError(error_info)

        if experiment.status not in ["COMPLETED", "FAILED"]:
            experiment.status = "RUNNING"
            if experiment.start_time is None:
                experiment.start_time = datetime.now(timezone.utc)
            experiment.error_message = None
            db.add(experiment)
            db.commit()
            logger.info(f"实验 {experiment.name} (ID: {experiment_id}) 状态更新为 RUNNING。")
        elif experiment.status == "COMPLETED":
            logger.info(f"实验 {experiment.name} (ID: {experiment_id}) 已完成，不再执行。")
            task_final_status = "已完成 (未重新执行)" # Set status for email
            return f"实验 {experiment_id} 已完成。"
        elif experiment.status == "FAILED":
            logger.warning(f"实验 {experiment.name} (ID: {experiment_id}) 状态为 FAILED，任务未执行。")
            task_final_status = "失败 (未重新执行)" # Set status for email
            error_info = experiment.error_message or "先前已标记为失败。"
            return f"实验 {experiment_id} 先前已失败。"

        brain_email = os.environ.get("BRAIN_CREDENTIAL_EMAIL")
        brain_password = os.environ.get("BRAIN_CREDENTIAL_PASSWORD")
        if not (brain_email and brain_password):
            error_msg = "Brain API 凭据未在环境变量中配置。"
            logger.error(error_msg)
            task_final_status = "失败 (配置错误)"
            error_info = error_msg
            raise EnvironmentError("Brain API 凭据未配置。")

        brain_api = BrainApiSession(email=brain_email, password=brain_password)
        logger.info("BrainApiSession 初始化成功。")

        ga_config = experiment.ga_config_json.copy() if experiment.ga_config_json else {}
        if ga_config_override: ga_config.update(ga_config_override)
        logger.info(f"使用遗传算法配置: {ga_config}")

        if 'random_seed' not in ga_config or ga_config['random_seed'] is None:
            ga_config['random_seed'] = random.randint(0, 2**32 - 1)
            logger.info(f"实验 {experiment_id} 生成/设置随机种子: {ga_config['random_seed']}")
            experiment.ga_config_json = ga_config
            db.add(experiment); db.commit()
        random.seed(ga_config['random_seed'])

        logger.info(f"实验 {experiment_id}: 遗传算法主循环开始...")
        time.sleep(2) # 模拟 GA 工作
        logger.info(f"实验 {experiment_id}: 遗传算法主循环完成。")

        # 假设GA成功完成，更新实验状态
        experiment.status = "COMPLETED"
        experiment.end_time = datetime.now(timezone.utc)
        db.add(experiment); db.commit(); db.refresh(experiment)
        logger.info(f"实验 {experiment.name} (ID: {experiment_id}) 已成功完成。")
        task_final_status = "成功完成"

        best_alpha = db.query(AlphaModel).filter(AlphaModel.experiment_id == experiment_id) \
            .order_by(AlphaModel.fitness_score.desc().nullslast()).first()
        if best_alpha:
            best_alpha_details = (
                f"最佳Alpha ID: {best_alpha.id}<br>"
                f"表达式: {best_alpha.expression[:100]}{'...' if len(best_alpha.expression) > 100 else ''}<br>"
                f"适应度得分: {best_alpha.fitness_score:.4f if best_alpha.fitness_score is not None else 'N/A'}"
            )

            # --- DEV-046: OOS 模拟逻辑开始 ---
            perform_oos = ga_config.get('perform_oos_simulation', False)
            if perform_oos:
                logger.info(f"为实验 {experiment_id} 的最佳Alpha ID {best_alpha.id} 触发OOS模拟。")
                oos_simulation_params = ga_config.get('oos_simulation_parameters')
                if not oos_simulation_params or not isinstance(oos_simulation_params, dict):
                    logger.warning(f"实验 {experiment_id} 配置中缺少或无效的 'oos_simulation_parameters'，跳过OOS模拟。")
                    oos_results_summary_for_email = "OOS模拟跳过 (配置缺失)。"
                else:
                    base_sim_settings = best_alpha.simulation_settings_json if best_alpha.simulation_settings_json else \
                                        ga_config.get('simulation_config_json', {}).get('settings', {}) # 从实验的simulation_config_json获取基础设置

                    if not base_sim_settings: # 如果完全没有基础设置
                        logger.error(f"无法为Alpha ID: {best_alpha.id} 找到基础模拟设置，无法执行OOS。")
                        oos_results_summary_for_email = "OOS模拟失败 (无基础设置)。"
                    else:
                        oos_payload_settings = base_sim_settings.copy()
                        oos_payload_settings.update(oos_simulation_params)
                        # 假设API通过settings中的特定参数（如 "simulationMode": "OOS" 或日期范围）区分OOS
                        # oos_payload_settings["simulationMode"] = "OOS" # 示例，具体参数需根据API文档

                        oos_simulate_data = {
                            "settings": oos_payload_settings,
                            "regularAlpha": best_alpha.expression
                        }
                        try:
                            logger.info(f"提交OOS模拟 Alpha ID: {best_alpha.id}, OOS设置: {oos_payload_settings}")
                            # DEV-006: run_simulation_and_get_results封装了start和progress
                            oos_results_json = brain_api.run_simulation_and_get_results(simulate_data=oos_simulate_data)

                            alpha_to_update = db.query(AlphaModel).filter(AlphaModel.id == best_alpha.id).first() # 重新获取以防会话问题
                            if alpha_to_update:
                                if oos_results_json and not oos_results_json.get("error_message") and oos_results_json.get('status', '').upper() == 'COMPLETED':
                                    logger.info(f"Alpha ID: {best_alpha.id} OOS模拟成功。")
                                    # 假设OOS统计数据在 'oos_stats' 或直接在结果的顶层
                                    alpha_to_update.oos_stats_json = oos_results_json.get('oos_stats', oos_results_json.get('is_stats', oos_results_json))
                                    db.add(alpha_to_update); db.commit()
                                    logger.info(f"Alpha ID: {best_alpha.id} OOS统计数据已保存。")
                                    oos_results_summary_for_email = "OOS模拟成功完成。"
                                else:
                                    error_msg = oos_results_json.get("error_message", "未知OOS模拟错误") if oos_results_json else "OOS模拟结果为空"
                                    logger.error(f"Alpha ID: {best_alpha.id} OOS模拟失败: {error_msg}")
                                    alpha_to_update.simulation_error_message = (alpha_to_update.simulation_error_message or "") + f"; OOS Error: {error_msg}" # 追加OOS错误
                                    db.add(alpha_to_update); db.commit()
                                    oos_results_summary_for_email = f"OOS模拟失败: {error_msg}"
                            else:
                                logger.error(f"未能找到Alpha ID: {best_alpha.id} 以更新OOS数据。")
                                oos_results_summary_for_email = "OOS模拟数据存储失败 (Alpha未找到)。"
                        except requests.exceptions.RequestException as req_err: # 网络/请求级别错误
                            logger.error(f"OOS模拟 API请求失败 Alpha ID: {best_alpha.id}: {req_err}", exc_info=True)
                            oos_results_summary_for_email = f"OOS模拟API请求失败: {str(req_err)[:100]}"
                        except Exception as oos_exc: # 其他所有执行OOS模拟的异常
                            logger.error(f"OOS模拟时发生异常 Alpha ID: {best_alpha.id}: {oos_exc}", exc_info=True)
                            oos_results_summary_for_email = f"OOS模拟时发生内部错误: {str(oos_exc)[:100]}"
            else: # perform_oos is False
                oos_results_summary_for_email = "OOS模拟未执行 (根据配置)。"
                logger.info(f"实验 {experiment_id}: 跳过OOS模拟 (配置未启用)。")
            # --- OOS 模拟逻辑结束 ---
        else:
            best_alpha_details = "未能找到最佳Alpha信息。"
            oos_results_summary_for_email = "OOS模拟未执行 (无最佳Alpha)。"


        return f"实验 {experiment_id} 成功完成。"

    except Exception as e:
        logger.error(f"实验 {experiment_id} 遗传算法任务失败: {e}", exc_info=True)
        task_final_status = "执行失败"
        error_info = f"{type(e).__name__}: {str(e)}"
        if experiment:
            experiment.status = "FAILED"
            if hasattr(experiment, 'error_message'):
                experiment.error_message = error_info[:499]
            if not experiment.end_time:
                experiment.end_time = datetime.now(timezone.utc)
            db.add(experiment)
            db.commit()
        raise

    finally:
        if experiment:
            recipient = os.environ.get("DEFAULT_NOTIFICATION_RECIPIENT")
            if recipient:
                exp_name = experiment.name if experiment.name else f"ID {experiment_id}"
                start_time_obj = experiment.start_time
                if start_time_obj and start_time_obj.tzinfo is None:
                    start_time_obj = start_time_obj.replace(tzinfo=timezone.utc)
                exp_start_time_str = start_time_obj.strftime("%Y-%m-%d %H:%M:%S %Z") if start_time_obj else "未知"
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
                    ".oos-details { border-left-color: #95de9c; }", # Greenish for OOS
                    "pre { white-space: pre-wrap; word-wrap: break-word; background-color: #e9ecef; padding: 10px; border-radius: 4px;}",
                    "hr { border: none; border-top: 1px solid #eee; margin: 20px 0; }",
                    ".footer { font-size: 0.9em; color: #777; margin-top: 20px; text-align: center; }",
                    "</style></head><body>",
                    f"<h1>实验执行通知</h1>",
                    f"<p><strong>实验名称:</strong> {exp_name}</p>",
                    f"<p><strong>实验ID:</strong> {experiment_id}</p>"
                ]
                status_class = "status-unknown"
                if task_final_status == "成功完成": status_class = "status-success"
                elif "失败" in task_final_status: status_class = "status-failed"
                html_parts.append(f"<p><strong>状态:</strong> <span class='{status_class}'>{task_final_status}</span></p>")
                html_parts.append(f"<p><strong>任务计划/实际开始时间:</strong> {exp_start_time_str}</p>")
                html_parts.append(f"<p><strong>通知生成时间 (任务结束):</strong> {exp_end_time_str}</p>")
                if task_final_status == "成功完成":
                    html_parts.append(f"<h2>实验结果摘要:</h2><div class='details-box alpha-details'>{best_alpha_details if best_alpha_details else '任务已顺利完成，无特定Alpha信息。'}</div>")
                    if oos_results_summary_for_email: # DEV-046: Add OOS summary to email
                         html_parts.append(f"<h2>OOS模拟摘要:</h2><div class='details-box oos-details'>{oos_results_summary_for_email}</div>")
                elif task_final_status != "未知" and error_info:
                    html_parts.append(f"<h2>错误详情:</h2><div class='details-box error-details'><pre>{error_info}</pre></div>")
                html_parts.extend(["<hr><p class='footer'>此邮件为WorldQuant Alpha Evolution系统自动发送。</p></body></html>"])
                body_html = "".join(html_parts)
                logger.info(f"准备发送实验 '{exp_name}' 完成通知邮件至 {recipient}。状态: {task_final_status}")
                if not send_email(recipient, subject, body_html):
                    logger.error(f"发送实验 '{exp_name}' 通知邮件失败。")
            else:
                logger.warning("DEFAULT_NOTIFICATION_RECIPIENT 未设置，无法发送任务完成邮件。")
        if db: db.close()
        logger.info(f"遗传算法任务处理完成，实验ID: {experiment_id}, Job ID: {job.id if job else 'N/A'}")
    return f"任务处理流程已结束，实验ID: {experiment_id}，最终状态: {task_final_status}"

[end of app/tasks.py]
