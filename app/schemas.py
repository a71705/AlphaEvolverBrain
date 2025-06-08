# app/schemas.py
# 此文件用于定义 Pydantic 模型，FastAPI 使用它们进行数据校验、序列化和文档生成。

from pydantic import BaseModel, EmailStr # EmailStr 用于邮箱格式验证
from datetime import datetime # 用于时间戳字段

# --- 认证相关模型 (DEV-016) ---

class LoginRequest(BaseModel):
    """
    用户登录请求体模型。
    需要用户提供邮箱和密码。
    """
    email: EmailStr  # 邮箱地址，Pydantic 会自动验证其格式
    password: str    # 用户密码

    # Pydantic V2 风格的示例配置 (如果项目使用 Pydantic V2)
    # class Config:
    #     json_schema_extra = {
    #         "example": {
    #             "email": "user@example.com",
    #             "password": "securepassword123"
    #         }
    #     }

class AuthResponse(BaseModel):
    """
    成功认证后的响应模型。
    返回一个会话 token 和其过期时间。
    """
    session_token: str      # 生成的会话令牌
    expires_at: datetime    # 会话令牌的过期UTC时间戳
    token_type: str = "bearer" # Token 类型，通常为 "bearer"

    # Pydantic V2 风格的示例配置
    # class Config:
    #     json_schema_extra = {
    #         "example": {
    #             "session_token": "your-generated-session-token-uuid",
    #             "expires_at": "2023-01-01T12:00:00Z",
    #             "token_type": "bearer"
    #         }
    #     }

# --- 未来其他模块的 Schema 定义将添加在此处 ---
# 例如 ExperimentCreate, ExperimentResponse, AlphaResponse 等 (用于 DEV-017, DEV-018)
