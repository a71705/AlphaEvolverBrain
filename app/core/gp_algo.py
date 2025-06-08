# app/core/gp_algo.py
# 遗传编程核心算法模块

# 导入 random 模块用于随机选择和生成
import random
# 导入 typing 中的类型提示，用于增强代码可读性和静态分析
from typing import Optional, List, Any, Tuple, Dict # Added Dict for fitness_fun settings

# 导入 logging 模块用于日志记录
import logging
# 导入 pandas (通常在实际适应度函数中使用，此处为占位符的未来准备)
import pandas as pd


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
    (详细注释见之前实现)
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
    (详细注释见之前实现)
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
    (详细注释见之前实现)
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

def _recursive_tree_to_alpha(node: Optional[Node]) -> str:
    """
    递归辅助函数，用于将表达式树节点转换为 Alpha 表达式字符串。
    (详细注释见之前实现)
    """
    if node is None:
        logger.warning("_recursive_tree_to_alpha: 遇到 None 节点。")
        return ""

    if node.value in all_terminals:
        return str(node.value)

    elif node.value in unary_ops:
        if node.left:
            left_expr = _recursive_tree_to_alpha(node.left)
            return f"{node.value}({left_expr})"
        else:
            logger.error(f"一元操作符 '{node.value}' 缺少左子节点。树结构错误。")
            return f"{node.value}(MISSING_OPERAND)"

    elif node.value in binary_ops or node.value in ts_ops:
        if node.left and node.right:
            left_expr = _recursive_tree_to_alpha(node.left)
            right_expr = _recursive_tree_to_alpha(node.right)
            return f"{node.value}({left_expr},{right_expr})"
        elif node.left:
             logger.error(f"操作符 '{node.value}' 缺少右子节点。树结构错误。")
             return f"{node.value}({_recursive_tree_to_alpha(node.left)},MISSING_RIGHT_OPERAND)"
        elif node.right:
             logger.error(f"操作符 '{node.value}' 缺少左子节点。树结构错误。")
             return f"{node.value}(MISSING_LEFT_OPERAND,{_recursive_tree_to_alpha(node.right)})"
        else:
            logger.error(f"操作符 '{node.value}' 同时缺少左右子节点。树结构错误。")
            return f"{node.value}(MISSING_BOTH_OPERANDS)"

    else:
        logger.error(f"遇到未知节点类型或值: '{node.value}'。无法转换为表达式。")
        return f"UNKNOWN_NODE_VALUE({node.value!r})"

def tree_to_alpha(tree_root: Node) -> str:
    """
    将整个表达式树转换为 Alpha 表达式字符串。
    (详细注释见之前实现)
    """
    if not isinstance(tree_root, Node):
        logger.error(f"tree_to_alpha接收到的输入不是Node类型: {type(tree_root)}")
        return ""

    logger.debug(f"开始将树转换为 Alpha 表达式: {tree_root!r}")
    expression = _recursive_tree_to_alpha(tree_root)
    logger.info(f"树成功转换为 Alpha 表达式: '{expression}'")
    return expression

def fitness_fun(
    alpha_expression: str,
    # data_df: pd.DataFrame,
    # settings: Optional[Dict[str, Any]] = None
) -> float:
    """
    计算给定 Alpha 表达式的适应度分数。
    【占位符实现】
    (详细注释见之前实现)
    """
    logger.warning(
        f"fitness_fun: 当前为占位符实现。正在为表达式 '{alpha_expression}' 返回伪适应度分数。"
        "请替换为实际的适应度计算逻辑。"
    )

    base_score = 0.0
    if alpha_expression:
        base_score = min(len(alpha_expression) / 100.0, 1.0)

    random_factor = random.uniform(-0.1, 0.1)
    pseudo_fitness = round(base_score + random_factor, 4)

    logger.info(f"为表达式 '{alpha_expression}' 计算的伪适应度分数为: {pseudo_fitness}")
    return pseudo_fitness

def copy_tree(original_node: Optional[Node]) -> Optional[Node]:
    """
    递归地深度复制一个表达式树。

    Args:
        original_node (Optional[Node]): 要复制的树的根节点。

    Returns:
        Optional[Node]: 新创建的树的根节点副本，如果原始节点为None则返回None。
    """
    if original_node is None:
        return None

    left_copy = copy_tree(original_node.left)
    right_copy = copy_tree(original_node.right)

    return Node(original_node.value, left_copy, right_copy)

def _collect_nodes_recursive(current_node: Optional[Node], nodes_list: List[Node]):
    """
    递归辅助函数，用于收集树中所有节点。

    Args:
        current_node (Optional[Node]): 当前正在访问的节点。
        nodes_list (List[Node]): 用于累积收集到的节点的列表。
    """
    if current_node is not None:
        nodes_list.append(current_node)
        _collect_nodes_recursive(current_node.left, nodes_list)
        _collect_nodes_recursive(current_node.right, nodes_list)

def get_all_nodes(root_node: Node) -> List[Node]:
    """
    获取给定树中的所有节点列表。

    Args:
        root_node (Node): 树的根节点。

    Returns:
        List[Node]: 包含树中所有节点的列表。
    """
    collected_nodes: List[Node] = []
    if root_node is not None: # 确保根节点不是None才开始收集
        _collect_nodes_recursive(root_node, collected_nodes)
    return collected_nodes

def get_random_node(root_node: Node) -> Optional[Node]:
    """
    从树中随机选择一个节点。

    Args:
        root_node (Node): 树的根节点。

    Returns:
        Optional[Node]: 随机选择的节点，如果树为空或无效则返回 None。
    """
    if root_node is None: # 处理空树的情况
        logger.warning("get_random_node: 尝试从空树中选择节点。")
        return None
    all_nodes = get_all_nodes(root_node)
    if not all_nodes:
        logger.warning("get_random_node: 未能从树中收集到任何节点。")
        return None
    return random.choice(all_nodes)

def mutate_random_node(
    original_tree_root: Node,
    max_mutation_depth: int = 1,
    available_terminals: Optional[List[str]] = None,
    available_unary_ops: Optional[List[str]] = None,
    available_binary_ops: Optional[List[str]] = None,
    available_ts_ops: Optional[List[str]] = None,
    available_ts_ops_params: Optional[List[str]] = None
) -> Optional[Node]: # 返回 Optional[Node] 以处理原始树为空的情况
    """
    对树进行变异操作：随机选择一个节点，并用一个新的随机生成的子树替换它。
    (详细注释见之前实现)
    """
    if original_tree_root is None:
        logger.warning("mutate_random_node: 尝试对空树进行变异，返回None。")
        return None

    mutated_tree_root = copy_tree(original_tree_root)
    if mutated_tree_root is None:
         logger.error("mutate_random_node: 复制树失败。")
         return original_tree_root

    node_to_mutate = get_random_node(mutated_tree_root)

    if node_to_mutate is None:
        logger.warning("mutate_random_node: 未能从树中选择节点进行变异，返回原始树副本。")
        return mutated_tree_root

    logger.debug(f"变异操作：选中节点 {node_to_mutate!r} (值为 '{node_to_mutate.value}') 进行变异。")

    if max_mutation_depth == 0:
        new_subtree_flag = 0
    else:
        new_subtree_flag = random.choice([0, 1, 2, 3])

    replacement_subtree_root = depth_one_tree(
        flag=new_subtree_flag,
        available_terminals=available_terminals,
        available_unary_ops=available_unary_ops,
        available_binary_ops=available_binary_ops,
        available_ts_ops=available_ts_ops,
        available_ts_ops_params=available_ts_ops_params
    )

    logger.debug(f"变异操作：生成替换子树 {replacement_subtree_root!r}")

    node_to_mutate.value = replacement_subtree_root.value
    node_to_mutate.left = replacement_subtree_root.left
    node_to_mutate.right = replacement_subtree_root.right

    logger.info(f"节点 (在副本中) 已变异。新值为 '{node_to_mutate.value}'。")
    return mutated_tree_root

def crossover(parent1_root: Node, parent2_root: Node) -> Tuple[Optional[Node], Optional[Node]]: # 返回 Optional Nodes
    """
    对两个父树进行交叉操作，生成两个子树。
    (详细注释见之前实现)
    """
    if parent1_root is None or parent2_root is None:
        logger.error("交叉操作：一个或两个父树为空。返回原始树（的副本，如果非空）。")
        return (copy_tree(parent1_root), copy_tree(parent2_root))

    child1_root = copy_tree(parent1_root)
    child2_root = copy_tree(parent2_root)

    if child1_root is None or child2_root is None:
        logger.error("交叉操作中复制父树失败。")
        # 返回原始树的副本，以防万一其中一个复制成功
        return (copy_tree(parent1_root) if child1_root is None else child1_root,
                copy_tree(parent2_root) if child2_root is None else child2_root)


    crossover_point1 = get_random_node(child1_root)
    crossover_point2 = get_random_node(child2_root)

    if crossover_point1 is None or crossover_point2 is None:
        logger.warning("交叉操作：未能从一个或两个子树中选择交叉点。返回原始树的副本。")
        return (child1_root, child2_root)

    logger.debug(f"交叉操作：选中 child1 的节点 {crossover_point1!r} (value: '{crossover_point1.value}')")
    logger.debug(f"交叉操作：选中 child2 的节点 {crossover_point2!r} (value: '{crossover_point2.value}')")

    p1_value, p1_left, p1_right = crossover_point1.value, crossover_point1.left, crossover_point1.right

    crossover_point1.value = crossover_point2.value
    crossover_point1.left = crossover_point2.left
    crossover_point1.right = crossover_point2.right

    crossover_point2.value = p1_value
    crossover_point2.left = p1_left
    crossover_point2.right = p1_right

    logger.info("交叉操作完成。")
    return (child1_root, child2_root)

# 后续将在此处定义遗传算法主循环等
