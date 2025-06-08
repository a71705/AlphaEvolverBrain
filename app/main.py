# 导入 FastAPI 类，用于创建 FastAPI 应用实例
from fastapi import FastAPI
# 导入 CORSMiddleware，用于配置跨源资源共享 (CORS)
from fastapi.middleware.cors import CORSMiddleware
# 从 .api.v1 模块导入 api_router，这里假设 api_router 会在 v1 模块中定义
# 这个路由器将包含 /api/v1 前缀下的所有 API 路由
from .api.v1 import api_router
# 从 .database 模块导入 create_tables 函数，用于在应用启动时创建数据库表
from .database import create_tables
# 从 .core.logging_config 模块导入 configure_logging 函数，用于配置日志系统
from .core.logging_config import configure_logging
# 从 .core.notifications 模块导入 initialize_yagmail 函数 (DEV-032 新增)
from .core.notifications import initialize_yagmail
from rq import Queue
from redis import Redis
from .tasks import test_task # 导入我们创建的测试任务
import os # 用于获取 REDIS_URL, 如果需要从环境变量配置
import logging # 确保 logger 可用

# 创建 FastAPI 应用实例
# title 参数为应用设置一个标题，这个标题会在 OpenAPI 文档 (例如 Swagger UI) 中显示
app = FastAPI(title="WorldQuant Brain Alpha Evolution System")

# FastAPI 应用启动事件处理器
# 使用 @app.on_event("startup") 装饰器注册一个在应用启动时执行的函数。
# 这对于执行初始化任务非常有用，例如创建数据库表、加载配置等。
@app.on_event("startup")
async def startup_event():
    # 调用 configure_logging() 函数，配置应用范围的日志记录器。
    # 建议在其他启动任务之前配置日志，以便后续任务可以立即使用配置好的日志系统。
    configure_logging()
    logger = logging.getLogger("main_startup") # 获取logger实例，确保在日志配置后获取
    logger.info("应用程序启动中...")

    logger.info("正在初始化数据库表...")
    create_tables() # 创建数据库表
    logger.info("数据库表初始化完成。")

    logger.info("正在初始化邮件服务...")
    initialize_yagmail() # 初始化邮件服务 (DEV-032 新增)
    # 如果 initialize_yagmail 中有测试邮件发送，它会被调用（当前版本已注释掉自动测试邮件）
    logger.info("邮件服务初始化流程完成 (具体状态请查看 core.notifications 日志)。")

    logger.info("应用程序启动完成。")


# --- 用于测试 RQ 任务提交的临时端点 ---
# 注意：这个端点主要用于开发和测试目的。
# 在生产环境中，任务的提交逻辑可能会更复杂，并且此端点可能需要被移除或加以保护。

# 初始化 Redis 连接。
# REDIS_HOST 环境变量可以用于在不同环境中配置 Redis 主机名。
# 在 Docker Compose 环境中，它通常是 Redis 服务的名称，例如 'redis'。
# 如果 REDIS_URL 环境变量已在 docker-compose.yml 中为 web 服务设置，
# 并且包含了完整的 URL (redis://redis:6379/0)，那么可以直接解析它。
# 为简单起见，这里我们假设 REDIS_HOST 和 REDIS_PORT。
# 或者，更稳健的做法是依赖已在环境中设置的 REDIS_URL (如 RQ worker 那样)。

# 尝试从环境变量获取 Redis 连接信息，与 RQ Worker 的方式保持一致
redis_url_from_env = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
# redis.from_url 需要完整的 URL
try:
    redis_conn = Redis.from_url(redis_url_from_env)
    # 测试连接 (可选, 但有助于早期发现问题)
    redis_conn.ping()
    # logger 已在 startup_event 中通过 configure_logging() 初始化，可以直接使用
    # 但如果此代码块在 FastAPI app 定义之前，则需要确保 logger 已配置
    # 为安全起见，我们可以在这里获取logger实例，或者确保configure_logging()在更早执行
    # 此处假设 logger 已配置
    logging.getLogger(__name__).info(f"成功连接到 Redis 用于任务队列: {redis_url_from_env}")
except Exception as e: # 更通用的异常捕获 Redis 连接错误
    logging.getLogger(__name__).error(f"无法连接到 Redis: {e}。请确保 Redis 服务正在运行并且配置正确 ({redis_url_from_env})。")
    # 可以选择让应用启动失败，或者在无法连接时禁用任务提交功能。
    # 这里我们允许应用继续运行，但任务提交会失败。
    redis_conn = None # 表示连接失败

# 创建一个 RQ 队列实例。
# 'default' 是队列的名称，与 worker 监听的队列一致。
# connection=redis_conn 将队列与 Redis 连接关联起来。
# 如果 redis_conn 为 None，Queue 的操作会失败。
default_queue = Queue("default", connection=redis_conn) if redis_conn else None

@app.post("/test/enqueue_task", summary="提交一个测试任务到RQ队列（开发用）")
async def enqueue_sample_task(task_name: str = "WorldQuant User", task_delay: int = 3):
    """
    一个用于将 `test_task` 提交到 RQ 'default' 队列的临时测试端点。
    主要用于开发和验证 Worker 是否正常工作。

    参数:
        task_name (str): 要传递给 test_task 的名称。
        task_delay (int): test_task 模拟工作的延迟秒数。

    返回:
        dict: 包含作业提交结果的信息。
    """
    current_logger = logging.getLogger(__name__) # 获取当前作用域的logger
    if not default_queue:
        current_logger.error("无法提交任务：RQ 队列未初始化（Redis连接失败）。")
        return {"error": "RQ队列未初始化，无法连接到Redis", "job_id": None, "status": "FAILURE"}

    try:
        current_logger.info(f"准备提交 test_task 到 'default' 队列，参数 name='{task_name}', delay={task_delay}")
        # 将 test_task 函数提交到队列中执行。
        # RQ 会在后台的 worker 中异步调用 test_task(task_name, task_delay)。
        job = default_queue.enqueue(test_task, task_name, task_delay, job_timeout='1h') # job_timeout示例

        current_logger.info(f"test_task 已成功提交到队列。作业ID: {job.id}")
        return {
            "message": "测试任务已成功提交到队列。",
            "job_id": job.id,
            "task_function": "test_task",
            "task_args": {"name": task_name, "delay": task_delay},
            "queue_name": default_queue.name,
            "status": "QUEUED" # 作业的初始状态
        }
    except Exception as e:
        current_logger.error(f"提交 test_task 到队列时发生错误: {e}", exc_info=True)
        return {"error": f"提交任务失败: {str(e)}", "job_id": None, "status": "FAILURE"}

# --- 临时端点结束 ---

# 配置 CORS 中间件
# origins 列表定义了允许访问本 API 的来源域
# 在生产环境中，应该将这里的示例 URL 替换为实际部署的前端 URL
origins = [
    "http://localhost:8080",  # 前端开发服务器的示例 URL
    # 在此处添加您部署的前端 URL
]

# 将 CORS 中间件添加到应用中
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 允许访问的源列表
    allow_credentials=True,  # 是否允许携带凭证 (例如 cookies)
    allow_methods=["*"],  # 允许所有 HTTP 方法 (GET, POST, PUT, DELETE 等)
    allow_headers=["*"],  # 允许所有 HTTP 请求头
)

# 包含 API 路由器
# 将 api_router 包含到主应用中，并为其添加 /api/v1 的前缀
# 这意味着在 api_router 中定义的所有路由都会以 /api/v1 开头
app.include_router(api_router, prefix="/api/v1")

# 定义根路由
# 这是一个 GET 请求的处理器，当访问应用的根路径 ("/") 时会调用此函数
@app.get("/")
async def root():
    # 返回一个 JSON 响应
    return {"message": "Welcome to WorldQuant Brain Alpha Evolution System API"}
