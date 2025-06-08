# 导入 Pydantic 的 BaseModel，用于定义数据模型 (模式)。
from pydantic import BaseModel, EmailStr, Field
# 导入 datetime 用于 AuthResponse 中的 expires_at 字段。
from datetime import datetime
# 导入 Optional 用于可选字段 (如果未来需要)。
from typing import Optional

# --- 请求模型 (Request Models) ---

class LoginRequest(BaseModel):
    """
    用户登录请求体模型。
    用于 FastAPI 端点验证进入的登录数据。
    """
    # 电子邮箱地址，使用 EmailStr 类型进行基本格式验证。
    email: EmailStr = Field(..., description="用户的注册电子邮箱地址。")
    # 用户密码，字符串类型。
    password: str = Field(..., min_length=1, description="用户的登录密码。") # min_length=1 确保密码不为空

    # Pydantic 模型配置示例 (可选)
    class Config:
        # schema_extra 用于在 OpenAPI/Swagger 文档中提供示例数据
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "securepassword123"
            }
        }


# --- 响应模型 (Response Models) ---

class AuthResponse(BaseModel):
    """
    认证成功后的响应体模型。
    包含发给客户端的会话令牌和其过期时间。
    """
    # 会话令牌，通常是一个唯一字符串 (例如 UUID)。
    session_token: str = Field(..., description="生成的会话令牌。")
    # 令牌的过期时间戳 (UTC)。
    expires_at: datetime = Field(..., description="会话令牌的过期 UTC 时间。")
    # （可选）可以添加 token_type，例如 "bearer"，如果遵循 OAuth2 风格。
    # token_type: str = Field("bearer", description="令牌类型，通常为 'bearer'。")

    class Config:
        schema_extra = {
            "example": {
                "session_token": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "expires_at": "2023-12-31T23:59:59.000Z"
                # "token_type": "bearer"
            }
        }

# 后续其他任务可能会在此文件中添加更多的 Pydantic 模型，
# 例如用于 Experiment 或 Alpha 数据的创建和响应。
