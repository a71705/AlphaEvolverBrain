# app/core/brain_api.py
# 导入必要的模块
import requests  # 用于发送 HTTP 请求
import time      # 用于处理时间相关的操作，如 token 过期
import os        # 用于访问环境变量
import logging   # 用于日志记录
from datetime import datetime, timedelta # 用于处理 token 过期时间

# 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

# 定义自定义异常，用于特定的错误场景
class AuthenticationError(Exception):
    """自定义异常，表示认证失败。"""
    pass

class PersonaLoginError(AuthenticationError):
    """自定义异常，表示检测到 Persona 登录，这通常不被允许用于 API 访问。"""
    pass

class BrainApiSession:
    """
    管理与 WorldQuant Brain API 的会话，包括认证、token 刷新和 API 请求。
    """
    # API 端点常量 (这些是基于通用实践的假设，实际值需要查阅 WQB API 文档)
    BASE_URL = "https://api.worldquantbrain.com" # 假设的基础 URL
    AUTH_ENDPOINT = "/authentication" # 假设的认证端点
    # 可以根据实际 API 文档添加其他端点

    # Token 过期前的缓冲时间 (秒)，例如提前5分钟刷新
    TOKEN_EXPIRY_BUFFER = 300

    def __init__(self, email: str = None, password: str = None):
        """
        初始化 BrainApiSession。

        Args:
            email (str, optional): 用户邮箱。如果未提供，则从环境变量 BRAIN_CREDENTIAL_EMAIL 读取。
            password (str, optional): 用户密码。如果未提供，则从环境变量 BRAIN_CREDENTIAL_PASSWORD 读取。
        """
        self._session = requests.Session()  # 创建一个持久的 requests session
        # 从参数或环境变量获取凭据
        self._email = email or os.environ.get("BRAIN_CREDENTIAL_EMAIL")
        self._password = password or os.environ.get("BRAIN_CREDENTIAL_PASSWORD")

        if not self._email or not self._password:
            logger.error("Brain API 邮箱或密码未提供。请设置 BRAIN_CREDENTIAL_EMAIL 和 BRAIN_CREDENTIAL_PASSWORD 环境变量或在初始化时传入。")
            raise ValueError("Brain API 邮箱或密码未提供。")

        self._auth_token = None  # API认证token
        self._auth_token_expiry_time = time.time()  # Token 过期的时间戳 (秒)

        # 可以在 session headers 中设置通用的内容，例如 User-Agent
        self._session.headers.update({
            "User-Agent": "WorldQuantBrainEvolutionSystemClient/1.0",
            "Content-Type": "application/json"
        })

        try:
            self._authenticate()  # 初始化时立即进行认证
        except Exception as e:
            logger.error(f"BrainApiSession 初始化认证失败: {e}")
            # 根据策略，这里可以选择重新抛出异常，或者允许实例创建但处于未认证状态
            raise

    def _authenticate(self):
        """
        执行认证流程，获取 API token。
        """
        auth_url = f"{self.BASE_URL}{self.AUTH_ENDPOINT}"
        payload = {
            "email": self._email,
            "password": self._password
            # WQB API 可能需要其他认证参数，如 'grant_type', 'client_id', 等
            # "grant_type": "password" # 示例
        }

        logger.info(f"尝试向 {auth_url} 进行认证，用户: {self._email}")

        try:
            response = self._session.post(auth_url, json=payload)
            response.raise_for_status()  # 如果 HTTP 状态码是 4xx 或 5xx，则抛出 HTTPError

            response_data = response.json()

            # ---- 开始：处理 Persona 登录场景 ----
            # 此处的逻辑需要根据 WQB API 对于 Persona 登录的实际响应来确定
            # 假设：如果响应中包含某个特定字段或消息，则判断为 Persona 登录
            # 例如，如果 API 在 Persona 登录时返回特定的错误码或消息
            if response_data.get("is_persona_login"): # 这是一个假设的字段
                logger.error(f"检测到 Persona 登录尝试，用户: {self._email}。Persona 登录通常不允许用于 API 访问。")
                raise PersonaLoginError("不允许使用 Persona 凭据进行 API 认证。请使用普通用户凭据。")
            # ---- 结束：处理 Persona 登录场景 ----

            # 从响应中提取 token 和过期信息
            # 这些字段名 ('access_token', 'expires_in', 'token_type') 是 OAuth2 通用字段，实际可能不同
            self._auth_token = response_data.get("access_token")
            expires_in = response_data.get("expires_in") # 通常是秒数
            token_type = response_data.get("token_type", "Bearer") #默认为 Bearer Token

            if not self._auth_token or expires_in is None:
                logger.error(f"认证响应中缺少 token 或过期信息。响应: {response_data}")
                raise AuthenticationError("认证响应无效：缺少 token 或过期信息。")

            # 计算 token 的绝对过期时间戳
            self._auth_token_expiry_time = time.time() + int(expires_in)

            # 更新 session 的 Authorization header
            self._session.headers.update({"Authorization": f"{token_type} {self._auth_token}"})

            logger.info(f"用户 {self._email} 认证成功。Token 将在 {datetime.fromtimestamp(self._auth_token_expiry_time).isoformat()} 到期。")

        except requests.exceptions.HTTPError as e:
            logger.error(f"认证 API 请求失败 (HTTP {e.response.status_code})，用户: {self._email}。响应: {e.response.text}")
            # 可以根据状态码细化错误处理
            if e.response.status_code == 401 or e.response.status_code == 403:
                raise AuthenticationError(f"认证失败：无效的凭据或权限不足 (HTTP {e.response.status_code})。")
            else:
                raise AuthenticationError(f"认证 API 请求遇到服务器错误 (HTTP {e.response.status_code})。")
        except requests.exceptions.RequestException as e:
            logger.error(f"认证 API 请求期间发生网络或连接错误: {e}")
            raise AuthenticationError(f"认证网络错误: {e}")
        except Exception as e: # 捕获其他潜在错误，如 JSON 解析错误
            logger.error(f"认证过程中发生未知错误: {e}")
            raise AuthenticationError(f"认证时发生未知错误: {e}")


    def _ensure_authenticated(self):
        """
        确保当前会话已认证且 token 有效。如果 token 即将过期或无效，则重新认证。
        """
        # 检查 token 是否存在，以及是否在缓冲期之前到期
        if not self._auth_token or (time.time() >= (self._auth_token_expiry_time - self.TOKEN_EXPIRY_BUFFER)):
            logger.info("Token 无效或即将过期，尝试重新认证...")
            try:
                self._authenticate()
            except AuthenticationError: # 如果重新认证失败，则向上抛出异常
                logger.error("重新认证失败。")
                raise
            except Exception as e:
                 logger.error(f"重新认证过程中发生未知错误: {e}")
                 raise AuthenticationError(f"重新认证时发生未知错误: {e}")


    def _request_with_retry(self, method: str, url: str, retries: int = 3, retry_delay: int = 5, **kwargs) -> requests.Response:
        """
        发送 HTTP 请求，并在失败时自动重试。在请求前确保已认证。

        Args:
            method (str): HTTP 方法 (例如 "GET", "POST").
            url (str): 请求的完整 URL.
            retries (int): 最大重试次数.
            retry_delay (int): 重试间的等待秒数.
            **kwargs: 其他传递给 requests 方法的参数 (例如 json, data, params).

        Returns:
            requests.Response: HTTP 响应对象.

        Raises:
            AuthenticationError: 如果认证或刷新失败。
            requests.exceptions.RequestException: 如果所有重试都失败后，仍然存在网络或请求错误。
        """
        self._ensure_authenticated() # 确保在每次请求前 token 有效

        last_exception = None
        for attempt in range(retries + 1): # 包括初次尝试
            try:
                logger.debug(f"发送请求 (尝试 {attempt + 1}/{retries + 1}): {method} {url}")
                response = self._session.request(method, url, **kwargs)
                response.raise_for_status() # 检查 HTTP 错误状态码
                logger.debug(f"请求成功: {method} {url} - 状态码 {response.status_code}")
                return response  # 成功则返回响应

            except requests.exceptions.HTTPError as e: # HTTP 错误 (4xx, 5xx)
                # 对于某些可重试的 HTTP 错误 (例如 502, 503, 504), 可以选择重试
                # 对于客户端错误 (4xx，特别是 401/403 可能是 token 问题)，可能不需要重试或需要特殊处理
                logger.warning(f"请求失败 (HTTP {e.response.status_code}) (尝试 {attempt + 1}): {method} {url}. 响应: {e.response.text}")
                last_exception = e
                if e.response.status_code in [401, 403]: # 未授权或禁止访问，可能 token 失效
                    logger.info("检测到 401/403 错误，尝试强制刷新 token 并重试一次...")
                    try:
                        self._authenticate() # 尝试强制刷新 token
                        # 如果上面认证成功，应该会更新 session header，下一次循环会用新 token
                        if attempt < retries: # 避免在最后一次尝试后还延迟
                            time.sleep(1) # 短暂等待后立即重试
                            continue # 跳过下面的 retry_delay
                    except AuthenticationError:
                        logger.error("强制刷新 token 失败，不再重试此请求。")
                        raise # 重新抛出认证错误

                if attempt < retries:
                    logger.info(f"将在 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"所有重试均失败 ({method} {url})。最后一次 HTTP 错误: {e.response.status_code}")
                    raise # 达到最大重试次数，抛出最后一次的 HTTPError

            except requests.exceptions.RequestException as e: # 其他网络错误 (超时，连接错误等)
                logger.warning(f"请求发生网络错误 (尝试 {attempt + 1}): {method} {url}. 错误: {e}")
                last_exception = e
                if attempt < retries:
                    logger.info(f"将在 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"所有重试均失败 ({method} {url})。最后一次网络错误: {e}")
                    raise # 达到最大重试次数，抛出最后一次的 RequestException

        # 此处理论上不应到达，因为成功或异常抛出应已发生
        if last_exception: # 以防万一
             raise last_exception
        # 如果循环结束且没有异常（不太可能），则抛出一个通用错误
        raise requests.exceptions.RequestException(f"请求 {method} {url} 在 {retries} 次重试后失败，但未捕获到具体异常。")

# 示例用法 (主要用于测试，实际应用中会由其他模块调用)
if __name__ == "__main__":
    # 配置基本日志以便在测试时看到输出
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 从环境变量获取凭据 (确保已设置)
    test_email = os.environ.get("BRAIN_CREDENTIAL_EMAIL")
    test_password = os.environ.get("BRAIN_CREDENTIAL_PASSWORD")

    if not test_email or not test_password:
        print("请设置 BRAIN_CREDENTIAL_EMAIL 和 BRAIN_CREDENTIAL_PASSWORD 环境变量以进行测试。")
    else:
        try:
            logger.info("开始 BrainApiSession 测试...")
            # 1. 初始化并认证
            session = BrainApiSession(email=test_email, password=test_password)
            logger.info("BrainApiSession 初始化成功。")

            # 2. 测试一个需要认证的 GET 请求 (假设的端点)
            # 注意：以下端点是虚构的，你需要替换为 WQB API 的实际有效端点
            test_api_url = f"{BrainApiSession.BASE_URL}/user/profile" # 假设的用户信息端点
            try:
                logger.info(f"尝试使用 session 发送 GET 请求到 {test_api_url}...")
                # 确保 _request_with_retry 是实例方法，通过 session 实例调用
                profile_response = session._request_with_retry("GET", test_api_url)
                logger.info(f"获取用户 profile 成功。状态码: {profile_response.status_code}")
                logger.info(f"响应内容: {profile_response.json()}")
            except Exception as e:
                logger.error(f"请求用户 profile 失败: {e}")

            # 3. 测试 token 刷新 (手动模拟 token 过期)
            logger.info("模拟 token 过期测试...")
            session._auth_token_expiry_time = time.time() - 1 # 将 token 设置为已过期
            try:
                logger.info(f"再次尝试使用 session 发送 GET 请求到 {test_api_url} (应触发 token 刷新)...")
                profile_response_after_refresh = session._request_with_retry("GET", test_api_url)
                logger.info(f"Token 刷新后获取用户 profile 成功。状态码: {profile_response_after_refresh.status_code}")
                logger.info(f"响应内容: {profile_response_after_refresh.json()}")
            except Exception as e:
                logger.error(f"Token 刷新后请求用户 profile 失败: {e}")

        except AuthenticationError as e:
            logger.error(f"BrainApiSession 测试认证失败: {e}")
        except ValueError as e:
             logger.error(f"BrainApiSession 测试值错误: {e}")
        except Exception as e:
            logger.error(f"BrainApiSession 测试期间发生未知错误: {e}", exc_info=True)
        finally:
            logger.info("BrainApiSession 测试结束。")
