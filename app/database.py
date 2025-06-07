# 导入 os 模块，用于访问环境变量。
import os
# 从 sqlalchemy 导入 create_engine，用于创建数据库引擎。
from sqlalchemy import create_engine
# 从 sqlalchemy.orm 导入 sessionmaker，用于创建数据库会话工厂。
from sqlalchemy.orm import sessionmaker
# 从 sqlalchemy.event 导入 listen，用于监听 SQLAlchemy 事件。
from sqlalchemy.event import listen
# 从 sqlalchemy.engine 导入 Engine 类型，用于类型注解。
from sqlalchemy.engine import Engine
# 从 .models 模块导入 Base，这是所有 ORM 模型的基础类。
# Base.metadata.create_all(bind=engine) 将使用它来创建所有定义的表。
from .models import Base

# 从环境变量 "DATABASE_URL" 获取数据库连接字符串。
# 如果环境变量未设置，则使用默认值 "sqlite:///./data/alpha_evolution.db"。
# 这表示将使用当前工作目录下 data 子目录中的 alpha_evolution.db SQLite 文件。
# Docker Volume 会将此路径映射到持久化存储。
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/alpha_evolution.db")

# 创建 SQLAlchemy 引擎。
# connect_args={"check_same_thread": False} 仅在 SQLite 连接时需要。
# 这是因为 SQLite 默认只允许在创建它的线程中使用连接，而 FastAPI 可能在多个线程中处理请求。
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
)

# 事件监听器：在 SQLAlchemy 引擎连接到 SQLite 数据库时启用 WAL (Write-Ahead Logging) 模式。
# WAL 模式可以提高并发性能和数据完整性。
@listen(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    # 检查连接的是否为 SQLite 数据库
    if "sqlite" in SQLALCHEMY_DATABASE_URL:
        # 获取数据库游标
        cursor = dbapi_connection.cursor()
        # 执行 PRAGMA 命令以启用 WAL 模式
        cursor.execute("PRAGMA journal_mode=WAL")
        # 关闭游标
        cursor.close()

# 创建一个 SessionLocal 类 (会话工厂)。
# autocommit=False: 事务将不会自动提交，需要显式调用 db.commit()。
# autoflush=False: 查询前不会自动刷新会话，需要显式调用 db.flush()。
# bind=engine: 将此会话工厂绑定到我们创建的数据库引擎。
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 依赖注入函数：用于在 FastAPI 路由中获取数据库会话。
# 它是一个生成器函数，确保数据库会话在使用后总是被关闭。
def get_db():
    # 从会话工厂创建一个新的数据库会话实例
    db = SessionLocal()
    try:
        # 使用 yield 将会话对象提供给依赖它的代码块
        yield db
    finally:
        # 无论如何，在代码块执行完毕后关闭会话
        db.close()

# 函数：用于创建所有在 Base.metadata 中定义的数据库表。
# 这个函数将在应用启动时被调用。
def create_tables():
    # Base.metadata.create_all(bind=engine) 会检查数据库中是否存在表，
    # 如果不存在，则根据所有继承自 Base 的模型类创建它们。
    Base.metadata.create_all(bind=engine)
