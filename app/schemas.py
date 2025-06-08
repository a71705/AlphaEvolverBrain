# 导入 Pydantic 的 BaseModel，用于定义数据模型 (模式)。
from pydantic import BaseModel, EmailStr, Field
# 导入 datetime 用于 AuthResponse 中的 expires_at 字段。
from datetime import datetime
# 导入 Optional 用于可选字段 (如果未来需要)。
from typing import Optional, Dict, Any # 用于 config_json 的类型提示

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

# --- 实验相关的 Pydantic 模型 ---

class ExperimentCreate(BaseModel):
    """
    创建新实验时使用的请求体模型。
    """
    name: str = Field(..., min_length=1, max_length=100, description="实验的名称，必填项，长度限制1-100字符。")
    description: Optional[str] = Field(None, max_length=500, description="实验的详细描述，可选，最大长度500字符。")
    # config_json 用于存储遗传算法的配置，例如种群大小、迭代次数、变异率等。
    # 使用 Dict[str, Any] 表示它是一个灵活的JSON对象。
    config_json: Dict[str, Any] = Field(..., description="遗传算法的配置参数，以JSON对象形式提供。")
    code_version: Optional[str] = Field(None, max_length=64, description="可选，执行此次实验的代码版本号，例如Git提交哈希。")


    class Config:
        schema_extra = {
            "example": {
                "name": "我的第一个Alpha实验",
                "description": "测试基础参数下的遗传算法表现。",
                "config_json": {
                    "population_size": 100,
                    "generations": 50,
                    "mutation_rate": 0.05,
                    "crossover_rate": 0.7,
                    "max_depth": 3,
                    "simulation_settings": {"universe": "TOP3000", "delay": 1, "region": "USA"}
                },
                "code_version": "abcdef1234567890"
            }
        }

class ExperimentResponse(BaseModel):
    """
    用于API响应的实验数据模型。
    包含了实验在数据库中的主要信息，以及一些动态获取的状态。
    """
    id: int = Field(..., description="实验的唯一标识符。")
    name: str = Field(..., description="实验的名称。")
    description: Optional[str] = Field(None, description="实验的详细描述。")
    start_time: Optional[datetime] = Field(None, description="实验开始的UTC时间。") # 改为Optional，因为刚创建时可能还没有实际开始时间
    end_time: Optional[datetime] = Field(None, description="实验结束的UTC时间（如果已结束）。")
    status: str = Field(..., description="实验当前状态 (例如 PENDING, RUNNING, COMPLETED, FAILED)。")
    config_json: Dict[str, Any] = Field(..., description="实验的配置参数。")
    code_version: Optional[str] = Field(None, description="执行实验时的代码版本。")
    current_depth: int = Field(..., description="遗传算法当前进行到的深度级别。")
    current_iteration: int = Field(..., description="在当前深度下，遗传算法已完成的迭代次数。")
    random_seed: Optional[int] = Field(None, description="用于实验的随机数种子。")
    error_message: Optional[str] = Field(None, description="如果实验失败，记录的错误信息。")

    # 动态获取或计算的字段
    job_id: Optional[str] = Field(None, description="关联的RQ作业ID（如果任务已提交）。")
    job_status: Optional[str] = Field(None, description="关联的RQ作业的当前状态。")
    progress_percentage: Optional[float] = Field(None, ge=0, le=100, description="实验的估算完成进度百分比（0-100）。")

    class Config:
        orm_mode = True # 允许模型从ORM对象（如SQLAlchemy模型实例）中读取数据。
        schema_extra = {
            "example": {
                "id": 1,
                "name": "我的第一个Alpha实验",
                "description": "测试基础参数下的遗传算法表现。",
                "start_time": "2023-01-01T10:00:00Z",
                "end_time": None,
                "status": "RUNNING",
                "config_json": {"population_size": 100, "generations": 50},
                "code_version": "abcdef1234567890",
                "current_depth": 1,
                "current_iteration": 5,
                "random_seed": 12345,
                "error_message": None,
                "job_id": "exp_1",
                "job_status": "started", # RQ作业状态示例
                "progress_percentage": 25.5
            }
        }

# ... (其他已有的或未来的 Pydantic 模型) ...
