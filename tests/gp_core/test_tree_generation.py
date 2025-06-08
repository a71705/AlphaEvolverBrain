# tests/gp_core/test_tree_generation.py
import pytest
from typing import List, Dict, Any, Optional

from app.core.gp_algo import (
    Node,
    depth_one_trees,
    # depth_two_tree, # Not the primary focus for this task, but could be tested similarly
    # depth_three_tree,
    _is_node_semantically_valid,
    get_tree_depth,
    count_nodes,
    DEFAULT_TERMINAL_VALUES, unary_ops, binary_ops, ts_ops, ts_ops_values
)

# --- depth_one_trees Tests (DEV-045 enhanced version) ---

@pytest.mark.parametrize("flag, expected_op_type_list, expected_depth, expected_nodes", [
    (0, DEFAULT_TERMINAL_VALUES, 1, 1), # Terminal node
    (1, unary_ops, 2, 2),              # Unary op + 1 terminal
    (2, binary_ops, 2, 3),             # Binary op + 2 terminals
    (3, ts_ops, 2, 3),                 # TS op + 1 terminal + 1 ts_value
])
def test_depth_one_trees_generation_and_validity(
    flag: int,
    expected_op_type_list: List[str],
    expected_depth: int,
    expected_nodes: int,
    mock_ga_config_fixture: Dict[str, Any] # from conftest.py
):
    """
    测试 depth_one_trees 是否能生成符合基本结构、语义和约束的树。
    """
    if not expected_op_type_list: # Skip if operator list is empty, e.g. if unary_ops was empty
        pytest.skip(f"Operator list for flag {flag} is empty, skipping test.")

    # Use a minimal ga_config for depth_one_trees, as it should generate small trees
    # that usually pass default constraints. We primarily test semantic validity here.
    # Stricter constraints for d1 trees are now part of depth_one_trees internal logic.
    ga_config = mock_ga_config_fixture.copy()
    # Override with very loose constraints to ensure generation itself is okay
    # The function's internal logic for d1 trees applies stricter defaults if needed.
    ga_config['max_alpha_depth'] = 10
    ga_config['max_nodes_per_alpha'] = 20


    # Test multiple times due to randomness in operator/terminal choice
    for _ in range(5): # Generate a few trees for each flag
        tree = depth_one_trees(
            DEFAULT_TERMINAL_VALUES,
            binary_ops,
            ts_ops,
            ts_ops_values,
            unary_ops,
            flag,
            ga_config
        )

        assert tree is not None, f"depth_one_trees (flag={flag}) returned None"

        # 1. Check root value type
        if flag == 0: # Terminal
            assert tree.value in DEFAULT_TERMINAL_VALUES
        else: # Operator
            assert tree.value in expected_op_type_list

        # 2. Check basic structure and semantic validity using _is_node_semantically_valid
        assert _is_node_semantically_valid(tree), \
            f"Generated tree (flag={flag}, root='{tree.value}') failed semantic validation. Tree: {tree!r}"

        # 3. Check complexity (should be inherently met by depth_one_trees design and its internal checks)
        # The internal checks in depth_one_trees are stricter for d1 trees (e.g. depth 1 or 2)
        # So we check against the expected small depth/nodes for these trees.
        assert get_tree_depth(tree) == expected_depth, f"Tree {tree!r} (flag {flag})"
        assert count_nodes(tree) == expected_nodes, f"Tree {tree!r} (flag {flag})"


def test_depth_one_trees_empty_lists(mock_ga_config_fixture: Dict[str, Any]):
    """
    测试 depth_one_trees 在关键列表为空时的行为。
    """
    ga_config = mock_ga_config_fixture

    # Flag 0: Terminal - terminal_vals is empty
    with pytest.raises(ValueError, match="终端值列表不能为空"):
        depth_one_trees([], binary_ops, ts_ops, ts_ops_values, unary_ops, 0, ga_config)

    # Flag 1: Unary - un_ops is empty (should return None after attempts or raise if fallback fails)
    # The function now has internal fallbacks or might return None if ops list is empty.
    # Let's test if it returns None or a valid fallback if terminals are available.
    tree = depth_one_trees(DEFAULT_TERMINAL_VALUES, binary_ops, ts_ops, ts_ops_values, [], 1, ga_config)
    assert tree is None, "Expected None when unary_ops is empty and no fallback is possible or if retries fail"
    # If it had a fallback to terminal: assert tree.value in DEFAULT_TERMINAL_VALUES

    # Flag 1: Unary - terminal_vals is empty (should raise error)
    with pytest.raises(ValueError, match="终端值列表不能为空"):
        depth_one_trees([], binary_ops, ts_ops, ts_ops_values, unary_ops, 1, ga_config)

    # Flag 3: TS Op - ts_ops_values is empty (should raise error)
    with pytest.raises(ValueError, match="时间序列操作参数值列表不能为空"):
        depth_one_trees(DEFAULT_TERMINAL_VALUES, binary_ops, ts_ops, [], unary_ops, 3, ga_config)


def test_depth_one_trees_violates_internal_strict_constraints(mock_ga_config_fixture: Dict[str, Any]):
    """
    测试 depth_one_trees 如果其内部为深度1树设定的严格约束无法满足时是否返回None。
    例如，如果 ga_config 传递进来，但 max_alpha_depth 被设为0。
    """
    strict_config = mock_ga_config_fixture.copy()
    strict_config['max_alpha_depth'] = 0 # Impossible for any tree

    # Flag 0 (Terminal) should still work if max_depth is 1, but fail if max_depth is 0.
    # The function's internal logic for flag 0 sets max_d to 1.
    # If ga_config['max_alpha_depth'] is 0, it uses max(ga_config_val, internal_default_for_d1_type)
    # This test is a bit tricky due to the internal defaults.
    # Let's test if it fails if max_nodes is 0.
    strict_config['max_nodes_per_alpha'] = 0

    tree = depth_one_trees(
        DEFAULT_TERMINAL_VALUES, binary_ops, ts_ops, ts_ops_values, unary_ops,
        0, # Try to generate a terminal
        strict_config
    )
    assert tree is None, "Expected depth_one_trees to return None if constraints are impossible"

    strict_config['max_nodes_per_alpha'] = 2 # For an operator tree (flag 1,2,3), this would be too small
    tree_op = depth_one_trees(
        DEFAULT_TERMINAL_VALUES, binary_ops, ts_ops, ts_ops_values, unary_ops,
        2, # Try to generate a binary op tree (3 nodes)
        strict_config
    )
    assert tree_op is None, "Expected depth_one_trees to return None for operator if node constraint is too small"

# TODO: Tests for depth_two_tree and depth_three_tree can be added,
# focusing on how they combine sub-trees and if they correctly apply
# _is_node_semantically_valid to the newly formed parent nodes.
# They would also need to accept and use ga_config for complexity checks if they generate new nodes.
# For now, their semantic checks added in DEV-045 are basic.
