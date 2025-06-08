# app/api/v1/__init__.py

# 从 fastapi 导入 APIRouter，用于创建和组织路由。
from fastapi import APIRouter

# 从同级目录下的 auth.py 文件中导入认证相关的路由。
# 在 auth.py 中，APIRouter 实例被命名为 router。
from .auth import router as auth_router

# 从同级目录下的 experiments.py 文件中导入实验管理相关的路由。
from .experiments import router as experiments_router

# 从同级目录下的 alphas.py 文件中导入单个Alpha资源管理相关的路由。
from .alphas import router as alphas_router

# 从同级目录下的 data_sources.py 文件中导入数据源元数据相关的路由。
from .data_sources import router as data_sources_router

# 导入其他未来可能存在的v1版本的路由模块的占位符（将被后续任务填充）
# from .experiments import router as experiments_router
# from .alphas import router as alphas_router
# from .data_sources import router as data_sources_router
# from .utils import router as utils_router
# from .status import router as status_router

# 创建一个 APIRouter 实例，用于聚合所有 /api/v1 下的特定模块路由。
# 这个实例将被 app/main.py 导入并使用（在 main.py 中它被命名为 api_router）。
api_router = APIRouter()

# 将认证路由包含到 v1 的主路由器中。
# auth_router 中定义的路径（例如 /login）已经带有 /auth 前缀（在其自身定义中指定）。
# 当此 api_router 被 app/main.py 的主 app 包含并加上 /api/v1 前缀后，
# 完整的路径将是 /api/v1/auth/login。
api_router.include_router(auth_router)

# 将实验管理路由包含到 v1 的主路由器中。
# experiments_router 中定义的路径（例如 / 、 /{experiment_id}）已经带有 /experiments 前缀。
api_router.include_router(experiments_router)

# 将 Alpha 资源管理路由包含到 v1 的主路由器中。
api_router.include_router(alphas_router) # prefix="/alphas" 已在 alphas_router 内部定义

# 将数据源元数据路由包含到 v1 的主路由器中。
api_router.include_router(data_sources_router) # prefix="/data_sources" 已在 data_sources_router 内部定义


# 占位符注释：后续其他API模块的路由将在这里添加
# 例如：
# api_router.include_router(experiments_router) # experiments_router 自身也应有 prefix 和 tags
# api_router.include_router(alphas_router)
# api_router.include_router(data_sources_router)
# api_router.include_router(utils_router)
# api_router.include_router(status_router)

# 此文件定义并导出了 api_router，供 app/main.py 使用。
