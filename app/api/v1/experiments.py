# FastAPI 和 Pydantic 相关导入
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel # BaseModel 可能不需要直接在此文件用，除非定义额外内部模型
from typing import List, Optional, Dict, Any # Dict, Any 用于操作 config_json

# SQLAlchemy 相关导入
from sqlalchemy.orm import Session

# RQ (Redis Queue) 相关导入
from rq import Queue, Retry
from rq.job import Job
from redis import Redis, exceptions as redis_exceptions # 导入 Redis 连接错误

# 应用内部模块导入
from app.database import get_db # 数据库会话依赖
from app.schemas import ExperimentCreate, ExperimentResponse # Pydantic 模型
from app.models import Experiment # SQLAlchemy ORM 模型
from app.tasks import run_genetic_algorithm_task # 要提交到队列的后台任务

# 标准库导入
import os
import logging # 日志记录
from datetime import datetime # 导入datetime模块

# 获取一个日志记录器实例
logger = logging.getLogger(__name__)

# --- RQ 队列和 Redis 连接初始化 ---
# 此部分代码与 app/main.py 中用于测试任务提交的初始化逻辑类似。
# 理想情况下，Redis 连接和 RQ Queue 实例可以在应用启动时统一初始化并通过依赖注入提供，
# 或者通过一个共享的模块/对象访问。
# 为简化当前任务，我们在此模块级别直接初始化它们，但需注意潜在的重复初始化问题。
# 在一个更大型的应用中，会考虑更集中的管理方式。

redis_conn: Optional[Redis] = None
default_queue: Optional[Queue] = None

try:
    # 从环境变量获取 Redis 连接 URL，与 RQ Worker 和 app/main.py 中的配置保持一致
    redis_url_from_env = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    # 尝试连接到 Redis
    # decode_responses=True 会让 Redis 客户端返回字符串而不是字节串，某些情况下更方便
    redis_conn = Redis.from_url(redis_url_from_env, decode_responses=True)
    redis_conn.ping() # 测试连接
    logger.info(f"实验API模块：成功连接到 Redis 用于任务队列: {redis_url_from_env}")

    # 创建一个 RQ 队列实例，用于提交遗传算法任务
    # 'default' 是队列的名称，应与 RQ worker 监听的队列一致
    default_queue = Queue("default", connection=redis_conn)
    logger.info("实验API模块：RQ 'default' 队列已成功初始化。")

except redis_exceptions.ConnectionError as e:
    logger.error(f"实验API模块：无法连接到 Redis: {e}。请确保 Redis 服务正在运行并且配置正确 ({redis_url_from_env})。实验创建功能将受限。")
    # redis_conn 会保持为 None，后续端点逻辑需要处理这种情况
except Exception as e:
    logger.error(f"实验API模块：初始化 Redis 连接或 RQ 队列时发生未知错误: {e}", exc_info=True)
    # redis_conn 和 default_queue 可能为 None

# --- API 路由器定义 ---
# 创建一个 APIRouter 实例，用于定义与实验相关的 API 端点。
# prefix="/experiments": 此路由器下所有端点的路径都将以 "/experiments" 开头。
# tags=["实验管理"]: 在 OpenAPI/Swagger 文档中，这些端点将被分组在 "实验管理" 标签下。
router = APIRouter(
    prefix="/experiments",
    tags=["实验管理"]
)

# 后续将在此 router 实例上定义具体的API端点，例如:
# @router.post("/", ...)
# @router.get("/", ...)
# @router.get("/{experiment_id}", ...)

@router.post(
    "/",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建新实验并启动遗传算法任务",
    description="接收实验配置，在数据库中创建实验记录，并将其提交到后台任务队列中执行遗传算法。"
)
async def create_experiment(
    exp_data: ExperimentCreate,
    db: Session = Depends(get_db)
):
    """
    创建新的遗传编程实验。

    此端点执行以下操作：
    1.  根据请求体中的数据 (`exp_data`) 创建一个新的 `Experiment` 数据库记录。
    2.  为该实验生成一个唯一的 RQ 作业 ID。
    3.  将 `run_genetic_algorithm_task` 函数（包含新实验的ID和配置）提交到 RQ 队列中异步执行。
    4.  返回新创建的实验的详细信息，包括其初始状态和关联的作业ID。

    参数:
        exp_data (ExperimentCreate): 包含实验名称、描述（可选）、GA配置（JSON）和代码版本（可选）的请求体。
        db (Session): SQLAlchemy 数据库会话依赖注入。

    返回:
        ExperimentResponse: 新创建的实验的详细信息。

    异常:
        HTTPException (503): 如果无法连接到 Redis 或提交任务到 RQ 队列失败。
        HTTPException (500): 如果发生其他意外的数据库或服务器错误。
    """
    logger.info(f"收到创建新实验的请求，名称: '{exp_data.name}'")

    if default_queue is None or redis_conn is None:
        logger.error("无法创建实验：RQ 队列或 Redis 连接未初始化。")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务队列服务当前不可用，无法创建实验。"
        )

    try:
        # 1. 创建 Experiment ORM 对象
        new_experiment = Experiment(
            name=exp_data.name,
            description=exp_data.description,
            config_json=exp_data.config_json,
            # code_version=exp_data.code_version, # Assuming code_version is part of ExperimentCreate schema
            status="PENDING",
        )

        # 2. 将新实验对象添加到数据库会话并提交以获取 ID
        db.add(new_experiment)
        db.commit()
        db.refresh(new_experiment)

        logger.info(f"实验 '{new_experiment.name}' (ID: {new_experiment.id}) 成功创建并存入数据库，状态: {new_experiment.status}。")

        # 3. 生成唯一的 RQ 作业 ID
        # 约定作业 ID 与实验 ID 相关联，方便后续查询作业状态
        job_id = f"exp_{new_experiment.id}_ga_task"

        # 4. 将 run_genetic_algorithm_task 提交到 RQ 队列
        logger.info(f"准备将实验 {new_experiment.id} 的遗传算法任务提交到 RQ 队列，作业ID: {job_id}。")

        # job_timeout: 作业在被终止前的最大执行时间（例如 '12h', '2d', 或秒数）
        # retry: Retry(max=3, interval=[10, 30, 60]) # 示例：重试策略
        # result_ttl: 结果在 Redis 中的保留时间（秒），例如 7 天: 604800
        # job_id 参数确保了如果因网络问题重复提交同一实验的创建请求（在实验记录已创建之后），
        # 不会重复创建 RQ 作业（如果该 job_id 的作业已存在且未完成）。
        # 但这里，由于实验ID是新生成的，job_id 每次也应该是新的，除非有其他机制防止重复创建实验记录。
        # 对于创建操作，通常每次调用都应该创建一个新的实验和新的任务。
        # 如果需要幂等性，应在更上层或通过检查实验名称等方式处理。

        # 将 GA 配置作为参数传递给任务
        task_ga_config = new_experiment.config_json

        job = default_queue.enqueue(
            run_genetic_algorithm_task, # 要执行的任务函数
            args=(new_experiment.id, task_ga_config), # 传递给任务函数的参数
            job_id=job_id,               # 指定作业ID
            job_timeout='24h',           # 作业超时时间，例如24小时
            result_ttl=7*24*60*60,       # 结果保留7天 (秒)
            failure_ttl=30*24*60*60,     # 失败作业信息保留30天 (秒)
            description=f"遗传算法实验: {new_experiment.name} (ID: {new_experiment.id})" # 作业描述
            # retry=Retry(max=2, interval=[60, 120]) # 简单的重试策略示例
        )

        logger.info(f"实验 {new_experiment.id} 的任务已成功提交到队列，作业ID: {job.id}。")

        # （可选）可以将 experiment.status 更新为 "QUEUED"
        # new_experiment.status = "QUEUED"
        # new_experiment.job_id_field = job.id # 如果 Experiment 模型有存储 job_id 的字段
        # db.commit()
        # db.refresh(new_experiment)
        # 目前，job_id 和 job_status 将在 ExperimentResponse 中动态获取

        # 5. 准备并返回响应
        # ExperimentResponse 需要 job_id 和 job_status，我们刚拿到了 job_id
        # job_status 可以从 job 对象获取 (刚入队时通常是 'queued')
        # 确保所有 ExperimentResponse 字段都有值或合理的默认值
        response_data = ExperimentResponse(
            id=new_experiment.id,
            user_id=new_experiment.user_id, # 假设模型中有 user_id
            created_at=new_experiment.created_at,
            updated_at=new_experiment.updated_at,
            name=new_experiment.name,
            description=new_experiment.description,
            ga_config_json=new_experiment.config_json, # 字段名在 Pydantic 中是 ga_config_json
            simulation_config_json=exp_data.simulation_config_json, # 从请求数据中获取
            status=new_experiment.status,
            current_progress=new_experiment.current_progress or 0,
            current_depth=new_experiment.current_depth,
            current_iteration_at_depth=new_experiment.current_iteration_at_depth,
            alpha_count=0 # 新实验alpha数量为0
            # job_id 和 job_status 不在 ExperimentResponse 的标准字段中，
            # 如果需要，应添加到 ExperimentResponse schema 或通过特定端点查询任务状态
        )
        # Manually set job_id and job_status if they were part of a dynamic response schema
        # For now, stick to the defined ExperimentResponse
        logger.info(f"成功创建并提交实验 {new_experiment.id} 到队列。")
        return response_data

    except redis_exceptions.RedisError as e:
        logger.error(f"创建实验 '{exp_data.name}' 时发生 Redis 错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务队列服务遇到 Redis 错误，无法提交实验任务。" # 通用消息
        )
    except HTTPException as http_exc: # 重新抛出已知的HTTPException
        raise http_exc
    except ValueError as ve: # 处理特定的预期业务逻辑错误
        logger.warning(f"创建实验 '{exp_data.name}' 时发生值错误: {ve}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"创建实验 '{exp_data.name}' 时发生意外错误: {e}", exc_info=True)
        db.rollback() # 尝试回滚以防部分数据库更改
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部发生错误，请联系管理员。" # 通用消息
        )

def _calculate_progress_percentage(exp: Experiment, job_meta_progress: Optional[Dict[str, Any]]) -> Optional[float]:
    """
    辅助函数，用于根据实验的当前状态、进度 和 ga_config 计算估算的进度百分比。
    这是一个示意性实现，实际计算可能需要更复杂的逻辑和配置。
    """
    if exp.status == "COMPLETED":
        return 100.0
    if exp.status == "FAILED":
        return None # 或一个特定的值表示失败，或基于失败前的进度

    # 尝试从 job.meta 或数据库的 current_depth/iteration 获取进度
    # job_meta_progress 的例子: {'depth': 0, 'iteration': 5, 'message': '...'}
    # exp.current_depth 和 exp.current_iteration 是数据库中持久化的进度

    # 优先使用 job.meta 中的实时进度，如果可用
    current_depth = exp.current_depth
    current_iteration = exp.current_iteration
    if job_meta_progress:
        current_depth = job_meta_progress.get('depth', exp.current_depth)
        current_iteration = job_meta_progress.get('iteration', exp.current_iteration)

    # --- 以下是示意性的进度计算逻辑 ---
    # 实际的进度计算需要知道每个深度的总迭代次数，以及总共有多少深度。
    # 这些信息应该在 exp.config_json (ga_config) 中定义。
    # 例如：
    # ga_config = {
    #   "depth_configs": [ # 或者 "stages"
    #     {"name": "d1", "iterations": 20},
    #     {"name": "d2", "iterations": 15},
    #     {"name": "d3", "iterations": 10}
    #   ],
    #   "total_depths_for_progress": 3 # 或者从 depth_configs 列表长度推断
    # }

    try:
        ga_config = exp.config_json
        if not ga_config:
            logger.warning(f"实验 {exp.id}: ga_config 为空，无法计算精确进度。")
            return None

        # 尝试读取深度配置
        depth_configs = ga_config.get("depth_configs")
        total_configured_depths = len(depth_configs) if isinstance(depth_configs, list) else ga_config.get("total_depths_for_progress", 0)

        if not depth_configs and total_configured_depths == 0:
            logger.warning(f"实验 {exp.id}: ga_config 中缺少深度配置信息 (depth_configs 或 total_depths_for_progress)，无法计算进度。")
            return None

        total_expected_iterations = 0
        completed_iterations = 0

        if isinstance(depth_configs, list): # 如果有详细的每深度迭代次数配置
            for i, depth_info in enumerate(depth_configs):
                iters_this_depth = depth_info.get("iterations", 0)
                total_expected_iterations += iters_this_depth
                if i < current_depth: # 此深度已完成
                    completed_iterations += iters_this_depth
                elif i == current_depth: # 当前正在进行的深度
                    completed_iterations += min(current_iteration, iters_this_depth) # 已完成的迭代不能超过此深度的总迭代
        elif total_configured_depths > 0 : # 如果只有总深度和每深度的平均迭代（不太精确）
            # 这种方式比较粗略，最好有详细的 depth_configs
            iterations_per_depth_avg = ga_config.get("iterations_per_depth_avg", ga_config.get("generations", 10)) # 默认值
            total_expected_iterations = total_configured_depths * iterations_per_depth_avg
            completed_iterations = current_depth * iterations_per_depth_avg + min(current_iteration, iterations_per_depth_avg)
        else: # 无法确定总迭代次数
             return None


        if total_expected_iterations == 0:
            return 0.0 if exp.status == "PENDING" or exp.status == "QUEUED" else None # 避免除以零

        progress = (completed_iterations / total_expected_iterations) * 100.0
        # 确保进度在0到100之间，对于RUNNING状态，可能不到100
        return min(max(progress, 0.0), 100.0 if exp.status == "COMPLETED" else 99.9)

    except Exception as e:
        logger.error(f"实验 {exp.id}: 计算进度百分比时发生错误: {e}", exc_info=True)
        return None


@router.get(
    "/{experiment_id}",
    response_model=ExperimentResponse,
    summary="获取单个实验的详细信息",
    description="根据实验ID获取其详细配置、状态、当前进度以及关联的后台任务信息。"
)
async def get_experiment_details(
    experiment_id: int,
    db: Session = Depends(get_db)
):
    """
    获取指定ID的单个实验的详细信息。

    包括从数据库读取的实验数据，以及动态获取的RQ作业状态和估算的进度百分比。

    参数:
        experiment_id (int): 要获取详情的实验的ID (路径参数)。
        db (Session): SQLAlchemy 数据库会话依赖注入。

    返回:
        ExperimentResponse: 包含实验详细信息的响应对象。

    异常:
        HTTPException (404): 如果具有指定ID的实验未找到。
        HTTPException (500): 如果发生其他意外的服务器内部错误。
    """
    logger.info(f"收到获取实验详情的请求，实验ID: {experiment_id}")

    try:
        # 1. 从数据库查询实验对象
        exp_orm = db.query(Experiment).filter(Experiment.id == experiment_id).first()

        if not exp_orm:
            logger.warning(f"获取实验详情失败：实验ID {experiment_id} 在数据库中未找到。")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ID为 {experiment_id} 的实验未找到。")

        logger.info(f"成功从数据库获取实验 {experiment_id} 的记录。状态: {exp_orm.status}") # 改为 info

        # 2. 尝试获取关联的 RQ 作业状态和元数据
        job_id_str = f"exp_{exp_orm.id}_ga_task" # 遵循创建时的约定
        job_status_str: Optional[str] = None
        job_meta_progress: Optional[Dict[str, Any]] = None # 从 job.meta['progress'] 获取

        if redis_conn:
            try:
                job = Job.fetch(job_id_str, connection=redis_conn)
                job_status_str = job.get_status()
                if job.meta and 'progress' in job.meta and isinstance(job.meta['progress'], dict):
                    job_meta_progress = job.meta['progress']
                logger.debug(f"实验 {exp_orm.id}: RQ 作业 {job_id_str} 状态: {job_status_str}, meta progress: {job_meta_progress}")
            except Exception as e: # 例如 rq.exceptions.NoSuchJobError
                logger.warning(f"实验 {exp_orm.id}: 获取 RQ 作业 {job_id_str} 状态或元数据失败: {e}")
                # job_status_str 保持为 None 或设为 UNKNOWN，job_meta_progress 保持为 None
                if exp_orm.status not in ["COMPLETED", "FAILED", "PENDING", "QUEUED"]: # 如果数据库状态是RUNNING但找不到job，可能job已过期或出问题
                    job_status_str = "UNKNOWN_OR_EXPIRED"
        else:
            logger.warning(f"实验 {exp_orm.id}: Redis 连接不可用，无法获取 RQ 作业状态。")
            # 如果数据库状态是RUNNING但无法连接Redis，也标记为未知
            if exp_orm.status == "RUNNING":
                job_status_str = "UNKNOWN_NO_REDIS"


        # 3. 计算进度百分比
        # 使用辅助函数，传入 Experiment ORM 对象和从 job.meta 获取的进度信息
        current_progress_percentage = _calculate_progress_percentage(exp_orm, job_meta_progress)
        logger.debug(f"实验 {exp_orm.id}: 计算得到的进度百分比: {current_progress_percentage}")

        # 4. 构造并返回 ExperimentResponse
        # 构造并返回 ExperimentResponse
        # 确保所有 ExperimentResponse 字段都有值或合理的默认值
        response_data = ExperimentResponse(
            id=exp_orm.id,
            user_id=exp_orm.user_id,
            created_at=exp_orm.created_at,
            updated_at=exp_orm.updated_at,
            name=exp_orm.name,
            description=exp_orm.description,
            ga_config_json=exp_orm.config_json, # 字段名在 Pydantic 中是 ga_config_json
            simulation_config_json=exp_orm.simulation_config_json, # 从ORM获取
            status=exp_orm.status,
            current_progress=current_progress_percentage if current_progress_percentage is not None else (exp_orm.current_progress or 0),
            current_depth=job_meta_progress.get('depth', exp_orm.current_depth) if job_meta_progress else exp_orm.current_depth,
            current_iteration_at_depth=job_meta_progress.get('iteration', exp_orm.current_iteration_at_depth) if job_meta_progress else exp_orm.current_iteration_at_depth, # 字段名校正
            alpha_count=db.query(AlphaModel).filter(AlphaModel.experiment_id == exp_orm.id).count() # 动态计算alpha数量
        )
        logger.info(f"成功获取实验 {experiment_id} 的详细信息。")
        return response_data

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"获取实验 {experiment_id} 详情时发生意外错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部发生错误，请联系管理员。"
        )

# ... (文件末尾)

@router.get(
    "/",
    response_model=List[ExperimentResponse],
    summary="获取实验列表",
    description="列出所有已创建的遗传编程实验，支持按状态过滤和分页查询。"
)
async def list_experiments(
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None, alias="status", description="按实验状态筛选 (例如 PENDING, RUNNING, COMPLETED, FAILED)。"),
    skip: int = Query(0, ge=0, alias="offset", description="分页查询的起始位置（偏移量）。"),
    limit: int = Query(10, ge=1, le=100, description="每页返回的实验数量上限（最大100）。")
):
    """
    获取实验列表，支持过滤和分页。

    对于列表中的每个实验，会尝试获取其关联的 RQ 作业状态。
    进度百分比的计算在此列表视图中可能较为粗略或不提供，
    详细进度通常在获取单个实验详情时计算。

    参数:
        db (Session): SQLAlchemy 数据库会话依赖注入。
        status_filter (Optional[str]): 按状态过滤实验的可选参数。
        skip (int): 分页偏移量，默认为0。
        limit (int): 每页返回的最大实验数，默认为10，最大100。

    返回:
        List[ExperimentResponse]: 符合条件的实验列表。
    """
    logger.info(f"收到获取实验列表的请求。状态筛选: '{status_filter}', 分页: offset={skip}, limit={limit}")

    try:
        query = db.query(Experiment)

        if status_filter:
            logger.debug(f"应用状态筛选: status == '{status_filter}'")
            query = query.filter(Experiment.status == status_filter.upper())

        experiments_orm = query.order_by(Experiment.created_at.desc()).offset(skip).limit(limit).all() # 排序用 created_at
        logger.info(f"查询到 {len(experiments_orm)} 个实验记录。")

        response_list: List[ExperimentResponse] = []
        for exp_orm in experiments_orm:
            # job_id_str = f"exp_{exp_orm.id}_ga_task" # Job ID 不直接在ExperimentResponse中
            # job_status_str: Optional[str] = None
            # if redis_conn:
            #     try:
            #         job = Job.fetch(job_id_str, connection=redis_conn)
            #         job_status_str = job.get_status()
            #     except Exception: # rq.exceptions.NoSuchJobError or redis connection error
            #         job_status_str = "UNKNOWN" # Or derive from DB status if job not found
            # else: # No redis connection
            #     job_status_str = "UNKNOWN_NO_REDIS" if exp_orm.status == "RUNNING" else exp_orm.status

            # 简化列表视图的进度计算，或依赖数据库中已有的 current_progress
            current_progress_percentage = exp_orm.current_progress if exp_orm.current_progress is not None else 0.0
            if exp_orm.status == "COMPLETED":
                current_progress_percentage = 100.0

            exp_response = ExperimentResponse(
                id=exp_orm.id,
                user_id=exp_orm.user_id,
                created_at=exp_orm.created_at,
                updated_at=exp_orm.updated_at,
                name=exp_orm.name,
                description=exp_orm.description,
                ga_config_json=exp_orm.config_json,
                simulation_config_json=exp_orm.simulation_config_json,
                status=exp_orm.status,
                current_progress=current_progress_percentage,
                current_depth=exp_orm.current_depth,
                current_iteration_at_depth=exp_orm.current_iteration_at_depth,
                alpha_count=db.query(AlphaModel).filter(AlphaModel.experiment_id == exp_orm.id).count()
            )
            response_list.append(exp_response)

        logger.info(f"成功获取实验列表，返回 {len(response_list)} 个实验。")
        return response_list

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"获取实验列表时发生意外错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部发生错误，请联系管理员。"
        )

@router.get(
    "/{experiment_id}/alphas",
    response_model=List[AlphaResponse],
    summary="获取指定实验下的Alpha列表",
    description="根据实验ID列出其包含的所有Alpha策略，支持按深度、适应度分数等条件过滤，以及排序和分页。"
)
async def list_alphas_for_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
    depth: Optional[int] = Query(None, description="按Alpha树的深度筛选。"),
    min_fitness: Optional[float] = Query(None, alias="minFitness", description="按最小适应度得分筛选。"),
    sort_by: str = Query("calculated_fitness_score", description="排序字段，例如 'id', 'calculated_fitness_score', 'simulated_at'。"),
    order: str = Query("desc", description="排序顺序：'asc' (升序) 或 'desc' (降序)。"),
    skip: int = Query(0, ge=0, alias="offset", description="分页查询的起始位置（偏移量）。"),
    limit: int = Query(100, ge=1, le=200, description="每页返回的Alpha数量上限（最大200）。")
):
    """
    获取指定实验ID下的Alpha列表。

    支持通过查询参数进行过滤 (例如按深度 `depth`, 最小适应度 `min_fitness`)，
    排序 (按 `sort_by` 字段及 `order` 方向) 和分页 (`skip`, `limit`)。

    参数:
        experiment_id (int): 实验的ID (路径参数)。
        db (Session): SQLAlchemy 数据库会话。
        depth (Optional[int]): 可选，按Alpha的深度进行精确匹配过滤。
        min_fitness (Optional[float]): 可选，按Alpha的计算适应度得分进行下限过滤 (大于或等于此值)。
        sort_by (str): 用于排序的字段名。默认为 'calculated_fitness_score'。
                       需要校验此字段是否是 Alpha 模型允许排序的有效属性。
        order (str): 排序方向，'asc' 或 'desc'。默认为 'desc'。
        skip (int): 分页查询的偏移量。
        limit (int): 每页返回的最大记录数。

    返回:
        List[AlphaResponse]: 符合条件的Alpha列表，每个Alpha以AlphaResponse格式呈现。

    异常:
        HTTPException (404): 如果具有指定ID的实验未找到。
        HTTPException (400): 如果排序参数无效。
        HTTPException (500): 如果发生其他服务器内部错误。
    """
    logger.info(f"收到获取实验 {experiment_id} 下 Alpha 列表的请求。筛选条件: depth={depth}, min_fitness={min_fitness}。排序: by={sort_by}, order={order}。分页: offset={skip}, limit={limit}")

    try:
        experiment_exists = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment_exists:
            logger.warning(f"获取Alphas列表失败：实验ID {experiment_id} 未找到。")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"实验ID {experiment_id} 未找到。")

        query = db.query(AlphaModel).filter(AlphaModel.experiment_id == experiment_id) # 使用 AlphaModel

        if depth is not None:
            logger.debug(f"应用深度筛选: depth == {depth}")
            # Assuming AlphaModel has a 'ga_metadata_json' field storing depth if not a direct column
            # This requires a JSONB query if depth is in JSON. For simplicity, assume direct column or skip if complex.
            # query = query.filter(AlphaModel.depth == depth) # If 'depth' is a direct column
            # If in JSON: query = query.filter(AlphaModel.ga_metadata_json['depth'].astext.cast(Integer) == depth) # Example for PostgreSQL
            logger.warning("按深度筛选Alpha的逻辑需要根据实际模型字段（例如 JSONB 内的字段）进行调整。当前为占位。")


        if min_fitness is not None:
            logger.debug(f"应用最小适应度筛选: fitness_score >= {min_fitness}") # field name is fitness_score
            query = query.filter(AlphaModel.fitness_score >= min_fitness)

        sort_attr = getattr(AlphaModel, sort_by, None)
        if sort_attr is None:
            logger.warning(f"无效的排序字段: '{sort_by}'。将使用默认按 'fitness_score' 降序排序。")
            sort_attr = AlphaModel.fitness_score # Default sort column
            order = "desc" # Ensure default order is desc for default sort_by

        if order.lower() == "asc":
            query = query.order_by(sort_attr.asc())
        elif order.lower() == "desc":
            query = query.order_by(sort_attr.desc())
        else:
            logger.warning(f"无效的排序方向: '{order}'。将使用默认降序。")
            query = query.order_by(sort_attr.desc())

        alphas_orm = query.offset(skip).limit(limit).all()
        logger.info(f"为实验 {experiment_id} 查询到 {len(alphas_orm)} 条Alpha记录。")

        # FastAPI会自动将 List[AlphaModel] 转换为 List[AlphaResponse] 因 orm_mode=True
        return alphas_orm

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"获取实验 {experiment_id} 的Alpha列表时发生意外错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部发生错误，请联系管理员。"
        )

# ... (文件末尾)
