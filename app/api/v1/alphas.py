# FastAPI 和 Pydantic 相关导入
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
import uuid # 导入 uuid 以处理 Alpha ID

# SQLAlchemy 相关导入
from sqlalchemy.orm import Session

# 应用内部模块导入
from app.database import get_db
from app.schemas import AlphaResponse # 使用 AlphaResponse 作为详细信息的响应模型
from app.models import Alpha

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
    "/{alpha_id_str}", # 路径参数改为 alpha_id_str 以明确其为字符串
    response_model=AlphaResponse, # 使用 AlphaResponse
    summary="获取单个Alpha的详细信息",
    description="根据Alpha的唯一ID获取其所有详细数据，包括基本信息、父代、模拟设置、各类统计数据（样本内、样本外、PnL、年度）等。"
)
async def get_alpha_details(
    alpha_id_str: str, # 接收字符串类型的ID
    db: Session = Depends(get_db)
):
    """
    获取指定ID的单个Alpha策略的全部详细信息。

    参数:
        alpha_id_str (str): 要获取详情的Alpha的ID (路径参数, UUID字符串形式)。
        db (Session): SQLAlchemy 数据库会话依赖注入。

    返回:
        AlphaResponse: 包含Alpha所有详细信息的响应对象。

    异常:
        HTTPException (404): 如果具有指定ID的Alpha未找到。
        HTTPException (500): 如果发生其他意外的服务器内部错误。
    """
    logger.info(f"收到获取Alpha详情的请求，Alpha ID: {alpha_id}")

    try:
        try:
            # 将字符串ID转换为UUID对象进行查询
            alpha_uuid = uuid.UUID(alpha_id_str)
        except ValueError:
            logger.warning(f"获取Alpha详情失败：提供的Alpha ID '{alpha_id_str}' 不是有效的UUID格式。")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Alpha ID '{alpha_id_str}' 格式无效。")

        alpha_orm = db.query(Alpha).filter(Alpha.id == alpha_uuid).first()

        if not alpha_orm:
            logger.warning(f"获取Alpha详情失败：Alpha ID {alpha_uuid} 在数据库中未找到。")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ID为 {alpha_uuid} 的Alpha未找到。")

        logger.info(f"成功获取Alpha {alpha_uuid} 的详细信息。") # 改为 info, 记录成功
        return alpha_orm

    except HTTPException as http_exc:
        raise http_exc
    except ValueError as ve: # 特定于业务逻辑的错误，例如上面UUID转换失败（虽然已处理，但作为模式）
        logger.warning(f"获取Alpha详情处理过程中发生值错误: {ve}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"获取Alpha {alpha_id_str} 详情时发生意外错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部发生错误，请联系管理员。" # 标准化通用消息
        )

# ... (文件末尾，未来可能有其他与单个Alpha操作相关的端点，如删除、更新标记等)
