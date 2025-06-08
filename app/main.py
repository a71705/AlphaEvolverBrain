# app/main.py
# 导入 os 模块，用于访问环境变量
import os
# 导入 logging 模块，用于日志记录
import logging
# 导入 FastAPI 类，用于创建 Web 应用实例
from fastapi import FastAPI, APIRouter, HTTPException, status # APIRouter, HTTPException, status 用于测试端点
# 导入 CORSMiddleware，用于处理跨源资源共享 (CORS)
from fastapi.middleware.cors import CORSMiddleware
# 从 redis 库导入 Redis 类，用于连接 Redis
from redis import Redis
# 从 rq 库导入 Queue 类，用于与 RQ 队列交互
from rq import Queue

# 从同级目录的 api.v1 包中导入 api_router
# 这个 api_router 包含了 v1 版本的所有 API 端点
from .api.v1 import api_router
# 从同级目录的 database.py 文件中导入 create_tables 函数
# 此函数用于在应用启动时创建数据库表
from .database import create_tables
# 从 app.core.logging_config 模块导入日志配置函数
# 此函数用于在应用启动时配置日志记录器
from app.core.logging_config import configure_logging
# 从 app.tasks 模块导入我们定义的测试任务
from app.tasks import test_task

# 获取主应用的 logger 实例
# configure_logging() 会在 startup_event 中配置它的格式和级别
logger = logging.getLogger(__name__) # 通常使用 __name__ (即 'app.main') 作为 logger 名称

# 创建 FastAPI 应用实例
# title 参数设置了应用的标题，会显示在 Swagger UI 等文档中
app = FastAPI(title="WorldQuant Brain Alpha Evolution System")

# 配置 CORS 中间件
# origins 列表定义了允许访问此 API 的源（域名）
# 在生产环境中，应将 "http://localhost:8080" 替换为实际的前端部署 URL
origins = [
    "http://localhost:8080",  # 前端开发服务器的示例地址
    # 在此处添加您部署的前端 URL
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 允许来自指定源的请求
    allow_credentials=True,  # 允许携带凭据 (如 cookies) 的请求
    allow_methods=["*"],  # 允许所有 HTTP 方法 (GET, POST, PUT, DELETE 等)
    allow_headers=["*"],  # 允许所有 HTTP 请求头
)

# 应用启动事件处理器
# @app.on_event("startup") 装饰器指定此函数在 FastAPI 应用启动时执行
@app.on_event("startup")
async def startup_event():
    # 首先配置日志系统
    # 这确保了应用启动过程中的所有日志（包括后续的表创建等操作）都能按照预期格式进行记录
    configure_logging()
    logger.info("应用启动事件开始：配置日志、数据库、Redis 和 RQ...")

    # 调用 create_tables 函数
    # 这将确保在应用启动时，所有在 models.py 中定义的、继承自 Base 的表都会被创建 (如果尚不存在)
    create_tables()
    logger.info("数据库表已检查/创建。")

    # 初始化 Redis 连接 和 RQ Queue
    # 从环境变量 REDIS_HOST 读取 Redis 主机名，默认为 'redis' (docker-compose中的服务名)
    redis_host = os.environ.get("REDIS_HOST", "redis")
    try:
        # 将连接和队列存储在 app.state 中，以便在应用的其他部分访问
        # decode_responses=True 使得从 Redis 获取的字节串自动解码为 Python 字符串
        app.state.redis_conn = Redis(host=redis_host, port=6379, db=0, decode_responses=True)
        app.state.redis_conn.ping() # 尝试 ping Redis 以验证连接
        logger.info(f"成功连接到 Redis 主机: {redis_host}")

        # default_timeout 设置任务在队列中的默认超时时间，例如1小时 (3600秒)
        # "default" 是我们在 docker-compose.yml 中让 worker 监听的队列名
        app.state.default_queue = Queue("default", connection=app.state.redis_conn, default_timeout=3600)
        logger.info(f"RQ 'default' 队列已在 Redis 主机 '{redis_host}' 上初始化。")
    except Exception as e:
        logger.error(f"启动时无法连接到 Redis 主机 '{redis_host}' 或初始化 RQ 队列: {e}", exc_info=True)
        # 在无法连接 Redis 的情况下，队列功能将不可用。
        # 设置为 None 以便后续的端点逻辑可以检查并优雅地失败。
        app.state.redis_conn = None
        app.state.default_queue = None

    logger.info("应用启动事件完成。")

# 应用关闭事件处理器
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("应用关闭事件开始...")
    # 优雅地关闭 Redis 连接
    if hasattr(app.state, 'redis_conn') and app.state.redis_conn:
        try:
            app.state.redis_conn.close()
            logger.info("Redis 连接已关闭。")
        except Exception as e:
            logger.error(f"关闭 Redis 连接时发生错误: {e}", exc_info=True)
    logger.info("应用关闭事件完成。")

# 包含 v1 版本的 API 路由
# 所有在 api_router 中定义的路由都会以 "/api/v1" 作为前缀
app.include_router(api_router, prefix="/api/v1")

# --- 开发测试用的路由 ---
# 创建一个新的 APIRouter 用于测试任务提交
# prefix="/dev-test" 为此路由器下所有端点添加路径前缀
# tags=["Development Tests"] 用于在 Swagger UI 中将这些端点分组
test_router = APIRouter(prefix="/dev-test", tags=["Development Tests"])

@test_router.post("/enqueue-test-task/{name}", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_test_task_endpoint(name: str):
    """
    一个用于测试提交 test_task 到 RQ 队列的端点。
    提交成功后返回 HTTP 202 Accepted 状态码。
    """
    # 从 app.state 获取队列 (如果在启动时初始化失败，则为 None)
    queue = getattr(app.state, 'default_queue', None)

    if queue is None:
        logger.error("无法提交任务：RQ 队列 'default_queue' 未在 app.state 中初始化或不可用。")
        # 如果队列不可用，返回 HTTP 500 内部服务器错误
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RQ 队列不可用，无法提交任务。"
        )

    try:
        # 将 app.tasks.test_task 函数和参数 name 加入队列
        # RQ 会异步地在 worker 进程中调用 test_task(name)
        # job_timeout='1h' 设置此特定任务的超时时间为1小时
        job = queue.enqueue(test_task, name, job_timeout='1h')

        logger.info(f"任务 test_task 已成功提交到队列 'default'。任务 ID: {job.id}, 参数 name: '{name}'")
        # 返回包含任务信息的 JSON 响应
        return {
            "message": "测试任务已成功提交到 RQ 队列。",
            "job_id": job.id,
            "task_name": test_task.__name__, # 获取被调用函数的实际名称
            "input_name": name,
            "queue_name": queue.name, # 队列名称
            "queued_at": job.enqueued_at.isoformat() if job.enqueued_at else None, # 任务入队时间
            "status": job.get_status() # 任务当前状态 (例如: queued, started, finished, failed)
        }
    except Exception as e:
        logger.error(f"提交 test_task 到 RQ 队列时发生错误: {e}", exc_info=True)
        # 如果提交过程中发生异常，返回 HTTP 500 错误
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提交任务到 RQ 队列失败: {str(e)}"
        )

# 将测试路由器包含到主应用中
app.include_router(test_router)

# 定义根路由 (通常放在所有其他路由包含之后，以避免路径冲突)
# 这是一个简单的 GET 请求处理函数，当访问应用根路径 ("/") 时调用
@app.get("/")
async def root():
    # 返回一个 JSON 响应
    return {"message": "Welcome to WorldQuant Brain Alpha Evolution System API"}
