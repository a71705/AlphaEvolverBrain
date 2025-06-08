# app/database.py
# 导入 os 模块以访问环境变量
import os
# 从 sqlalchemy 导入创建引擎的功能
from sqlalchemy import create_engine
# 从 sqlalchemy.orm 导入 sessionmaker 用于创建数据库会话
from sqlalchemy.orm import sessionmaker
# 从 sqlalchemy.event 导入 listen 用于监听引擎事件
from sqlalchemy.event import listen
# 从 sqlalchemy.engine 导入 Engine 类型，用于类型注解
from sqlalchemy.engine import Engine
# 从当前目录的 models.py 文件中导入 Base
# Base 是所有 SQLAlchemy 模型的基础，用于创建表
from .models import Base

# 定义 SQLAlchemy 数据库连接 URL
# 优先从环境变量 "DATABASE_URL" 获取
# 如果环境变量未设置，则默认为 SQLite 数据库，文件位于 ./data/alpha_evolution.db
# 注意: "./data/" 是相对于应用运行时的当前工作目录。
# 在 Docker 环境中，此路径将指向容器内的 /app/data/alpha_evolution.db (如果工作目录是 /app)
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/alpha_evolution.db")

# 创建 SQLAlchemy 引擎
# create_engine 是 SQLAlchemy 应用的起点
# connect_args={"check_same_thread": False} 仅在 SQLite 使用时需要。
# 这是因为 SQLite 默认只允许在创建它的线程中使用连接，FastAPI 可能在多个线程中处理请求。
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
)

# 为 SQLite 数据库连接设置 PRAGMA journal_mode=WAL
# WAL (Write-Ahead Logging) 模式可以提高并发性能和数据完整性
# 使用 @listen 装饰器将此函数注册为在引擎 "connect" 事件发生时调用
@listen(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    # 检查是否为 SQLite 数据库连接
    if "sqlite" in SQLALCHEMY_DATABASE_URL:
        # 获取数据库游标
        cursor = dbapi_connection.cursor()
        # 执行 PRAGMA 命令
        cursor.execute("PRAGMA journal_mode=WAL")
        # 关闭游标
        cursor.close()

# 创建一个 SessionLocal 类
# sessionmaker 用于创建一个数据库会话工厂
# autocommit=False: 禁用自动提交，需要显式调用 db.commit()
# autoflush=False: 禁用自动刷新，避免不必要的数据库查询
# bind=engine: 将此会话工厂绑定到之前创建的引擎
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 定义一个 FastAPI 依赖项 (dependency) get_db
# 此函数将在 API 路由处理函数中用作依赖项，以获取数据库会话
def get_db():
    # 从 SessionLocal 工厂创建一个新的数据库会话
    db = SessionLocal()
    try:
        # 使用 yield 将数据库会话提供给路径操作函数
        # 当路径操作函数执行完毕后，代码将继续执行 finally 块
        yield db
    finally:
        # 确保数据库会话在请求结束后总是关闭
        db.close()

# 定义一个函数来创建所有数据库表
# 此函数会查找所有继承自 Base 的模型，并在数据库中创建相应的表
def create_tables():
    # Base.metadata.create_all() 会发出 CREATE TABLE 语句
    # bind=engine 指定了在哪个数据库引擎上执行这些操作
    Base.metadata.create_all(bind=engine)
    # 可以在此处添加日志，表明表已创建或检查
    print("数据库表已检查/创建。") # 简单打印，实际项目中应使用日志模块
