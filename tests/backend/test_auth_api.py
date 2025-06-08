# tests/backend/test_auth_api.py
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock # pytest-mock的mocker fixture也可通过conftest.py全局提供或直接导入
import logging
from datetime import datetime, timedelta

# from app.core.brain_api import BrainApiSession # 实际被patch的类
# from app.schemas import AuthResponse # 用于类型提示或验证响应结构

logger = logging.getLogger(__name__)

# 注意: `client` fixture 来自 `tests/backend/conftest.py`
# `mocker` fixture 会由 `pytest-mock` 插件自动提供

def test_login_success(client: TestClient, mocker: MagicMock): # mocker fixture from pytest-mock
    """
    测试成功登录的情况。
    需要mock BrainApiSession以模拟成功的外部API认证。
    """
    logger.info("开始测试成功登录 POST /api/v1/auth/login ...")

    # 1. 准备 Mock BrainApiSession
    #    当 app.api.v1.auth.BrainApiSession 被实例化时，我们希望返回一个mock对象。
    #    这个mock对象需要有一个 _auth_token 属性，该属性不为None，表示认证成功。
    mock_brain_session_instance = mocker.MagicMock()
    mock_brain_session_instance._auth_token = "mocked_brain_api_token_12345" # 模拟认证成功后获取到的token

    # 使用 patch 来替换在 app.api.v1.auth 模块中使用的 BrainApiSession 类
    # 当 new BrainApiSession(...) 被调用时，它将返回 mock_brain_session_instance
    with patch("app.api.v1.auth.BrainApiSession", return_value=mock_brain_session_instance) as mock_brain_constructor:
        login_data = {"email": "test@example.com", "password": "password123"}
        response = client.post("/api/v1/auth/login", json=login_data)

    # 2. 验证响应状态码和内容
    assert response.status_code == 200, f"成功登录预期状态码200, 实际为 {response.status_code}. 响应: {response.text}"
    response_data = response.json()
    assert "session_token" in response_data, "响应中缺少 'session_token'"
    assert "expires_at" in response_data, "响应中缺少 'expires_at'"
    assert response_data["token_type"] == "bearer", "响应中 'token_type' 不为 'bearer'" # 假设 AuthResponse 中有此字段

    # 验证 session_token 是一个字符串 (通常是UUID)
    assert isinstance(response_data["session_token"], str)
    # 验证 expires_at 是一个有效的ISO格式日期时间字符串
    try:
        expires_datetime = datetime.fromisoformat(response_data["expires_at"].replace('Z', '+00:00'))
        assert expires_datetime > datetime.now(timezone.utc if response_data["expires_at"].endswith('Z') else None) # 确保过期时间在未来
    except ValueError:
        pytest.fail(f"expires_at '{response_data['expires_at']}' 不是有效的ISO日期时间格式。")

    # 3. (可选) 验证 BrainApiSession 构造器是否以正确的凭据被调用
    mock_brain_constructor.assert_called_once_with(email=login_data["email"], password=login_data["password"])

    logger.info(f"成功登录测试通过。Session Token (前缀): {response_data['session_token'][:8]}...")


def test_login_failure_invalid_credentials(client: TestClient, mocker: MagicMock):
    """
    测试因无效凭据（例如密码错误）导致登录失败的情况。
    BrainApiSession 的构造函数或其内部的 _authenticate 方法应模拟认证失败。
    """
    logger.info("开始测试无效凭据登录 POST /api/v1/auth/login ...")

    # 1. 配置 Mock BrainApiSession 以模拟认证失败 (例如，构造函数返回一个 _auth_token 为 None 的实例)
    mock_brain_session_instance_failure = mocker.MagicMock()
    mock_brain_session_instance_failure._auth_token = None # 表示 WQB API 认证未成功获取token

    with patch("app.api.v1.auth.BrainApiSession", return_value=mock_brain_session_instance_failure) as mock_brain_constructor:
        login_data = {"email": "user@example.com", "password": "wrongpassword"}
        response = client.post("/api/v1/auth/login", json=login_data)

    # 2. 验证响应
    assert response.status_code == 401, f"无效凭据登录预期状态码401, 实际为 {response.status_code}. 响应: {response.text}"
    response_data = response.json()
    assert "detail" in response_data, "失败响应中缺少 'detail' 字段"
    # 检查 detail 消息是否符合预期（可能包含“无效凭据”等字样）
    # assert "无效" in response_data["detail"] or "unauthorized" in response_data["detail"].lower()
    logger.info(f"无效凭据登录测试通过。响应详情: {response_data['detail']}")


def test_login_persona_auth_required(client: TestClient, mocker: MagicMock):
    """
    测试因需要 Persona 认证导致登录失败的情况。
    BrainApiSession 的构造函数应抛出包含 "Persona" 信息的 ValueError。
    """
    logger.info("开始测试 Persona 认证需求 POST /api/v1/auth/login ...")

    # 1. 配置 Mock BrainApiSession 以模拟需要 Persona 认证 (抛出特定 ValueError)
    # side_effect 可以是一个异常实例或一个函数
    persona_error_message = "Persona 认证场景被检测到，请完成额外验证步骤。"
    with patch("app.api.v1.auth.BrainApiSession", side_effect=ValueError(persona_error_message)) as mock_brain_constructor:
        login_data = {"email": "persona_user@example.com", "password": "password123"}
        response = client.post("/api/v1/auth/login", json=login_data)

    # 2. 验证响应
    assert response.status_code == 401, f"Persona认证需求预期状态码401, 实际为 {response.status_code}. 响应: {response.text}"
    response_data = response.json()
    assert "detail" in response_data
    assert "Persona" in response_data["detail"] or "生物特征" in response_data["detail"] # 检查关键字
    logger.info(f"Persona 认证需求测试通过。响应详情: {response_data['detail']}")

# 可以添加更多测试用例，例如：
# - Brain API 服务暂时不可用 (例如，requests.exceptions.ConnectionError)
# - Brain API 返回意外的 5xx 错误
# - 请求体格式错误 (例如，缺少 email 或 password 字段，由Pydantic自动处理，返回422)

def test_login_missing_fields(client: TestClient):
    """测试请求体中缺少字段的情况 (由 Pydantic 自动处理)。"""
    logger.info("开始测试登录时缺少字段 POST /api/v1/auth/login ...")

    response = client.post("/api/v1/auth/login", json={"email": "user@example.com"}) # 缺少 password
    assert response.status_code == 422 # Unprocessable Entity
    logger.info("缺少 password 字段测试通过。")

    response = client.post("/api/v1/auth/login", json={"password": "password123"}) # 缺少 email
    assert response.status_code == 422
    logger.info("缺少 email 字段测试通过。")

    response = client.post("/api/v1/auth/login", json={}) # 空json
    assert response.status_code == 422
    logger.info("空JSON请求体测试通过。")
