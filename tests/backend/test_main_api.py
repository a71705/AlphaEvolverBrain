# tests/backend/test_main_api.py
from fastapi.testclient import TestClient
import logging

# 获取logger实例，测试日志的配置通常在pytest.ini或conftest.py中处理
logger = logging.getLogger(__name__)

def test_read_root(client: TestClient): # client fixture 来自 conftest.py
    """
    测试根路径 ('/') 是否成功响应。
    预期行为：返回状态码200和特定的欢迎JSON消息。
    """
    logger.info("开始测试根路径 GET / ...")
    response = client.get("/")

    assert response.status_code == 200, f"根路径响应状态码错误: {response.status_code}, 内容: {response.text}"

    expected_json = {"message": "Welcome to WorldQuant Brain Alpha Evolution System API"}
    assert response.json() == expected_json, f"根路径响应JSON不匹配: {response.json()}, 期望: {expected_json}"

    logger.info("根路径 GET / 测试通过。")

# 可以添加更多对 app/main.py 中其他非特定模块的全局端点的测试 (如果未来有的话)
# 例如，如果有一个全局的 /ping 或 /status 端点（非模块化的那个）
# def test_ping_endpoint(client: TestClient):
#     logger.info("测试 /ping 端点...")
#     response = client.get("/ping") # 假设有一个 /ping 端点
#     assert response.status_code == 200
#     assert response.json() == {"ping": "pong"}
#     logger.info("/ping 端点测试通过。")
