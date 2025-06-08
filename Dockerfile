# Dockerfile
# 阶段 1: 构建阶段 (如果需要编译或打包特定依赖)
# 对于纯 Python 项目，多阶段构建可能不是立即必需的，但这是一个好习惯
# 此处我们使用单阶段构建以简化初始设置

# 使用官方 Python 运行时作为父镜像
# python:3.9-slim-buster 提供了较小的镜像体积
FROM python:3.9-slim-buster AS base

# 设置环境变量
# PYTHONUNBUFFERED: 确保 Python 输出直接发送到终端，便于 Docker 日志查看
# PYTHONDONTWRITEBYTECODE: 防止 Python 写入 .pyc 文件，保持容器清洁
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 设置工作目录
# 后续的 RUN, CMD, COPY, ADD 指令都将在此目录下执行
WORKDIR /app

# 安装系统依赖 (如果项目需要)
# 例如: RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*
# 当前项目暂无额外系统依赖

# 复制依赖文件到工作目录
# 首先复制 requirements.txt，这样可以利用 Docker 的层缓存机制
# 只有当 requirements.txt 发生变化时，才会重新执行 pip install
COPY requirements.txt .

# 安装 Python 依赖
# --no-cache-dir: 不使用缓存，减小镜像体积
# -r requirements.txt: 从指定文件安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码到工作目录
# 将当前目录下的 app 文件夹 (包含 FastAPI 应用) 复制到镜像的 /app/app 目录
COPY ./app /app/app

# 暴露端口
# 声明容器在运行时监听的端口，FastAPI 应用将运行在 8000 端口
EXPOSE 8000

# 定义容器启动时执行的命令
# 使用 uvicorn 启动 FastAPI 应用 (app.main:app)
# --host 0.0.0.0: 使应用可以从容器外部访问
# --port 8000: 指定应用监听的端口
# --reload: 开发时使用，当代码变化时自动重启服务 (生产环境通常不使用 --reload)
# 注意: 在 docker-compose.yml 中可以覆盖此 CMD 指令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
