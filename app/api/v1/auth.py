# 从 fastapi 导入 APIRouter，用于创建模块化的API路由。
from fastapi import APIRouter, Depends, HTTPException, status
# 从 sqlalchemy.orm 导入 Session，用于类型提示数据库会话依赖。
from sqlalchemy.orm import Session
# 从 pydantic 导入 BaseModel（如果需要定义此文件内的模型，但通常模型在 schemas.py）。
import requests # 导入 requests 模块以处理其异常

# 导入应用内部模块：
# get_db 依赖，用于获取数据库会话。
from app.database import get_db
# LoginRequest 和 AuthResponse Pydantic 模型，用于请求体验证和响应体定义。
from app.schemas import LoginRequest, AuthResponse
# BrainApiSession 类，用于与 WorldQuant Brain API 进行实际的认证交互。
from app.core.brain_api import BrainApiSession

# 标准库导入：
import uuid # 用于生成唯一的会话令牌 (session_token)。
from datetime import datetime, timedelta # 用于设置会话令牌的过期时间。
import os # 用于访问环境变量 (例如 Brain API 凭据，尽管 BrainApiSession 内部会处理)

# 获取一个日志记录器实例，通常以当前模块名命名。
import logging
logger = logging.getLogger(__name__)

# 创建一个 APIRouter 实例。
# prefix="/auth": 此路由器下所有端点的路径都将以 "/auth" 开头。
# tags=["认证"]: 在 OpenAPI/Swagger 文档中，这些端点将被分组在 "认证" 标签下。
router = APIRouter(
    prefix="/auth",
    tags=["认证"]
)

@router.post("/login", response_model=AuthResponse, summary="用户登录并获取会话令牌")
async def login_api(
    credentials: LoginRequest,
    # db: Session = Depends(get_db) # 数据库会话，当前简单令牌方案可能不用，但保留以备将来扩展
):
    """
    用户登录接口。

    接收用户邮箱和密码，尝试通过 WorldQuant Brain API 进行认证。
    - **成功认证**: 返回一个有时效性的会话令牌 (`session_token`) 和过期时间 (`expires_at`)。
    - **凭据无效**: 返回 HTTP 401 Unauthorized 错误。
    - **需要生物识别/Persona认证**: 返回 HTTP 401 Unauthorized 错误，并提示特定信息。
    - **其他API错误**: 返回相应的 HTTP 错误。

    参数:
        credentials (LoginRequest): 包含用户邮箱和密码的请求体。
        # db (Session): SQLAlchemy 数据库会话依赖注入 (当前未直接使用)。

    返回:
        AuthResponse: 包含会话令牌和过期时间的响应。

    异常 (通过 FastAPI 转换为 HTTP 响应):
        HTTPException: 发生认证失败或请求错误时抛出。
    """
    logger.info(f"收到登录请求，用户邮箱: {credentials.email}")

    try:
        # 1. 使用 BrainApiSession 尝试向 WorldQuant Brain API 认证凭据。
        # BrainApiSession 的构造函数会尝试调用其内部的 _authenticate 方法。
        # 如果凭据无效或遇到 Persona 认证，_authenticate 应该会处理或 BrainApiSession 构造函数会抛出异常。
        logger.debug("尝试使用提供的凭据初始化 BrainApiSession...")
        brain_session = BrainApiSession(email=credentials.email, password=credentials.password)

        # 如果 BrainApiSession 初始化成功，意味着 WQB 认证通过。
        # （注意：BrainApiSession 的 _authenticate 可能会因网络等原因直接抛出 ConnectionError 等，
        #  这些异常也需要在外层或此处被捕获并转换为合适的 HTTP 响应。
        #  当前的 _authenticate 实现倾向于返回 bool 或抛出特定 ValueError/ConnectionError）
        #  为了确保覆盖验收标准，我们需要显式检查 BrainApiSession 是否成功获取了token，
        #  或者依赖它在认证失败时（例如无效凭据）抛出可被捕获的异常。
        #  在 DEV-005 中，_authenticate 失败时会返回 False，或因 Persona/连接问题抛异常。
        #  如果 _authenticate 返回 False 但没有抛异常，brain_session 实例仍会创建。
        #  我们需要一种方式确认认证真的成功了。

        # 假设 BrainApiSession 在认证失败（非异常情况，如密码错误）时，
        # 其内部的 _auth_token 会是 None，或者它会在构造时就抛出异常。
        # 我们在 DEV-005 的 _authenticate 中，对于无效凭据是返回 False 且记录错误。
        # 对于 Persona 是抛出 ValueError。
        # 这里需要适配这种行为。

        # 一个更可靠的检查是，BrainApiSession 内部应该有一个状态表明认证是否成功，
        # 或者 _authenticate 在失败时应一致地抛出特定类型的异常。
        # 假设：如果 brain_session._auth_token 为 None，则表示认证未成功（除了Persona）。
        if not brain_session._auth_token: # 检查内部 token 是否获取成功
             # 此情况可能是 _authenticate 返回了 False 但未抛出异常
             logger.warning(f"BrainApiSession 初始化后 token 仍为空，用户: {credentials.email}，视为认证失败。")
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="提供的凭据无效或认证失败。",
                headers={"WWW-Authenticate": "Bearer"}, # 标准的401响应头
            )

        logger.info(f"用户 {credentials.email} 通过 Brain API 认证成功。")

        # 2. 生成会话令牌和过期时间 (简单会话令牌机制)
        session_token = str(uuid.uuid4())
        # 令牌有效期，例如设置为1小时。可以从配置中读取。
        session_duration = timedelta(hours=1)
        expires_at = datetime.utcnow() + session_duration

        logger.info(f"为用户 {credentials.email} 生成会话令牌。过期时间: {expires_at.isoformat()}")

        # 当前不将会话令牌存储在后端。
        # 客户端（前端）负责存储此令牌，并在后续请求中通过头部发送回来。

        return AuthResponse(
            session_token=session_token,
            expires_at=expires_at
            # token_type="bearer" # 如果 AuthResponse 中定义了此字段
        )

    except ValueError as ve:
        # 捕获由 BrainApiSession._authenticate 抛出的关于 Persona 认证的 ValueError
        if "Persona 认证场景被检测到" in str(ve):
            logger.warning(f"用户 {credentials.email} 登录失败：需要 Persona 认证。详情: {ve}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"认证失败：需要进行生物特征识别或多因素认证。{str(ve)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            # 其他类型的 ValueError，可能是认证响应无效等
            logger.error(f"用户 {credentials.email} 登录时发生值错误: {ve}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, # 或 500，取决于错误性质
                detail=f"登录请求处理失败，内部值错误: {str(ve)}",
            )

    except requests.exceptions.HTTPError as http_err:
        # 捕获 BrainApiSession 中 _authenticate 可能因API返回4xx/5xx错误而抛出的 HTTPError
        # （特别是直接的401无效凭据，如果_authenticate内部没有完全处理掉并转化为False返回的话）
        log_message = f"用户 {credentials.email} 登录时 Brain API 请求发生 HTTP 错误: {http_err}"
        if http_err.response is not None:
            log_message += f" 状态码: {http_err.response.status_code}, 响应: {http_err.response.text[:200]}" # 限制响应文本长度
        logger.error(log_message, exc_info=True)

        status_code = status.HTTP_503_SERVICE_UNAVAILABLE # 默认外部服务问题
        detail_message = "认证服务暂时不可用或遇到错误。"
        if http_err.response is not None and http_err.response.status_code == 401:
            status_code = status.HTTP_401_UNAUTHORIZED
            detail_message = "提供的凭据无效。"

        raise HTTPException(
            status_code=status_code,
            detail=detail_message,
            headers={"WWW-Authenticate": "Bearer"} if status_code == 401 else None,
        )

    except requests.exceptions.RequestException as req_err:
        # 捕获 BrainApiSession 中可能发生的其他网络连接类错误
        logger.error(f"用户 {credentials.email} 登录时 Brain API 请求发生连接错误: {req_err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="认证服务连接失败，请稍后重试。",
        )

    except Exception as e:
        # 捕获所有其他未预料的异常
        logger.error(f"用户 {credentials.email} 登录时发生未预料的服务器内部错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录服务发生内部错误，请联系管理员。",
        )

# ... (文件末尾)
