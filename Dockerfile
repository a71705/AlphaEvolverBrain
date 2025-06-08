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
COPY ./app /app/app # 确保 app 目录被正确复制到 /app/app
COPY ./scripts /app/scripts # 复制 scripts 目录 (如果需要脚本在容器内)
COPY ./data /app/data # 复制 data 目录的初始内容 (如果需要) - 注意：通常数据卷会覆盖这里
# 如果根目录下有其他需要复制的文件，例如 main.py (如果 app.main:app 指的是根目录的main.py)
# COPY main.py . # 示例，根据实际项目结构调整

# --- 安全加固：创建并切换到非root用户 (DEV-040) ---
# 1. 创建一个用户组 'appgroup' 和一个系统用户 'appuser'。
#    '-r' 表示创建系统用户/组。
#    '--no-log-init' (如果可用) 减少不必要的日志。
#    '--shell /bin/false' 或 '--shell /sbin/nologin' 禁止此用户直接登录。
#    '--no-create-home' 此用户不需要家目录。
RUN groupadd -r appgroup && \
    useradd --no-log-init -r -g appgroup --shell /sbin/nologin --no-create-home appuser

# 2. (可选但推荐) 更改应用目录的所有权给新创建的用户和组。
#    确保 /app 目录中的所有文件和子目录都归 appuser:appgroup 所有。
#    这允许非root用户读取应用文件，并写入其被授权的子目录（如果需要）。
#    对于 /app/data 目录，如果它是由卷挂载的，Docker卷的权限管理更为复杂，
#    可能需要在容器启动时或通过其他方式调整。
#    如果 SQLite 数据库文件在 /app/data 中，并且应用需要写入，则 appuser 必须有权写入。
#    如果 /app/data 是一个命名卷，Docker通常会处理好权限以便容器内用户可以写入。
#    如果它是一个主机路径挂载，则宿主机上的权限和容器内用户的UID/GID映射会起作用。
RUN chown -R appuser:appgroup /app
# 如果有其他应用需要写入的目录（例如日志目录），也应在此处设置权限：
# RUN mkdir -p /var/log/app_logs && chown -R appuser:appgroup /var/log/app_logs

# 3. 切换到非root用户 'appuser'。
#    此后的所有 RUN, CMD, ENTRYPOINT 指令都将以此用户身份执行。
USER appuser
# --- 安全加固结束 ---

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
