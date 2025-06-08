# app/core/gp_algo.py
# 遗传编程核心算法模块

# 导入 random 模块用于随机选择和生成
import random
# 导入 typing 中的类型提示，用于增强代码可读性和静态分析
from typing import Optional, List, Any, Tuple # Tuple for crossover return

# 导入 logging 模块用于日志记录
import logging

# 获取当前模块的 logger 实例
# 日志将以 "app.core.gp_algo" 的名称记录
logger = logging.getLogger(__name__)

class Node:
    """
    表示遗传编程中表达式树的一个节点。
    每个节点可以是一个操作符（内部节点）或一个终端值（叶节点）。
    """
    def __init__(self, value: Any, left: Optional['Node'] = None, right: Optional['Node'] = None):
        """
        初始化一个节点。

        Args:
            value (Any): 此节点存储的值（例如，操作符如 'add', 'ts_rank'；终端如 'close', 'vwap', 数值如 '20'）。
            left (Optional[Node]): 左子节点。对于一元操作符，这通常是其参数。对于二元操作符，这是第一个参数。
            right (Optional[Node]): 右子节点。对于一元操作符，通常为 None。对于二元操作符，这是第二个参数。
        """
        self.value = value  # 节点的值 (操作符或终端)
        self.left = left    # 左子节点
        self.right = right  # 右子节点

    def __repr__(self) -> str:
        """
        返回节点的字符串表示形式，主要用于调试。
        例如: Node('add', Node('close'), Node('open'))
        """
        if self.left is None and self.right is None: # 叶节点
            return f"Node({self.value!r})"
        elif self.right is None: # 可能是一元操作符
             return f"Node({self.value!r}, {self.left!r})" # !r 会调用子节点的 __repr__
        else: # 二元操作符
            return f"Node({self.value!r}, {self.left!r}, {self.right!r})"

# 定义 Alpha 表达式的构建模块 (building blocks)
terminal_values: List[str] = [
    "close", "open", "high", "low", "vwap",
    "adv20", "volume", "cap", "returns", "dividend"
]
ts_ops: List[str] = [
    "ts_zscore", "ts_rank", "ts_arg_max", "ts_arg_min",
    "ts_backfill", "ts_delta", "ts_ir", "ts_mean",
    "ts_median", "ts_product", "ts_std_dev"
]
binary_ops: List[str] = [
    "add", "subtract", "divide", "multiply", "max", "min"
]
ts_ops_values: List[str] = ["20", "40", "60", "120", "240"]
unary_ops: List[str] = [
    "rank", "zscore", "winsorize", "normalize",
    "rank_by_side", "sigmoid", "pasteurize", "log"
]
all_operators: List[str] = ts_ops + binary_ops + unary_ops
all_terminals: List[str] = terminal_values + ts_ops_values

def depth_one_tree(
    flag: int,
    available_terminals: Optional[List[str]] = None,
    available_unary_ops: Optional[List[str]] = None,
    available_binary_ops: Optional[List[str]] = None,
    available_ts_ops: Optional[List[str]] = None,
    available_ts_ops_params: Optional[List[str]] = None
) -> Node:
    """
    生成一个深度最多为1的随机树 (操作符 + 叶子节点) 或深度为0的树 (单个叶子节点)。

    Args:
        flag (int): 控制生成节点类型的标志。
                    (假设: 0=终端, 1=一元操作, 2=二元操作, 3=时间序列操作)
        available_terminals (Optional[List[str]]): 可用的基础终端值。默认为全局 `terminal_values`。
        available_unary_ops (Optional[List[str]]): 可用的一元操作符。默认为全局 `unary_ops`。
        available_binary_ops (Optional[List[str]]): 可用的二元操作符。默认为全局 `binary_ops`。
        available_ts_ops (Optional[List[str]]): 可用的时间序列操作符。默认为全局 `ts_ops`。
        available_ts_ops_params (Optional[List[str]]): 可用的时间序列操作参数值。默认为全局 `ts_ops_values`。

    Returns:
        Node: 生成的树的根节点。
    """
    terminals = available_terminals if available_terminals is not None else terminal_values
    unary = available_unary_ops if available_unary_ops is not None else unary_ops
    binary = available_binary_ops if available_binary_ops is not None else binary_ops
    ts = available_ts_ops if available_ts_ops is not None else ts_ops
    ts_params = available_ts_ops_params if available_ts_ops_params is not None else ts_ops_values

    if not terminals:
        logger.error("depth_one_tree: 终端值列表为空，无法生成树。")
        raise ValueError("终端值列表不能为空。")

    node = None
    op_choice = ""

    if flag == 0:
        op_choice = "终端"
        value = random.choice(terminals)
        node = Node(value)
    elif flag == 1 and unary:
        op_choice = "一元"
        operator = random.choice(unary)
        operand = Node(random.choice(terminals))
        node = Node(operator, left=operand)
    elif flag == 2 and binary:
        op_choice = "二元"
        operator = random.choice(binary)
        operand1 = Node(random.choice(terminals))
        operand2 = Node(random.choice(terminals))
        node = Node(operator, left=operand1, right=operand2)
    elif flag == 3 and ts and ts_params:
        op_choice = "时间序列"
        operator = random.choice(ts)
        operand1 = Node(random.choice(terminals))
        operand2 = Node(random.choice(ts_params))
        node = Node(operator, left=operand1, right=operand2)
    else:
        op_choice = f"终端 (备选，flag={flag} 无效或操作符列表为空)"
        logger.warning(f"depth_one_tree: flag={flag} 无效或所需操作符列表为空，默认创建终端节点。")
        value = random.choice(terminals)
        node = Node(value)

    logger.debug(f"depth_one_tree (flag={flag}, choice='{op_choice}') 生成: {node}")
    return node

def depth_two_tree(
    flag: int,
    available_terminals: Optional[List[str]] = None,
    available_unary_ops: Optional[List[str]] = None,
    available_binary_ops: Optional[List[str]] = None,
    available_ts_ops: Optional[List[str]] = None,
    available_ts_ops_params: Optional[List[str]] = None
) -> Node:
    """
    生成一个深度正好为2的随机树。
    这意味着根节点是一个操作符，其至少一个子节点是一个深度为1的子树（操作符+终端），
    或者两个子节点都是深度为1的子树。

    Args:
        flag (int): 控制根节点操作符类型的标志。
                    (假设: 0=一元, 1=二元, 2=时间序列)
        (其他参数与 depth_one_tree 类似)

    Returns:
        Node: 生成的深度为2的树的根节点。
    """
    terminals = available_terminals if available_terminals is not None else terminal_values
    unary = available_unary_ops if available_unary_ops is not None else unary_ops
    binary = available_binary_ops if available_binary_ops is not None else binary_ops
    ts = available_ts_ops if available_ts_ops is not None else ts_ops
    ts_params = available_ts_ops_params if available_ts_ops_params is not None else ts_ops_values

    node = None
    op_choice = ""

    if flag == 0 and unary:
        op_choice = "一元"
        operator = random.choice(unary)
        child_flag = random.choice([1, 2, 3])
        child_node = depth_one_tree(child_flag, terminals, unary, binary, ts, ts_params)
        node = Node(operator, left=child_node)

    elif flag == 1 and binary:
        op_choice = "二元"
        operator = random.choice(binary)
        if random.random() < 0.5:
            child1_flag = random.choice([1, 2, 3])
            child1 = depth_one_tree(child1_flag, terminals, unary, binary, ts, ts_params)
            child2_flag = random.choice([0, 1, 2, 3])
            child2 = depth_one_tree(child2_flag, terminals, unary, binary, ts, ts_params)
        else:
            child1_flag = random.choice([0, 1, 2, 3])
            child1 = depth_one_tree(child1_flag, terminals, unary, binary, ts, ts_params)
            child2_flag = random.choice([1, 2, 3])
            child2 = depth_one_tree(child2_flag, terminals, unary, binary, ts, ts_params)
        node = Node(operator, left=child1, right=child2)

    elif flag == 2 and ts and ts_params:
        op_choice = "时间序列"
        operator = random.choice(ts)
        child1_flag = random.choice([1, 2, 3])
        operand1 = depth_one_tree(child1_flag, terminals, unary, binary, ts, ts_params)
        operand2 = Node(random.choice(ts_params))
        node = Node(operator, left=operand1, right=operand2)

    else:
        op_choice = f"备选 (flag={flag} 无效或列表为空)"
        logger.warning(f"depth_two_tree: flag={flag} 无效或操作符列表为空，尝试其他类型。")
        valid_flags = []
        if unary: valid_flags.append(0)
        if binary: valid_flags.append(1)
        if ts and ts_params: valid_flags.append(2)

        if not valid_flags:
            logger.error("depth_two_tree: 所有操作符列表均为空，无法生成深度2的树。")
            raise ValueError("无法生成深度2的树，所有操作符列表均为空。")

        new_flag = random.choice(valid_flags)
        node = depth_two_tree(new_flag, terminals, unary, binary, ts, ts_params)

    logger.debug(f"depth_two_tree (flag={flag}, choice='{op_choice}') 生成: {node}")
    return node

def depth_three_tree(
    flag: int,
    available_terminals: Optional[List[str]] = None,
    available_unary_ops: Optional[List[str]] = None,
    available_binary_ops: Optional[List[str]] = None,
    available_ts_ops: Optional[List[str]] = None,
    available_ts_ops_params: Optional[List[str]] = None
) -> Node:
    """
    生成一个深度正好为3的随机树。
    根节点是一个操作符，其至少一个子节点是一个深度为2的子树。

    Args:
        flag (int): 控制根节点操作符类型的标志。
                    (假设: 0=一元, 1=二元, 2=时间序列)
        (其他参数与 depth_one_tree 类似)

    Returns:
        Node: 生成的深度为3的树的根节点。
    """
    terminals = available_terminals if available_terminals is not None else terminal_values
    unary = available_unary_ops if available_unary_ops is not None else unary_ops
    binary = available_binary_ops if available_binary_ops is not None else binary_ops
    ts = available_ts_ops if available_ts_ops is not None else ts_ops
    ts_params = available_ts_ops_params if available_ts_ops_params is not None else ts_ops_values

    node = None
    op_choice = ""

    if flag == 0 and unary:
        op_choice = "一元"
        operator = random.choice(unary)
        child_flag = random.choice([0, 1, 2])
        child_node = depth_two_tree(child_flag, terminals, unary, binary, ts, ts_params)
        node = Node(operator, left=child_node)

    elif flag == 1 and binary:
        op_choice = "二元"
        operator = random.choice(binary)
        if random.random() < 0.5:
            child1_flag = random.choice([0, 1, 2])
            child1 = depth_two_tree(child1_flag, terminals, unary, binary, ts, ts_params)
            child2_flag = random.choice([0, 1, 2, 3])
            child2 = depth_one_tree(child2_flag, terminals, unary, binary, ts, ts_params)
        else:
            child1_flag = random.choice([0, 1, 2, 3])
            child1 = depth_one_tree(child1_flag, terminals, unary, binary, ts, ts_params)
            child2_flag = random.choice([0, 1, 2])
            child2 = depth_two_tree(child2_flag, terminals, unary, binary, ts, ts_params)
        node = Node(operator, left=child1, right=child2)

    elif flag == 2 and ts and ts_params:
        op_choice = "时间序列"
        operator = random.choice(ts)
        child1_flag = random.choice([0, 1, 2])
        operand1 = depth_two_tree(child1_flag, terminals, unary, binary, ts, ts_params)
        operand2 = Node(random.choice(ts_params))
        node = Node(operator, left=operand1, right=operand2)

    else:
        op_choice = f"备选 (flag={flag} 无效或列表为空)"
        logger.warning(f"depth_three_tree: flag={flag} 无效或操作符列表为空，尝试其他类型。")
        valid_flags = []
        if unary: valid_flags.append(0)
        if binary: valid_flags.append(1)
        if ts and ts_params: valid_flags.append(2)

        if not valid_flags:
            logger.error("depth_three_tree: 所有操作符列表均为空，无法生成深度3的树。")
            raise ValueError("无法生成深度3的树，所有操作符列表均为空。")

        new_flag = random.choice(valid_flags)
        node = depth_three_tree(new_flag, terminals, unary, binary, ts, ts_params)

    logger.debug(f"depth_three_tree (flag={flag}, choice='{op_choice}') 生成: {node}")
    return node

# 后续将在此处定义其他遗传编程相关函数 (如交叉、变异、树转表达式等)
