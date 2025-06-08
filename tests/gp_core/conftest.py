# tests/gp_core/conftest.py
import pytest
from typing import Dict, Any

@pytest.fixture
def mock_ga_config_fixture() -> Dict[str, Any]:
    """
    提供一个基础的 ga_config mock字典，用于测试gp_algo中的函数。
    测试用例可以根据需要覆盖或扩展这些默认值。
    """
    config = {
        "max_alpha_depth": 7,  # 最大Alpha树深度
        "max_nodes_per_alpha": 50,  # 每个Alpha的最大节点数
        "max_generation_attempts": 10, # 树生成（如depth_one_trees）时的最大尝试次数
        "max_mutation_attempts_per_node": 5, # 单个节点变异时的最大尝试次数

        # 用于动态数据字段权重调整 (DEV-044)
        "use_dynamic_field_weights": False, # 是否启用动态字段权重调整
        "dynamic_weight_learning_rate": 0.1, # 动态权重的学习率
        "dynamic_weight_decay": 0.01,        # 动态权重的衰减因子
        "dynamic_weight_min": 0.1,           # 动态权重的最小值
        "dynamic_weight_max": 10.0,          # 动态权重的最大值
        "elite_selection_size_for_weight_update": 5, # 用于更新权重的精英种群大小

        # 用于父代选择策略 (DEV-050)
        "parent_selection_strategy": "tournament", # 父代选择策略
        "tournament_selection_size": 3,          # 锦标赛选择的锦标赛大小
        "num_parents_to_select": 20,             # 每代选择用于繁殖的父代数量
        "higher_fitness_is_better": True,        # 适应度值是否越高越好

        # 数据源和字段选择参数 (用于 _get_dynamic_terminal_values)
        "data_source_params": { # 参数用于调用 brain_api_session.get_datafields
            "instrument_type": "EQUITY",
            "region": "USA",
            "delay": 1,
            "universe": "TOP3000",
            "dataset_id": ""
        },
        "datafield_selection_strategy": "random", # 终端字段的选择策略
        "datafield_selection_params": {          # 特定于字段选择策略的参数
            "num_selected_fields": 10,           # 例如，随机选择10个字段
            # "weights": {"close": 0.5, "open": 0.3}, # 用于 weighted_random
            # "whitelist": ["close", "vwap"],          # 用于 whitelist
            # "blacklist": ["adv20", "volume"]         # 用于 blacklist
        },
        # 其他可能在gp_algo.py中会用到的ga_config参数...
    }
    return config
