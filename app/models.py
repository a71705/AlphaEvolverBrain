# app/models.py
# 导入 SQLAlchemy 的 declarative_base，它是所有 ORM 模型的基础
from sqlalchemy.ext.declarative import declarative_base

# 创建一个 Base 类实例
# 后续所有的数据库模型都将继承自这个 Base 类
# SQLAlchemy 会使用这个 Base 类来收集所有定义的模型，并将它们映射到数据库表
Base = declarative_base()

# 后续任务 (如 DEV-008) 将在此文件中定义具体的模型类，例如:
# class Experiment(Base):
#     __tablename__ = "experiments"
#     # ... columns and relationships ...

# class Alpha(Base):
#     __tablename__ = "alphas"
#     # ... columns and relationships ...
