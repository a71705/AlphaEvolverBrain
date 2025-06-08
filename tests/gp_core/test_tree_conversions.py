# tests/gp_core/test_tree_conversions.py
import pytest
from typing import Optional, List

from app.core.gp_algo import (
    Node,
    tree_to_alpha,      # DEV-041 version
    _tokenize_expression, # DEV-042 version
    alpha_to_tree,      # DEV-042 version
    # For _tokenize_expression and alpha_to_tree to work correctly, they need access to these lists.
    # In the actual gp_algo.py, these are global. For testing, we can either
    # import them or, if functions are pure, pass them as arguments (not current design).
    unary_ops, binary_ops, ts_ops, DEFAULT_TERMINAL_VALUES, ts_ops_values
)

# --- tree_to_alpha (DEV-041) Tests ---
@pytest.mark.parametrize("tree_node, expected_expression", [
    (Node("close"), "close"),
    (Node("20"), "20"), # ts_ops_value
    (Node("rank", left=Node("open")), "rank(open)"),
    (Node("add", left=Node("high"), right=Node("low")), "add(high,low)"),
    (Node("ts_rank", left=Node("vwap"), right=Node("60")), "ts_rank(vwap,60)"),
    (Node("add", Node("ts_rank", Node("close"), Node("20")), Node("rank", Node("vwap"))),
     "add(ts_rank(close,20),rank(vwap))"),
    (None, ""), # Empty tree
    # Error case: operator missing a child (should return empty string and log error)
    (Node("add", left=Node("close")), ""),
    (Node("ts_rank", left=Node("close")), ""),
    (Node("ts_rank", left=Node("close"), right=Node("invalid_period_val")), ""), # Invalid period value
    (Node("ts_rank", left=Node("close"), right=Node("add", Node("10"), Node("5"))), ""), # Period is not a leaf
    (Node("unknown_op", Node("close")), "") # Unknown operator
])
def test_tree_to_alpha_conversion(tree_node: Optional[Node], expected_expression: str, caplog):
    """测试 tree_to_alpha (DEV-041) 的各种情况。"""
    # Ensure global lists are populated for the test context if not imported directly
    # For this test, gp_algo.py's global lists will be used.

    # Update global terminal_values for this test if necessary, or assume dynamic terminals are used
    # For simplicity, we rely on the default ones and those in ts_ops_values
    # To make tests more robust, could mock these lists or pass them as args if functions supported it.
    # For now, we assume 'close', 'open', 'high', 'low', 'vwap' are in some terminal list accessible by the functions.
    # And '20', '60' are in ts_ops_values.

    # Inject DEFAULT_TERMINAL_VALUES into gp_algo.terminal_values for test if needed
    # Or ensure that _recursive_tree_to_alpha correctly uses dynamic_terminal_values or similar
    # For DEV-041, it was simplified to check against operator lists only for non-leaf nodes.

    # Monkeypatching the global terminal_values for testing specific terminals
    # This is generally not ideal, but gp_algo.py uses global lists.
    # A better design would be to pass these lists as parameters.
    # For now, we'll assume 'close', 'open', etc. are treated as non-operators.

    # from app.core import gp_algo
    # original_terminals = gp_algo.terminal_values
    # gp_algo.terminal_values = ["close", "open", "high", "low", "vwap"] + DEFAULT_TERMINAL_VALUES

    result = tree_to_alpha(tree_node)
    assert result == expected_expression

    if expected_expression == "" and tree_node is not None : # Expect errors to be logged for failed conversions
        assert len(caplog.records) > 0, "Expected error/warning logs for invalid tree conversion"
        # Example: assert "错误" in caplog.text or "无效" in caplog.text

    # gp_algo.terminal_values = original_terminals # Restore original


# --- _tokenize_expression (DEV-042) Tests ---
@pytest.mark.parametrize("expression_str, expected_tokens", [
    ("add(close, open)", ["add", "(", "close", ",", "open", ")"]),
    ("ts_rank(vwap, 20)", ["ts_rank", "(", "vwap", ",", "20", ")"]),
    ("rank(ts_mean(close,40))", ["rank", "(", "ts_mean", "(", "close", ",", "40", ")", ")"]),
    ("  add ( close , open )  ", ["add", "(", "close", ",", "open", ")"]), # With spaces
    ("neg(-1.5)", ["neg", "(", "-1.5", ")"]), # Assuming 'neg' is a unary_op and -1.5 a number
    ("my_field_1", ["my_field_1"]),
    ("123.45", ["123.45"]),
    ("", []),
    ("add(close,)", None), # Invalid syntax, expecting MISMATCH or error
    ("add(close, #open)", None), # Illegal character
])
def test_tokenize_expression(expression_str: str, expected_tokens: Optional[List[str]], caplog):
    """测试 _tokenize_expression (DEV-042) 的各种情况。"""
    # Add 'neg' to unary_ops for the test case if it's not there
    if "neg" not in unary_ops and "neg(-1.5)" in expression_str :
        unary_ops.append("neg") # Temporary addition for test

    tokens = _tokenize_expression(expression_str)
    assert tokens == expected_tokens
    if expected_tokens is None and expression_str != "": # Expect error logs for failed tokenization
         assert len(caplog.records) > 0
         assert "词法分析错误" in caplog.text

    if "neg" in unary_ops and "neg(-1.5)" in expression_str:
        unary_ops.remove("neg") # Clean up

# --- alpha_to_tree (DEV-042) Tests ---
@pytest.mark.parametrize("expression_str, expected_tree_repr", [
    ("close", "Node('close')"),
    ("rank(open)", "Node('rank', left=Node('open'))"),
    ("add(high,low)", "Node('add', left=Node('high'), right=Node('low'))"),
    ("ts_rank(vwap,20)", "Node('ts_rank', left=Node('vwap'), right=Node('20'))"),
    ("add(ts_rank(close,20),rank(vwap))",
     "Node('add', left=Node('ts_rank', left=Node('close'), right=Node('20')), right=Node('rank', left=Node('vwap')))"),
    # Error cases
    ("add(close)", None), # Missing argument
    ("rank(close,open)", None), # Too many arguments for unary
    ("ts_rank(close,open)", None), # Second arg for ts_rank should be a ts_ops_value like "20"
    ("unknown(close)", None), # Unknown operator
    ("add(close,(open)", None), # Mismatched parentheses
    ("close add open", None), # Missing operator syntax
    ("add(close,open) trailing_junk", None) # Trailing characters
])
def test_alpha_to_tree_conversion(expression_str: str, expected_tree_repr: Optional[str], caplog):
    """测试 alpha_to_tree (DEV-042) 的各种情况。"""
    # Note: terminal_values, unary_ops etc. are used by the parser internally.
    # Ensure they are available in the test scope (imported from gp_algo)

    # For this test, we assume 'close', 'open', 'high', 'low', 'vwap' are valid terminals.
    # And '20' is a valid ts_ops_value.
    # This relies on the global lists in gp_algo.py.

    tree = alpha_to_tree(expression_str)

    if expected_tree_repr is None:
        assert tree is None
        if expression_str: # Only expect logs if input was not empty
            assert len(caplog.records) > 0, f"Expected error logs for invalid expression: {expression_str}"
            # assert "解析错误" in caplog.text or "词法分析错误" in caplog.text
    else:
        assert tree is not None, f"Expected tree for '{expression_str}', got None. Logs: {caplog.text}"
        assert repr(tree) == expected_tree_repr
        # For successful parsing, there might be info logs, but not necessarily error logs
        # Check that no ERROR level logs were produced for valid expressions
        error_logs = [rec for rec in caplog.records if rec.levelname == "ERROR"]
        assert not error_logs, f"Unexpected error logs for valid expression '{expression_str}': {error_logs}"


def test_alpha_to_tree_empty_and_whitespace():
    """测试 alpha_to_tree 对空字符串和纯空格字符串的处理。"""
    assert alpha_to_tree("") is None # Or an empty list from tokenizer leading to None tree
    assert alpha_to_tree("   ") is None


# Example of a more complex nested structure for alpha_to_tree
def test_alpha_to_tree_complex_nested():
    """测试 alpha_to_tree 对复杂嵌套表达式的解析。"""
    expr = "ts_rank(add(rank(close),multiply(ts_mean(open,40),-1.5)),60)"
    tree = alpha_to_tree(expr)
    assert tree is not None
    assert tree.value == "ts_rank"
    assert tree.left.value == "add"
    assert tree.right.value == "60"
    assert tree.left.left.value == "rank"
    assert tree.left.left.left.value == "close"
    assert tree.left.right.value == "multiply"
    assert tree.left.right.left.value == "ts_mean"
    assert tree.left.right.left.left.value == "open"
    assert tree.left.right.left.right.value == "40"
    assert tree.left.right.right.value == "-1.5"

# TODO: Add more specific tests for _tokenize_expression, especially for edge cases
# like numbers vs. identifiers, and ensuring all known operators are tokenized correctly.
# TODO: Add tests for _parse_atom if its logic becomes more complex or needs direct testing.
# (Currently, its behavior is well-covered by testing alpha_to_tree)
