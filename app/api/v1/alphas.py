# FastAPI 和 Pydantic 相关导入
from fastapi import APIRouter, Depends, HTTPException, status, Query # Query 可能在此文件用不到，但先导入以保持一致性
from typing import List, Optional # List 可能在未来扩展时用到

# SQLAlchemy 相关导入
from sqlalchemy.orm import Session

# 应用内部模块导入
from app.database import get_db # 数据库会话依赖
from app.schemas import AlphaDetailsResponse, AlphaResponse # Pydantic 模型 (AlphaResponse 可能用于未来扩展)
from app.models import Alpha # SQLAlchemy ORM 模型

# 标准库导入
import logging # 日志记录

# 获取一个日志记录器实例
logger = logging.getLogger(__name__)

# --- API 路由器定义 ---
# 创建一个 APIRouter 实例，用于定义与单个 Alpha 资源相关的 API 端点。
# prefix="/alphas": 此路由器下所有端点的路径都将以 "/alphas" 开头。
# tags=["Alpha管理"]: 在 OpenAPI/Swagger 文档中，这些端点将被分组在 "Alpha管理" 标签下。
router = APIRouter(
    prefix="/alphas",
    tags=["Alpha管理"]
)

# 后续将在此 router 实例上定义具体的API端点，例如:
# @router.get("/{alpha_id}", response_model=AlphaDetailsResponse)

@router.get(
    "/{alpha_id}",
    response_model=AlphaDetailsResponse,
    summary="获取单个Alpha的详细信息",
    description="根据Alpha的唯一ID获取其所有详细数据，包括基本信息、父代、模拟设置、各类统计数据（样本内、样本外、PnL、年度）等。"
)
async def get_alpha_details(
    alpha_id: int,
    db: Session = Depends(get_db)
):
    """
    获取指定ID的单个Alpha策略的全部详细信息。

    参数:
        alpha_id (int): 要获取详情的Alpha的ID (路径参数)。
        db (Session): SQLAlchemy 数据库会话依赖注入。

    返回:
        AlphaDetailsResponse: 包含Alpha所有详细信息的响应对象。

    异常:
        HTTPException (404): 如果具有指定ID的Alpha未找到。
        HTTPException (500): 如果发生其他意外的服务器内部错误。
    """
    logger.info(f"收到获取Alpha详情的请求，Alpha ID: {alpha_id}")

    try:
        # 1. 从数据库查询 Alpha 对象
        # 可以使用 .options(selectinload(Alpha.experiment)) 等来预加载关联的实验信息，
        # 但 AlphaDetailsResponse 目前不直接包含整个 Experiment 对象，所以简单查询即可。
        alpha_orm = db.query(Alpha).filter(Alpha.id == alpha_id).first()

        if not alpha_orm:
            logger.warning(f"Alpha ID {alpha_id} 在数据库中未找到。")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ID为 {alpha_id} 的Alpha未找到。")

        logger.debug(f"成功从数据库获取Alpha {alpha_id} 的记录。表达式: {alpha_orm.expression[:50]}...") # 日志中截断长表达式

        # 2. Pydantic 模型会自动从 ORM 对象转换字段
        # AlphaDetailsResponse 的 Config 中设置了 orm_mode = True
        # 确保 AlphaDetailsResponse 定义的字段名与 Alpha ORM 模型的属性名匹配，
        # 或者使用 Pydantic 的 alias 功能。
        # 当前设计是匹配的。

        return alpha_orm # FastAPI 会自动使用 AlphaDetailsResponse(orm_mode=True) 来序列化 alpha_orm

    except HTTPException: # 重新抛出已由我们处理的 HTTPException (如 404)
        raise
    except Exception as e:
        logger.error(f"获取Alpha {alpha_id} 详情时发生未预料的服务器内部错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取Alpha {alpha_id} 详情时发生内部错误: {str(e)}"
        )

# ... (文件末尾，未来可能有其他与单个Alpha操作相关的端点，如删除、更新标记等)
