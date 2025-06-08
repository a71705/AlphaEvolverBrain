# FastAPI 相关导入
from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional

# 应用内部模块导入
from app.core.brain_api import BrainApiSession # 用于与 Brain API 交互
from app.schemas import DataSetResponse, DataFieldResponse # Pydantic 响应模型

# 标准库导入
import os # 用于访问环境变量 (Brain API 凭据)
import logging # 日志记录
import asyncio # 用于在异步端点中运行同步代码

# 获取一个日志记录器实例
logger = logging.getLogger(__name__)

# --- API 路由器定义 ---
# 创建一个 APIRouter 实例，用于定义与数据源元数据相关的 API 端点。
# prefix="/data_sources": 此路由器下所有端点的路径都将以 "/data_sources" 开头。
# tags=["数据源管理"]: 在 OpenAPI/Swagger 文档中，这些端点将被分组在 "数据源管理" 标签下。
router = APIRouter(
    prefix="/data_sources", # 遵循开发文档中的下划线命名
    tags=["数据源管理"]
)

# --- 依赖项函数 (用于获取 BrainApiSession) ---
# 这个依赖项函数负责实例化 BrainApiSession，封装凭据获取逻辑。
# 这比在每个端点中或在模块级别直接实例化 BrainApiSession 更灵活且易于测试。
async def get_brain_session() -> BrainApiSession:
    """
    FastAPI 依赖项，用于创建并返回一个 BrainApiSession 实例。
    它会从环境变量中读取 BRAIN_CREDENTIAL_EMAIL 和 BRAIN_CREDENTIAL_PASSWORD。
    如果凭据缺失，会抛出 HTTPException。
    """
    email = os.environ.get("BRAIN_CREDENTIAL_EMAIL")
    password = os.environ.get("BRAIN_CREDENTIAL_PASSWORD")

    if not email or not password:
        logger.error("数据源API：Brain API 凭据 (BRAIN_CREDENTIAL_EMAIL 或 BRAIN_CREDENTIAL_PASSWORD) 未在环境变量中配置。")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, # 或者 500，表示配置问题
            detail="Brain API 服务凭据未配置，无法访问数据源元数据。"
        )
    try:
        # 每次调用此依赖项都会创建一个新的会话实例。
        # BrainApiSession 内部有 token 缓存和刷新机制。
        # 如果需要应用级别的单例 BrainApiSession，则需要更复杂的应用状态管理或缓存方案。
        return BrainApiSession(email=email, password=password)
    except Exception as e: # 捕获 BrainApiSession 初始化时可能发生的错误 (例如连接认证服务器失败)
        logger.error(f"数据源API：初始化 BrainApiSession 时失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"连接 Brain API 服务失败: {str(e)}"
        )

# 后续将在此 router 实例上定义具体的API端点，例如:
# @router.get("/datasets", response_model=List[DataSetResponse])
# @router.get("/datafields", response_model=List[DataFieldResponse])

@router.get(
    "/datasets",
    response_model=List[DataSetResponse],
    summary="获取可用数据集列表",
    description="从WorldQuant Brain API获取可用的数据集元数据列表，结果会被缓存以提高后续请求的性能。"
)
async def get_datasets_api(
    # 查询参数，与 BrainApiSession.get_datasets 方法的参数对应
    instrument_type: str = Query('EQUITY', description="资产类型，例如 'EQUITY', 'FUTURES'。"),
    region: str = Query('USA', description="地区，例如 'USA', 'CHN', 'GLOBAL'。"),
    delay: int = Query(1, description="数据延迟天数。"),
    universe: str = Query('TOP3000', description="资产池，例如 'TOP3000', 'RUSSELL1000'。"),
    # 注入 BrainApiSession 依赖
    brain_api: BrainApiSession = Depends(get_brain_session)
):
    """
    获取平台支持的数据集列表。

    利用 `BrainApiSession` 的 `get_datasets` 方法（该方法内置了LRU缓存）
    来从 WorldQuant Brain API 拉取数据。

    参数 (通过查询参数传入):
        instrument_type (str): 资产类型。
        region (str): 地区。
        delay (int): 数据延迟。
        universe (str): 资产池。
    依赖注入:
        brain_api (BrainApiSession): 用于与Brain API交互的会话实例。

    返回:
        List[DataSetResponse]: 数据集元数据列表。

    异常:
        HTTPException (503): 如果 Brain API 服务不可用或凭据配置错误。
        HTTPException (500): 如果发生其他未预料的服务器内部错误。
    """
    logger.info(
        f"收到获取数据集列表请求: instrument_type='{instrument_type}', region='{region}', "
        f"delay={delay}, universe='{universe}'"
    )

    try:
        # 调用 BrainApiSession 的 get_datasets 方法
        # 该方法已使用 @lru_cache 装饰，会自动处理缓存
        datasets_df = await asyncio.to_thread(
            brain_api.get_datasets,
            instrument_type=instrument_type,
            region=region,
            delay=delay,
            universe=universe
        )
        # get_datasets 是一个同步方法，但在异步的 FastAPI 端点中调用它时，
        # 最好使用 asyncio.to_thread 将其包装起来，以避免阻塞事件循环。
        # (如果 get_datasets 内部的 _request_with_retry 已经是异步的，则不需要 to_thread)
        # 检查我们 DEV-007 中 get_datasets 的实现：它是同步的 (因为它使用了同步的 requests 库)。
        # 因此，使用 asyncio.to_thread 是一个好实践。

        if datasets_df is None or datasets_df.empty:
            logger.info("未从 Brain API 获取到数据集信息，或返回为空。")
            return [] # 返回空列表

        # 将 Pandas DataFrame 转换为字典列表，Pydantic 会自动转换为 List[DataSetResponse]
        response_data = datasets_df.to_dict(orient="records")
        logger.info(f"成功获取并格式化 {len(response_data)} 个数据集。")
        return response_data

    except HTTPException: # 重新抛出由 get_brain_session 可能引发的 HTTPException
        raise
    except Exception as e:
        # 捕获调用 brain_api.get_datasets 时可能发生的其他所有异常
        # 例如，如果 DataFrame 转换失败，或者 _request_with_retry 抛出了未被 get_brain_session 捕获的异常
        logger.error(f"获取数据集时发生错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据集信息时发生内部错误: {str(e)}"
        )

@router.get(
    "/datafields",
    response_model=List[DataFieldResponse],
    summary="获取可用数据字段列表",
    description="从WorldQuant Brain API获取可用的数据字段元数据列表，支持多种参数进行筛选，结果会被缓存以提高后续请求的性能。"
)
async def get_datafields_api(
    # 查询参数，与 BrainApiSession.get_datafields 方法的参数对应
    instrument_type: str = Query('EQUITY', description="资产类型，例如 'EQUITY', 'FUTURES'。"),
    region: str = Query('USA', description="地区，例如 'USA', 'CHN', 'GLOBAL'。"),
    delay: int = Query(1, description="数据延迟天数。"),
    universe: str = Query('TOP3000', description="资产池，例如 'TOP3000', 'RUSSELL1000'。"),
    dataset_id: str = Query('', description="按特定数据集ID筛选数据字段（可选）。"), # 注意：'' 是 Query 的默认值，而非 None
    search: str = Query('', description="用于在字段名称或描述中搜索的关键词（可选）。"),
    # page_size 参数在 get_datafields 方法内部处理分页逻辑，API端点不直接暴露分页参数给客户端，
    # 因为 get_datafields 会获取所有页的数据。如果需要API级别分页，则需修改 get_datafields 行为。
    # 注入 BrainApiSession 依赖
    brain_api: BrainApiSession = Depends(get_brain_session)
):
    """
    获取平台支持的数据字段列表。

    利用 `BrainApiSession` 的 `get_datafields` 方法（该方法内置了LRU缓存和分页逻辑）
    来从 WorldQuant Brain API 拉取数据。

    参数 (通过查询参数传入):
        instrument_type (str): 资产类型。
        region (str): 地区。
        delay (int): 数据延迟。
        universe (str): 资产池。
        dataset_id (str): 特定数据集的ID (可选)。
        search (str): 搜索关键词 (可选)。
    依赖注入:
        brain_api (BrainApiSession): 用于与Brain API交互的会话实例。

    返回:
        List[DataFieldResponse]: 数据字段元数据列表。

    异常:
        HTTPException (503): 如果 Brain API 服务不可用或凭据配置错误。
        HTTPException (500): 如果发生其他未预料的服务器内部错误。
    """
    logger.info(
        f"收到获取数据字段列表请求: instrument_type='{instrument_type}', region='{region}', delay={delay}, "
        f"universe='{universe}', dataset_id='{dataset_id}', search='{search}'"
    )

    try:
        # 调用 BrainApiSession 的 get_datafields 方法
        # 该方法已使用 @lru_cache 装饰并包含内部分页逻辑
        datafields_df = await asyncio.to_thread(
            brain_api.get_datafields,
            instrument_type=instrument_type,
            region=region,
            delay=delay,
            universe=universe,
            dataset_id=dataset_id,
            search=search
            # page_size 参数由 get_datafields 方法内部默认或可配置，此处不直接传入
        )
        # get_datafields 是同步的，使用 asyncio.to_thread 运行

        if datafields_df is None or datafields_df.empty:
            logger.info("未从 Brain API 获取到数据字段信息，或返回为空。")
            return []

        # 将 Pandas DataFrame 转换为字典列表
        response_data = datafields_df.to_dict(orient="records")
        logger.info(f"成功获取并格式化 {len(response_data)} 个数据字段。")
        return response_data

    except HTTPException: # 重新抛出由 get_brain_session 可能引发的 HTTPException
        raise
    except Exception as e:
        logger.error(f"获取数据字段时发生错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据字段信息时发生内部错误: {str(e)}"
        )

# ... (文件末尾)
