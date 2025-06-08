# app/api/v1/__init__.py
# 导入 FastAPI 的 APIRouter，用于定义路由
from fastapi import APIRouter

# 创建一个 APIRouter 实例
# 这个 router 将用于注册所有 v1 版本的 API 端点
api_router = APIRouter()

# 此处可以稍后添加导入其他路由模块的代码
# 例如: from . import items, users
