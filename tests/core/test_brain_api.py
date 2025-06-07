# 导入 unittest 模块，Python 内置的单元测试框架。
import unittest
# 从 unittest 模块导入 mock，用于模拟对象和函数。
from unittest import mock
# 导入 requests 模块中的异常类，用于测试错误处理。
import requests
# 导入 os 模块，用于在测试中设置环境变量。
import os
# 导入 time 模块，用于控制时间相关的模拟。
import time

# 从待测试的模块 app.core.brain_api 导入 BrainApiSession 类。
# 假设测试运行时，项目的根目录在 Python 的搜索路径中。
from app.core.brain_api import BrainApiSession, TOKEN_URL # 假设 USER_ME_URL 在模块中定义用于测试

# 定义一个测试类，继承自 unittest.TestCase。
class TestBrainApiSession(unittest.TestCase):
    """
    针对 BrainApiSession 类的单元测试套件。
    """

    USER_ME_URL = "https://api.worldquantbrain.com/users/me" # 定义测试用的URL

    # setUp 方法会在每个测试方法执行前被调用。
    # 通常用于设置测试环境。
    def setUp(self):
        """测试开始前的准备工作。"""
        # 设置必要的环境变量的模拟值，用于测试从环境变量读取凭据的逻辑。
        self.mock_env = {
            "BRAIN_CREDENTIAL_EMAIL": "test@example.com",
            "BRAIN_CREDENTIAL_PASSWORD": "testpassword"
        }
        # 使用 mock.patch.dict 来临时修改 os.environ。
        self.patched_env = mock.patch.dict(os.environ, self.mock_env)
        self.patched_env.start() # 启动 mock

        # 初始化 BrainApiSession 实例进行测试。
        self.session = BrainApiSession()

    # tearDown 方法会在每个测试方法执行后被调用。
    # 通常用于清理测试环境。
    def tearDown(self):
        """测试结束后的清理工作。"""
        self.patched_env.stop() # 停止 mock，恢复原始的 os.environ

    # 使用 mock.patch 装饰器来模拟 requests.Session 类。
    # new_callable=mock.MagicMock 指定用 MagicMock 实例替换 Session。
    @mock.patch('app.core.brain_api.requests.Session', new_callable=mock.MagicMock)
    def test_successful_authentication(self, mock_requests_session_cls):
        """测试成功认证的场景。"""
        # 获取模拟的 session 实例 (即 self.session._session)。
        mock_session_instance = mock_requests_session_cls.return_value
        self.session._session = mock_session_instance # 确保我们的实例使用这个 mock

        # 配置模拟的 post 方法的返回值，模拟认证成功。
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        # 模拟 API 返回的 token 数据。
        mock_response.json.return_value = {"token": "fake_token", "expires_in": 3600}
        mock_session_instance.post.return_value = mock_response

        # 调用认证方法。
        authenticated = self.session._authenticate()

        # 断言认证成功。
        self.assertTrue(authenticated)
        # 断言 token 被正确存储。
        self.assertEqual(self.session._auth_token, "fake_token")
        # 断言 Authorization 头部被设置。
        mock_session_instance.headers.update.assert_called_with({"Authorization": "Bearer fake_token"})
        # 断言认证请求被发送到了正确的 URL 和正确的 payload。
        mock_session_instance.post.assert_called_once_with(
            TOKEN_URL, # 假设 TOKEN_URL 是正确的认证端点
            json={"username": "test@example.com", "password": "testpassword"},
            timeout=10
        )

    @mock.patch('app.core.brain_api.requests.Session', new_callable=mock.MagicMock)
    def test_authentication_failure_invalid_credentials(self, mock_requests_session_cls):
        """测试因无效凭据导致认证失败的场景。"""
        mock_session_instance = mock_requests_session_cls.return_value
        self.session._session = mock_session_instance

        # 模拟认证失败 (例如返回 401 Unauthorized)。
        mock_response = mock.MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"detail": "Invalid credentials"} # 模拟错误详情
        # 配置 HTTPError 异常，当 raise_for_status 被调用时抛出。
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_session_instance.post.return_value = mock_response

        authenticated = self.session._authenticate()

        self.assertFalse(authenticated)
        self.assertIsNone(self.session._auth_token)

    @mock.patch('app.core.brain_api.requests.Session', new_callable=mock.MagicMock)
    def test_persona_authentication_scenario(self, mock_requests_session_cls):
        """测试 Persona 认证场景，应抛出 ValueError。"""
        mock_session_instance = mock_requests_session_cls.return_value
        self.session._session = mock_session_instance

        # 模拟 Persona 认证所需的响应。
        mock_response = mock.MagicMock()
        mock_response.status_code = 200 # Persona 场景可能返回 200 但包含特定消息
        mock_response.json.return_value = {"type": "PERSONA_AUTH_REQUIRED", "message": "Persona auth needed"}
        mock_session_instance.post.return_value = mock_response

        # 断言调用 _authenticate 会抛出 ValueError。
        with self.assertRaisesRegex(ValueError, "Persona 认证场景被检测到"):
            self.session._authenticate()

        self.assertIsNone(self.session._auth_token)

    @mock.patch('app.core.brain_api.time.time') # 模拟 time.time()
    @mock.patch('app.core.brain_api.requests.Session', new_callable=mock.MagicMock)
    def test_token_refresh_logic(self, mock_requests_session_cls, mock_time):
        """测试 token 自动刷新逻辑。"""
        mock_session_instance = mock_requests_session_cls.return_value
        self.session._session = mock_session_instance

        # 初始认证:
        # 第一次模拟 time.time() 返回一个初始时间。
        mock_time.return_value = 1000
        mock_auth_response = mock.MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "initial_token", "expires_in": 100} # token 100秒后过期
        # mock_session_instance.post.return_value = mock_auth_response # Set for the first call

        # 为了让 side_effect 生效，确保它按顺序返回。
        # 第一次 post 是初始认证，第二次是刷新。
        mock_refresh_response = mock.MagicMock()
        mock_refresh_response.status_code = 200
        mock_refresh_response.json.return_value = {"token": "refreshed_token", "expires_in": 100}
        mock_session_instance.post.side_effect = [mock_auth_response, mock_refresh_response]


        self.session._authenticate()
        self.assertEqual(self.session._auth_token, "initial_token")
        # 预期过期时间戳 = 1000 (当前时间) + 100 (有效期) = 1100
        self.assertEqual(self.session._auth_token_expiry_timestamp, 1100)

        # 模拟时间流逝，但不足以触发刷新 (token 有效期内，且未到刷新缓冲区)
        self.session._token_refresh_buffer_seconds = 10 # 测试时改小刷新缓冲
        self.session._token_lifetime_seconds = 100 # 与 expires_in 一致

        mock_time.return_value = 1050 # 时间到了 1050，token 还有 50 秒过期
        self.session._ensure_authenticated()
        # _authenticate 不应该被再次调用，因为 token 仍然有效且未到刷新点 (1100 - 10 = 1090)
        # (1050 < 1090)
        # mock_session_instance.post.call_count 应该仍然是 1 (初始认证)
        self.assertEqual(mock_session_instance.post.call_count, 1)
        self.assertEqual(self.session._auth_token, "initial_token")


        # 模拟时间进一步流逝，到达刷新点
        # mock_time.return_value = 1095 # 当前时间 1095。过期时间 1100。刷新点 1090 (1100-10)。
                                      # 1095 > 1090，应该触发刷新。

        # 为了更清晰地测试刷新，我们可以在 _ensure_authenticated 之前手动设置一个已过期的 token 状态
        # 或者直接让时间超过过期时间戳
        self.session._auth_token_expiry_timestamp = 1000 # 假设 token 已过期
        mock_time.return_value = 1001 # 当前时间超过了过期时间

        self.session._ensure_authenticated() # 应该触发 _authenticate (第二次调用 post)

        self.assertEqual(self.session._auth_token, "refreshed_token")
        # 新的过期时间 = 1001 (当前时间) + 100 (有效期) = 1101
        self.assertEqual(self.session._auth_token_expiry_timestamp, 1101)
        # 认证 (post) 应该被调用了两次 (一次初始，一次刷新)
        self.assertEqual(mock_session_instance.post.call_count, 2)


    @mock.patch('app.core.brain_api.requests.Session', new_callable=mock.MagicMock)
    def test_request_with_retry_successful_first_try(self, mock_requests_session_cls):
        """测试 _request_with_retry 第一次尝试就成功。"""
        mock_session_instance = mock_requests_session_cls.return_value
        self.session._session = mock_session_instance

        # 先模拟一次成功的认证
        self.session._auth_token = "fake_token"
        self.session._auth_token_expiry_timestamp = time.time() + 3600 # Token 一小时后过期
        mock_session_instance.headers = {"Authorization": "Bearer fake_token"}

        # 模拟 API 请求成功
        mock_api_response = mock.MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {"data": "success"}
        # mock_session_instance.request 是实际发送请求的方法
        mock_session_instance.request.return_value = mock_api_response

        # 调用 _request_with_retry
        response = self.session._request_with_retry("GET", self.USER_ME_URL, params={"test": "123"})

        self.assertEqual(response.json(), {"data": "success"})
        mock_session_instance.request.assert_called_once_with(
            "GET", self.USER_ME_URL, params={"test": "123"}, headers={"Authorization": "Bearer fake_token"}
        )

    @mock.patch('app.core.brain_api.time.sleep', return_value=None) # 阻止 time.sleep 生效
    @mock.patch('app.core.brain_api.requests.Session', new_callable=mock.MagicMock)
    def test_request_with_retry_after_one_failure(self, mock_requests_session_cls, mock_sleep):
        """测试 _request_with_retry 在一次失败后重试成功。"""
        mock_session_instance = mock_requests_session_cls.return_value
        self.session._session = mock_session_instance
        self.session._auth_token = "fake_token"
        self.session._auth_token_expiry_timestamp = time.time() + 3600

        # 模拟第一次请求失败 (例如 500 服务器错误)，第二次成功
        mock_failure_response = mock.MagicMock()
        mock_failure_response.status_code = 500
        mock_failure_response.text = "Server Error"
        mock_failure_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_failure_response)

        mock_success_response = mock.MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"data": "retry_success"}

        # mock_session_instance.request 会按顺序返回这两个响应
        mock_session_instance.request.side_effect = [mock_failure_response, mock_success_response]

        response = self.session._request_with_retry("GET", self.USER_ME_URL)

        self.assertEqual(response.json(), {"data": "retry_success"})
        self.assertEqual(mock_session_instance.request.call_count, 2) # 应该调用了两次
        mock_sleep.assert_called_once_with(self.session._retry_delay) # 验证是否调用了 sleep

    @mock.patch('app.core.brain_api.time.sleep', return_value=None)
    @mock.patch('app.core.brain_api.requests.Session', new_callable=mock.MagicMock)
    def test_request_with_retry_exhausts_retries(self, mock_requests_session_cls, mock_sleep):
        """测试 _request_with_retry 在耗尽所有重试次数后失败。"""
        mock_session_instance = mock_requests_session_cls.return_value
        self.session._session = mock_session_instance
        self.session._auth_token = "fake_token"
        self.session._auth_token_expiry_timestamp = time.time() + 3600
        self.session._max_retries = 1 # 为了测试方便，减少重试次数

        # 模拟所有尝试都失败
        mock_failure_response = mock.MagicMock()
        mock_failure_response.status_code = 500
        mock_failure_response.text = "Persistent Server Error"
        mock_failure_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_failure_response)

        mock_session_instance.request.return_value = mock_failure_response # 每次调用都返回失败

        with self.assertRaises(requests.exceptions.HTTPError):
            self.session._request_with_retry("GET", self.USER_ME_URL)

        # 总共调用次数 = 1 (初始尝试) + 1 (重试次数) = 2
        self.assertEqual(mock_session_instance.request.call_count, self.session._max_retries + 1)


    @mock.patch('app.core.brain_api.time.time')
    @mock.patch('app.core.brain_api.time.sleep', return_value=None)
    @mock.patch('app.core.brain_api.requests.Session', new_callable=mock.MagicMock)
    def test_request_with_retry_handles_401_and_refreshes_token(self, mock_requests_session_cls, mock_sleep, mock_current_time):
        """测试 _request_with_retry 处理401错误，刷新token并成功重试。"""
        mock_session_instance = mock_requests_session_cls.return_value
        self.session._session = mock_session_instance

        # 初始状态：未认证
        self.session._auth_token = None
        self.session._auth_token_expiry_timestamp = 0

        # 模拟时间
        initial_time = 1000
        mock_current_time.return_value = initial_time

        # 第一次 API 调用 (非认证接口) -> 应该先触发认证
        # 模拟认证成功
        mock_auth_response = mock.MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "first_token", "expires_in": 100} # 100秒有效期

        # 模拟第一次调用受保护接口时返回 401 (假设token意外失效)
        mock_401_response = mock.MagicMock()
        mock_401_response.status_code = 401
        mock_401_response.text = "Token expired"
        mock_401_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_401_response)

        # 模拟第二次认证 (刷新) 成功
        mock_refresh_auth_response = mock.MagicMock()
        mock_refresh_auth_response.status_code = 200
        mock_refresh_auth_response.json.return_value = {"token": "refreshed_token", "expires_in": 100}

        # 模拟刷新后调用受保护接口成功
        mock_success_after_refresh_response = mock.MagicMock()
        mock_success_after_refresh_response.status_code = 200
        mock_success_after_refresh_response.json.return_value = {"data": "success after refresh"}

        # 配置 mock_session_instance.post (用于认证) 和 mock_session_instance.request (用于API调用)
        # 第一次 _ensure_authenticated -> _authenticate (post)
        # 第一次 _request_with_retry -> request (返回401)
        # 401后 -> _ensure_authenticated (强制) -> _authenticate (post)
        # 第二次 _request_with_retry -> request (成功)
        mock_session_instance.post.side_effect = [mock_auth_response, mock_refresh_auth_response]
        mock_session_instance.request.side_effect = [mock_401_response, mock_success_after_refresh_response]

        # 调用受保护的 API
        response = self.session._request_with_retry("GET", self.USER_ME_URL)

        self.assertEqual(response.json(), {"data": "success after refresh"})
        self.assertEqual(self.session._auth_token, "refreshed_token")

        # 验证调用次数
        # post 应该被调用两次 (初始认证 + 401后的刷新认证)
        self.assertEqual(mock_session_instance.post.call_count, 2)
        # request 应该被调用两次 (一次401，一次成功)
        self.assertEqual(mock_session_instance.request.call_count, 2)


# 这个块允许直接从命令行运行测试文件。
if __name__ == '__main__':
    unittest.main()
