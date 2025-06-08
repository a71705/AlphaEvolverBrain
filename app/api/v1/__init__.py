# app/api/v1/__init__.py
# 这个文件使得 app/api/v1 目录可以被 Python 识别为一个包。
# 它同时定义了 v1 版本 API 的主路由器 (api_router)。

from fastapi import APIRouter

# 创建 v1 版本 API 的主 APIRouter 实例
# 所有 v1 版本的特定功能模块的路由器 (如认证、实验、Alpha等) 都将包含在此路由器下。
api_router = APIRouter()

# --- 包含认证相关的路由 ---
# 从同级目录的 auth.py 文件中导入认证路由器 (通常命名为 router)
from .auth import router as auth_router # 使用 as auth_router 避免命名冲突 (如果将来有其他 router)
# 将认证路由器包含到 v1 主路由器中
# auth_router 中定义的端点 (例如 /login) 将自动获得 /api/v1 的前缀 (来自 app/main.py 中对 api_router 的包含)
# 和 /auth 的前缀 (来自 auth.py 中 APIRouter 的定义)。
# 因此, /login 的完整路径将是 /api/v1/auth/login。
api_router.include_router(auth_router)


# --- 后续其他 v1 API 模块的路由器将在此处包含 ---
# 例如:
# from .experiments import router as experiments_router
# api_router.include_router(experiments_router)
#
# from .alphas import router as alphas_router
# api_router.include_router(alphas_router)
