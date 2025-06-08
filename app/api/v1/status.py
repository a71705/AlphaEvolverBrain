# app/api/v1/status.py
import logging
import math
from typing import List, Optional
from datetime import datetime, timezone # 确保 timezone 导入
import uuid # 用于 ErrorLogEntry 中的 log_id

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc # 导入 desc 用于排序

from app.database import get_db
from app.models import Alpha as AlphaModel # 使用别名
# from app.core.brain_api import BrainApiSession, get_brain_api_session # 暂时不直接依赖BrainApiSession获取用量
from app.schemas import (
    ApiUsageResponse,
    ErrorLogEntry,
    RecentErrorLogResponse
)

logger = logging.getLogger(__name__)
router = APIRouter() # prefix 和 tags 将在 __init__.py 中定义

@router.get("/api_usage", response_model=ApiUsageResponse)
async def get_api_usage_status(
    # brain_api: BrainApiSession = Depends(get_brain_api_session) # 如果BrainApiSession实现了用量统计，则取消注释
):
    """
    获取对WorldQuant Brain API的使用量统计信息 (当前为模拟或应用级统计)。
    """
    # 真实实现需要 BrainApiSession 提供这些数据
    # usage_stats = brain_api.get_api_usage_stats() # 假设的方法
    # calls_today = usage_stats.get("calls_today", 0)
    # ... 其他统计信息 ...
    try:
        logger.info("请求API使用状态 (当前为模拟数据)。")
        # 实际中，这些信息可能需要从BrainApiSession或一个专门的服务中获取
        # 或者通过分析应用日志来估算调用次数
        # total_calls_today 可以考虑从一个简单计数器或应用级日志聚合中获取，但此处保持为0作为占位符。
        return ApiUsageResponse(
            total_calls_today=0,
            remaining_daily_quota=None,
            total_daily_quota=None,
            quota_reset_time=None,
            data_source="模拟数据/占位符 - 完整功能需增强BrainApiSession或对接平台API以获取真实用量和配额。"
        )
    except Exception as e:
        logger.error(f"获取API使用状态时发生意外错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部发生错误，请联系管理员。"
        )

@router.get("/error_log", response_model=RecentErrorLogResponse)
async def get_recent_error_logs(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页条目数，范围1-100"),
    alpha_id: Optional[str] = Query(None, description="按特定Alpha ID过滤错误日志 (UUID字符串)"),
    experiment_id: Optional[str] = Query(None, description="按特定实验ID过滤错误日志 (UUID字符串)")
):
    """
    获取最近在Alpha模拟或其他关键操作中记录的错误日志。
    这些错误通常保存在 Alpha 模型的 `simulation_error_message` 字段中。
    """
    logger.info(f"查询错误日志：第 {page} 页，每页 {page_size} 条。Alpha ID: {alpha_id}, Experiment ID: {experiment_id}")

    offset = (page - 1) * page_size

    try:
        # 构建基础查询：error_message 不为空且不为空字符串
        query = db.query(AlphaModel).filter(AlphaModel.simulation_error_message != None, AlphaModel.simulation_error_message != "")

        # 应用可选的过滤条件
        if alpha_id:
            try:
                alpha_uuid = uuid.UUID(alpha_id)
                query = query.filter(AlphaModel.id == alpha_uuid)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"提供的Alpha ID '{alpha_id}' 格式无效。")

        if experiment_id:
            try:
                exp_uuid = uuid.UUID(experiment_id)
                query = query.filter(AlphaModel.experiment_id == exp_uuid)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"提供的实验ID '{experiment_id}' 格式无效。")

        total_available_errors = query.count()
        if total_available_errors == 0:
            return RecentErrorLogResponse(errors=[], total_available_errors=0, page=page, page_size=page_size, total_pages=0)

        # 按模拟时间（或记录时间）倒序排列，获取分页结果
        # 使用 updated_at 作为错误记录时间的代理，因为 simulated_at 可能仅在成功模拟时更新
        error_alphas_db = query.order_by(desc(AlphaModel.updated_at)).limit(page_size).offset(offset).all()
        logger.info(f"查询到 {len(error_alphas_db)} 条符合条件的Alpha错误记录。")

        error_entries: List[ErrorLogEntry] = []
        for alpha_db_entry in error_alphas_db:
            # 截断表达式以作预览，避免过长
            expression_preview = (alpha_db_entry.expression[:75] + '...') if alpha_db_entry.expression and len(alpha_db_entry.expression) > 75 else alpha_db_entry.expression

            # 确保时间戳有时区信息，如果数据库中存储的是naive datetime，则假定为UTC
            timestamp_to_use = alpha_db_entry.updated_at # 使用 updated_at 作为错误记录时间
            if timestamp_to_use and timestamp_to_use.tzinfo is None:
                timestamp_to_use = timestamp_to_use.replace(tzinfo=timezone.utc)
            elif not timestamp_to_use: # 如果 updated_at 也可能为 None (理论上不应该)
                timestamp_to_use = datetime.now(timezone.utc) # Fallback

            error_entries.append(ErrorLogEntry(
                log_id=alpha_db_entry.id, # 使用 Alpha 的 ID 作为日志条目的ID
                alpha_id=str(alpha_db_entry.id),
                experiment_id=str(alpha_db_entry.experiment_id) if alpha_db_entry.experiment_id else None,
                timestamp=timestamp_to_use,
                expression_preview=expression_preview,
                error_message=alpha_db_entry.simulation_error_message # 从 simulation_error_message 获取
            ))

        total_pages = math.ceil(total_available_errors / page_size)

        return RecentErrorLogResponse(
            errors=error_entries,
            total_available_errors=total_available_errors,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    except HTTPException as http_exc: # 重新抛出由ID验证或内部逻辑引发的HTTPException
        raise http_exc
    except ValueError as ve: # 特定于业务逻辑的错误 (例如，如果参数验证更复杂)
        logger.warning(f"查询错误日志处理过程中发生值错误: {ve}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"查询错误日志时发生意外错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部发生错误，请联系管理员。" # 标准化通用消息
        )

# 需要在 app/api/v1/__init__.py 中注册这个 router
# (确保已导入：from typing import List, Optional; import logging, math; from datetime import datetime, timezone; import uuid)
# (确保已导入：from fastapi import APIRouter, Depends, Query, HTTPException, status; from sqlalchemy.orm import Session; from sqlalchemy import desc)
# (确保已导入：from app.database import get_db; from app.models import Alpha as AlphaModel)
# (确保已导入：from app.schemas import ApiUsageResponse, ErrorLogEntry, RecentErrorLogResponse)
