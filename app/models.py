# app/models.py
# 导入 SQLAlchemy 的 declarative_base，它是所有 ORM 模型的基础
from sqlalchemy.ext.declarative import declarative_base
# 导入 SQLAlchemy 的列、数据类型、外键、索引等
from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean, ForeignKey, Index
# 导入 SQLAlchemy 的关系定义功能
from sqlalchemy.orm import relationship
# 导入 Python 的 datetime 模块，用于处理日期和时间
from datetime import datetime

# 创建一个 Base 类实例
# 后续所有的数据库模型都将继承自这个 Base 类
# SQLAlchemy 会使用这个 Base 类来收集所有定义的模型，并将它们映射到数据库表
Base = declarative_base()

class Experiment(Base):
    # 表名
    __tablename__ = 'experiments'

    # 主键ID, 自动增长, 带索引
    id = Column(Integer, primary_key=True, index=True, comment="实验的唯一标识符")
    # 实验名称, 带索引, 不允许为空
    name = Column(String, index=True, nullable=False, comment="实验的名称")
    # 实验描述, 可为空
    description = Column(String, nullable=True, comment="实验的详细描述")
    # 实验开始时间, 默认为当前UTC时间
    start_time = Column(DateTime, default=datetime.utcnow, comment="实验开始的UTC时间")
    # 实验结束时间, 可为空 (例如实验正在进行中或未正常结束)
    end_time = Column(DateTime, nullable=True, comment="实验结束的UTC时间")
    # 实验状态 (例如: PENDING, RUNNING, COMPLETED, FAILED), 带索引, 默认为 PENDING
    status = Column(String, default="PENDING", index=True, comment="实验的当前状态")
    # 存储实验配置的JSON对象 (例如遗传算法参数), 不允许为空
    config_json = Column(JSON, nullable=False, comment="实验配置参数的JSON对象")
    # 代码版本 (例如 Git commit hash), 可为空
    code_version = Column(String, nullable=True, comment="执行实验时的代码版本 (如Git commit hash)")
    # 当前进化到的Alpha树的最大深度
    current_depth = Column(Integer, default=0, comment="遗传算法当前进化到的Alpha树最大深度")
    # 当前进化到的迭代次数/代数
    current_iteration = Column(Integer, default=0, comment="遗传算法当前进化到的迭代次数/代数")
    # 随机种子, 用于复现实验, 可为空
    random_seed = Column(Integer, nullable=True, comment="用于初始化随机数生成器的种子，以确保实验可复现")

    # 定义与 Alpha 模型的一对多关系
    # 'alphas' 属性将允许从 Experiment 对象访问其关联的所有 Alpha 对象
    # back_populates='experiment' 指向 Alpha 模型中名为 'experiment' 的反向关系属性
    # cascade='all, delete-orphan' 表示当 Experiment 被删除时，其关联的 Alpha 也应被删除 (delete),
    # 并且对 Experiment 的操作 (如添加到 session) 会级联到关联的 Alpha (all)。
    # 'delete-orphan' 意味着如果一个 Alpha 不再关联任何 Experiment，它也会被删除。
    alphas = relationship("Alpha", back_populates="experiment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Experiment(id={self.id}, name='{self.name}', status='{self.status}')>"

class Alpha(Base):
    # 表名
    __tablename__ = 'alphas'

    # 主键ID, 自动增长, 带索引
    id = Column(Integer, primary_key=True, index=True, comment="Alpha的唯一标识符")
    # 外键,关联到 Experiment 表的 id 字段, 不允许为空
    experiment_id = Column(Integer, ForeignKey('experiments.id'), nullable=False, comment="关联的实验ID")

    # Alpha 表达式字符串, 不允许为空, 带索引
    expression = Column(String, nullable=False, index=True, comment="Alpha表达式的字符串表示")
    # Alpha 树的深度, 可为空 (某些Alpha可能没有明确的深度概念或未计算)
    depth = Column(Integer, nullable=True, comment="Alpha树的深度")
    # 生成此Alpha时的迭代次数/代数, 不允许为空
    iteration = Column(Integer, nullable=False, comment="生成此Alpha时的遗传算法迭代次数/代数")
    # 父Alpha的ID列表 (JSON格式), 用于血缘追踪, 可为空
    parent_ids = Column(JSON, nullable=True, comment="父Alpha的ID列表 (JSON格式)，用于血缘关系追踪")

    # 模拟此Alpha时使用的具体设置 (JSON格式), 可为空
    simulation_settings_json = Column(JSON, nullable=True, comment="模拟此Alpha时使用的具体参数设置 (JSON格式)")
    # Alpha被模拟的时间戳, 默认为当前UTC时间
    simulated_at = Column(DateTime, default=datetime.utcnow, comment="Alpha被模拟的UTC时间戳")

    # 样本内统计数据 (JSON格式), 可为空
    is_stats_json = Column(JSON, nullable=True, comment="样本内(In-Sample)统计数据 (JSON格式)")
    # 样本内测试结果 (JSON格式), 可为空
    is_tests_json = Column(JSON, nullable=True, comment="样本内(In-Sample)测试结果 (JSON格式)")
    # 样本外统计数据 (JSON格式), 可为空
    oos_stats_json = Column(JSON, nullable=True, comment="样本外(Out-of-Sample)统计数据 (JSON格式)")
    # PnL (Profit and Loss) 时间序列数据 (JSON格式), 可为空
    pnl_data_json = Column(JSON, nullable=True, comment="PnL (Profit and Loss) 时间序列数据 (JSON格式)")
    # 年度统计数据 (JSON格式), 可为空
    yearly_stats_data_json = Column(JSON, nullable=True, comment="年度统计数据 (JSON格式)")

    # 计算出的适应度分数, 可为空, 带索引
    calculated_fitness_score = Column(Float, nullable=True, index=True, comment="根据适应度函数计算得到的分数")
    # 标记此Alpha是否为历史最佳之一, 默认为False, 带索引
    is_history_best = Column(Boolean, default=False, index=True, comment="标记此Alpha是否在其进化历史中被认为是最佳之一")
    # 模拟或处理此Alpha时发生的错误信息, 可为空
    error_message = Column(String, nullable=True, comment="如果模拟或处理此Alpha失败，记录错误信息")

    # 定义与 Experiment 模型的多对一关系
    # 'experiment' 属性将允许从 Alpha 对象访问其关联的 Experiment 对象
    # back_populates='alphas' 指向 Experiment 模型中名为 'alphas' 的反向关系属性
    experiment = relationship("Experiment", back_populates="alphas")

    # 定义表级参数，主要用于创建索引
    __table_args__ = (
        # 任务卡片中指定的索引
        Index('idx_alpha_experiment_id', 'experiment_id', comment="按实验ID查询Alpha的索引"), # 对应 ForeignKey 自动创建的索引，这里显式定义以控制命名和注释
        Index('idx_alpha_depth_iteration', 'depth', 'iteration', comment="按深度和迭代次数查询Alpha的索引"),
        Index('idx_alpha_fitness_score', 'calculated_fitness_score', comment="按适应度分数查询Alpha的索引"), # 对应字段上的 index=True，这里可省略或用于复合索引
        Index('idx_alpha_simulated_at', 'simulated_at', comment="按模拟时间查询Alpha的索引"),

        # 额外的实用索引 (可以根据实际查询模式调整或合并)
        Index('idx_alpha_exp_iter', 'experiment_id', 'iteration', comment="按实验ID和迭代次数联合查询Alpha的索引"),
        Index('idx_alpha_exp_fitness', 'experiment_id', 'calculated_fitness_score', comment="按实验ID和适应度分数联合查询Alpha的索引"),
    )

    def __repr__(self):
        return f"<Alpha(id={self.id}, expression='{self.expression[:30]}...', experiment_id={self.experiment_id}, fitness={self.calculated_fitness_score})>"
