# app/main.py
# 导入 FastAPI 类，用于创建 Web 应用实例
from fastapi import FastAPI
# 导入 CORSMiddleware，用于处理跨源资源共享 (CORS)
from fastapi.middleware.cors import CORSMiddleware
# 从同级目录的 api.v1 包中导入 api_router
# 这个 api_router 包含了 v1 版本的所有 API 端点
from .api.v1 import api_router

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

# 包含 v1 版本的 API 路由
# 所有在 api_router 中定义的路由都会以 "/api/v1" 作为前缀
app.include_router(api_router, prefix="/api/v1")

# 定义根路由
# 这是一个简单的 GET 请求处理函数，当访问应用根路径 ("/") 时调用
@app.get("/")
async def root():
    # 返回一个 JSON 响应
    return {"message": "Welcome to WorldQuant Brain Alpha Evolution System API"}
