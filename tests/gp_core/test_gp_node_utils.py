# tests/gp_core/test_gp_node_utils.py
import pytest
import random
from typing import List, Tuple, Optional

# 从 app.core.gp_algo 导入需要测试的类和函数
from app.core.gp_algo import (
    Node,
    copy_tree,
    get_tree_depth,
    count_nodes,
    _get_all_nodes_with_parent,
    _replace_child,
    _is_node_semantically_valid, # DEV-045
    OPERATOR_ARITY, # DEV-045
    unary_ops, binary_ops, ts_ops, ts_ops_values # For semantic validation tests
)

# --- Node Class Tests ---
def test_node_creation():
    """测试Node类的基本创建和属性。"""
    node1 = Node("close")
    assert node1.value == "close"
    assert node1.left is None
    assert node1.right is None

    node2 = Node("add", left=Node("open"), right=Node("close"))
    assert node2.value == "add"
    assert node2.left is not None
    assert node2.left.value == "open"
    assert node2.right is not None
    assert node2.right.value == "close"

def test_node_repr():
    """测试Node的__repr__方法。"""
    node = Node("ts_rank", Node("vwap"), Node("20"))
    # repr格式: Node('value', left=Node('left_val'), right=Node('right_val'))
    # 或 Node('value', left=Node('left_val'))
    # 或 Node('value')
    expected_repr = "Node('ts_rank', left=Node('vwap'), right=Node('20'))"
    assert repr(node) == expected_repr
    assert repr(Node("close")) == "Node('close')"
    assert repr(Node("rank", Node("open"))) == "Node('rank', left=Node('open'))"


# --- copy_tree Tests ---
def test_copy_tree_simple():
    """测试copy_tree复制简单树。"""
    original = Node("add", Node("close"), Node("open"))
    copied = copy_tree(original)

    assert copied is not None
    assert copied is not original # 确保是不同的对象
    assert copied.value == original.value
    assert copied.left is not original.left
    assert copied.left.value == original.left.value
    assert copied.right is not original.right
    assert copied.right.value == original.right.value
    assert copied.left.left is None # 确保叶子节点的子节点也是None

def test_copy_tree_complex():
    """测试copy_tree复制更复杂的嵌套树。"""
    # rank(ts_rank(add(close,vwap),20))
    original = Node("rank",
                    left=Node("ts_rank",
                              left=Node("add",
                                         left=Node("close"),
                                         right=Node("vwap")),
                              right=Node("20")))
    copied = copy_tree(original)
    assert copied is not None
    assert copied is not original
    assert copied.value == "rank"
    assert copied.left.value == "ts_rank"
    assert copied.left.left.value == "add"
    assert copied.left.left.left.value == "close"
    assert copied.left.left.right.value == "vwap"
    assert copied.left.right.value == "20"

    # 确保对象不同
    assert copied.left is not original.left
    assert copied.left.left is not original.left.left
    assert copied.left.left.left is not original.left.left.left


def test_copy_tree_empty():
    """测试copy_tree处理None输入。"""
    assert copy_tree(None) is None

# --- get_tree_depth Tests ---
@pytest.mark.parametrize("tree_structure, expected_depth", [
    (None, 0),
    (Node("close"), 1),
    (Node("rank", Node("close")), 2),
    (Node("add", Node("open"), Node("close")), 2),
    (Node("ts_rank", Node("rank", Node("close")), Node("20")), 3), # rank(close) is depth 2, ts_rank is 2+1=3
    (Node("add", Node("rank", Node("close")), Node("ts_mean", Node("open"), Node("20"))), 4) # rank(close) depth 2, ts_mean(open,20) depth 2. Max is 2. Add 1 for root. -> 3
                                                                                         # Correction: ts_mean(Node(open), Node(20)) is depth 2. rank(Node(close)) is depth 2.
                                                                                         # So max(depth(left_subtree), depth(right_subtree)) + 1 = max(2,2)+1 = 3
])
def test_get_tree_depth_various(tree_structure, expected_depth):
    """测试get_tree_depth对不同树结构的计算。"""
    # Correction for the last test case in parametrize:
    if tree_structure and tree_structure.value == "add" and \
       tree_structure.left and tree_structure.left.value == "rank" and \
       tree_structure.right and tree_structure.right.value == "ts_mean":
        # rank(close) -> depth 2
        # ts_mean(open, 20) -> depth 2
        # add(Node(rank), Node(ts_mean)) -> max(2,2) + 1 = 3
        assert get_tree_depth(tree_structure) == 3 # Corrected expected depth
    else:
        assert get_tree_depth(tree_structure) == expected_depth


# --- count_nodes Tests ---
@pytest.mark.parametrize("tree_structure, expected_nodes", [
    (None, 0),
    (Node("close"), 1),
    (Node("rank", Node("close")), 2),
    (Node("add", Node("open"), Node("close")), 3),
    (Node("ts_rank", Node("rank", Node("close")), Node("20")), 4), # ts_rank, rank, close, 20
])
def test_count_nodes_various(tree_structure, expected_nodes):
    """测试count_nodes对不同树结构的计算。"""
    assert count_nodes(tree_structure) == expected_nodes

# --- _get_all_nodes_with_parent Tests ---
def test_get_all_nodes_with_parent():
    """测试 _get_all_nodes_with_parent 是否正确返回节点及其父节点。"""
    n_c = Node("close")
    n_o = Node("open")
    n_add = Node("add", n_c, n_o)
    n_r = Node("rank", n_add) # rank(add(close,open))

    result = _get_all_nodes_with_parent(n_r)

    # 预期的节点和父节点值
    # (NodeValue, ParentValue or None for root)
    expected_pairs = {
        ("rank", None),
        ("add", "rank"),
        ("close", "add"),
        ("open", "add")
    }

    result_pairs = set((node.value, parent.value if parent else None) for node, parent in result)
    assert result_pairs == expected_pairs
    assert len(result) == 4 # 总共4个节点

def test_get_all_nodes_with_parent_single_node():
    n_c = Node("close")
    result = _get_all_nodes_with_parent(n_c)
    assert len(result) == 1
    assert result[0][0] == n_c
    assert result[0][1] is None

def test_get_all_nodes_with_parent_empty():
    assert _get_all_nodes_with_parent(None) == []

# --- _replace_child Tests ---
def test_replace_child():
    """测试 _replace_child 是否能正确替换左或右子节点。"""
    n_c = Node("close")
    n_o = Node("open")
    n_v = Node("vwap")
    parent = Node("add", n_c, n_o)

    # 替换左子节点
    assert _replace_child(parent, n_c, n_v) is True
    assert parent.left == n_v
    assert parent.right == n_o # 右子节点不变

    # 替换右子节点
    parent.left = n_c # 恢复左子节点
    assert _replace_child(parent, n_o, n_v) is True
    assert parent.right == n_v
    assert parent.left == n_c # 左子节点不变

    # 尝试替换不存在的子节点
    assert _replace_child(parent, Node("non_child"), n_v) is False


# --- _is_node_semantically_valid Tests (DEV-045) ---
# 确保 OPERATOR_ARITY 在此作用域内可用 (通常gp_algo.py在顶部定义)
# from app.core.gp_algo import OPERATOR_ARITY, unary_ops, binary_ops, ts_ops, ts_ops_values

def test_is_node_semantically_valid_terminals_and_values():
    """测试终端和ts_ops_values的语义有效性 (通常应为True)。"""
    assert _is_node_semantically_valid(Node("close")) is True
    assert _is_node_semantically_valid(Node("20")) is True # ts_ops_value

def test_is_node_semantically_valid_unary_ops():
    """测试一元操作符的语义有效性。"""
    valid_unary = Node(unary_ops[0], left=Node("close"))
    assert _is_node_semantically_valid(valid_unary) is True

    invalid_unary_no_child = Node(unary_ops[0]) # 缺少子节点
    assert _is_node_semantically_valid(invalid_unary_no_child) is False

    invalid_unary_too_many_children = Node(unary_ops[0], left=Node("close"), right=Node("open"))
    assert _is_node_semantically_valid(invalid_unary_too_many_children) is False

def test_is_node_semantically_valid_binary_ops():
    """测试二元操作符的语义有效性。"""
    valid_binary = Node(binary_ops[0], left=Node("close"), right=Node("open"))
    assert _is_node_semantically_valid(valid_binary) is True

    invalid_binary_one_child = Node(binary_ops[0], left=Node("close"))
    assert _is_node_semantically_valid(invalid_binary_one_child) is False

    invalid_binary_no_children = Node(binary_ops[0])
    assert _is_node_semantically_valid(invalid_binary_no_children) is False

def test_is_node_semantically_valid_ts_ops():
    """测试时间序列操作符的语义有效性。"""
    valid_ts_op = Node(ts_ops[0], left=Node("close"), right=Node(ts_ops_values[0]))
    assert _is_node_semantically_valid(valid_ts_op) is True

    valid_ts_op_numeric_value = Node(ts_ops[0], left=Node("close"), right=Node("10")) # 纯数字也应有效
    assert _is_node_semantically_valid(valid_ts_op_numeric_value) is True

    invalid_ts_op_missing_right = Node(ts_ops[0], left=Node("close"))
    assert _is_node_semantically_valid(invalid_ts_op_missing_right) is False

    invalid_ts_op_right_not_leaf = Node(ts_ops[0], left=Node("close"), right=Node("add", Node("10"), Node("5")))
    assert _is_node_semantically_valid(invalid_ts_op_right_not_leaf) is False

    invalid_ts_op_right_not_in_values = Node(ts_ops[0], left=Node("close"), right=Node("not_a_ts_value"))
    assert _is_node_semantically_valid(invalid_ts_op_right_not_in_values) is False

def test_is_node_semantically_valid_none_node():
    """测试 None 节点是否被视为有效（当前实现是 True）。"""
    assert _is_node_semantically_valid(None) is True
