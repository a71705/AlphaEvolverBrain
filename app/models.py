# 导入 SQLAlchemy 的 declarative_base 函数，用于创建 ORM 模型类的基类。
from sqlalchemy.ext.declarative import declarative_base

# 调用 declarative_base() 创建一个 Base 类。
# 项目中所有的 ORM 模型都应该继承自这个 Base 类。
# SQLAlchemy 会使用这个 Base 类来收集所有定义的模型，并将其映射到数据库表。
Base = declarative_base()

# 后续具体的数据库模型 (如 Experiment, Alpha 等) 将在此文件中定义，并继承自此类 Base。
# 例如:
# class User(Base):
#     __tablename__ = "users"
#     id = Column(Integer, primary_key=True, index=True)
#     username = Column(String, unique=True, index=True)
#     ...
