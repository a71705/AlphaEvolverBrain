# app/core/brain_api.py
# 导入必要的模块
import requests  # 用于发送 HTTP 请求
import time      # 用于处理时间相关的操作，如 token 过期
import os        # 用于访问环境变量
import logging   # 用于日志记录
from datetime import datetime, timedelta # 用于处理 token 过期时间
from typing import Union, List, Dict, Any # 用于类型注解

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
    SIMULATIONS_ENDPOINT = "/simulations"  # 端点用于提交模拟
    # 假设单个模拟状态端点格式，实际需WQB API文档确认
    SIMULATION_PROGRESS_ENDPOINT = "/simulations/{simulation_id}/progress"
    # 假设批量模拟状态端点格式，实际需WQB API文档确认
    MULTISIMULATION_PROGRESS_ENDPOINT = "/multisimulations/{multisimulation_id}/progress"

    # Token 过期前的缓冲时间 (秒)，例如提前5分钟刷新
    TOKEN_EXPIRY_BUFFER = 300

    # 轮询参数
    DEFAULT_POLLING_INTERVAL_SECONDS = 10  # 默认轮询间隔
    DEFAULT_POLLING_TIMEOUT_SECONDS = 600   # 默认轮询超时时间 (10分钟)


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
                logger.warning(f"请求失败 (HTTP {e.response.status_code}) (尝试 {attempt + 1}): {method} {url}. 响应: {e.response.text}")
                last_exception = e
                if e.response.status_code in [401, 403]:
                    logger.info("检测到 401/403 错误，尝试强制刷新 token 并重试一次...")
                    try:
                        self._authenticate()
                        if attempt < retries:
                            time.sleep(1)
                            continue
                    except AuthenticationError:
                        logger.error("强制刷新 token 失败，不再重试此请求。")
                        raise

                if attempt < retries:
                    logger.info(f"将在 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"所有重试均失败 ({method} {url})。最后一次 HTTP 错误: {e.response.status_code}")
                    raise

            except requests.exceptions.RequestException as e:
                logger.warning(f"请求发生网络错误 (尝试 {attempt + 1}): {method} {url}. 错误: {e}")
                last_exception = e
                if attempt < retries:
                    logger.info(f"将在 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"所有重试均失败 ({method} {url})。最后一次网络错误: {e}")
                    raise

        if last_exception:
             raise last_exception
        raise requests.exceptions.RequestException(f"请求 {method} {url} 在 {retries} 次重试后失败，但未捕获到具体异常。")

    def start_simulation(self, simulate_data: Union[dict, list]) -> Dict[str, Any]:
        """
        提交 Alpha 模拟请求到 WorldQuant Brain API。

        Args:
            simulate_data (Union[dict, list]): 单个模拟的配置字典或多个模拟配置的列表。
                                              具体结构需参照 WQB API 文档。

        Returns:
            Dict[str, Any]: API 响应解析后的 JSON 对象，通常包含一个任务 ID
                            (例如 'simulation_id' 或 'job_id') 用于后续查询进度。
                            如果 API 直接返回错误，也会在此阶段捕获并可能重新抛出或返回错误结构。

        Raises:
            requests.exceptions.RequestException: 如果 API 请求在重试后仍然失败。
            AuthenticationError: 如果认证失败。
        """
        url = f"{self.BASE_URL}{self.SIMULATIONS_ENDPOINT}"
        logger.info(f"向 {url} 提交模拟请求...")
        logger.debug(f"模拟请求数据: {simulate_data}")

        try:
            response = self._request_with_retry("POST", url, json=simulate_data)
            response_data = response.json()
            logger.info(f"模拟请求提交成功。响应: {response_data}")

            if not response_data.get("simulation_id") and not response_data.get("job_id"):
                 logger.warning(f"模拟提交响应中未找到预期的 'simulation_id' 或 'job_id'。响应: {response_data}")

            return response_data

        except requests.exceptions.HTTPError as e:
            logger.error(f"提交模拟请求失败 (HTTP {e.response.status_code})。URL: {url}。响应: {e.response.text}")
            return {
                "error": True,
                "status_code": e.response.status_code,
                "message": f"提交模拟失败: HTTP {e.response.status_code}",
                "details": e.response.text
            }
        except Exception as e:
            logger.error(f"提交模拟请求时发生严重错误。URL: {url}。错误: {e}")
            return {
                "error": True,
                "message": f"提交模拟时发生严重错误: {str(e)}",
                "details": str(e)
            }

    def _poll_progress(self, progress_url: str, job_type: str = "模拟") -> Dict[str, Any]:
        """
        内部辅助函数，用于轮询指定 URL 的任务进度。

        Args:
            progress_url (str): 用于查询进度的完整 URL。
            job_type (str): 任务类型描述，用于日志。

        Returns:
            Dict[str, Any]: 最终的模拟结果 JSON，或者包含错误信息的字典。
        """
        start_time = time.time()
        logger.info(f"开始轮询 {job_type} 进度: {progress_url}")

        while True:
            current_time = time.time()
            if (current_time - start_time) > self.DEFAULT_POLLING_TIMEOUT_SECONDS:
                logger.error(f"{job_type} 轮询超时 ({self.DEFAULT_POLLING_TIMEOUT_SECONDS}秒): {progress_url}")
                return {"error": True, "message": f"{job_type} 轮询超时。", "url": progress_url}

            try:
                logger.debug(f"查询 {job_type} 进度: {progress_url}")
                response = self._request_with_retry("GET", progress_url)
                status_data = response.json()
                logger.debug(f"{job_type} 状态响应: {status_data}")

                current_status = status_data.get("status", "").upper()

                if current_status in ["COMPLETED", "SUCCESS"]:
                    logger.info(f"{job_type} 完成: {progress_url}")
                    return status_data
                elif current_status in ["FAILED", "ERROR"]:
                    error_message = status_data.get("message", "未知错误")
                    error_details = status_data.get("details", status_data)
                    logger.error(f"{job_type} 失败: {progress_url}。消息: {error_message}。详情: {error_details}")
                    return {"error": True, "message": error_message, "details": error_details, "status": current_status}
                elif current_status in ["PENDING", "RUNNING", "IN_PROGRESS"]:
                    logger.info(f"{job_type} 仍在进行中 ({current_status})，将在 {self.DEFAULT_POLLING_INTERVAL_SECONDS} 秒后再次查询: {progress_url}")
                    time.sleep(self.DEFAULT_POLLING_INTERVAL_SECONDS)
                else:
                    logger.warning(f"收到未知的 {job_type} 状态 '{current_status}' 或状态字段缺失: {progress_url}。响应: {status_data}")
                    time.sleep(self.DEFAULT_POLLING_INTERVAL_SECONDS)

            except requests.exceptions.HTTPError as e:
                logger.error(f"查询 {job_type} 进度时发生 HTTP 错误 (HTTP {e.response.status_code}): {progress_url}。响应: {e.response.text}")
                if e.response.status_code == 404:
                    return {"error": True, "message": f"{job_type} ID 未找到或无效 (HTTP 404)。", "url": progress_url}
                time.sleep(self.DEFAULT_POLLING_INTERVAL_SECONDS)

            except Exception as e:
                logger.error(f"查询 {job_type} 进度时发生严重错误: {progress_url}。错误: {e}")
                return {"error": True, "message": f"查询 {job_type} 进度时发生严重错误: {str(e)}", "details": str(e)}


    def simulation_progress(self, simulation_id: str) -> Dict[str, Any]:
        """
        轮询单个 Alpha 模拟的进度，直到完成或失败。

        Args:
            simulation_id (str): 通过 start_simulation 返回的模拟任务 ID。

        Returns:
            Dict[str, Any]: 最终的模拟结果 JSON (如果成功)，或者包含错误信息的字典。
        """
        progress_url = f"{self.BASE_URL}{self.SIMULATION_PROGRESS_ENDPOINT.format(simulation_id=simulation_id)}"
        return self._poll_progress(progress_url, job_type=f"单个模拟({simulation_id})")


    def multisimulation_progress(self, multisimulation_id: str) -> Dict[str, Any]:
        """
        轮询批量 Alpha 模拟的进度，直到完成或失败。

        Args:
            multisimulation_id (str): 通过 start_simulation (提交批量任务时) 返回的主任务 ID。

        Returns:
            Dict[str, Any]: 包含所有子 Alpha 结果的列表 (如果成功)，
                            或者包含错误信息的字典。
        """
        progress_url = f"{self.BASE_URL}{self.MULTISIMULATION_PROGRESS_ENDPOINT.format(multisimulation_id=multisimulation_id)}"
        return self._poll_progress(progress_url, job_type=f"批量模拟({multisimulation_id})")

# 示例用法 (主要用于测试，实际应用中会由其他模块调用)
if __name__ == "__main__":
    # 配置基本日志以便在测试时看到输出
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 从环境变量获取凭据 (确保已设置)
    test_email = os.environ.get("BRAIN_CREDENTIAL_EMAIL")
    test_password = os.environ.get("BRAIN_CREDENTIAL_PASSWORD")
    session = None # 初始化 session 变量

    if not test_email or not test_password:
        print("请设置 BRAIN_CREDENTIAL_EMAIL 和 BRAIN_CREDENTIAL_PASSWORD 环境变量以进行测试。")
    else:
        try:
            logger.info("开始 BrainApiSession 测试...")
            # 1. 初始化并认证
            session = BrainApiSession(email=test_email, password=test_password)
            logger.info("BrainApiSession 初始化成功。")

            # 2. 测试一个需要认证的 GET 请求 (假设的端点)
            test_api_url = f"{BrainApiSession.BASE_URL}/user/profile"
            try:
                logger.info(f"尝试使用 session 发送 GET 请求到 {test_api_url}...")
                profile_response = session._request_with_retry("GET", test_api_url)
                logger.info(f"获取用户 profile 成功。状态码: {profile_response.status_code}")
                logger.info(f"响应内容: {profile_response.json()}")
            except Exception as e:
                logger.error(f"请求用户 profile 失败: {e}")

            # 3. 测试 token 刷新 (手动模拟 token 过期)
            logger.info("模拟 token 过期测试...")
            session._auth_token_expiry_time = time.time() - 1
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

        if session: # 确保 session 初始化成功再进行后续测试
            # 4. 测试模拟提交 (使用假设的简单数据和端点)
            single_sim_data = {
                "alpha_expression": "rank(close)",
                "settings": {"universe": "TOP3000", "delay": 1, "region": "USA"}
            }
            # multi_sim_data = [ # 取消注释以测试 (如果API和逻辑支持)
            #     {"alpha_expression": "rank(open)", "settings": {"universe": "TOP3000"}},
            #     {"alpha_expression": "ts_rank(vwap, 20)", "settings": {"universe": "TOP3000"}}
            # ]

            logger.info("\n--- 测试单个模拟提交流程 ---")
            try:
                sim_submission_response = session.start_simulation(single_sim_data)
                if sim_submission_response and not sim_submission_response.get("error"):
                    submission_id = sim_submission_response.get("simulation_id") or sim_submission_response.get("job_id")
                    if submission_id:
                        logger.info(f"单个模拟提交成功，ID: {submission_id}。开始轮询进度...")
                        logger.warning("模拟轮询部分在离线测试中无法完全执行，仅测试提交和模拟轮询调用结构。")
                        # progress_result = session.simulation_progress(submission_id) # 实际调用
                        # logger.info(f"单个模拟轮询结果: {progress_result}")
                    else:
                        logger.error(f"单个模拟提交响应中未找到 simulation_id 或 job_id: {sim_submission_response}")
                else:
                    logger.error(f"单个模拟提交失败: {sim_submission_response}")
            except Exception as e:
                logger.error(f"测试单个模拟提交时发生错误: {e}", exc_info=True)

            # 批量模拟提交示例 (假设API支持列表形式提交到同一端点)
            # logger.info("\n--- 测试批量模拟提交流程 ---")
            # try:
            #     multi_sim_response = session.start_simulation(multi_sim_data)
            #     if multi_sim_response and not multi_sim_response.get("error"):
            #         multisim_id = multi_sim_response.get("multisimulation_id") # 或 "job_id"
            #         if multisim_id:
            #             logger.info(f"批量模拟提交成功，ID: {multisim_id}。开始轮询进度...")
            #             logger.warning("批量模拟轮询部分在离线测试中无法完全执行，仅测试提交和模拟轮询调用结构。")
            #             # multi_progress_result = session.multisimulation_progress(multisim_id) # 实际调用
            #             # logger.info(f"批量模拟轮询结果: {multi_progress_result}")
            #         else:
            #             logger.error(f"批量模拟提交响应中未找到 multisimulation_id: {multi_sim_response}")
            #     else:
            #         logger.error(f"批量模拟提交失败: {multi_sim_response}")
            # except Exception as e:
            #     logger.error(f"测试批量模拟提交时发生错误: {e}", exc_info=True)

        logger.info("BrainApiSession 测试结束。")
