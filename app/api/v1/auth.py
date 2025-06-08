# app/api/v1/auth.py
# 此模块处理用户认证相关的 API 端点。

import logging
import uuid # 用于生成唯一的会话令牌 (session token)
from datetime import datetime, timedelta # 用于设置会шения令牌的过期时间

from fastapi import APIRouter, HTTPException, status # FastAPI 核心组件

# 从应用核心模块导入 Brain API 会话管理和自定义异常
from app.core.brain_api import BrainApiSession, AuthenticationError, PersonaLoginError
# 从应用模式定义模块导入请求和响应模型
from app.schemas import LoginRequest, AuthResponse

# 初始化当前模块的 logger
logger = logging.getLogger(__name__)

# 创建一个 APIRouter 实例，用于定义此模块中的路由
# prefix="/auth": 此路由器下所有端点都将以 /auth 作为路径前缀 (完整路径将是 /api/v1/auth)
# tags=["Authentication"]: 在 OpenAPI (Swagger) 文档中将这些端点归类到 "Authentication" 标签下
router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=AuthResponse)
async def login_api(credentials: LoginRequest):
    """
    用户登录端点。
    接收用户邮箱和密码，尝试通过 WorldQuant Brain API 进行认证。
    成功后返回一个临时的会话令牌。

    Args:
        credentials (LoginRequest): 包含用户邮箱和密码的请求体。

    Raises:
        HTTPException (401 Unauthorized): 如果凭据无效或 Brain API 认证失败。
        HTTPException (403 Forbidden): 如果检测到 Persona 登录尝试。
        HTTPException (500 Internal Server Error): 如果在认证过程中发生其他未预料的错误。

    Returns:
        AuthResponse: 包含会话令牌、过期时间和令牌类型的响应。
    """
    logger.info(f"收到登录请求，用户邮箱: {credentials.email}")

    try:
        # 尝试使用提供的凭据初始化 BrainApiSession
        # BrainApiSession 的 __init__ 方法会尝试调用 _authenticate
        # 如果认证失败（错误凭据、Persona登录、网络问题等），它会抛出异常
        logger.debug(f"尝试为用户 {credentials.email} 初始化 BrainApiSession...")
        # 注意：BrainApiSession 实例在这里是局部的，仅用于验证凭据。
        # 它不会被存储或重用在此次登录请求之外。
        brain_session = BrainApiSession(email=credentials.email, password=credentials.password)
        # 如果上面没有抛出异常，说明 WQB API 认为凭据有效且不是 Persona 登录

        logger.info(f"用户 {credentials.email} 通过 WorldQuant Brain API 认证成功。")

        # 生成一个简单的会话令牌 (UUID)
        session_token = str(uuid.uuid4())
        # 设置会话令牌的过期时间 (例如，1小时后)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        token_type = "bearer" # 标准的 token 类型

        logger.info(f"为用户 {credentials.email} 生成会话令牌成功，令牌类型: {token_type}。")

        # 返回包含会话令牌和过期时间的响应
        return AuthResponse(
            session_token=session_token,
            expires_at=expires_at,
            token_type=token_type
        )

    except PersonaLoginError as ple:
        # 特别处理 Persona 登录错误
        logger.warning(f"登录尝试被拒绝 (Persona登录): 用户 {credentials.email}。错误: {ple}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Persona 登录不被允许进行 API 访问。({str(ple)})"
        )
    except AuthenticationError as ae:
        # 处理 BrainApiSession 抛出的其他认证相关错误
        logger.warning(f"登录尝试失败 (认证错误): 用户 {credentials.email}。错误: {ae}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"认证失败：无效的凭据或认证服务问题。({str(ae)})"
        )
    except ValueError as ve: # BrainApiSession 在 email/password 为空时可能抛出 ValueError
        logger.warning(f"登录尝试失败 (值错误，可能凭据未在环境中正确设置给BrainApiSession的默认值): 用户 {credentials.email}。错误: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, # 或者 401，但 ValueError 更像请求问题
            detail=f"登录请求数据无效或配置错误。({str(ve)})"
        )
    except Exception as e:
        # 捕获所有其他在 BrainApiSession 初始化或认证过程中可能发生的未知错误
        logger.error(f"登录过程中发生未知服务器错误，用户: {credentials.email}。错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录过程中发生内部服务器错误，请稍后重试。"
        )

# 可以在此模块中添加其他认证相关端点，例如 /logout, /refresh-token (如果需要)
