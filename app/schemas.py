# app/schemas.py
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
import datetime # 确保导入 datetime
import uuid # 用于 Alpha ID

# --- 枚举类型 (保持与 models.py 一致或根据需要定义) ---
# class ExperimentStatusEnum(str, Enum):
#     PENDING = "PENDING"
#     RUNNING = "RUNNING"
#     COMPLETED = "COMPLETED"
#     FAILED = "FAILED"
#     CANCELLED = "CANCELLED"

# --- Alpha 相关的 Schema ---
class AlphaBase(BaseModel):
    """Alpha 的基础模型，包含通用字段"""
    expression: str = Field(..., description="Alpha表达式的字符串表示")
    description: Optional[str] = Field(None, description="Alpha的描述信息")
    # 基础模型中不包含与数据库或特定请求/响应相关的字段

class AlphaCreate(AlphaBase):
    """用于创建新 Alpha 的模型"""
    # experiment_id: str # 在创建时通常需要关联到一个实验
    # 在API层面，experiment_id 可以从路径参数获取，或者包含在请求体中
    # 如果 experiment_id 在请求体中，则应在此处定义
    # 模拟设置也应该在这里定义，如果它们在创建Alpha时就已确定
    simulation_settings_json: Optional[Dict[str, Any]] = Field(None, description="Alpha的模拟回测设置 (JSON格式)")
    # ga_config_json: Optional[Dict[str, Any]] = Field(None, description="生成此Alpha的遗传算法配置 (JSON格式)")


class AlphaUpdate(BaseModel):
    """用于更新现有 Alpha 的模型 (部分更新)"""
    expression: Optional[str] = Field(None, description="Alpha表达式的字符串表示")
    description: Optional[str] = Field(None, description="Alpha的描述信息")
    is_active: Optional[bool] = Field(None, description="标记Alpha是否为活跃/选中状态")
    # 模拟结果字段通常不由用户直接更新，而是通过模拟流程更新
    # simulation_settings_json: Optional[Dict[str, Any]] = None # 如果允许更新模拟设置

class AlphaResponse(AlphaBase):
    """用于API响应的Alpha模型，包含数据库中的ID和其他生成字段"""
    id: uuid.UUID = Field(..., description="Alpha在数据库中的唯一ID")
    experiment_id: Optional[uuid.UUID] = Field(None, description="关联的实验ID (如果存在)") # 改为 UUID
    created_at: datetime.datetime = Field(..., description="Alpha创建时间戳")
    updated_at: datetime.datetime = Field(..., description="Alpha最后更新时间戳")

    # 模拟结果相关字段 (与 Alpha 模型中的 JSON 字段对应)
    simulation_settings_json: Optional[Dict[str, Any]] = Field(None, description="Alpha的模拟回测设置")
    is_stats_json: Optional[Dict[str, Any]] = Field(None, description="样本内统计数据 (IS)")
    is_tests_json: Optional[Dict[str, Any]] = Field(None, description="样本内测试结果 (IS)")
    oos_stats_json: Optional[Dict[str, Any]] = Field(None, description="样本外统计数据 (OOS)") # (如果适用)
    oos_tests_json: Optional[Dict[str, Any]] = Field(None, description="样本外测试结果 (OOS)") # (如果适用)

    pnl_data_json: Optional[Dict[str, Any]] = Field(None, description="PNL数据 (例如每日收益)")
    yearly_stats_data_json: Optional[Dict[str, Any]] = Field(None, description="年度统计数据")

    fitness_score: Optional[float] = Field(None, description="Alpha的适应度评分 (如果通过GA生成)")
    simulated_at: Optional[datetime.datetime] = Field(None, description="上次成功模拟的时间戳")
    simulation_status: Optional[str] = Field(None, description="当前或最后一次模拟的状态") # 例如 PENDING, RUNNING, COMPLETED, FAILED
    simulation_error_message: Optional[str] = Field(None, description="模拟失败时的错误信息")

    is_active: bool = Field(default=True, description="标记Alpha是否为活跃/选中状态")
    # WQB 模拟相关ID
    wqb_simulation_id: Optional[str] = Field(None, description="WorldQuant BRAIN Simulation ID (如果适用)")
    wqb_simulation_details: Optional[Dict[str, Any]] = Field(None, description="来自WQB平台的额外模拟详情")

    class Config:
        orm_mode = True # 允许从ORM对象自动映射 (Pydantic V1)
        # from_attributes = True # Pydantic V2

# --- Experiment 相关的 Schema ---
class ExperimentBase(BaseModel):
    """实验的基础模型"""
    name: str = Field(..., min_length=3, max_length=100, description="实验的名称")
    description: Optional[str] = Field(None, description="实验的详细描述")
    ga_config_json: Dict[str, Any] = Field(..., description="遗传算法配置 (JSON格式)")
    simulation_config_json: Dict[str, Any] = Field(..., description="模拟回测配置 (JSON格式)")

class ExperimentCreate(ExperimentBase):
    """用于创建新实验的模型"""
    pass # 目前与 Base 相同，但可以扩展

class ExperimentUpdate(BaseModel):
    """用于更新实验的模型 (部分更新)"""
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = None
    ga_config_json: Optional[Dict[str, Any]] = None
    simulation_config_json: Optional[Dict[str, Any]] = None
    status: Optional[str] = Field(None, description="实验状态 (例如 PENDING, RUNNING, COMPLETED)") # 考虑使用枚举
    current_progress: Optional[int] = Field(None, ge=0, le=100, description="实验当前进度百分比")
    current_depth: Optional[int] = Field(None, ge=0, description="GA进行到的当前深度")
    current_iteration_at_depth: Optional[int] = Field(None, ge=0, description="当前深度下的迭代次数")


class ExperimentResponse(ExperimentBase):
    """用于API响应的实验模型"""
    id: uuid.UUID = Field(..., description="实验在数据库中的唯一ID") # 改为 UUID
    user_id: Optional[uuid.UUID] = Field(None, description="创建实验的用户ID (如果多用户)") # 改为 UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime
    status: str = Field(default="PENDING", description="实验状态")
    current_progress: int = Field(default=0, description="实验当前进度百分比")
    current_depth: Optional[int] = Field(None, description="GA进行到的当前深度")
    current_iteration_at_depth: Optional[int] = Field(None, description="当前深度下的迭代次数")

    # 可以选择性地包含与实验关联的Alphas的简要信息或数量
    # alphas: List[AlphaResponse] = [] # 直接嵌入可能导致响应过大，通常分页获取
    alpha_count: int = Field(0, description="此实验生成的Alpha数量")

    class Config:
        orm_mode = True
        # from_attributes = True # Pydantic V2

# --- GA Task 相关的 Schema (用于Celery任务状态等) ---
class GeneticAlgorithmTaskStatus(BaseModel):
    """遗传算法Celery任务的状态响应模型"""
    task_id: str = Field(..., description="Celery任务的ID")
    status: str = Field(..., description="任务当前状态 (例如 PENDING, STARTED, SUCCESS, FAILURE)")
    progress: int = Field(default=0, description="任务大致进度百分比")
    details: Optional[Dict[str, Any]] = Field(None, description="与任务相关的其他详细信息或结果")
    current_depth: Optional[int] = Field(None, description="GA进行到的当前深度 (如果任务正在运行)")
    current_iteration_at_depth: Optional[int] = Field(None, description="当前深度下的迭代次数 (如果任务正在运行)")
    error_message: Optional[str] = Field(None, description="如果任务失败，相关的错误信息")


# --- Alpha 组合与导出相关的 Schema (DEV-027) ---

class AlphaCombinationRequest(BaseModel):
    """请求组合多个Alpha的输入模型"""
    alpha_ids: List[str] = Field(..., description="要组合的Alpha的数据库ID列表 (UUID字符串形式)")
    method: str = Field(default="add", description="组合方法，例如 'add' 或 'mean'")
    # （可选）可以加入组合后Alpha的模拟设置，如果希望用户指定
    # simulation_settings: Optional[Dict[str, Any]] = Field(None, description="组合后Alpha的模拟设置")

    @validator('method')
    def method_must_be_supported(cls, v):
        """验证组合方法是否为支持的方法"""
        supported_methods = ["add", "mean"]
        if v not in supported_methods:
            raise ValueError(f"不支持的组合方法: '{v}'. 支持的方法: {supported_methods}")
        return v

class CombinedAlphaSimulatedData(BaseModel): # 用于嵌套在响应中显示模拟结果
    """组合后Alpha的模拟结果数据结构 (简化版)"""
    is_stats: Optional[Dict[str, Any]] = Field(None, description="样本内统计数据")
    is_tests: Optional[Dict[str, Any]] = Field(None, description="样本内测试结果")
    pnl_data: Optional[Dict[str, Any]] = Field(None, description="PNL数据")
    yearly_stats_data: Optional[Dict[str, Any]] = Field(None, description="年度统计数据")
    # 根据需要添加更多模拟结果字段，例如 pnl_data_json 等
    status: Optional[str] = Field(None, description="模拟状态 (例如 COMPLETED, FAILED)")
    error_message: Optional[str] = Field(None, description="模拟过程中的错误信息")


class AlphaCombinationResponse(BaseModel):
    """组合Alpha操作的响应模型"""
    combined_expression: str = Field(..., description="组合生成的Alpha表达式")
    simulation_details: Optional[CombinedAlphaSimulatedData] = Field(None, description="组合后Alpha的模拟结果详情")
    # 如果组合后的Alpha会被保存，可以返回其ID
    # new_alpha_id: Optional[str] = Field(None, description="如果组合后的Alpha被保存，则为其新ID (UUID字符串形式)")


class AlphaExportResponse(BaseModel):
    """导出Alpha数据的响应模型"""
    alpha_id: str = Field(..., description="Alpha的ID (UUID字符串形式)")
    expression: str = Field(..., description="Alpha的表达式")
    simulation_settings_json: Optional[Dict[str, Any]] = Field(None, description="Alpha原始的模拟设置")
    # 可以考虑加入其他元数据
    experiment_id: Optional[str] = Field(None, description="关联的实验ID (UUID字符串形式, 如果有)")
    created_at: Optional[datetime.datetime] = Field(None, description="Alpha创建时间")
    description: Optional[str] = Field(None, description="Alpha的描述")

    class Config:
        orm_mode = True # 允许从ORM对象自动映射
        # from_attributes = True # Pydantic V2
        # 如果 created_at 直接来自 SQLAlchemy 模型，orm_mode 会处理
        # 如果是手动填充，确保类型正确


# --- 新增：API 使用与错误状态相关的 Schema (DEV-028) ---

class ApiUsageResponse(BaseModel):
    """API使用量统计的响应模型"""
    total_calls_today: int = Field(0, description="今日应用自身记录的对WQ Brain API的调用次数")
    # 以下字段依赖于WQ Brain平台是否提供以及BrainApiSession的实现程度
    remaining_daily_quota: Optional[int] = Field(None, description="预估的每日剩余配额 (如果可用)")
    total_daily_quota: Optional[int] = Field(None, description="预估的每日总配额 (如果可用)")
    quota_reset_time: Optional[datetime.datetime] = Field(None, description="配额预计重置时间 (UTC, 如果可用)")
    # estimated_cost_today: Optional[float] = Field(None, description="今日预估API成本 (如果可用)")
    data_source: str = Field("应用内部初步统计/模拟数据", description="API使用数据的来源说明")

class ErrorLogEntry(BaseModel):
    """单个错误日志条目的数据模型"""
    log_id: uuid.UUID = Field(..., description="日志条目的唯一ID (通常是关联的Alpha或记录的ID)")
    alpha_id: Optional[str] = Field(None, description="关联的Alpha的ID (UUID字符串, 如果错误与特定Alpha相关)")
    experiment_id: Optional[str] = Field(None, description="关联的实验ID (UUID字符串, 如果错误与特定实验相关)")
    timestamp: datetime.datetime = Field(..., description="错误发生的时间戳 (UTC)")
    expression_preview: Optional[str] = Field(None, description="相关的Alpha表达式预览 (截断显示)")
    error_message: str = Field(..., description="详细的错误信息")
    # error_source: Optional[str] = Field(None, description="错误来源模块，例如 'simulation', 'database', 'task_processing'")

    class Config:
        orm_mode = True # 如果 ErrorLogEntry 是从 ORM 对象（如AlphaModel）转换而来


class RecentErrorLogResponse(BaseModel):
    """最近错误日志列表的响应模型 (支持分页)"""
    errors: List[ErrorLogEntry] = Field(..., description="最近的错误日志条目列表")
    total_available_errors: int = Field(..., description="数据库中符合条件的错误总数 (用于计算分页)")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条目数")
    total_pages: int = Field(..., description="总页数")
