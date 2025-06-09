# app/api/v1/experiments.py
# 此模块处理与遗传编程实验相关的 API 端点，包括创建、列表查询和详情获取。

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime # 用于生成时间戳或比较

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from rq import Queue
from rq.job import Job, NoSuchJobError # Job用于类型提示和获取任务状态

from app.database import get_db # FastAPI依赖项，用于获取数据库会话
from app.models import Experiment # SQLAlchemy Experiment模型
# 从 schemas 导入请求和响应Pydantic模型
from app.schemas import (
    ExperimentCreate,
    ExperimentResponse,
    ExperimentListResponse,
    ExperimentProgress # 用于构建进度信息
)
from app.tasks import run_genetic_algorithm_task # 要提交到RQ的任务函数
from .dependencies import get_rq_queue # 从同级目录的dependencies.py导入get_rq_queue

# 初始化当前模块的 logger
logger = logging.getLogger(__name__)

# 创建一个 APIRouter 实例，用于定义此模块中的路由
# prefix="/experiments": 所有端点路径前缀为 /experiments
# tags=["Experiments"]: 在 OpenAPI 文档中归类到 "Experiments"
router = APIRouter(prefix="/experiments", tags=["Experiments"])

def _get_experiment_progress(
    exp: Experiment,
    rq_job_id: Optional[str],
    queue: Queue
) -> Optional[ExperimentProgress]:
    """
    辅助函数，用于获取并计算指定实验的 RQ 任务进度。

    Args:
        exp (Experiment): SQLAlchemy Experiment 对象。
        rq_job_id (Optional[str]): 与实验关联的 RQ Job ID。
        queue (Queue): RQ 队列实例。

    Returns:
        Optional[ExperimentProgress]: 实验的进度信息模型，如果无法获取则返回 None。
    """
    if not rq_job_id:
        logger.debug(f"实验 {exp.id}: 无 RQ Job ID，无法获取任务进度。")
        return None

    try:
        job = Job.fetch(rq_job_id, connection=queue.connection)

        # 从 job.meta 获取进度信息，这是由 _report_progress 在任务中设置的
        current_iter = job.meta.get('progress', {}).get('iteration', exp.current_iteration or 0)
        status_message = job.meta.get('progress', {}).get('message', job.get_status(refresh=False)) # refresh=False 避免过多redis调用
        rq_job_status = job.get_status(refresh=False)

        # 从实验配置中获取总代数
        total_iter_config = exp.config_json.get("generations")
        if not isinstance(total_iter_config, int) or total_iter_config <= 0:
            logger.warning(f"实验 {exp.id} 的配置中 'generations' 无效 ({total_iter_config})，无法准确计算进度百分比。")
            # 如果总代数无效，将使用当前迭代作为总迭代来计算百分比（可能不准确）
            total_iter = current_iter
            percentage = 0.0 if total_iter == 0 and rq_job_status not in ['finished', 'failed'] else 100.0
        else:
            total_iter = total_iter_config
            percentage = (current_iter / total_iter) * 100 if total_iter > 0 else 0.0

        percentage = round(min(max(percentage, 0.0), 100.0), 2)

        # 如果任务在RQ中已完成或失败，确保百分比和状态反映这一点
        if rq_job_status == 'finished' and current_iter >= total_iter:
            percentage = 100.0
            status_message = job.meta.get('progress', {}).get('message', "已完成") # 优先使用meta中的最终消息
        elif rq_job_status == 'failed':
            # 失败时，百分比可能停留在失败时的进度
            status_message = job.meta.get('progress', {}).get('message', "任务失败")

        return ExperimentProgress(
            current_iteration=current_iter,
            total_iterations=total_iter,
            percentage=percentage,
            status_message=status_message,
            rq_job_status=rq_job_status
        )
    except NoSuchJobError:
        logger.warning(f"实验 {exp.id}: 未找到 RQ Job ID '{rq_job_id}'。可能任务已过期或被清除。")
        # 根据 Experiment 表的最终状态来推断进度
        if exp.status == "COMPLETED":
             return ExperimentProgress(current_iteration=exp.config_json.get("generations", exp.current_iteration or 0),
                                       total_iterations=exp.config_json.get("generations", exp.current_iteration or 0),
                                       percentage=100.0, status_message="已完成 (从数据库状态推断)",
                                       rq_job_status="finished")
        elif exp.status == "FAILED":
             total_iter_fallback = exp.config_json.get("generations", exp.current_iteration or 1) # 避免除以0
             percentage_failed = (exp.current_iteration / total_iter_fallback) * 100 if total_iter_fallback > 0 else 0
             return ExperimentProgress(current_iteration=exp.current_iteration or 0,
                                       total_iterations=total_iter_fallback,
                                       percentage=round(min(max(percentage_failed,0.0),100.0),2),
                                       status_message=f"失败 (从数据库状态推断，错误信息: {exp.error_message or 'N/A'})" if hasattr(exp, 'error_message') else "失败 (从数据库状态推断)",
                                       rq_job_status="failed")
        return None
    except Exception as e:
        logger.error(f"实验 {exp.id}: 获取 RQ Job '{rq_job_id}' 进度时发生错误: {e}", exc_info=True)
        return None


@router.post("/", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment_api(
    exp_data: ExperimentCreate,
    db: Session = Depends(get_db),
    queue: Queue = Depends(get_rq_queue)
):
    """
    创建新的遗传编程实验，并将其提交到 RQ 任务队列执行。
    """
    logger.info(f"收到创建新实验的请求: {exp_data.name}")

    if not isinstance(exp_data.config_json.get("generations"), int) or exp_data.config_json["generations"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="实验配置 'config_json' 必须包含一个有效的 'generations' (正整数) 参数。"
        )

    try:
        db_experiment = Experiment(
            name=exp_data.name, description=exp_data.description,
            config_json=exp_data.config_json, status="PENDING",
            # start_time, current_iteration, random_seed 等由任务或 _report_progress 初始化
        )
        db.add(db_experiment); db.commit(); db.refresh(db_experiment)
        logger.info(f"实验 '{db_experiment.name}' (ID: {db_experiment.id}) 已在数据库中创建，状态: PENDING。")

        job = queue.enqueue(
            run_genetic_algorithm_task, db_experiment.id,
            db_experiment.config_json, job_timeout='24h'
        )

        db_experiment.rq_job_id = job.id
        db.add(db_experiment); db.commit(); db.refresh(db_experiment)
        logger.info(f"任务 run_genetic_algorithm_task 已为实验 {db_experiment.id} 提交到队列 '{queue.name}'。RQ Job ID: {job.id}")

        # 使用 model_validate (Pydantic V2)
        return ExperimentResponse.model_validate(db_experiment)

    except Exception as e:
        logger.error(f"创建实验 '{exp_data.name}' 或提交任务时发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"创建实验或提交任务时发生内部错误: {str(e)}")


@router.get("/", response_model=ExperimentListResponse)
async def get_experiments_api(
    db: Session = Depends(get_db),
    queue: Queue = Depends(get_rq_queue),
    status_filter: Optional[str] = Query(None, alias="status", description="按实验状态过滤 (例如 PENDING, RUNNING, COMPLETED, FAILED)"),
    limit: int = Query(10, ge=1, le=100, description="每页返回的实验数量"),
    offset: int = Query(0, ge=0, description="查询结果的偏移量，用于分页")
):
    """
    获取实验列表，支持按状态过滤和分页。
    """
    logger.info(f"收到获取实验列表请求: status_filter='{status_filter}', limit={limit}, offset={offset}")

    query = db.query(Experiment)
    if status_filter:
        query = query.filter(Experiment.status == status_filter.upper())

    total_count = query.count()
    db_experiments = query.order_by(Experiment.id.desc()).limit(limit).offset(offset).all()

    experiment_responses: List[ExperimentResponse] = []
    for db_exp in db_experiments:
        exp_resp_obj = ExperimentResponse.model_validate(db_exp) # Pydantic V2

        # 为列表中的每个实验获取进度
        exp_resp_obj.progress = _get_experiment_progress(db_exp, db_exp.rq_job_id, queue)
        experiment_responses.append(exp_resp_obj)

    return ExperimentListResponse(total=total_count, experiments=experiment_responses)


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment_details_api(
    experiment_id: int,
    db: Session = Depends(get_db),
    queue: Queue = Depends(get_rq_queue)
):
    """
    获取单个实验的详细信息及其当前进度。
    """
    logger.info(f"收到获取实验详情请求，实验ID: {experiment_id}")

    db_experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if db_experiment is None:
        logger.warning(f"请求的实验ID {experiment_id} 未找到。")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"实验ID {experiment_id} 未找到。")

    exp_resp_obj = ExperimentResponse.model_validate(db_experiment) # Pydantic V2

    # 获取并设置实验进度
    exp_resp_obj.progress = _get_experiment_progress(db_experiment, db_experiment.rq_job_id, queue)

    return exp_resp_obj
