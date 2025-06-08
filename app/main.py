# app/main.py
# 导入 FastAPI 类，用于创建 Web 应用实例
from fastapi import FastAPI
# 导入 CORSMiddleware，用于处理跨源资源共享 (CORS)
from fastapi.middleware.cors import CORSMiddleware
# 从同级目录的 api.v1 包中导入 api_router
# 这个 api_router 包含了 v1 版本的所有 API 端点
from .api.v1 import api_router
# 从同级目录的 database.py 文件中导入 create_tables 函数
# 此函数用于在应用启动时创建数据库表
from .database import create_tables
# 从 app.core.logging_config 模块导入日志配置函数
# 此函数用于在应用启动时配置日志记录器
from app.core.logging_config import configure_logging

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

    # 调用 create_tables 函数
    # 这将确保在应用启动时，所有在 models.py 中定义的、继承自 Base 的表都会被创建 (如果尚不存在)
    # 这是进行数据库初始化的推荐位置
    create_tables()

# 包含 v1 版本的 API 路由
# 所有在 api_router 中定义的路由都会以 "/api/v1" 作为前缀
app.include_router(api_router, prefix="/api/v1")

# 定义根路由
# 这是一个简单的 GET 请求处理函数，当访问应用根路径 ("/") 时调用
@app.get("/")
async def root():
    # 返回一个 JSON 响应
    return {"message": "Welcome to WorldQuant Brain Alpha Evolution System API"}
