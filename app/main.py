# 导入 FastAPI 类，用于创建 FastAPI 应用实例
from fastapi import FastAPI
# 导入 CORSMiddleware，用于配置跨源资源共享 (CORS)
from fastapi.middleware.cors import CORSMiddleware
# 从 .api.v1 模块导入 api_router，这里假设 api_router 会在 v1 模块中定义
# 这个路由器将包含 /api/v1 前缀下的所有 API 路由
from .api.v1 import api_router
# 从 .database 模块导入 create_tables 函数，用于在应用启动时创建数据库表
from .database import create_tables

# 创建 FastAPI 应用实例
# title 参数为应用设置一个标题，这个标题会在 OpenAPI 文档 (例如 Swagger UI) 中显示
app = FastAPI(title="WorldQuant Brain Alpha Evolution System")

# FastAPI 应用启动事件处理器
# 使用 @app.on_event("startup") 装饰器注册一个在应用启动时执行的函数。
# 这对于执行初始化任务非常有用，例如创建数据库表、加载配置等。
@app.on_event("startup")
async def startup_event():
    # 调用 create_tables() 函数，创建在 app.models 中定义的数据库表。
    # 如果表已存在，此操作通常不会产生影响。
    create_tables()
    # 可以在此处添加其他启动时需要执行的逻辑，例如初始化日志配置 (将在后续任务中添加)
    # print("数据库表创建（如果不存在）完成。") # 临时打印，用于确认启动事件执行

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
