# tests/backend/test_database_models.py
from sqlalchemy.orm import Session as SQLAlchemySession # 使用别名以防与pytest的Session冲突
import pytest # 导入 pytest 以便可以使用其特性，例如xfail, skip等 (如果需要)
import uuid # 用于生成和比较UUID
import datetime
import logging

# 从主应用导入模型定义
from app.models import Experiment, Alpha
# (如果测试其他模型，也需要在此导入)

logger = logging.getLogger(__name__)

# db_session fixture 来自 tests/backend/conftest.py

def test_create_and_retrieve_experiment(db_session: SQLAlchemySession):
    """
    测试创建一个Experiment记录，存入数据库，然后能成功取回并验证其字段。
    """
    logger.info("开始测试 Experiment 模型：创建和检索...")

    # 准备实验数据
    # experiment_id = uuid.uuid4() # id 通常是数据库自动生成的，除非模型定义中指定了 client-side 生成
    experiment_name = "GP Run - Test001"
    experiment_desc = "测试实验，用于验证数据库模型。"
    ga_conf = {"population_size": 100, "generations": 50, "mutation_rate": 0.1}
    sim_conf = {"startDate": "2020-01-01", "endDate": "2022-12-31", "universe": "TOP1000"}

    # 创建 Experiment 对象
    new_experiment = Experiment(
        # id=str(experiment_id), # 如果 id 是 UUID 类型且手动提供，需转为 str (如果模型字段是String) 或直接用UUID (如果模型字段是UUID类型)
        # 在当前模型中，id是自增整数，所以不需要手动提供。
        name=experiment_name,
        description=experiment_desc,
        config_json=ga_conf, # 在模型中是 config_json，但在 Pydantic schema 中是 ga_config_json
                             # 这里应与模型字段名一致，或者在模型中调整字段名。
                             # 假设模型中是 config_json, Pydantic schema 中是 ga_config_json
                             # 修正：模型中是 config_json
        # simulation_config_json=sim_conf, # 模型中没有此字段，它在 Pydantic schema 中
                                         # GA 和 Sim 配置都应合并到 config_json 或分开存储在模型中
                                         # 当前模型只有一个 config_json。我们把两者都存进去
        # 假设模型中的 config_json 需要包含所有配置
        config_json = {"ga_config": ga_conf, "simulation_config": sim_conf, "code_version": "test_v1"},
        # code_version="test_v1.0", # 模型中有此字段
        status="PENDING",
        # created_at 和 updated_at 通常由数据库或 SQLAlchemy 自动填充 (如果设置了default/onupdate)
        # 如果没有，则需要手动设置：
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc)
    )

    # 添加到会话并提交
    db_session.add(new_experiment)
    db_session.commit()
    db_session.refresh(new_experiment) # 刷新以获取数据库生成的ID等信息

    logger.debug(f"已创建实验记录，ID: {new_experiment.id}")

    # 从数据库中检索刚创建的实验
    retrieved_experiment = db_session.query(Experiment).filter(Experiment.id == new_experiment.id).first()

    # 断言验证
    assert retrieved_experiment is not None, "未能从数据库中检索到实验。"
    assert retrieved_experiment.name == experiment_name
    assert retrieved_experiment.description == experiment_desc
    assert retrieved_experiment.status == "PENDING"
    assert retrieved_experiment.config_json["ga_config"]["population_size"] == 100
    assert retrieved_experiment.config_json["simulation_config"]["universe"] == "TOP1000"
    assert retrieved_experiment.config_json["code_version"] == "test_v1" # 检查合并后的config
    # assert retrieved_experiment.code_version == "test_v1.0" # 如果 code_version 是独立字段

    logger.info(f"Experiment 模型创建、字段赋值和检索测试通过。ID: {retrieved_experiment.id}")


def test_create_alpha_for_experiment(db_session: SQLAlchemySession):
    """
    测试为已存在的实验创建一个Alpha记录，并验证其关系和字段。
    """
    logger.info("开始测试 Alpha 模型：创建并关联到 Experiment...")

    # 1. 首先创建一个父 Experiment (与上一个测试类似，但简化)
    parent_experiment = Experiment(
        name="Alpha Parent Experiment",
        config_json={"ga_params": "test"},
        # simulation_config_json={"sim_params": "test"}, # 假设合并到 config_json
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db_session.add(parent_experiment)
    db_session.commit()
    db_session.refresh(parent_experiment)
    logger.debug(f"已创建父实验，ID: {parent_experiment.id}")

    # 2. 创建 Alpha 对象，关联到父 Experiment
    alpha_expression = "rank(close)"
    # alpha_id_uuid = uuid.uuid4() # Alpha ID 也是自增整数

    new_alpha = Alpha(
        # id=str(alpha_id_uuid), # 如果是UUID String 类型
        experiment_id=parent_experiment.id, # 建立外键关联
        expression=alpha_expression,
        depth=2, # 假设的深度
        iteration=1, # 假设的迭代次数
        # parent_ids=[], # 如果是初始Alpha，父ID为空列表或None
        simulation_settings_json={"region": "USA", "universe": "TOP100"},
        # calculated_fitness_score=0.75, # 适应度得分
        # is_history_best=True,
        created_at=datetime.datetime.now(datetime.timezone.utc), # 手动设置，如果模型无default
        updated_at=datetime.datetime.now(datetime.timezone.utc)  # 手动设置，如果模型无onupdate
    )
    db_session.add(new_alpha)
    db_session.commit()
    db_session.refresh(new_alpha)
    logger.debug(f"已创建Alpha记录，ID: {new_alpha.id}, 关联到实验ID: {new_alpha.experiment_id}")

    # 3. 从数据库检索Alpha并验证
    retrieved_alpha = db_session.query(Alpha).filter(Alpha.id == new_alpha.id).first()
    assert retrieved_alpha is not None, "未能从数据库检索到Alpha。"
    assert retrieved_alpha.expression == alpha_expression
    assert retrieved_alpha.experiment_id == parent_experiment.id
    assert retrieved_alpha.depth == 2
    assert retrieved_alpha.simulation_settings_json["universe"] == "TOP100"

    # 4. 验证关系是否生效 (从 Experiment 访问 Alphas)
    #    需要重新查询 experiment 对象，或确保关系在当前会话中已更新
    db_session.refresh(parent_experiment) # 刷新以加载关系
    assert len(parent_experiment.alphas) == 1, "Alpha未能正确关联到Experiment的alphas列表。"
    assert parent_experiment.alphas[0].id == new_alpha.id, "关联的Alpha ID不匹配。"

    logger.info(f"Alpha 模型创建、关联和基本字段验证通过。Alpha ID: {retrieved_alpha.id}")

# TODO: 考虑添加更多测试用例:
# - 测试 nullable 字段的默认值或None情况。
# - 测试 JSON 字段的复杂结构存储和检索。
# - 测试索引是否按预期工作 (这通常需要更专门的查询性能测试，可能超出单元测试范围)。
# - 测试 ondelete="CASCADE" 行为：删除 Experiment 时，其关联的 Alphas 是否也被删除。
#   (这需要小心操作，确保测试数据库的隔离性)。
# - 测试字段约束 (例如，如果String字段有长度限制，虽然SQLAlchemy层面可能不直接强制)。
