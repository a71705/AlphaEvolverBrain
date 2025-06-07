# ---- 构建阶段 (Builder Stage) ----
# 使用 python:3.9-slim-buster 作为基础镜像进行构建。
# slim-buster 版本是一个轻量级的 Debian Buster 发行版，适合减小最终镜像体积。
FROM python:3.9-slim-buster AS builder

# 设置工作目录。所有后续的 RUN, COPY, CMD 等指令都将在此目录下执行。
WORKDIR /app

# 安装构建依赖。
# gcc 和 libpq-dev 是示例，如果您的项目依赖其他需要编译的库，请在此处添加。
# 此处暂时不安装额外的系统依赖，因为当前 requirements.txt 中的库不需要。
# RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# 设置 PIP_NO_CACHE_DIR 环境变量，禁止 pip 缓存，以减小镜像层的大小。
ENV PIP_NO_CACHE_DIR=off
# 设置 PIP_DISABLE_PIP_VERSION_CHECK 环境变量，禁止 pip 版本检查，加快构建速度。
ENV PIP_DISABLE_PIP_VERSION_CHECK=on

# 复制 requirements.txt 文件到工作目录。
COPY requirements.txt .

# 安装 Python 依赖。
# --no-cache-dir 选项确保不使用缓存，帮助减小镜像大小。
# --prefix=/install 选项将依赖安装到一个独立的目录，方便从构建阶段复制到最终阶段。
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---- 运行阶段 (Final Stage) ----
# 使用与构建阶段相同的基础镜像，以保持一致性并利用缓存。
FROM python:3.9-slim-buster

# 设置工作目录。
WORKDIR /app

# 从构建阶段复制已安装的 Python 依赖到最终镜像。
# 这种方式可以避免将构建工具和中间文件带入最终镜像。
COPY --from=builder /install /usr/local

# 复制应用代码到工作目录。
# 注意：.dockerignore 文件中定义的模式将在此处生效，被忽略的文件不会被复制。
COPY . .

# 暴露端口 8000。
# 这是 FastAPI 应用（通过 Uvicorn 运行）将监听的端口。
# 注意：EXPOSE 指令仅作为文档说明，实际端口映射在 docker-compose.yml 或 docker run 命令中完成。
EXPOSE 8000

# 定义容器启动时执行的命令。
# 使用 uvicorn 运行 app.main 模块中的 app 对象。
# --host 0.0.0.0 使服务可以从容器外部访问。
# --port 8000 指定监听端口。
# --reload 选项用于开发环境，当代码更改时自动重新加载服务。生产环境应移除此选项。
# 为了符合 DEV-002 的要求 (非生产环境的初始设置)，暂时保留 --reload。
# 后续任务中可能会针对生产环境进行优化。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
