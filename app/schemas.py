# app/schemas.py
# 此文件用于定义 Pydantic 模型，FastAPI 使用它们进行数据校验、序列化和文档生成。

from pydantic import BaseModel, EmailStr # EmailStr 用于邮箱格式验证
from datetime import datetime # 用于时间戳字段
from typing import Optional, List, Dict, Any # 用于更复杂的类型提示

# --- 认证相关模型 (DEV-016) ---

class LoginRequest(BaseModel):
    """
    用户登录请求体模型。
    需要用户提供邮箱和密码。
    """
    email: EmailStr  # 邮箱地址，Pydantic 会自动验证其格式
    password: str    # 用户密码

    # Pydantic V2 风格的示例配置 (如果项目使用 Pydantic V2)
    # model_config = {
    #     "json_schema_extra": {
    #         "example": {
    #             "email": "user@example.com",
    #             "password": "securepassword123"
    #         }
    #     }
    # }

class AuthResponse(BaseModel):
    """
    成功认证后的响应模型。
    返回一个会话 token 和其过期时间。
    """
    session_token: str      # 生成的会话令牌
    expires_at: datetime    # 会话令牌的过期UTC时间戳
    token_type: str = "bearer" # Token 类型，通常为 "bearer"

    # Pydantic V2 风格的示例配置
    # model_config = {
    #     "json_schema_extra": {
    #         "example": {
    #             "session_token": "your-generated-session-token-uuid",
    #             "expires_at": "2023-01-01T12:00:00Z",
    #             "token_type": "bearer"
    #         }
    #     }
    # }

# --- 实验管理相关模型 (DEV-017) ---

class ExperimentBase(BaseModel):
    """
    实验模型的基础字段。
    包含用户在创建或更新实验时通常会提供的核心信息。
    """
    name: str  # 实验的名称，必填
    description: Optional[str] = None  # 实验的详细描述，可选
    # 实验配置，以JSON对象形式存储，例如包含遗传算法的各种参数
    config_json: Dict[str, Any]

    # Pydantic V2 风格的示例配置
    # model_config = {
    #     "json_schema_extra": {
    #         "example": {
    #             "name": "My First GA Experiment",
    #             "description": "Trying out a new set of parameters for alpha generation.",
    #             "config_json": {
    #                 "generations": 100,
    #                 "population_size": 50,
    #                 "crossover_rate": 0.7,
    #                 "mutation_rate": 0.1,
    #                 "simulation_settings": {"universe": "TOP1000", "delay": 0}
    #             }
    #         }
    #     }
    # }


class ExperimentCreate(ExperimentBase):
    """
    创建新实验时使用的请求体模型。
    继承自 ExperimentBase，目前没有额外字段，但为未来扩展性保留。
    """
    pass # 目前与 ExperimentBase 相同


class ExperimentProgress(BaseModel):
    """
    用于表示实验当前进度的模型。
    """
    current_iteration: int       # 当前已完成的迭代/代数
    total_iterations: int        # 实验配置的总迭代/代数
    percentage: float            # 进度百分比 (0.0 到 100.0)
    status_message: str          # RQ Job 的当前状态或自定义进度消息
    rq_job_status: Optional[str] = None # RQ Job 的原始状态字符串 (e.g., 'queued', 'started', 'finished')


class ExperimentResponse(ExperimentBase):
    """
    用于API响应的实验模型，包含数据库生成或管理的字段。
    """
    id: int  # 实验的唯一ID (数据库生成)
    start_time: Optional[datetime] = None # 实验开始时间
    end_time: Optional[datetime] = None   # 实验结束时间
    status: str  # 实验的当前状态 (例如 PENDING, RUNNING, COMPLETED, FAILED)
    code_version: Optional[str] = None # 执行实验时的代码版本
    current_depth: Optional[int] = None  # 遗传算法当前进化到的Alpha树最大深度 (如果适用)
    # current_iteration 通过 ExperimentProgress 提供，这里不重复，但DB模型中有

    rq_job_id: Optional[str] = None # 关联的 RQ 任务 ID
    progress: Optional[ExperimentProgress] = None # 实验的实时进度信息

    # Pydantic V2 使用 model_config = {"from_attributes": True}
    # Pydantic V1 使用 orm_mode = True
    class Config:
        from_attributes = True # 用于从 ORM 模型自动映射属性


class ExperimentListResponse(BaseModel):
    """
    用于响应实验列表查询的模型，包含分页信息和实验列表。
    """
    total: int  # 符合查询条件的总实验数量
    experiments: List[ExperimentResponse] # 当前页的实验对象列表

    # Pydantic V2 风格的示例配置
    # model_config = {
    #     "json_schema_extra": {
    #         "example": {
    #             "total": 1,
    #             "experiments": [
    #                 {
    #                     "id": 1,
    #                     "name": "My First GA Experiment",
    #                     "description": "Description here.",
    #                     "config_json": {"generations": 10},
    #                     "status": "COMPLETED",
    #                     "start_time": "2023-01-01T10:00:00Z",
    #                     "end_time": "2023-01-01T11:00:00Z",
    #                     "rq_job_id": "rq:job:some-uuid",
    #                     "progress": {
    #                         "current_iteration": 10,
    #                         "total_iterations": 10,
    #                         "percentage": 100.0,
    #                         "status_message": "finished",
    #                         "rq_job_status": "finished"
    #                     }
    #                 }
    #             ]
    #         }
    #     }
    # }

# --- Alpha 相关模型 (DEV-018) 将添加在此处 ---
# class AlphaBase(BaseModel):
#     expression: str
#     # ... other common fields

# class AlphaCreate(AlphaBase): # 可能不需要直接创建Alpha的API，它们通常由实验生成
#     pass

# class AlphaResponse(AlphaBase):
#     id: int
#     experiment_id: int
#     # ... all fields from DB model, including stats, pnl, fitness etc.
#     class Config:
#         from_attributes = True

# class AlphaListResponse(BaseModel):
#     total: int
#     alphas: List[AlphaResponse]
