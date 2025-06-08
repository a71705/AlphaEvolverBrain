# tests/gp_core/test_genetic_operators.py
import pytest
import random
from typing import List, Dict, Any, Tuple, Optional
from unittest.mock import patch, MagicMock # For mocking random choices etc.

from app.core.gp_algo import (
    Node,
    copy_tree,
    get_tree_depth,
    count_nodes,
    mutate_random_node, # DEV-043 / DEV-045 version
    crossover,          # DEV-043 / DEV-045 version
    _get_all_nodes_with_parent, # Helper, might be useful for assertions
    _is_node_semantically_valid, # For checking results
    OPERATOR_ARITY,
    # Lists needed by mutate_random_node and potentially for constructing test trees
    DEFAULT_TERMINAL_VALUES, unary_ops, binary_ops, ts_ops, ts_ops_values
)

# Helper to create a simple tree for testing, e.g., add(close, open)
def create_simple_tree_add_close_open() -> Node:
    return Node("add", Node("close"), Node("open"))

# Helper to create a slightly more complex tree, e.g., ts_rank(rank(vwap), 20)
def create_complex_tree_tsrank_rank_vwap_20() -> Node:
    return Node("ts_rank", Node("rank", Node("vwap")), Node("20"))

# --- mutate_random_node Tests ---
# Note: Testing randomized functions can be tricky. We can:
# 1. Mock random choices to make outcomes deterministic.
# 2. Run many times and check statistical properties (more complex).
# 3. Check invariants (e.g., output is always a valid tree, adheres to constraints).

def test_mutate_random_node_basic_mutation(mock_ga_config_fixture: Dict[str, Any], mocker: MagicMock):
    """测试mutate_random_node是否能对节点进行变异。"""
    original_tree = create_simple_tree_add_close_open() # add(close,open)

    # Mock random.choice for _get_random_node to select a specific node for mutation
    # Let's say we want to mutate the "close" node.
    # _get_all_nodes_with_parent(original_tree) would be:
    # [(add, None), (close, add), (open, add)]
    # To mutate "close", random.choice should return the Node("close") object.
    # We need to find this specific object within the copied tree.

    # Mock depth_one_trees to return a predictable new node, e.g., Node("vwap")
    mocker.patch("app.core.gp_algo.depth_one_trees", return_value=Node("vwap"))

    # To make _get_random_node deterministic for this test:
    # We want it to pick the 'close' node from the *copied* tree.
    # This is hard to do directly without knowing the copy's object ID.
    # Alternative: patch random.choice used by _get_random_node.
    # Let's assume _get_random_node picks the 'left' child of 'add' (which is 'close')

    # This is still tricky as _get_random_node operates on a copy.
    # A simpler test: verify *a* mutation happened and constraints are met.

    mutated_tree = mutate_random_node(
        original_tree,
        mock_ga_config_fixture,
        DEFAULT_TERMINAL_VALUES,
        unary_ops, binary_ops, ts_ops, ts_ops_values
    )

    assert mutated_tree is not None
    # Check if it's different from original (probabilistically, it should be)
    # This isn't a strong assertion due to randomness.
    # A better check would be to see if *any* node value changed, or if structure changed.
    # For this test, we rely on the mocked depth_one_trees returning "vwap".
    # We need to ensure one of the nodes is "vwap".

    nodes_in_mutated = [n.value for n,p in _get_all_nodes_with_parent(mutated_tree)]
    assert "vwap" in nodes_in_mutated # Since depth_one_trees is mocked to return Node("vwap")

    # Check complexity constraints
    assert get_tree_depth(mutated_tree) <= mock_ga_config_fixture["max_alpha_depth"]
    assert count_nodes(mutated_tree) <= mock_ga_config_fixture["max_nodes_per_alpha"]

    # Check semantic validity of the mutated part (if we could identify it)
    # For now, check the whole tree's root (if it's an op)
    if OPERATOR_ARITY.get(mutated_tree.value):
        assert _is_node_semantically_valid(mutated_tree)

def test_mutate_random_node_respects_constraints(mock_ga_config_fixture: Dict[str, Any], mocker: MagicMock):
    """测试变异在多次尝试后，如果始终超限，则返回原始树的拷贝。"""
    original_tree = Node("add", Node("close"), Node("open")) # Depth 2, Nodes 3

    # Configure ga_config for very strict constraints that a new depth-one tree would violate
    # if it replaced a terminal (e.g. max_depth = 1, but new tree is depth 2)
    strict_ga_config = mock_ga_config_fixture.copy()
    strict_ga_config["max_alpha_depth"] = 1 # Mutation of a terminal to op(terminal) would make depth 2
    strict_ga_config["max_nodes_per_alpha"] = 1 # Mutation of a terminal to op(terminal) would make 2 or 3 nodes
    strict_ga_config["max_mutation_attempts_per_node"] = 3

    # Mock depth_one_trees to always return a 2-level node, e.g., rank(adv20)
    mocker.patch("app.core.gp_algo.depth_one_trees", return_value=Node("rank", Node("adv20")))

    # Mock _get_random_node to always pick a terminal (e.g., "close") for mutation
    # This is complex because _get_random_node operates on a copy.
    # Instead, we'll rely on the fact that replacing any node with rank(adv20)
    # in add(close,open) will likely violate depth=1 or nodes=1 constraint.

    mutated_tree = mutate_random_node(
        original_tree,
        strict_ga_config,
        DEFAULT_TERMINAL_VALUES,
        unary_ops, binary_ops, ts_ops, ts_ops_values
    )

    # Expect original tree (or its copy) to be returned due to constraint violation
    assert mutated_tree.value == original_tree.value
    assert (mutated_tree.left.value if mutated_tree.left else None) == (original_tree.left.value if original_tree.left else None)
    assert (mutated_tree.right.value if mutated_tree.right else None) == (original_tree.right.value if original_tree.right else None)
    assert mutated_tree is not original_tree # Should be a copy


# --- crossover Tests (DEV-043 / DEV-045 version) ---
def test_crossover_basic_swap(mock_ga_config_fixture: Dict[str, Any], mocker: MagicMock):
    """测试基本的子树交换。"""
    p1 = Node("add", Node("close"), Node("open"))  # Depth 2, Nodes 3
    p2 = Node("ts_rank", Node("vwap"), Node("20")) # Depth 2, Nodes 3

    # Mock _get_random_non_root_node_and_parent to pick specific nodes
    # For p1 (copied as child1), pick Node("close")
    # For p2 (copied as child2), pick Node("vwap")

    # This mocking is tricky because the function is called on copies.
    # We'll check the outcome instead.
    # Expected: child1 = add(vwap, open), child2 = ts_rank(close, 20)
    # OR child1 = add(close, 20), child2 = ts_rank(vwap, open) etc. depending on what's swapped.

    # To make it deterministic, we can patch random.choice inside _get_random_non_root_node_and_parent
    # or patch _get_random_non_root_node_and_parent itself.

    # Let's assume _get_random_non_root_node_and_parent for child1 returns (child1.left, child1)
    # and for child2 returns (child2.left, child2)

    def mock_selection_logic(tree_copy):
        if tree_copy.value == "add": # Parent1's copy
            return (tree_copy.left, tree_copy) # Select 'close' node from add(close,open)
        elif tree_copy.value == "ts_rank": # Parent2's copy
            return (tree_copy.left, tree_copy) # Select 'vwap' node from ts_rank(vwap,20)
        return None

    mocker.patch("app.core.gp_algo._get_random_non_root_node_and_parent", side_effect=mock_selection_logic)

    child1, child2 = crossover(p1, p2, mock_ga_config_fixture)

    assert child1 is not None
    assert child2 is not None

    # Expected: child1 = add(vwap, open), child2 = ts_rank(close, 20)
    assert child1.value == "add"
    assert child1.left is not None and child1.left.value == "vwap" # Swapped from p2
    assert child1.right is not None and child1.right.value == "open"

    assert child2.value == "ts_rank"
    assert child2.left is not None and child2.left.value == "close" # Swapped from p1
    assert child2.right is not None and child2.right.value == "20"

    # Check complexity and semantics (should pass if parents were valid and swap is simple)
    assert get_tree_depth(child1) <= mock_ga_config_fixture["max_alpha_depth"]
    assert count_nodes(child1) <= mock_ga_config_fixture["max_nodes_per_alpha"]
    assert _is_node_semantically_valid(child1) # Check root of swapped subtree's new parent

    assert get_tree_depth(child2) <= mock_ga_config_fixture["max_alpha_depth"]
    assert count_nodes(child2) <= mock_ga_config_fixture["max_nodes_per_alpha"]
    assert _is_node_semantically_valid(child2)


def test_crossover_violates_constraints_returns_parents(mock_ga_config_fixture: Dict[str, Any], mocker: MagicMock):
    """测试交叉后子代超限，应返回父代拷贝。"""
    p1 = Node("rank", Node("add", Node("close"), Node("open"))) # Depth 3, Nodes 4
    p2 = Node("ts_rank", Node("vwap"), Node("20"))             # Depth 2, Nodes 3

    strict_ga_config = mock_ga_config_fixture.copy()
    strict_ga_config["max_alpha_depth"] = 2 # This will be violated if 'add(close,open)' is swapped into p2's 'vwap'

    # Mock selections:
    # From p1 (child1): select Node("add", Node("close"), Node("open"))
    # From p2 (child2): select Node("vwap")
    def mock_selection_logic_constraints(tree_copy):
        if tree_copy.value == "rank": # p1's copy
            return (tree_copy.left, tree_copy) # node1 = add(close,open), parent_of_node1 = rank
        elif tree_copy.value == "ts_rank": # p2's copy
            return (tree_copy.left, tree_copy) # node2 = vwap, parent_of_node2 = ts_rank
        return None

    mocker.patch("app.core.gp_algo._get_random_non_root_node_and_parent", side_effect=mock_selection_logic_constraints)

    child1, child2 = crossover(p1, p2, strict_ga_config)

    # child1 would become: rank(vwap) -> Depth 2, Nodes 2 (OK)
    # child2 would become: ts_rank(add(close,open), 20) -> Depth 3, Nodes 5 (Violates max_depth=2)
    # So, child2 should be a copy of p2.

    assert child1.value == "rank"
    assert child1.left.value == "vwap"

    assert child2.value == p2.value # child2 reverted to p2 copy
    assert child2.left.value == p2.left.value
    assert child2.right.value == p2.right.value
    assert child2 is not p2 # ensure it's a copy

# TODO: Add tests for crossover semantic violations if _is_node_semantically_valid is made more strict for it.
# For example, if swapping results in ts_rank(close, rank(open)) -> this should fail semantic check on parent ts_rank.
