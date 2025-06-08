# tests/backend/conftest.py
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession # 使用别名避免与pytest的Session冲突
from fastapi.testclient import TestClient # 用于同步测试 FastAPI 应用
import os
import logging

# 应用内部模块导入
from app.database import Base, get_db # 从主应用导入Base和get_db
from app.main import app # 导入FastAPI应用实例
# from app.models import Experiment, Alpha # 导入模型用于可能的预填充或清理 (按需导入)

# 配置测试日志，使其在测试输出中可见
# logger = logging.getLogger(__name__) # 获取当前conftest的logger
# logging.basicConfig(level=logging.DEBUG) # 基础配置，pytest.ini中的log_cli_level会覆盖控制台级别

# 测试数据库配置
# 使用内存SQLite进行快速测试，或指定一个本地文件用于调试
# TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:" # 内存数据库，每次测试都是全新的
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///./test_alpha_evolution.db" # 使用文件，便于调试后检查
# 确保测试数据库与生产/开发数据库隔离

@pytest.fixture(scope="session") # session级别的fixture，整个测试会话只执行一次
def test_engine():
    """
    创建一个用于整个测试会话的SQLite引擎。
    在会话开始时创建所有数据库表，在会话结束时删除它们。
    """
    logger = logging.getLogger("conftest.test_engine") # 为fixture创建特定logger
    logger.info(f"为测试会话创建数据库引擎，URL: {TEST_SQLALCHEMY_DATABASE_URL}")

    # 如果使用文件数据库，先确保旧的测试数据库文件被删除，保证幂等性
    if "sqlite:///" in TEST_SQLALCHEMY_DATABASE_URL and TEST_SQLALCHEMY_DATABASE_URL != "sqlite:///:memory:":
        db_file_path = TEST_SQLALCHEMY_DATABASE_URL.split("sqlite:///./")[1]
        if os.path.exists(db_file_path):
            logger.debug(f"删除已存在的测试数据库文件: {db_file_path}")
            try:
                os.unlink(db_file_path)
            except OSError as e:
                logger.error(f"删除旧测试数据库文件 {db_file_path} 失败: {e}。测试可能使用旧数据或失败。")


    engine = create_engine(
        TEST_SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False} # SQLite 在多线程/异步测试中通常需要此参数
    )

    logger.info("在测试数据库中创建所有表 (Base.metadata.create_all)...")
    Base.metadata.create_all(bind=engine) # 应用所有模型到此引擎 (创建表)

    yield engine # 提供引擎给需要的fixture或测试

    # 测试会话结束后清理
    logger.info("测试会话结束，销毁测试数据库表...")
    Base.metadata.drop_all(bind=engine) # 删除所有表

    if "sqlite:///" in TEST_SQLALCHEMY_DATABASE_URL and TEST_SQLALCHEMY_DATABASE_URL != "sqlite:///:memory:":
        db_file_path = TEST_SQLALCHEMY_DATABASE_URL.split("sqlite:///./")[1]
        if os.path.exists(db_file_path):
            logger.info(f"删除测试数据库文件: {db_file_path}")
            try:
                os.unlink(db_file_path)
            except OSError as e:
                 logger.error(f"删除测试数据库文件 {db_file_path} 失败: {e}。请手动清理。")


@pytest.fixture(scope="function") # function级别的fixture，每个测试函数执行一次
def db_session(test_engine):
    """
    为每个测试函数提供一个独立的数据库事务。
    测试开始时，启动一个事务；测试结束后，回滚该事务以确保测试间的隔离性。
    同时，此fixture会覆盖FastAPI应用中的 get_db 依赖，使其使用此事务性会话。
    """
    logger = logging.getLogger("conftest.db_session") # 为fixture创建特定logger
    connection = test_engine.connect()
    transaction = connection.begin() # 开始一个事务

    # 创建一个会话，绑定到此连接的事务中
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    db: SQLAlchemySession = TestingSessionLocal()

    logger.debug("测试数据库会话已创建并开始事务。")

    # 覆盖 FastAPI 应用中的 get_db 依赖
    original_get_db_override = app.dependency_overrides.get(get_db)
    def override_get_db():
        try:
            yield db
        finally:
            # db.close() # 会话由fixture本身管理关闭
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield db # 将会话提供给测试用例

    # 测试函数执行完毕后
    logger.debug("测试函数执行完毕，回滚事务并关闭会话/连接。")
    db.close()
    transaction.rollback() # 回滚事务，保持数据库清洁，使每个测试独立
    connection.close()

    # 恢复原始的 get_db 依赖 (如果之前有其他覆盖，否则移除)
    if original_get_db_override:
        app.dependency_overrides[get_db] = original_get_db_override
    else:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="module") # module级别的fixture，每个测试模块执行一次
def client(test_engine) -> TestClient:
    """
    创建一个FastAPI TestClient实例，用于向应用发送HTTP请求。
    此fixture依赖test_engine以确保数据库表在客户端创建前已设置好。
    TestClient将使用被db_session fixture覆盖了get_db依赖的FastAPI app实例，
    因此API调用将使用事务性会话。
    """
    logger = logging.getLogger("conftest.client")
    logger.info("为测试模块创建FastAPI TestClient。")
    # FastAPI TestClient会自动处理应用的startup和shutdown事件
    # 如果在startup中有数据库连接或表创建，TestClient会触发它们
    # 但我们使用test_engine fixture来显式管理测试数据库的生命周期
    test_app_client = TestClient(app)
    return test_app_client
