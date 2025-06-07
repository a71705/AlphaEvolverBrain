# 导入 SQLAlchemy 的 declarative_base 函数，用于创建 ORM 模型类的基类。
from sqlalchemy.ext.declarative import declarative_base

# 从 python 标准库导入 datetime，用于设置默认时间戳
from datetime import datetime

# 从 sqlalchemy 导入 ORM 模型所需的各种列类型和约束
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Float, Boolean, Index
# 从 sqlalchemy.orm 导入 relationship，用于定义模型之间的关系
from sqlalchemy.orm import relationship
# 从 sqlalchemy.ext.declarative 导入 declarative_base，已在 DEV-003 中创建 Base 时导入
# from sqlalchemy.ext.declarative import declarative_base # 这行应该已经存在

# 调用 declarative_base() 创建一个 Base 类。
# 项目中所有的 ORM 模型都应该继承自这个 Base 类。
# SQLAlchemy 会使用这个 Base 类来收集所有定义的模型，并将其映射到数据库表。
Base = declarative_base()

class Experiment(Base):
    """
    实验模型 (Experiment Model)。
    存储遗传算法实验的总体信息、配置和状态。
    """
    __tablename__ = "experiments"  # 定义数据库中的表名

    # 主键ID，自增
    id = Column(Integer, primary_key=True, index=True, comment="实验的唯一标识符，主键")

    # 实验名称，建立索引以便快速查询
    name = Column(String, index=True, nullable=False, comment="实验的名称")

    # 实验的详细描述，可以为空
    description = Column(String, nullable=True, comment="实验的详细描述")

    # 实验开始时间，默认为记录创建时的 UTC 时间
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False, comment="实验开始时间（UTC）")

    # 实验结束时间，可以为空（表示实验尚未结束或异常终止）
    end_time = Column(DateTime, nullable=True, comment="实验结束时间（UTC）")

    # 实验状态 (例如 PENDING, RUNNING, COMPLETED, FAILED)，建立索引以便按状态筛选
    status = Column(String, default="PENDING", index=True, nullable=False, comment="实验当前状态 (例如 PENDING, RUNNING, COMPLETED, FAILED)")

    # 实验配置，以 JSON 格式存储
    config_json = Column(JSON, nullable=False, comment="实验的配置参数，以JSON格式存储")

    # 执行此次实验的代码版本（例如 Git commit hash），可以为空
    code_version = Column(String, nullable=True, comment="执行实验时的代码版本（如Git commit hash）")

    # 遗传算法进行到的当前深度（对于分阶段的遗传算法）
    current_depth = Column(Integer, default=0, nullable=False, comment="遗传算法当前进行到的深度级别")

    # 遗传算法在当前深度下进行到的迭代次数
    current_iteration = Column(Integer, default=0, nullable=False, comment="在当前深度下，遗传算法已完成的迭代次数")

    # 随机数种子，用于实验的可复现性，可以为空
    random_seed = Column(Integer, nullable=True, comment="用于实验的随机数种子，确保可复现性")

    # 定义与 Alpha 模型的一对多关系
    # "Alpha" 是关联的类名。
    # back_populates="experiment" 指明在 Alpha 模型中有一个名为 "experiment" 的属性反向关联回此 Experiment。
    # cascade="all, delete-orphan" 表示对此 Experiment 的操作（如删除）会级联到其关联的 Alpha 记录，
    # 并且如果一个 Alpha 不再关联任何 Experiment，它将被标记为孤立并删除。
    alphas = relationship("Alpha", back_populates="experiment", cascade="all, delete-orphan", passive_deletes=True) # passive_deletes=True 推荐用于 SQLite on delete cascade

    def __repr__(self):
        # 为模型定义一个可读的字符串表示形式，方便调试
        return f"<Experiment(id={self.id}, name='{self.name}', status='{self.status}')>"

class Alpha(Base):
    """
    Alpha 模型 (Alpha Model)。
    存储由遗传算法生成或评估的单个 Alpha 策略的详细信息。
    """
    __tablename__ = "alphas"  # 定义数据库中的表名

    # 主键ID，自增
    id = Column(Integer, primary_key=True, index=True, comment="Alpha的唯一标识符，主键")

    # 外键，关联到 Experiment 表的 id 字段，表示此 Alpha 所属的实验
    # nullable=False 确保每个 Alpha都必须属于一个实验
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, comment="关联的实验ID") # ondelete="CASCADE" 确保删除实验时，其下的Alphas也被删除

    # Alpha 表达式字符串
    expression = Column(String, nullable=False, comment="Alpha表达式的字符串表示")

    # Alpha 树的深度
    depth = Column(Integer, nullable=False, comment="生成此Alpha的树的深度")

    # 在遗传算法的第几次迭代中产生
    iteration = Column(Integer, nullable=False, comment="Alpha在遗传算法的第几次迭代中产生")

    # 父 Alpha ID 的列表，以 JSON 格式存储（例如，通过交叉操作产生的 Alpha 可能有多个父代）
    parent_ids = Column(JSON, nullable=True, comment="父Alpha的ID列表（JSON格式）")

    # 该 Alpha 进行模拟时使用的具体设置，以 JSON 格式存储
    simulation_settings_json = Column(JSON, nullable=False, comment="模拟此Alpha时使用的具体参数设置（JSON格式）")

    # Alpha 模拟完成的时间戳，可以为空（如果尚未模拟或模拟失败）
    simulated_at = Column(DateTime, nullable=True, comment="Alpha模拟完成的时间（UTC）")

    # 样本内 (In-Sample) 统计数据，以 JSON 格式存储
    is_stats_json = Column(JSON, nullable=True, comment="样本内（IS）回测的详细统计数据（JSON格式）")

    # 样本内 (In-Sample) 测试结果 (例如 PValue 测试等)，以 JSON 格式存储
    is_tests_json = Column(JSON, nullable=True, comment="样本内（IS）的各项检验结果，如PValue测试（JSON格式）")

    # 样本外 (Out-of-Sample) 统计数据，以 JSON 格式存储
    oos_stats_json = Column(JSON, nullable=True, comment="样本外（OOS）回测的详细统计数据（JSON格式）")

    # PnL (Profit and Loss) 曲线数据，以 JSON 格式存储 (例如时间序列的 PnL 值)
    pnl_data_json = Column(JSON, nullable=True, comment="PnL曲线数据，通常是时间序列格式（JSON格式）")

    # 年度统计数据，以 JSON 格式存储
    yearly_stats_data_json = Column(JSON, nullable=True, comment="年度统计数据（JSON格式）")

    # 计算得出的适应度得分，建立索引以便排序和查询
    calculated_fitness_score = Column(Float, nullable=True, index=True, comment="根据预设标准计算得出的适应度得分")

    # 标记此 Alpha 是否曾是其所在实验中的历史最佳之一
    is_history_best = Column(Boolean, default=False, nullable=False, comment="标记此Alpha是否曾是历史最优之一")

    # 如果 Alpha 在模拟或处理过程中发生错误，记录错误信息
    error_message = Column(String, nullable=True, comment="若Alpha模拟或处理失败，记录错误信息")

    # 定义与 Experiment 模型的多对一关系
    # back_populates="alphas" 指明在 Experiment 模型中有一个名为 "alphas" 的属性反向关联回此 Alpha 列表。
    experiment = relationship("Experiment", back_populates="alphas")

    # 定义表参数，用于创建复合索引等
    __table_args__ = (
        Index("idx_alpha_experiment_id", "experiment_id"), # 为外键 experiment_id 创建索引（尽管ForeignKey也会创建，显式定义更清晰）
        Index("idx_alpha_depth_iteration", "depth", "iteration"), # 为深度和迭代次数的组合创建索引
        Index("idx_alpha_simulated_at", "simulated_at"), # 为模拟完成时间创建索引
        # calculated_fitness_score 字段已通过在其 Column 定义中设置 index=True 来创建索引
    )

    def __repr__(self):
        # 为模型定义一个可读的字符串表示形式，方便调试
        return f"<Alpha(id={self.id}, experiment_id={self.experiment_id}, fitness={self.calculated_fitness_score})>"

# 后续具体的数据库模型 (如 Experiment, Alpha 等) 将在此文件中定义，并继承自此类 Base。
# 例如:
# class User(Base):
#     __tablename__ = "users"
#     id = Column(Integer, primary_key=True, index=True)
#     username = Column(String, unique=True, index=True)
#     ...
