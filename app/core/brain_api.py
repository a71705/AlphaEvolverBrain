# 导入必要的模块
import requests # 用于发送 HTTP 请求
import time # 用于处理时间相关的操作，如 token 过期和重试间隔
import os # 用于访问环境变量，如 API 凭据
import logging # 用于记录日志信息
from datetime import datetime, timedelta # 用于处理 token 过期时间
import pandas as pd # 用于数据处理，特别是将 API 响应转换为 DataFrame
from functools import lru_cache # 用于实现方法调用的缓存机制

# 获取当前模块的日志记录器实例
logger = logging.getLogger(__name__)

# WorldQuant Brain API 的基础 URL (假设)
# 注意：请根据实际的 API 文档替换为正确的 URL
BRAIN_BASE_URL = "https://api.worldquantbrain.com" # 示例 URL
TOKEN_URL = f"{BRAIN_BASE_URL}/auth/token" # 示例认证 URL

# 模拟提交相关的端点
SIMULATIONS_URL = f"{BRAIN_BASE_URL}/simulations" # 用于提交单个或批量模拟

# 模拟进度相关的端点 (模板字符串，需要替换 ID)
# SIMULATION_PROGRESS_URL_TEMPLATE: 获取单个模拟任务进度的 URL 模板。
# 需要将 {simulation_id} 替换为实际的模拟任务 ID。
SIMULATION_PROGRESS_URL_TEMPLATE = f"{BRAIN_BASE_URL}/simulations/{{simulation_id}}"
# MULTISIMULATION_PROGRESS_URL_TEMPLATE: 获取批量模拟任务进度的 URL 模板。
# 需要将 {job_id} 替换为实际的批量任务 ID。
MULTISIMULATION_PROGRESS_URL_TEMPLATE = f"{BRAIN_BASE_URL}/simulations/batch/{{job_id}}" # 或类似的路径，取决于API设计

# 用户信息端点 (在 DEV-005 的测试代码中用到，实际应用中可能不需要或不同)
USER_ME_URL = f"{BRAIN_BASE_URL}/users/me"

# 数据集和数据字段相关的端点
# DATASETS_URL: 获取可用数据集列表的端点。
DATASETS_URL = f"{BRAIN_BASE_URL}/datasets" # 假设的端点路径

# DATAFIELDS_URL: 获取可用数据字段列表的端点。
# 此端点可能支持多种查询参数进行筛选和分页。
DATAFIELDS_URL = f"{BRAIN_BASE_URL}/datafields" # 假设的端点路径

class BrainApiSession:
    """
    封装与 WorldQuant Brain API 交互的会话管理类。
    包括自动认证、token 刷新和请求重试逻辑。
    """
    def __init__(self, email: str = None, password: str = None, max_retries: int = 3, retry_delay: int = 5):
        """
        初始化 BrainApiSession。

        参数:
            email (str, optional): WorldQuant Brain 平台邮箱。如果为 None，则从环境变量 BRAIN_CREDENTIAL_EMAIL 读取。
            password (str, optional): WorldQuant Brain 平台密码。如果为 None，则从环境变量 BRAIN_CREDENTIAL_PASSWORD 读取。
            max_retries (int): API 请求失败时的最大重试次数。
            retry_delay (int): 重试之间的延迟秒数。
        """
        # 初始化 requests 会话，会话对象可以保持 cookie 等信息
        self._session = requests.Session()
        # 从参数或环境变量获取邮箱和密码
        self._email = email or os.environ.get("BRAIN_CREDENTIAL_EMAIL")
        self._password = password or os.environ.get("BRAIN_CREDENTIAL_PASSWORD")

        # 检查是否成功获取凭据
        if not self._email or not self._password:
            logger.error("Brain API 凭据 (邮箱或密码) 未提供。请设置 BRAIN_CREDENTIAL_EMAIL 和 BRAIN_CREDENTIAL_PASSWORD 环境变量或在初始化时传入。")
            # 在这种情况下，可以选择抛出异常，或者让后续的 _authenticate 失败
            # 此处选择让 _authenticate 处理，因为它会在首次需要 token 时被调用

        # 初始化认证 token 和其过期时间
        self._auth_token = None
        # Token 过期时间戳 (Unix timestamp)，0 表示尚未认证或已过期
        self._auth_token_expiry_timestamp = 0
        # Token 的有效期，例如 1 小时 (3600 秒)。API 文档应明确此值。此处假设为 1 小时。
        self._token_lifetime_seconds = 3600
        # 在 token 过期前多少秒进行刷新，例如提前 5 分钟 (300 秒)
        self._token_refresh_buffer_seconds = 300

        self._max_retries = max_retries
        self._retry_delay = retry_delay

    def _authenticate(self) -> bool:
        """
        向 WorldQuant Brain API 进行认证，获取并存储认证 token。

        返回:
            bool: 如果认证成功则返回 True，否则返回 False。

        异常:
            ConnectionError: 如果连接到认证服务器失败。
            ValueError: 如果认证响应无效或缺少必要字段。
        """
        logger.info(f"尝试向 {TOKEN_URL} 进行认证，用户: {self._email}")
        if not self._email or not self._password:
            logger.error("认证失败：邮箱或密码未配置。")
            return False

        try:
            # 构造认证请求的 payload
            payload = {
                "username": self._email, # API 可能使用 'username' 或 'email'
                "password": self._password
            }
            # 发送 POST 请求进行认证
            response = self._session.post(TOKEN_URL, json=payload, timeout=10) # 设置超时
            response.raise_for_status()  # 如果 HTTP 状态码表示错误 (4xx 或 5xx)，则抛出异常

            token_data = response.json()

            # 检查是否为 Persona 认证场景 (根据文档描述，此处为假设)
            # Persona 认证通常意味着用户需要进行额外的操作，API 不会直接返回可用 token
            if token_data.get("type") == "PERSONA_AUTH_REQUIRED" or "persona" in token_data.get("message", "").lower():
                logger.error(f"认证失败：需要 Persona 认证。响应: {token_data.get('message')}")
                # 可以定义一个特定的异常类型
                raise ValueError(f"Persona 认证场景被检测到: {token_data.get('message')}")

            # 从响应中获取 token，具体字段名需要参考 API 文档 (例如 'token', 'access_token')
            self._auth_token = token_data.get("token") or token_data.get("access_token")
            if not self._auth_token:
                logger.error(f"认证失败：响应中未找到 token。响应: {token_data}")
                return False

            # 设置 token 过期时间
            # 假设 API 返回 token 的有效期 (expires_in，单位秒) 或绝对过期时间戳
            expires_in = token_data.get("expires_in", self._token_lifetime_seconds) # 秒
            self._auth_token_expiry_timestamp = time.time() + expires_in

            # 在会话的 headers 中设置认证 token，以便后续请求自动携带
            self._session.headers.update({"Authorization": f"Bearer {self._auth_token}"})
            logger.info("认证成功，Token 已获取并设置。")
            return True

        except requests.exceptions.HTTPError as e:
            # 处理 HTTP 错误，例如 401 Unauthorized
            logger.error(f"认证 API 请求失败 (HTTP {e.response.status_code}): {e.response.text}")
            if e.response.status_code == 401:
                 # 检查是否因为凭据错误
                error_detail = ""
                try:
                    error_detail = e.response.json().get("detail", "")
                except requests.exceptions.JSONDecodeError:
                    error_detail = e.response.text

                if "persona" in error_detail.lower(): # 再次检查 persona 场景
                     logger.error(f"认证失败：需要 Persona 认证。详情: {error_detail}")
                     raise ValueError(f"Persona 认证场景被检测到: {error_detail}")
                else:
                    logger.error(f"认证失败：无效的凭据或未授权。详情: {error_detail}")
            return False
        except requests.exceptions.RequestException as e:
            # 处理其他请求相关的异常，如网络问题
            logger.error(f"认证 API 请求时发生连接错误: {e}")
            raise ConnectionError(f"无法连接到认证服务器 {TOKEN_URL}: {e}") from e
        except (KeyError, ValueError) as e:
            # 处理 JSON 解析错误或响应中缺少关键字段的情况
            logger.error(f"认证响应无效或缺少必要字段: {e}")
            raise ValueError(f"认证响应格式错误: {e}") from e

    def _ensure_authenticated(self) -> None:
        """
        确保当前会话已认证且 token 有效。
        如果 token 不存在、无效或即将过期，则尝试重新认证。
        """
        # 计算当前时间加上一个缓冲时间，用于判断 token 是否即将过期
        current_time_with_buffer = time.time() + self._token_refresh_buffer_seconds

        # 如果 token 不存在或者已过期 (或即将过期)
        if not self._auth_token or current_time_with_buffer >= self._auth_token_expiry_timestamp:
            logger.info("Token 不存在或已过期/即将过期，尝试重新认证...")
            if not self._authenticate():
                # 如果认证失败，可以抛出异常，或者让后续的 API 调用失败
                # 此处选择记录错误，让调用方处理后续的请求失败
                logger.error("重新认证失败。后续 API 调用可能会失败。")
                # raise RuntimeError("无法刷新认证 Token.") # 或者抛出异常

    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        使用当前会话发送 HTTP 请求，并包含认证检查和重试逻辑。

        参数:
            method (str): HTTP 方法 (例如 "GET", "POST")。
            url (str): 请求的 URL。
            **kwargs: 传递给 requests.request 的其他参数 (例如 json, params, data)。

        返回:
            requests.Response: HTTP 响应对象。

        异常:
            requests.exceptions.RequestException: 如果在多次重试后请求仍然失败。
            RuntimeError: 如果认证失败且无法继续。
        """
        self._ensure_authenticated() # 确保在请求前已认证

        # 如果在 _ensure_authenticated 中认证失败且没有抛出异常，_auth_token 可能仍为 None
        if not self._auth_token and "auth/token" not in url: # 避免在认证请求自身时死循环
            logger.error(f"请求 {method} {url} 失败：用户未认证。")
            # 根据策略返回一个模拟的失败响应或抛出异常
            raise RuntimeError("用户未认证，无法执行请求。")


        for attempt in range(self._max_retries + 1):
            try:
                logger.debug(f"发送请求 (尝试 {attempt + 1}/{self._max_retries + 1}): {method} {url}")
                # 确保认证头部是最新的
                if self._auth_token:
                    kwargs.setdefault('headers', {}).update({"Authorization": f"Bearer {self._auth_token}"})

                response = self._session.request(method, url, **kwargs)
                response.raise_for_status()  # 如果 HTTP 状态码是 4xx 或 5xx，则抛出异常
                return response
            except requests.exceptions.HTTPError as e:
                # 如果是 401 Unauthorized 错误，并且不是认证请求本身，则可能是 token 过期
                if e.response.status_code == 401 and "auth/token" not in url:
                    logger.warning(f"请求收到 401 未授权错误，尝试刷新 Token。URL: {url}")
                    # 强制重新认证
                    self._auth_token = None
                    self._auth_token_expiry_timestamp = 0
                    # 清除旧的认证头，以防影响 _authenticate 中的请求
                    if 'Authorization' in self._session.headers:
                        del self._session.headers['Authorization']

                    self._ensure_authenticated() # 这会调用 _authenticate
                    # 如果认证成功，则在下一次循环中重试请求 (如果还有重试次数)
                    if self._auth_token: # 检查认证是否成功
                        logger.info("Token 已刷新，将重试请求。")
                        # 如果是最后一次尝试，则不继续，直接抛出原始异常
                        if attempt == self._max_retries:
                            logger.error(f"Token 刷新后，请求 {method} {url} 达到最大重试次数后仍然失败: {e}")
                            raise
                        time.sleep(self._retry_delay) # 等待一段时间再重试
                        continue # 继续下一次重试
                    else:
                        logger.error(f"Token 刷新失败，无法重试请求 {method} {url}。")
                        raise RuntimeError(f"请求 {method} {url} 因认证失败 (401) 且无法刷新 Token 而失败。") from e

                # 对于其他 HTTP 错误，或者如果是最后一次尝试
                if attempt == self._max_retries:
                    logger.error(f"请求 {method} {url} 在 {self._max_retries + 1} 次尝试后失败 (HTTP {e.response.status_code}): {e.response.text if e.response else e}")
                    raise
                logger.warning(f"请求 {method} {url} 失败 (HTTP {e.response.status_code}): {e.response.text if e.response else e}。将在 {self._retry_delay} 秒后重试...")

            except requests.exceptions.RequestException as e: # 更通用的网络错误
                if attempt == self._max_retries:
                    logger.error(f"请求 {method} {url} 在 {self._max_retries + 1} 次尝试后因连接错误失败: {e}")
                    raise
                logger.warning(f"请求 {method} {url} 发生连接错误: {e}。将在 {self._retry_delay} 秒后重试...")

            time.sleep(self._retry_delay) # 等待一段时间再重试

        raise RuntimeError(f"请求 {method} {url} 在所有重试尝试后均失败。")

    def start_simulation(self, simulate_data: dict or list) -> requests.Response:
        """
        提交一个或多个 Alpha 表达式进行模拟。

        参数:
            simulate_data (dict or list): 包含模拟请求所需数据的字典（用于单个模拟）
                                         或字典列表（用于批量模拟）。
                                         此数据的具体结构取决于 WorldQuant Brain API 的要求。
                                         例如:
                                         单个模拟: {"expression": "close", "settings": {...}}
                                         批量模拟: [{"expression": "close", ...}, {"expression": "open", ...}]

        返回:
            requests.Response: API 返回的原始响应对象。
                               调用者应检查响应的状态码和内容。
                               成功提交模拟后，响应体中通常会包含一个或多个任务 ID (例如 simulation_id, job_id)。

        异常:
            requests.exceptions.RequestException: 如果 API 请求失败且重试耗尽。
            RuntimeError: 如果认证失败。
        """
        # 记录将要提交的数据的类型和简要信息 (例如，如果是列表，则记录列表长度)
        if isinstance(simulate_data, list):
            logger.info(f"准备向 {SIMULATIONS_URL} 提交批量模拟请求，包含 {len(simulate_data)} 个 Alpha。")
        else:
            logger.info(f"准备向 {SIMULATIONS_URL} 提交单个模拟请求。")

        # 记录提交数据的摘要或关键部分 (注意不要记录过多或敏感信息)
        # logger.debug(f"提交的模拟数据 (部分): {str(simulate_data)[:200]}") # 截断避免日志过长

        # 使用 _request_with_retry 方法发送 POST 请求
        # SIMULATIONS_URL 是在模块级别定义的提交模拟的端点
        # json=simulate_data 将 simulate_data 字典或列表序列化为 JSON 并作为请求体发送
        try:
            response = self._request_with_retry("POST", SIMULATIONS_URL, json=simulate_data, timeout=30) # 增加超时时间以应对可能的网络延迟或服务端处理
            logger.info(f"模拟提交请求已发送至 {SIMULATIONS_URL}。响应状态码: {response.status_code}")
            # logger.debug(f"模拟提交响应内容: {response.text}") # 响应内容可能较大，谨慎记录
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"提交模拟请求到 {SIMULATIONS_URL} 失败: {e}")
            raise # 将异常重新抛出，以便上层调用者处理
        except RuntimeError as e:
            logger.error(f"提交模拟请求到 {SIMULATIONS_URL} 因认证问题失败: {e}")
            raise

    def simulation_progress(self, simulation_id: str, polling_interval: int = 5, timeout: int = 300) -> dict:
        """
        轮询单个 Alpha 模拟任务的进度直到完成、失败或超时。

        参数:
            simulation_id (str): 要查询进度的模拟任务的 ID。
                                 通常从 start_simulation 方法的响应中获取。
            polling_interval (int): 轮询 API 的时间间隔（秒）。默认为 5 秒。
            timeout (int): 等待模拟完成的总超时时间（秒）。默认为 300 秒 (5 分钟)。

        返回:
            dict: 一个包含模拟结果或错误信息的字典。
                  成功时，例如: {"status": "COMPLETED", "alpha_json": {...}, "simulation_id": "..."}
                  失败时，例如: {"status": "FAILED", "message": "Error details", "simulation_id": "..."}
                  超时时，例如: {"status": "TIMEOUT", "message": "Simulation polling timed out.", "simulation_id": "..."}
        """
        if not simulation_id:
            logger.error("查询模拟进度失败：simulation_id 不能为空。")
            return {"status": "ERROR", "message": "simulation_id is required.", "simulation_id": simulation_id}

        # 构建特定模拟任务的进度查询 URL
        progress_url = SIMULATION_PROGRESS_URL_TEMPLATE.format(simulation_id=simulation_id)
        logger.info(f"开始轮询模拟任务 {simulation_id} 的进度，URL: {progress_url}，间隔: {polling_interval}s，超时: {timeout}s。")

        start_time = time.time() # 记录开始时间，用于判断超时

        while True:
            current_time = time.time()
            # 检查是否超时
            if current_time - start_time > timeout:
                logger.warning(f"轮询模拟任务 {simulation_id} 超时（超过 {timeout} 秒）。")
                return {"status": "TIMEOUT", "message": f"Simulation {simulation_id} polling timed out after {timeout} seconds.", "simulation_id": simulation_id}

            try:
                logger.debug(f"正在查询模拟任务 {simulation_id} 的进度...")
                response = self._request_with_retry("GET", progress_url, timeout=15) # 设置请求超时

                # 检查响应是否成功 (2xx 状态码已由 _request_with_retry 处理)
                # 现在解析响应内容
                progress_data = response.json()
                # logger.debug(f"模拟任务 {simulation_id} 进度响应: {progress_data}")

                # 从响应中获取模拟状态，状态字段名可能因 API 而异 (例如 "status", "state")
                # 假设状态字段为 "status"
                simulation_status = progress_data.get("status", "").upper() # 转换为大写以便比较

                if simulation_status == "COMPLETED":
                    logger.info(f"模拟任务 {simulation_id} 已成功完成。")
                    # 假设完成时，响应中包含名为 "alpha_json" 或 "result" 的字段包含 Alpha 的详细信息
                    alpha_result = progress_data.get("alpha_json") or progress_data.get("result") or progress_data
                    return {"status": "COMPLETED", "alpha_json": alpha_result, "simulation_id": simulation_id}

                elif simulation_status == "FAILED":
                    logger.error(f"模拟任务 {simulation_id} 执行失败。")
                    # 提取错误信息，特别是 "message" 字段
                    error_message = progress_data.get("message", "Unknown error during simulation.")
                    error_details = progress_data.get("details") # 可能包含更详细的错误信息
                    return {"status": "FAILED", "message": error_message, "details": error_details, "simulation_id": simulation_id}

                elif simulation_status in ["RUNNING", "PENDING", "QUEUED"]:
                    logger.info(f"模拟任务 {simulation_id} 仍在进行中，状态: {simulation_status}。将在 {polling_interval} 秒后再次查询。")

                else: # 未知或非预期的状态
                    logger.warning(f"模拟任务 {simulation_id} 返回未知状态: '{simulation_status}'. 原始响应: {progress_data}")
                    # 可以选择继续轮询或将其视为一种错误
                    # return {"status": "UNKNOWN_STATUS", "message": f"Unknown simulation status: {simulation_status}", "data": progress_data, "simulation_id": simulation_id}

            except requests.exceptions.RequestException as e:
                logger.error(f"查询模拟任务 {simulation_id} 进度时发生请求错误: {e}。将在 {polling_interval} 秒后重试（如果未超时）。")
                # 即使请求失败，也继续轮询，除非超时，因为这可能是暂时的网络问题
            except ValueError as e: # JSON 解析错误
                logger.error(f"解析模拟任务 {simulation_id} 进度响应时发生错误: {e}。响应内容可能不是有效的 JSON。将在 {polling_interval} 秒后重试。")
            except Exception as e: # 其他意外错误
                logger.error(f"查询模拟任务 {simulation_id} 进度时发生意外错误: {e}", exc_info=True)
                # 对于意外错误，可以选择停止轮询并返回错误
                # return {"status": "ERROR", "message": f"Unexpected error polling simulation {simulation_id}: {str(e)}", "simulation_id": simulation_id}


            # 等待指定的轮询间隔
            time.sleep(polling_interval)

    def multisimulation_progress(self, job_id: str, polling_interval: int = 10, timeout: int = 600) -> dict:
        """
        轮询批量 Alpha 模拟任务的进度直到完成、失败或超时。

        参数:
            job_id (str): 要查询进度的批量模拟任务的 ID。
                          通常从 start_simulation 方法（当提交批量数据时）的响应中获取。
            polling_interval (int): 轮询 API 的时间间隔（秒）。默认为 10 秒。
            timeout (int): 等待批量模拟完成的总超时时间（秒）。默认为 600 秒 (10 分钟)。

        返回:
            dict: 一个包含批量模拟结果或错误信息的字典。
                  成功时，例如: {"status": "COMPLETED", "results": [{...}, {...}], "job_id": "..."}
                           (其中 results 是一个包含每个子 Alpha 结果的列表)
                  失败时，例如: {"status": "FAILED", "message": "Error details", "job_id": "..."}
                  超时时，例如: {"status": "TIMEOUT", "message": "Batch simulation polling timed out.", "job_id": "..."}
        """
        if not job_id:
            logger.error("查询批量模拟进度失败：job_id 不能为空。")
            return {"status": "ERROR", "message": "job_id is required.", "job_id": job_id}

        # 构建特定批量模拟任务的进度查询 URL
        progress_url = MULTISIMULATION_PROGRESS_URL_TEMPLATE.format(job_id=job_id)
        logger.info(f"开始轮询批量模拟任务 {job_id} 的进度，URL: {progress_url}，间隔: {polling_interval}s，超时: {timeout}s。")

        start_time = time.time() # 记录开始时间，用于判断超时

        while True:
            current_time = time.time()
            # 检查是否超时
            if current_time - start_time > timeout:
                logger.warning(f"轮询批量模拟任务 {job_id} 超时（超过 {timeout} 秒）。")
                return {"status": "TIMEOUT", "message": f"Batch simulation {job_id} polling timed out after {timeout} seconds.", "job_id": job_id}

            try:
                logger.debug(f"正在查询批量模拟任务 {job_id} 的进度...")
                response = self._request_with_retry("GET", progress_url, timeout=20) # 增加 GET 请求的超时

                progress_data = response.json()
                # logger.debug(f"批量模拟任务 {job_id} 进度响应: {progress_data}")

                # 从响应中获取批量模拟状态
                # 假设状态字段为 "status" 或 "job_status"
                job_status = progress_data.get("status", progress_data.get("job_status", "")).upper()

                if job_status == "COMPLETED":
                    logger.info(f"批量模拟任务 {job_id} 已成功完成。")
                    # 假设完成时，响应中包含名为 "results" 或 "simulations" 的列表，其中包含每个子 Alpha 的结果
                    results_list = progress_data.get("results") or progress_data.get("simulations") or progress_data
                    return {"status": "COMPLETED", "results": results_list, "job_id": job_id}

                elif job_status == "FAILED":
                    logger.error(f"批量模拟任务 {job_id} 执行失败。")
                    error_message = progress_data.get("message", "Unknown error during batch simulation.")
                    error_details = progress_data.get("details")
                    return {"status": "FAILED", "message": error_message, "details": error_details, "job_id": job_id}

                elif job_status in ["RUNNING", "PENDING", "QUEUED", "IN_PROGRESS"]:
                    # API 可能还会提供更详细的进度，例如已完成的子任务数量
                    completed_tasks = progress_data.get("completed_tasks", 0)
                    total_tasks = progress_data.get("total_tasks", 0)
                    progress_percent = progress_data.get("progress_percentage", 0)
                    logger.info(f"批量模拟任务 {job_id} 仍在进行中，状态: {job_status} (已完成: {completed_tasks}/{total_tasks}, 进度: {progress_percent}%). 将在 {polling_interval} 秒后再次查询。")

                else: # 未知或非预期的状态
                    logger.warning(f"批量模拟任务 {job_id} 返回未知状态: '{job_status}'. 原始响应: {progress_data}")
                    # return {"status": "UNKNOWN_STATUS", "message": f"Unknown batch simulation status: {job_status}", "data": progress_data, "job_id": job_id}

            except requests.exceptions.RequestException as e:
                logger.error(f"查询批量模拟任务 {job_id} 进度时发生请求错误: {e}。将在 {polling_interval} 秒后重试（如果未超时）。")
            except ValueError as e: # JSON 解析错误
                logger.error(f"解析批量模拟任务 {job_id} 进度响应时发生错误: {e}。响应内容可能不是有效的 JSON。将在 {polling_interval} 秒后重试。")
            except Exception as e: # 其他意外错误
                logger.error(f"查询批量模拟任务 {job_id} 进度时发生意外错误: {e}", exc_info=True)
                # return {"status": "ERROR", "message": f"Unexpected error polling batch simulation {job_id}: {str(e)}", "job_id": job_id}

            time.sleep(polling_interval)

    @lru_cache(maxsize=1) # 缓存最近一次调用的结果 (基于参数组合)
    def get_datasets(self, instrument_type: str = 'EQUITY', region: str = 'USA', delay: int = 1, universe: str = 'TOP3000') -> pd.DataFrame:
        """
        获取指定条件下的可用数据集列表，并缓存结果。

        参数:
            instrument_type (str): 资产类型 (例如 'EQUITY', 'FUTURES')。默认为 'EQUITY'。
            region (str): 地区 (例如 'USA', 'CHN', 'GLOBAL')。默认为 'USA'。
            delay (int): 数据延迟 (例如 1 代表日频延迟为1的数据)。默认为 1。
            universe (str): 资产池 (例如 'TOP3000', 'RUSSELL1000')。默认为 'TOP3000'。

        返回:
            pd.DataFrame: 包含数据集信息的 Pandas DataFrame。
                          如果获取失败或无数据，则返回空的 DataFrame。
                          DataFrame 的列结构取决于 API 返回的数据。
        """
        logger.info(
            f"开始获取数据集列表: instrument_type='{instrument_type}', region='{region}', delay={delay}, universe='{universe}'"
        )
        # 构建请求参数字典
        params = {
            "instrument_type": instrument_type,
            "region": region,
            "delay": delay,
            "universe": universe
            # API 可能需要其他参数，例如 'page', 'limit'，如果数据集列表也支持分页
            # 但通常数据集列表较短，可能不分页，或 lru_cache(maxsize=1) 暗示我们期望一次获取全部
        }

        try:
            # 使用 _request_with_retry 方法发送 GET 请求
            response = self._request_with_retry("GET", DATASETS_URL, params=params, timeout=20)

            # 假设 API 成功时返回一个 JSON 列表，其中每个对象是一个数据集的信息
            datasets_list = response.json() # 直接获取整个列表，如果API返回结构是 {"results": [...]} 则需调整为 response.json().get("results", [])

            if not datasets_list:
                logger.info("未找到满足条件的数据集，或 API 返回空列表。")
                return pd.DataFrame() # 返回空的 DataFrame

            # 将数据集列表转换为 Pandas DataFrame
            df_datasets = pd.DataFrame(datasets_list)
            logger.info(f"成功获取并转换了 {len(df_datasets)} 个数据集到 DataFrame。")
            return df_datasets

        except requests.exceptions.RequestException as e:
            logger.error(f"获取数据集列表时发生请求错误: {e}")
            return pd.DataFrame() # 返回空的 DataFrame
        except ValueError as e: # JSON 解析错误
            logger.error(f"解析数据集列表响应时发生错误: {e}。响应内容: {response.text if 'response' in locals() else 'N/A'}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"获取数据集列表时发生未预料的错误: {e}", exc_info=True)
            return pd.DataFrame()

    @lru_cache(maxsize=128) # 缓存最近128次不同参数组合调用的结果
    def get_datafields(self, instrument_type: str = 'EQUITY', region: str = 'USA', delay: int = 1,
                       universe: str = 'TOP3000', dataset_id: str = '', search: str = '',
                       page_size: int = 100) -> pd.DataFrame: # page_size 是我们定义的单次请求量
        """
        获取指定条件下的可用数据字段列表，支持分页，并缓存结果。

        参数:
            instrument_type (str): 资产类型。默认为 'EQUITY'。
            region (str): 地区。默认为 'USA'。
            delay (int): 数据延迟。默认为 1。
            universe (str): 资产池。默认为 'TOP3000'。
            dataset_id (str): 特定数据集的 ID (可选)。默认为空字符串。
            search (str): 搜索关键词 (可选, 用于筛选字段名称或描述)。默认为空字符串。
            page_size (int): 每次 API 请求获取的条目数量（如果 API 支持自定义分页大小）。
                             注意：API 可能有其自身的最大分页限制。此参数用于控制我方请求。

        返回:
            pd.DataFrame: 包含数据字段信息的 Pandas DataFrame。
                          如果获取失败或无数据，则返回空的 DataFrame。
        """
        logger.info(
            f"开始获取数据字段列表: instrument_type='{instrument_type}', region='{region}', delay={delay}, "
            f"universe='{universe}', dataset_id='{dataset_id}', search='{search}'"
        )

        all_datafields_list = [] # 用于存储所有分页获取到的数据字段
        current_page = 1 # API 分页通常从1开始，或者使用 offset

        # 构建基础请求参数字典，不包含分页参数
        base_params = {
            "instrument_type": instrument_type,
            "region": region,
            "delay": delay,
            "universe": universe,
        }
        if dataset_id: # 如果提供了 dataset_id，则添加到参数中
            base_params["dataset_id"] = dataset_id
        if search: # 如果提供了 search 关键词，则添加到参数中
            base_params["search"] = search

        while True:
            # 每次循环时，复制基础参数并添加当前页的分页参数
            params = base_params.copy()
            # API 可能使用 'page' 和 'page_size'/'limit', 或者 'offset' 和 'limit'
            # 此处假设使用 'page' 和 'limit' (或 'page_size')
            params["page"] = current_page
            params["limit"] = page_size # 告知 API 我们期望每页获取多少条

            logger.debug(f"正在获取数据字段第 {current_page} 页，参数: {params}")

            try:
                response = self._request_with_retry("GET", DATAFIELDS_URL, params=params, timeout=20)
                response_data = response.json()

                # 从响应中提取当前页的数据字段列表和总数信息
                # API 响应结构可能不同，常见的有:
                # 1. {"results": [...], "count": total_items, "next": "next_page_url", "previous": "..."}
                # 2. {"data": [...], "total": total_items, "page": current, "last_page": ...}
                # 此处假设第一种结构
                current_page_items = response_data.get("results", [])
                total_items = response_data.get("count") # 可选，用于日志或提前判断
                next_page_url = response_data.get("next") # 是否有下一页的直接链接

                if not current_page_items: # 如果当前页没有数据
                    if current_page == 1: # 如果是第一页就没有数据
                        logger.info("未找到满足条件的数据字段，或 API 返回空列表。")
                    else: # 如果不是第一页，说明已经取完了所有数据
                        logger.info(f"已获取所有数据字段，总共 {len(all_datafields_list)} 条。")
                    break # 退出循环

                all_datafields_list.extend(current_page_items)
                logger.info(f"已获取 {len(current_page_items)} 条数据字段 (第 {current_page} 页)。累计: {len(all_datafields_list)} 条。")

                # 判断是否还有下一页
                if next_page_url: # 如果 API 直接提供了下一页的 URL
                    current_page += 1 # 准备请求下一页
                elif total_items is not None: # 如果 API 提供了总数
                    if len(all_datafields_list) >= total_items:
                        logger.info(f"已获取所有 {total_items} 条数据字段。")
                        break # 已获取全部数据
                    else:
                        current_page += 1 # 准备请求下一页
                else: # 如果既没有 next_page_url 也没有 total_items，且当前页有数据，则只能假设还有下一页
                      # 这是一种不太理想的 API 设计，但需要处理。或者，如果当前页数据少于 page_size，也可认为结束。
                    if len(current_page_items) < page_size:
                        logger.info(f"当前页获取的数据条数 ({len(current_page_items)}) 小于请求的页面大小 ({page_size})，认为已获取所有数据。")
                        break
                    else:
                        current_page += 1

                # 防止无限循环的额外检查 (例如，如果API分页逻辑有问题)
                if current_page > 500: # 假设最多500页，避免意外的无限循环
                    logger.warning("获取数据字段时，页数超过500页，可能存在问题，停止获取。")
                    break

            except requests.exceptions.RequestException as e:
                logger.error(f"获取数据字段列表 (第 {current_page} 页) 时发生请求错误: {e}")
                # 发生错误时，可以选择返回已获取的部分数据，或者返回空 DataFrame
                return pd.DataFrame(all_datafields_list) if all_datafields_list else pd.DataFrame()
            except ValueError as e: # JSON 解析错误
                logger.error(f"解析数据字段列表响应 (第 {current_page} 页) 时发生错误: {e}。响应内容: {response.text if 'response' in locals() else 'N/A'}")
                return pd.DataFrame(all_datafields_list) if all_datafields_list else pd.DataFrame()
            except Exception as e:
                logger.error(f"获取数据字段列表 (第 {current_page} 页) 时发生未预料的错误: {e}", exc_info=True)
                return pd.DataFrame(all_datafields_list) if all_datafields_list else pd.DataFrame()

        if not all_datafields_list:
            return pd.DataFrame() # 如果最终列表为空，返回空 DataFrame

        # 将所有获取到的数据字段列表转换为 Pandas DataFrame
        df_datafields = pd.DataFrame(all_datafields_list)
        logger.info(f"成功获取并转换了总共 {len(df_datafields)} 个数据字段到 DataFrame。")
        return df_datafields

    # === 后续任务中将添加其他与 Brain API 交互的方法 ===
    # 这些方法都应该使用 self._request_with_retry 来执行实际的 API 调用

# 示例用法 (用于基本测试，实际测试应使用单元测试框架)
if __name__ == "__main__":
    # 配置基本日志以便在控制台看到输出
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    if not os.environ.get("BRAIN_CREDENTIAL_EMAIL") or not os.environ.get("BRAIN_CREDENTIAL_PASSWORD"):
        print("错误：请设置 BRAIN_CREDENTIAL_EMAIL 和 BRAIN_CREDENTIAL_PASSWORD 环境变量以进行测试。")
    else:
        logger.info("开始 BrainApiSession 示例用法...")
        try:
            brain_session = BrainApiSession()
            USER_ME_URL = f"{BRAIN_BASE_URL}/users/me" # 示例端点
            logger.info(f"尝试调用受保护的端点: {USER_ME_URL}")

            # 模拟一个 GET 请求
            # 注意：真实的 BRAIN_BASE_URL, TOKEN_URL 可能不同，此示例主要用于流程演示
            # 如果 TOKEN_URL 和 BRAIN_BASE_URL 指向无法访问或行为不符的地址，此处会失败
            user_info_response = brain_session._request_with_retry("GET", USER_ME_URL, timeout=10)

            logger.info(f"获取用户信息响应状态: {user_info_response.status_code}")
            logger.info(f"获取用户信息响应内容: {user_info_response.text}")

        except ConnectionError as e:
            logger.error(f"示例用法中发生连接错误: {e}")
        except ValueError as e:
            logger.error(f"示例用法中发生值错误: {e}")
        except RuntimeError as e:
            logger.error(f"示例用法中发生运行时错误: {e}")
        except Exception as e:
            logger.error(f"示例用法中发生未预料的错误: {e}", exc_info=True)

        logger.info("BrainApiSession 示例用法结束。")
