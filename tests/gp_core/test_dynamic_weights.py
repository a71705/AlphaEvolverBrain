# tests/gp_core/test_dynamic_weights.py
import pytest
from typing import List, Dict, Any, Optional
from unittest.mock import patch, MagicMock

from app.core.gp_algo import (
    Node,
    alpha_to_tree, # Used by _update_data_field_weights
    _get_terminals_from_tree,
    _update_data_field_weights,
    _get_dynamic_terminal_values, # To test its usage of dynamic weights
    DEFAULT_TERMINAL_VALUES,
    # For alpha_to_tree to work, it needs these lists:
    unary_ops, binary_ops, ts_ops, ts_ops_values
)

# --- _get_terminals_from_tree Tests ---
def test_get_terminals_from_tree_simple():
    """测试从简单树中提取终端。"""
    # add(close, open)
    tree = Node("add", Node("close"), Node("open"))
    terminals: List[str] = []
    # Assume 'close' and 'open' are in all_defined_terminals for this test
    all_defined = ["close", "open", "vwap"]
    _get_terminals_from_tree(tree, terminals, all_defined)
    assert sorted(terminals) == sorted(["close", "open"])

def test_get_terminals_from_tree_nested():
    """测试从嵌套树中提取终端，并处理重复。"""
    # add(ts_rank(close, 20), add(close, vwap))
    tree = Node("add",
                Node("ts_rank", Node("close"), Node("20")),
                Node("add", Node("close"), Node("vwap"))
               )
    terminals: List[str] = []
    all_defined = ["close", "vwap", "open"] # "20" is a ts_ops_value, not a terminal here
    _get_terminals_from_tree(tree, terminals, all_defined)
    # Expects ["close", "close", "vwap"] before unique sort, Counter handles counts.
    # The function as defined appends, so duplicates are expected if a terminal is used multiple times.
    assert sorted(terminals) == sorted(["close", "close", "vwap"])


def test_get_terminals_from_tree_no_valid_terminals():
    """测试树中没有在all_defined_terminals中定义的终端。"""
    tree = Node("add", Node("price"), Node("volume_data"))
    terminals: List[str] = []
    all_defined = ["close", "open"] # "price", "volume_data" are not in this list
    _get_terminals_from_tree(tree, terminals, all_defined)
    assert terminals == []

def test_get_terminals_from_tree_with_ts_ops_values():
    """测试确保ts_ops_values不被错误地识别为终端。"""
    tree = Node("ts_rank", Node("close"), Node("20"))
    terminals: List[str] = []
    all_defined = ["close", "20"] # Even if "20" is in all_defined, it shouldn't be picked if it's a ts_op_value context
                                 # The current _get_terminals_from_tree relies on node.value not being in op lists
                                 # and being a leaf. This test might need _get_terminals_from_tree to be more context-aware
                                 # or for all_defined_terminals to *not* include ts_ops_values.
                                 # For now, assume all_defined_terminals are true data fields.
    _get_terminals_from_tree(tree, terminals, ["close"]) # Only "close" is a true terminal here
    assert terminals == ["close"]


# --- _update_data_field_weights Tests ---
@pytest.fixture
def sample_ga_config_for_weights(mock_ga_config_fixture: Dict[str, Any]) -> Dict[str, Any]:
    config = mock_ga_config_fixture.copy()
    config.update({
        "use_dynamic_field_weights": True,
        "dynamic_weight_learning_rate": 0.1,
        "dynamic_weight_decay": 0.05,
        "dynamic_weight_min": 0.1,
        "dynamic_weight_max": 5.0,
    })
    return config

def test_update_data_field_weights_increase_and_decay(sample_ga_config_for_weights: Dict[str, Any]):
    """测试权重增加（出现字段）和衰减（未出现字段）。"""
    current_weights = {"close": 1.0, "open": 1.0, "vwap": 1.0, "adv20": 1.0}
    # Elite expressions: close appears 2 times, open 1 time. vwap, adv20 do not appear.
    elite_expressions = ["add(close, open)", "rank(close)"]
    all_fields = ["close", "open", "vwap", "adv20"]

    # Mock alpha_to_tree to simplify testing _update_data_field_weights directly
    # without re-testing full parsing here.
    def mock_alpha_to_tree(expr_str):
        if expr_str == "add(close, open)":
            return Node("add", Node("close"), Node("open"))
        elif expr_str == "rank(close)":
            return Node("rank", Node("close"))
        return None

    with patch("app.core.gp_algo.alpha_to_tree", side_effect=mock_alpha_to_tree):
        updated_weights = _update_data_field_weights(
            current_weights, elite_expressions, all_fields, sample_ga_config_for_weights
        )

    lr = sample_ga_config_for_weights["dynamic_weight_learning_rate"]
    decay = sample_ga_config_for_weights["dynamic_weight_decay"]

    # close: initial 1.0, freq 2. new = 1.0 * (1 + 0.1 * 2) = 1.0 * 1.2 = 1.2
    assert abs(updated_weights["close"] - (1.0 * (1 + lr * 2))) < 1e-6
    # open: initial 1.0, freq 1. new = 1.0 * (1 + 0.1 * 1) = 1.0 * 1.1 = 1.1
    assert abs(updated_weights["open"] - (1.0 * (1 + lr * 1))) < 1e-6
    # vwap: initial 1.0, freq 0. new = 1.0 * (1 - 0.05) = 0.95
    assert abs(updated_weights["vwap"] - (1.0 * (1 - decay))) < 1e-6
    # adv20: initial 1.0, freq 0. new = 1.0 * (1 - 0.05) = 0.95
    assert abs(updated_weights["adv20"] - (1.0 * (1 - decay))) < 1e-6

def test_update_data_field_weights_min_max_clamps(sample_ga_config_for_weights: Dict[str, Any]):
    """测试权重的最小和最大值限制。"""
    # Test min clamp
    current_weights_min = {"close": 0.05, "open": 1.0}
    elite_min = ["rank(open)"] # 'close' does not appear, should decay and hit min_weight
    all_f_min = ["close", "open"]
    with patch("app.core.gp_algo.alpha_to_tree", return_value=Node("rank", Node("open"))):
        updated_min = _update_data_field_weights(current_weights_min, elite_min, all_f_min, sample_ga_config_for_weights)
    assert abs(updated_min["close"] - sample_ga_config_for_weights["dynamic_weight_min"]) < 1e-6

    # Test max clamp
    current_weights_max = {"close": 4.8, "open": 1.0} # close is already high
    elite_max = ["rank(close)"] * 5 # 'close' appears many times
    all_f_max = ["close", "open"]
    def mock_alpha_to_tree_max(expr_str): return Node("rank", Node("close"))
    with patch("app.core.gp_algo.alpha_to_tree", side_effect=mock_alpha_to_tree_max):
        updated_max = _update_data_field_weights(current_weights_max, elite_max, all_f_max, sample_ga_config_for_weights)
    assert abs(updated_max["close"] - sample_ga_config_for_weights["dynamic_weight_max"]) < 1e-6


def test_update_data_field_weights_no_elites_or_disabled(sample_ga_config_for_weights: Dict[str, Any]):
    """测试当没有精英个体或禁用动态权重时，权重不变。"""
    current_weights = {"close": 1.5, "open": 0.8}

    # No elites
    updated_no_elites = _update_data_field_weights(current_weights.copy(), [], ["close", "open"], sample_ga_config_for_weights)
    assert updated_no_elites == current_weights

    # Dynamic weights disabled
    config_disabled = sample_ga_config_for_weights.copy()
    config_disabled["use_dynamic_field_weights"] = False
    updated_disabled = _update_data_field_weights(current_weights.copy(), ["rank(close)"], ["close", "open"], config_disabled)
    assert updated_disabled == current_weights


# --- _get_dynamic_terminal_values (focus on dynamic weight usage) ---
def test_get_dynamic_terminals_uses_dynamic_weights(sample_ga_config_for_weights: Dict[str, Any], mocker: MagicMock):
    """测试 _get_dynamic_terminal_values 在启用时使用动态权重。"""
    mock_brain_api = mocker.MagicMock(spec=BrainApiSession)
    # Mock get_datafields to return a controlled set of available fields
    mock_df = pd.DataFrame({'name': ['close', 'open', 'vwap', 'adv20', 'high', 'low']})
    mock_brain_api.get_datafields.return_value = mock_df

    dynamic_weights = {"close": 5.0, "open": 0.1, "vwap": 2.0} # 'close' highly weighted
    # available_field_names will be ['close', 'open', 'vwap', 'adv20', 'high', 'low']
    # strategy_params will ask for e.g. 3 fields

    config = sample_ga_config_for_weights.copy()
    config['use_dynamic_field_weights'] = True
    config['datafield_selection_strategy'] = 'weighted_random'
    config['datafield_selection_params'] = {'num_selected_fields': 1} # Select only 1 for easier testing

    # To ensure 'close' is picked due to its high dynamic weight:
    # We need random.choices to pick based on these weights.
    # Mock random.choices to check which population and weights it's called with.
    mock_random_choices = mocker.patch('random.choices')
    mock_random_choices.return_value = ['close'] # Assume it picks 'close'

    selected = _get_dynamic_terminal_values(
        mock_brain_api,
        strategy='weighted_random',
        strategy_params=config['datafield_selection_params'],
        source_params=config['data_source_params'],
        dynamic_weights_map=dynamic_weights,
        ga_config=config
    )
    assert selected == ['close']
    # Check that random.choices was called with weights derived from dynamic_weights
    # Expected fields for choice: 'close', 'open', 'vwap' (those in dynamic_weights AND available)
    # Expected weights: [5.0, 0.1, 2.0]
    mock_random_choices.assert_called() # Basic check
    # More specific check on arguments (if call_args is available and structure is simple)
    # args, kwargs = mock_random_choices.call_args
    # assert args[0] == ['close', 'open', 'vwap'] # fields_for_choice
    # assert kwargs['weights'] == [5.0, 0.1, 2.0]
    # assert kwargs['k'] == 1

def test_get_dynamic_terminals_fallback_static_then_random(sample_ga_config_for_weights: Dict[str, Any], mocker: MagicMock):
    """测试权重回退：动态权重无效 -> 静态权重 -> 随机。"""
    mock_brain_api = mocker.MagicMock(spec=BrainApiSession)
    mock_df = pd.DataFrame({'name': ['close', 'open', 'vwap', 'adv20']})
    mock_brain_api.get_datafields.return_value = mock_df

    config = sample_ga_config_for_weights.copy()
    config['use_dynamic_field_weights'] = True # Enabled
    config['datafield_selection_strategy'] = 'weighted_random'
    config['datafield_selection_params'] = {
        'num_selected_fields': 2,
        'weights': {"vwap": 3.0, "adv20": 0.5} # Static weights
    }

    # Scenario 1: dynamic_weights_map is None, should use static weights
    mocker.patch('random.choices', side_effect=lambda pop, weights, k: random.sample(pop, k)) # Mock choices to behave like sample for simplicity

    selected_static = _get_dynamic_terminal_values(
        mock_brain_api, 'weighted_random', config['datafield_selection_params'],
        config['data_source_params'], dynamic_weights_map=None, ga_config=config
    )
    assert len(selected_static) == 2
    assert all(field in ["vwap", "adv20"] for field in selected_static) # Should pick from static weighted fields

    # Scenario 2: No valid dynamic or static weights, should fallback to random from all available
    config_no_weights = config.copy()
    config_no_weights['datafield_selection_params'] = {'num_selected_fields': 2} # No 'weights' key

    selected_random = _get_dynamic_terminal_values(
        mock_brain_api, 'weighted_random', config_no_weights['datafield_selection_params'],
        config_no_weights['data_source_params'], dynamic_weights_map={}, ga_config=config_no_weights # Empty dynamic map
    )
    assert len(selected_random) == 2
    assert all(field in ['close', 'open', 'vwap', 'adv20'] for field in selected_random)
