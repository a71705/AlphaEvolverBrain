# app/core/brain_api.py
# 导入必要的模块
import requests  # 用于发送 HTTP 请求
import time      # 用于处理时间相关的操作，如 token 过期
import os        # 用于访问环境变量
import logging   # 用于日志记录
from datetime import datetime, timedelta # 用于处理 token 过期时间
from typing import Union, List, Dict, Any # 用于类型注解
from functools import lru_cache # 用于缓存方法结果
import pandas as pd # 用于将数据转换为DataFrame

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
    # API 端点常量
    BASE_URL = "https://api.worldquantbrain.com"
    AUTH_ENDPOINT = "/authentication"
    SIMULATIONS_ENDPOINT = "/simulations"
    SIMULATION_PROGRESS_ENDPOINT = "/simulations/{simulation_id}/progress"
    MULTISIMULATION_PROGRESS_ENDPOINT = "/multisimulations/{multisimulation_id}/progress"
    DATAFIELDS_ENDPOINT = "/datafields"  # 假设的数据字段端点
    DATASETS_ENDPOINT = "/datasets"    # 假设的数据集端点
    API_PAGE_SIZE = 100               # 假设API分页时每页的项目数

    # Token 过期前的缓冲时间 (秒)
    TOKEN_EXPIRY_BUFFER = 300

    # 轮询参数
    DEFAULT_POLLING_INTERVAL_SECONDS = 10
    DEFAULT_POLLING_TIMEOUT_SECONDS = 600

    def __init__(self, email: str = None, password: str = None):
        self._session = requests.Session()
        self._email = email or os.environ.get("BRAIN_CREDENTIAL_EMAIL")
        self._password = password or os.environ.get("BRAIN_CREDENTIAL_PASSWORD")

        if not self._email or not self._password:
            logger.error("Brain API 邮箱或密码未提供。请设置 BRAIN_CREDENTIAL_EMAIL 和 BRAIN_CREDENTIAL_PASSWORD 环境变量或在初始化时传入。")
            raise ValueError("Brain API 邮箱或密码未提供。")

        self._auth_token = None
        self._auth_token_expiry_time = time.time()

        self._session.headers.update({
            "User-Agent": "WorldQuantBrainEvolutionSystemClient/1.0",
            "Content-Type": "application/json"
        })

        try:
            self._authenticate()
        except Exception as e:
            logger.error(f"BrainApiSession 初始化认证失败: {e}")
            raise

    def _authenticate(self):
        auth_url = f"{self.BASE_URL}{self.AUTH_ENDPOINT}"
        payload = {"email": self._email, "password": self._password}
        logger.info(f"尝试向 {auth_url} 进行认证，用户: {self._email}")
        try:
            response = self._session.post(auth_url, json=payload)
            response.raise_for_status()
            response_data = response.json()
            if response_data.get("is_persona_login"):
                logger.error(f"检测到 Persona 登录尝试，用户: {self._email}。")
                raise PersonaLoginError("不允许使用 Persona 凭据进行 API 认证。")
            self._auth_token = response_data.get("access_token")
            expires_in = response_data.get("expires_in")
            token_type = response_data.get("token_type", "Bearer")
            if not self._auth_token or expires_in is None:
                logger.error(f"认证响应中缺少 token 或过期信息。响应: {response_data}")
                raise AuthenticationError("认证响应无效：缺少 token 或过期信息。")
            self._auth_token_expiry_time = time.time() + int(expires_in)
            self._session.headers.update({"Authorization": f"{token_type} {self._auth_token}"})
            logger.info(f"用户 {self._email} 认证成功。Token 将在 {datetime.fromtimestamp(self._auth_token_expiry_time).isoformat()} 到期。")
        except requests.exceptions.HTTPError as e:
            logger.error(f"认证 API 请求失败 (HTTP {e.response.status_code})，用户: {self._email}。响应: {e.response.text}")
            if e.response.status_code in [401, 403]:
                raise AuthenticationError(f"认证失败：无效的凭据或权限不足 (HTTP {e.response.status_code})。")
            else:
                raise AuthenticationError(f"认证 API 请求遇到服务器错误 (HTTP {e.response.status_code})。")
        except requests.exceptions.RequestException as e:
            logger.error(f"认证 API 请求期间发生网络或连接错误: {e}")
            raise AuthenticationError(f"认证网络错误: {e}")
        except Exception as e:
            logger.error(f"认证过程中发生未知错误: {e}")
            raise AuthenticationError(f"认证时发生未知错误: {e}")

    def _ensure_authenticated(self):
        if not self._auth_token or (time.time() >= (self._auth_token_expiry_time - self.TOKEN_EXPIRY_BUFFER)):
            logger.info("Token 无效或即将过期，尝试重新认证...")
            try:
                self._authenticate()
            except AuthenticationError:
                logger.error("重新认证失败。")
                raise
            except Exception as e:
                 logger.error(f"重新认证过程中发生未知错误: {e}")
                 raise AuthenticationError(f"重新认证时发生未知错误: {e}")

    def _request_with_retry(self, method: str, url: str, retries: int = 3, retry_delay: int = 5, **kwargs) -> requests.Response:
        self._ensure_authenticated()
        last_exception = None
        for attempt in range(retries + 1):
            try:
                logger.debug(f"发送请求 (尝试 {attempt + 1}/{retries + 1}): {method} {url}")
                response = self._session.request(method, url, **kwargs)
                response.raise_for_status()
                logger.debug(f"请求成功: {method} {url} - 状态码 {response.status_code}")
                return response
            except requests.exceptions.HTTPError as e:
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
            return {"error": True, "status_code": e.response.status_code, "message": f"提交模拟失败: HTTP {e.response.status_code}", "details": e.response.text}
        except Exception as e:
            logger.error(f"提交模拟请求时发生严重错误。URL: {url}。错误: {e}")
            return {"error": True, "message": f"提交模拟时发生严重错误: {str(e)}", "details": str(e)}

    def _poll_progress(self, progress_url: str, job_type: str = "模拟") -> Dict[str, Any]:
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
        progress_url = f"{self.BASE_URL}{self.SIMULATION_PROGRESS_ENDPOINT.format(simulation_id=simulation_id)}"
        return self._poll_progress(progress_url, job_type=f"单个模拟({simulation_id})")

    def multisimulation_progress(self, multisimulation_id: str) -> Dict[str, Any]:
        progress_url = f"{self.BASE_URL}{self.MULTISIMULATION_PROGRESS_ENDPOINT.format(multisimulation_id=multisimulation_id)}"
        return self._poll_progress(progress_url, job_type=f"批量模拟({multisimulation_id})")

    @lru_cache(maxsize=128)
    def get_datafields(self, instrument_type: str = 'EQUITY', region: str = 'USA', delay: int = 1, universe: str = 'TOP3000', dataset_id: str = '', search: str = '') -> pd.DataFrame:
        logger.info(f"获取数据字段: instrument_type={instrument_type}, region={region}, delay={delay}, universe={universe}, dataset_id='{dataset_id}', search='{search}'")
        all_datafields = []
        current_offset = 0
        total_count = None
        params = {
            "instrument_type": instrument_type, "region": region, "delay": delay,
            "universe": universe, "dataset_id": dataset_id, "search": search,
            "limit": self.API_PAGE_SIZE, "offset": current_offset
        }
        while True:
            try:
                url = f"{self.BASE_URL}{self.DATAFIELDS_ENDPOINT}"
                logger.debug(f"请求数据字段，URL: {url}, 参数: {params}")
                response = self._request_with_retry("GET", url, params=params)
                response_data = response.json()
                results = response_data.get("results", [])
                if not isinstance(results, list):
                    logger.error(f"获取数据字段时，API返回的 'results' 不是列表: {results}")
                    return pd.DataFrame()
                all_datafields.extend(results)
                if total_count is None:
                    total_count = response_data.get("count")
                    if total_count is None:
                        logger.warning("API响应中未提供 'count' 字段，分页可能不完整或依赖 'next' 链接。")
                next_page_url = response_data.get("next")
                if next_page_url:
                    logger.debug(f"发现下一页数据字段链接: {next_page_url}")
                    if len(results) < self.API_PAGE_SIZE :
                         break
                    current_offset += len(results)
                    params["offset"] = current_offset
                    if total_count is not None and current_offset >= total_count:
                        break
                elif total_count is not None:
                    if len(all_datafields) >= total_count or not results:
                        break
                elif not results:
                    break
                else:
                    current_offset += len(results)
                    params["offset"] = current_offset
            except requests.exceptions.RequestException as e:
                logger.error(f"获取数据字段时发生请求错误: {e}")
                return pd.DataFrame()
            except ValueError as e:
                logger.error(f"解析数据字段响应时发生错误: {e}")
                return pd.DataFrame()
            except Exception as e:
                logger.error(f"获取数据字段时发生未知错误: {e}", exc_info=True)
                return pd.DataFrame()
        logger.info(f"成功获取 {len(all_datafields)} 个数据字段。")
        return pd.DataFrame(all_datafields)

    @lru_cache(maxsize=4)
    def get_datasets(self, instrument_type: str = 'EQUITY', region: str = 'USA', delay: int = 1, universe: str = 'TOP3000') -> pd.DataFrame:
        logger.info(f"获取数据集: instrument_type={instrument_type}, region={region}, delay={delay}, universe={universe}")
        params = {"instrument_type": instrument_type, "region": region, "delay": delay, "universe": universe}
        try:
            url = f"{self.BASE_URL}{self.DATASETS_ENDPOINT}"
            logger.debug(f"请求数据集，URL: {url}, 参数: {params}")
            response = self._request_with_retry("GET", url, params=params)
            response_data = response.json()
            results = response_data.get("results", [])
            if not isinstance(results, list):
                 logger.error(f"获取数据集时，API返回的 'results' 不是列表: {results}")
                 return pd.DataFrame()
            logger.info(f"成功获取 {len(results)} 个数据集。")
            return pd.DataFrame(results)
        except requests.exceptions.RequestException as e:
            logger.error(f"获取数据集时发生请求错误: {e}")
            return pd.DataFrame()
        except ValueError as e:
            logger.error(f"解析数据集响应时发生错误: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"获取数据集时发生未知错误: {e}", exc_info=True)
            return pd.DataFrame()

# 示例用法
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    test_email = os.environ.get("BRAIN_CREDENTIAL_EMAIL")
    test_password = os.environ.get("BRAIN_CREDENTIAL_PASSWORD")
    session = None
    if not test_email or not test_password:
        print("请设置 BRAIN_CREDENTIAL_EMAIL 和 BRAIN_CREDENTIAL_PASSWORD 环境变量以进行测试。")
    else:
        try:
            logger.info("开始 BrainApiSession 测试...")
            session = BrainApiSession(email=test_email, password=test_password)
            logger.info("BrainApiSession 初始化成功。")
            test_api_url = f"{BrainApiSession.BASE_URL}/user/profile"
            try:
                logger.info(f"尝试使用 session 发送 GET 请求到 {test_api_url}...")
                profile_response = session._request_with_retry("GET", test_api_url)
                logger.info(f"获取用户 profile 成功。状态码: {profile_response.status_code}")
                logger.info(f"响应内容: {profile_response.json()}")
            except Exception as e:
                logger.error(f"请求用户 profile 失败: {e}")
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

        if session:
            single_sim_data = {"alpha_expression": "rank(close)", "settings": {"universe": "TOP3000", "delay": 1, "region": "USA"}}
            logger.info("\n--- 测试单个模拟提交流程 ---")
            try:
                sim_submission_response = session.start_simulation(single_sim_data)
                if sim_submission_response and not sim_submission_response.get("error"):
                    submission_id = sim_submission_response.get("simulation_id") or sim_submission_response.get("job_id")
                    if submission_id:
                        logger.info(f"单个模拟提交成功，ID: {submission_id}。")
                        logger.warning("模拟轮询部分在离线测试中无法完全执行。")
                    else:
                        logger.error(f"单个模拟提交响应中未找到 simulation_id 或 job_id: {sim_submission_response}")
                else:
                    logger.error(f"单个模拟提交失败: {sim_submission_response}")
            except Exception as e:
                logger.error(f"测试单个模拟提交时发生错误: {e}", exc_info=True)

            logger.info("\n--- 测试 get_datafields ---")
            try:
                datafields_df = session.get_datafields(instrument_type='EQUITY', region='USA', universe='TOP3000')
                if not datafields_df.empty:
                    logger.info(f"成功获取 {len(datafields_df)} 个数据字段。前5条:")
                    logger.info(datafields_df.head().to_string())
                else:
                    logger.warning("未获取到数据字段或返回为空。")
                logger.info("再次调用 get_datafields (应从缓存读取)...")
                datafields_df_cached = session.get_datafields(instrument_type='EQUITY', region='USA', universe='TOP3000')
                if not datafields_df_cached.empty:
                     logger.info(f"从缓存获取 {len(datafields_df_cached)} 个数据字段。")
                else:
                     logger.warning("从缓存获取数据字段失败或为空。")
            except Exception as e:
                logger.error(f"测试 get_datafields 时发生错误: {e}", exc_info=True)

            logger.info("\n--- 测试 get_datasets ---")
            try:
                datasets_df = session.get_datasets(instrument_type='EQUITY', region='USA', universe='TOP3000')
                if not datasets_df.empty:
                    logger.info(f"成功获取 {len(datasets_df)} 个数据集。前5条:")
                    logger.info(datasets_df.head().to_string())
                else:
                    logger.warning("未获取到数据集或返回为空。")
                logger.info("再次调用 get_datasets (应从缓存读取)...")
                datasets_df_cached = session.get_datasets(instrument_type='EQUITY', region='USA', universe='TOP3000')
                if not datasets_df_cached.empty:
                    logger.info(f"从缓存获取 {len(datasets_df_cached)} 个数据集。")
                else:
                    logger.warning("从缓存获取数据集失败或为空。")
            except Exception as e:
                logger.error(f"测试 get_datasets 时发生错误: {e}", exc_info=True)

            logger.info(f"get_datafields 缓存信息: {session.get_datafields.cache_info()}")
            logger.info(f"get_datasets 缓存信息: {session.get_datasets.cache_info()}")

        logger.info("BrainApiSession 测试结束。")
