#!/bin/bash
# 脚本: backup_db.sh
# 描述: 用于备份 SQLite 数据库，压缩并上传到 GCP Cloud Storage 的脚本。
# 作者: WorldQuant Alpha Evolution System 开发团队
# 版本: 1.0.0
# 创建日期: $(date +"%Y-%m-%d")

# --- 配置段落 开始 ---
# 这些变量应该通过外部环境变量设置，或作为脚本参数传递。
# 为了脚本的灵活性，优先使用环境变量。

# 数据库文件在容器内的绝对路径，或者在宿主机上可以直接访问的路径。
# 如果脚本在宿主机运行，并且数据库在Docker卷中，需要先通过 `docker cp` 复制出来，
# 或者挂载卷到另一个临时容器中执行备份。
# 假设此脚本的运行环境可以直接访问原始DB文件或其安全副本。
DB_FILE_PATH="${DB_FILE_PATH_FOR_BACKUP:-/app/data/alpha_evolution.db}"

# 临时存放备份文件的目录 (在执行脚本的机器上)
# 确保此目录可写。
BACKUP_TEMP_DIR="${BACKUP_TEMP_DIR:-/tmp/db_backups}"

# 您的 GCP Cloud Storage Bucket 名称 (例如: 'my-alpha-evo-backups')
GCS_BUCKET_NAME="${GCS_BUCKET_NAME}"

# 在GCS Bucket中存储备份的路径 (可选，例如 'daily_backups/')
GCS_BACKUP_PATH_PREFIX="${GCS_BACKUP_PATH_PREFIX:-database_backups}"

# GCP 服务账户密钥JSON文件的路径 (可选, 如果 gsutil 未配置默认认证或需要在特定服务账户下运行)
# GCS_SERVICE_ACCOUNT_KEY_FILE="${GCS_SERVICE_ACCOUNT_KEY_FILE}"

# --- 配置段落 结束 ---

# --- 函数定义 开始 ---

# 日志函数，带时间戳
log_message() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") - $1"
}

# 错误处理函数
handle_error() {
    local error_message="$1"
    local exit_code="${2:-1}" # 默认为1
    log_message "错误: ${error_message}"
    log_message "数据库备份过程意外终止。"
    exit "${exit_code}"
}

# --- 函数定义 结束 ---

# --- 主逻辑 开始 ---

log_message "数据库备份脚本开始执行..."

# 0. 设置set -e，使得脚本在任何命令执行失败时立即退出
set -e

# 1. 检查必要的配置
if [ -z "${DB_FILE_PATH}" ]; then
    handle_error "环境变量 DB_FILE_PATH_FOR_BACKUP 未设置。请指定数据库文件路径。"
fi
if [ -z "${GCS_BUCKET_NAME}" ]; then
    handle_error "环境变量 GCS_BUCKET_NAME 未设置。请指定GCP Cloud Storage Bucket名称。"
fi
# DB_FILE_PATH 的存在性检查将在 sqlite3 .backup 命令执行前进行，如果文件不存在，sqlite3会报错

# (可选) 如果使用服务账户密钥文件进行gsutil认证
if [ -n "${GCS_SERVICE_ACCOUNT_KEY_FILE}" ]; then
    if [ ! -f "${GCS_SERVICE_ACCOUNT_KEY_FILE}" ]; then
        handle_error "指定的服务账户密钥文件 '${GCS_SERVICE_ACCOUNT_KEY_FILE}' 未找到。"
    fi
    log_message "尝试使用服务账户 '${GCS_SERVICE_ACCOUNT_KEY_FILE}' 进行GCP认证..."
    # 确保 gcloud 命令行工具已安装
    if ! command -v gcloud &> /dev/null; then
        handle_error "gcloud 命令行工具未找到。请先安装 Google Cloud SDK。"
    fi
    gcloud auth activate-service-account --key-file="${GCS_SERVICE_ACCOUNT_KEY_FILE}" || handle_error "GCP服务账户认证失败。"
    log_message "GCP服务账户认证成功。"
fi

# 2. 准备本地备份环境
log_message "准备本地备份目录 '${BACKUP_TEMP_DIR}'..."
mkdir -p "${BACKUP_TEMP_DIR}" # || handle_error "创建本地备份目录 '${BACKUP_TEMP_DIR}' 失败。" (set -e 会处理)

DB_BASENAME=$(basename "${DB_FILE_PATH}")
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
# 使用 .sqlite3 扩展名以明确是SQLite文件，然后再加 .gz
LOCAL_SQLITE_BACKUP_FILE="${BACKUP_TEMP_DIR}/${DB_BASENAME}_${TIMESTAMP}.sqlite3"
LOCAL_GZ_BACKUP_FILE="${LOCAL_SQLITE_BACKUP_FILE}.gz"

# 3. 执行 SQLite 数据库备份 (使用 .backup 命令保证一致性)
log_message "正在使用 SQLite '.backup' 命令创建数据库副本从 '${DB_FILE_PATH}' 到 '${LOCAL_SQLITE_BACKUP_FILE}'..."
# 需要系统中安装了 sqlite3 命令行工具
if ! command -v sqlite3 &> /dev/null; then
    handle_error "sqlite3 命令行工具未找到。请先安装它 (例如: sudo apt install sqlite3)。"
fi

if [ ! -f "${DB_FILE_PATH}" ]; then
    handle_error "指定的原始数据库文件 '${DB_FILE_PATH}' 不存在或不是一个文件。"
fi

# 从原始数据库文件创建一个精确的副本
sqlite3 "${DB_FILE_PATH}" ".backup '${LOCAL_SQLITE_BACKUP_FILE}'" # set -e 会处理错误
log_message "数据库副本创建成功。"

# 4. 压缩备份文件
log_message "正在压缩数据库副本 '${LOCAL_SQLITE_BACKUP_FILE}' 为 '${LOCAL_GZ_BACKUP_FILE}'..."
gzip -f "${LOCAL_SQLITE_BACKUP_FILE}" # set -e 会处理错误; -f 强制覆盖输出文件
log_message "数据库副本压缩成功。"

if [ ! -f "${LOCAL_GZ_BACKUP_FILE}" ]; then
    handle_error "压缩后的备份文件 '${LOCAL_GZ_BACKUP_FILE}' 未找到 (压缩步骤可能失败)。"
fi

# 5. 上传到 GCP Cloud Storage
# 确保 GCS_BACKUP_PATH_PREFIX 不以 / 开头，并且如果非空则以 / 结尾
GCS_TARGET_PATH_PREFIX_FORMATTED=$(echo "${GCS_BACKUP_PATH_PREFIX}" | sed 's:/*$::' | sed 's:^/*::')
if [ -n "${GCS_TARGET_PATH_PREFIX_FORMATTED}" ]; then
    GCS_TARGET_PATH="gs://${GCS_BUCKET_NAME}/${GCS_TARGET_PATH_PREFIX_FORMATTED}/$(basename ${LOCAL_GZ_BACKUP_FILE})"
else
    GCS_TARGET_PATH="gs://${GCS_BUCKET_NAME}/$(basename ${LOCAL_GZ_BACKUP_FILE})"
fi

log_message "正在上传压缩备份文件 '${LOCAL_GZ_BACKUP_FILE}' 到 '${GCS_TARGET_PATH}'..."
# 需要系统中安装了 gsutil 命令行工具 (通常随 gcloud CLI 一起安装)
if ! command -v gsutil &> /dev/null; then
    handle_error "gsutil 命令行工具未找到。请确保已安装 Google Cloud SDK 并正确配置。"
fi

gsutil cp "${LOCAL_GZ_BACKUP_FILE}" "${GCS_TARGET_PATH}" # set -e 会处理错误
log_message "备份文件成功上传到 GCP Cloud Storage。"

# 6. 清理本地临时备份文件
log_message "正在删除本地临时压缩备份文件 '${LOCAL_GZ_BACKUP_FILE}'..."
rm -f "${LOCAL_GZ_BACKUP_FILE}" # set -e 会处理错误 (如果 rm 失败，但不应轻易失败)
# LOCAL_SQLITE_BACKUP_FILE 已被 gzip 删除或重命名，所以不需要再次删除它
log_message "本地临时文件清理完毕。"

log_message "数据库备份脚本成功执行完毕。"
exit 0

# --- 主逻辑 结束 ---
