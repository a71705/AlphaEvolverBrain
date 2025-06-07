# 导入必要的模块
import requests # 用于发送 HTTP 请求
import time # 用于处理时间相关的操作，如 token 过期和重试间隔
import os # 用于访问环境变量，如 API 凭据
import logging # 用于记录日志信息
from datetime import datetime, timedelta # 用于处理 token 过期时间

# 获取当前模块的日志记录器实例
logger = logging.getLogger(__name__)

# WorldQuant Brain API 的基础 URL (假设)
# 注意：请根据实际的 API 文档替换为正确的 URL
BRAIN_BASE_URL = "https://api.worldquantbrain.com" # 示例 URL
TOKEN_URL = f"{BRAIN_BASE_URL}/auth/token" # 示例认证 URL
SIMULATIONS_URL = f"{BRAIN_BASE_URL}/simulations" # 示例模拟 URL

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

    # === 后续任务中将添加其他与 Brain API 交互的方法 ===
    # 例如: start_simulation, simulation_progress, get_datasets, get_datafields 等
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
