# app/core/gp_algo.py
# 遗传编程核心算法模块

# 导入 random 模块用于随机选择和生成
import random
# 导入 typing 中的类型提示，用于增强代码可读性和静态分析
from typing import Optional, List, Any, Tuple, Dict # Added Dict for fitness_fun settings
# 导入 re 模块用于正则表达式词法分析
import re

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
ts_ops_values: List[str] = ["20", "40", "60", "120", "240"] # 这些也是终端
unary_ops: List[str] = [
    "rank", "zscore", "winsorize", "normalize",
    "rank_by_side", "sigmoid", "pasteurize", "log"
]
all_operators: List[str] = ts_ops + binary_ops + unary_ops
all_terminals: List[str] = terminal_values + ts_ops_values # 包含数值参数作为终端

def tokenize_expression(expression_str: str) -> List[str]:
    """
    将 Alpha 表达式字符串分解为标记列表。
    标记可以是操作符、终端、数字、括号或逗号。

    Args:
        expression_str (str): 要进行词法分析的 Alpha 表达式字符串。

    Returns:
        List[str]: 从表达式中提取的标记列表。
    """
    if not expression_str:
        logger.debug("tokenize_expression: 输入的表达式字符串为空。")
        return []

    pattern = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[(),]")
    tokens = pattern.findall(expression_str)

    logger.debug(f"表达式 '{expression_str}' 被词法分析为: {tokens}")
    return tokens

def alpha_to_tree(expression_str: str) -> Optional[Node]:
    """
    将 Alpha 表达式字符串转换为 Node 树结构。
    使用递归下降法进行解析，处理函数式表示法如 operator(arg1, arg2)。

    Args:
        expression_str (str): 要解析的 Alpha 表达式字符串。

    Returns:
        Optional[Node]: 构建的树的根节点。如果解析失败则返回 None。
    """
    if not expression_str or not expression_str.strip():
        logger.error("alpha_to_tree: 输入的表达式字符串为空或仅包含空白。")
        return None

    tokens = tokenize_expression(expression_str)
    if not tokens:
        logger.error(f"alpha_to_tree: 表达式 '{expression_str}' 词法分析后为空列表或无效。")
        return None

    pos = 0

    def peek_current_token() -> Optional[str]:
        if pos < len(tokens):
            return tokens[pos]
        return None

    def consume_expected_token(expected: Optional[str] = None) -> str:
        nonlocal pos
        current_token_val = peek_current_token()

        if current_token_val is None:
            err_msg = f"解析错误: 期望 token '{expected if expected else '更多输入'}' 但已到达输入末尾。"
            logger.error(err_msg)
            raise SyntaxError(err_msg)

        if expected and current_token_val != expected:
            context_start = max(0, pos - 2)
            context_end = min(len(tokens), pos + 3)
            context_str = "' ... " + " ".join(tokens[context_start:pos]) + " >>" + tokens[pos] + "<< " + " ".join(tokens[pos+1:context_end]) + " ... '"
            err_msg = f"解析错误: 在位置 {pos} 期望 token '{expected}' 但得到 '{current_token_val}'. 上下文: {context_str}"
            logger.error(err_msg)
            raise SyntaxError(err_msg)

        pos += 1
        return current_token_val

    def parse_atom_recursive_internal() -> Node:
        token_val = peek_current_token()
        if token_val is None:
            raise SyntaxError("解析错误: 期望一个原子表达式（终端或数字），但输入已结束。")

        is_number_token = False
        try:
            # 尝试将 token 转换为 float。如果成功，它就是数字。
            # 注意：我们仍然以字符串形式存储数字节点的值，以保持与 'ts_ops_values' (如 '20') 的一致性。
            # 实际的数值转换应在计算 Alpha 值时进行。
            float(token_val)
            is_number_token = True
        except ValueError:
            is_number_token = False

        # all_terminals 已经包含了 terminal_values 和 ts_ops_values
        if token_val in all_terminals or is_number_token:
            consume_expected_token()
            return Node(token_val)
        else:
            raise SyntaxError(f"解析错误: 在位置 {pos} 期望一个终端或数字，但得到 '{token_val}'. 上下文: '{' '.join(tokens[max(0,pos-2):min(len(tokens),pos+3)])}'")

    def parse_expression_recursive_internal() -> Node:
        token_val = peek_current_token()
        if token_val is None:
            raise SyntaxError("解析错误: 期望表达式，但输入已结束。")

        if token_val in all_operators: # 检查是否是已知操作符
            op_name = consume_expected_token()
            consume_expected_token("(")

            args = []
            if peek_current_token() == ')':
                logger.debug(f"操作符 '{op_name}' 参数列表为空。")
            else:
                args.append(parse_expression_recursive_internal())
                while peek_current_token() == ',':
                    consume_expected_token(",")
                    if peek_current_token() == ')': # 避免 "op(arg1,)"
                        raise SyntaxError(f"解析错误: 操作符 '{op_name}' 在逗号后缺少参数。")
                    args.append(parse_expression_recursive_internal())

            consume_expected_token(")")

            if op_name in unary_ops:
                if len(args) == 1:
                    return Node(op_name, left=args[0])
                else:
                    raise SyntaxError(f"解析错误: 一元操作符 '{op_name}' 期望1个参数，得到 {len(args)}。参数: {args}")
            elif op_name in binary_ops or op_name in ts_ops: # ts_ops 也被视为二元结构
                if len(args) == 2:
                    return Node(op_name, left=args[0], right=args[1])
                else:
                    raise SyntaxError(f"解析错误: 二元/时间序列操作符 '{op_name}' 期望2个参数，得到 {len(args)}。参数: {args}")
            # 此处不应到达，因为 token_val 已经在 all_operators 中
        else: # 如果不是操作符，则必须是原子（终端或数字）
            return parse_atom_recursive_internal()

    try:
        parsed_tree = parse_expression_recursive_internal()
        if pos != len(tokens): # 检查是否所有 token 都被消耗
            remaining_tokens = tokens[pos:]
            logger.error(f"alpha_to_tree: 解析成功，但表达式 '{expression_str}' 末尾有未消耗的标记: {remaining_tokens}。")
            # 根据严格程度，可以选择返回 None 或抛出错误
            raise SyntaxError(f"解析错误: 表达式末尾有未消耗的标记: {remaining_tokens}")

        logger.info(f"表达式 '{expression_str}' 成功解析为树。")
        logger.debug(f"解析得到的树: {parsed_tree!r}")
        return parsed_tree
    except SyntaxError as e:
        logger.error(f"解析表达式 '{expression_str}' 时发生语法错误: {e}")
        return None
    except Exception as e: # 捕获其他潜在的运行时错误
        logger.error(f"解析表达式 '{expression_str}' 时发生未知错误: {e}", exc_info=True)
        return None

def depth_one_tree(
    flag: int,
    available_terminals: Optional[List[str]] = None,
    available_unary_ops: Optional[List[str]] = None,
    available_binary_ops: Optional[List[str]] = None,
    available_ts_ops: Optional[List[str]] = None,
    available_ts_ops_params: Optional[List[str]] = None
) -> Node:
    terminals = available_terminals if available_terminals is not None else all_terminals # 使用 all_terminals
    unary = available_unary_ops if available_unary_ops is not None else unary_ops
    binary = available_binary_ops if available_binary_ops is not None else binary_ops
    ts = available_ts_ops if available_ts_ops is not None else ts_ops
    # ts_params 已包含在 all_terminals 中，但特定于 ts_op 的右子节点仍可从 ts_ops_values 选择
    ts_specific_params = available_ts_ops_params if available_ts_ops_params is not None else ts_ops_values

    if not terminals:
        logger.error("depth_one_tree: 终端值列表为空，无法生成树。")
        raise ValueError("终端值列表不能为空。")

    node = None
    op_choice = ""

    if flag == 0:
        op_choice = "终端"
        value = random.choice(terminals) # 从所有终端中选择
        node = Node(value)
    elif flag == 1 and unary:
        op_choice = "一元"
        operator = random.choice(unary)
        operand = Node(random.choice(terminals)) # 操作数可以是任何终端
        node = Node(operator, left=operand)
    elif flag == 2 and binary:
        op_choice = "二元"
        operator = random.choice(binary)
        operand1 = Node(random.choice(terminals))
        operand2 = Node(random.choice(terminals))
        node = Node(operator, left=operand1, right=operand2)
    elif flag == 3 and ts and ts_specific_params:
        op_choice = "时间序列"
        operator = random.choice(ts)
        operand1 = Node(random.choice(terminal_values)) # ts_op 第一个参数通常是数据字段
        operand2 = Node(random.choice(ts_specific_params))
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
    terminals = available_terminals if available_terminals is not None else all_terminals
    unary = available_unary_ops if available_unary_ops is not None else unary_ops
    binary = available_binary_ops if available_binary_ops is not None else binary_ops
    ts = available_ts_ops if available_ts_ops is not None else ts_ops
    ts_specific_params = available_ts_ops_params if available_ts_ops_params is not None else ts_ops_values
    node = None
    op_choice = ""
    if flag == 0 and unary:
        op_choice = "一元"
        operator = random.choice(unary)
        child_flag = random.choice([1, 2, 3])
        child_node = depth_one_tree(child_flag, terminals, unary, binary, ts, ts_specific_params)
        node = Node(operator, left=child_node)
    elif flag == 1 and binary:
        op_choice = "二元"
        operator = random.choice(binary)
        if random.random() < 0.5:
            child1_flag = random.choice([1, 2, 3])
            child1 = depth_one_tree(child1_flag, terminals, unary, binary, ts, ts_specific_params)
            child2_flag = random.choice([0, 1, 2, 3])
            child2 = depth_one_tree(child2_flag, terminals, unary, binary, ts, ts_specific_params)
        else:
            child1_flag = random.choice([0, 1, 2, 3])
            child1 = depth_one_tree(child1_flag, terminals, unary, binary, ts, ts_specific_params)
            child2_flag = random.choice([1, 2, 3])
            child2 = depth_one_tree(child2_flag, terminals, unary, binary, ts, ts_specific_params)
        node = Node(operator, left=child1, right=child2)
    elif flag == 2 and ts and ts_specific_params:
        op_choice = "时间序列"
        operator = random.choice(ts)
        child1_flag = random.choice([1, 2, 3])
        operand1 = depth_one_tree(child1_flag, terminal_values, unary, binary, ts, ts_specific_params) # 确保第一个是数据字段或其组合
        operand2 = Node(random.choice(ts_specific_params))
        node = Node(operator, left=operand1, right=operand2)
    else:
        op_choice = f"备选 (flag={flag} 无效或列表为空)"
        logger.warning(f"depth_two_tree: flag={flag} 无效或操作符列表为空，尝试其他类型。")
        valid_flags = []
        if unary: valid_flags.append(0)
        if binary: valid_flags.append(1)
        if ts and ts_specific_params: valid_flags.append(2)
        if not valid_flags:
            logger.error("depth_two_tree: 所有操作符列表均为空，无法生成深度2的树。")
            raise ValueError("无法生成深度2的树，所有操作符列表均为空。")
        new_flag = random.choice(valid_flags)
        node = depth_two_tree(new_flag, terminals, unary, binary, ts, ts_specific_params)
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
    terminals = available_terminals if available_terminals is not None else all_terminals
    unary = available_unary_ops if available_unary_ops is not None else unary_ops
    binary = available_binary_ops if available_binary_ops is not None else binary_ops
    ts = available_ts_ops if available_ts_ops is not None else ts_ops
    ts_specific_params = available_ts_ops_params if available_ts_ops_params is not None else ts_ops_values
    node = None
    op_choice = ""
    if flag == 0 and unary:
        op_choice = "一元"
        operator = random.choice(unary)
        child_flag = random.choice([0, 1, 2])
        child_node = depth_two_tree(child_flag, terminals, unary, binary, ts, ts_specific_params)
        node = Node(operator, left=child_node)
    elif flag == 1 and binary:
        op_choice = "二元"
        operator = random.choice(binary)
        if random.random() < 0.5:
            child1_flag = random.choice([0, 1, 2])
            child1 = depth_two_tree(child1_flag, terminals, unary, binary, ts, ts_specific_params)
            child2_flag = random.choice([0, 1, 2, 3])
            child2 = depth_one_tree(child2_flag, terminals, unary, binary, ts, ts_specific_params)
        else:
            child1_flag = random.choice([0, 1, 2, 3])
            child1 = depth_one_tree(child1_flag, terminals, unary, binary, ts, ts_specific_params)
            child2_flag = random.choice([0, 1, 2])
            child2 = depth_two_tree(child2_flag, terminals, unary, binary, ts, ts_specific_params)
        node = Node(operator, left=child1, right=child2)
    elif flag == 2 and ts and ts_specific_params:
        op_choice = "时间序列"
        operator = random.choice(ts)
        child1_flag = random.choice([0, 1, 2])
        operand1 = depth_two_tree(child1_flag, terminal_values, unary, binary, ts, ts_specific_params) # 第一个参数是基于数据字段的树
        operand2 = Node(random.choice(ts_specific_params))
        node = Node(operator, left=operand1, right=operand2)
    else:
        op_choice = f"备选 (flag={flag} 无效或列表为空)"
        logger.warning(f"depth_three_tree: flag={flag} 无效或操作符列表为空，尝试其他类型。")
        valid_flags = [];
        if unary: valid_flags.append(0)
        if binary: valid_flags.append(1)
        if ts and ts_specific_params: valid_flags.append(2)
        if not valid_flags:
            logger.error("depth_three_tree: 所有操作符列表均为空，无法生成深度3的树。")
            raise ValueError("无法生成深度3的树，所有操作符列表均为空。")
        new_flag = random.choice(valid_flags)
        node = depth_three_tree(new_flag, terminals, unary, binary, ts, ts_specific_params)
    logger.debug(f"depth_three_tree (flag={flag}, choice='{op_choice}') 生成: {node}")
    return node

def _recursive_tree_to_alpha(node: Optional[Node]) -> str:
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
    if not isinstance(tree_root, Node):
        logger.error(f"tree_to_alpha接收到的输入不是Node类型: {type(tree_root)}")
        return ""
    logger.debug(f"开始将树转换为 Alpha 表达式: {tree_root!r}")
    expression = _recursive_tree_to_alpha(tree_root)
    logger.info(f"树成功转换为 Alpha 表达式: '{expression}'")
    return expression

def fitness_fun(alpha_expression: str) -> float:
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
    if original_node is None: return None
    left_copy = copy_tree(original_node.left)
    right_copy = copy_tree(original_node.right)
    return Node(original_node.value, left_copy, right_copy)

def _collect_nodes_recursive(current_node: Optional[Node], nodes_list: List[Node]):
    if current_node is not None:
        nodes_list.append(current_node)
        _collect_nodes_recursive(current_node.left, nodes_list)
        _collect_nodes_recursive(current_node.right, nodes_list)

def get_all_nodes(root_node: Node) -> List[Node]:
    collected_nodes: List[Node] = []
    if root_node is not None:
        _collect_nodes_recursive(root_node, collected_nodes)
    return collected_nodes

def get_random_node(root_node: Node) -> Optional[Node]:
    if root_node is None:
        logger.warning("get_random_node: 尝试从空树中选择节点。")
        return None
    all_nodes = get_all_nodes(root_node)
    if not all_nodes:
        logger.warning("get_random_node: 未能从树中收集到任何节点。")
        return None
    return random.choice(all_nodes)

def mutate_random_node(
    original_tree_root: Node, max_mutation_depth: int = 1,
    available_terminals: Optional[List[str]] = None,
    available_unary_ops: Optional[List[str]] = None,
    available_binary_ops: Optional[List[str]] = None,
    available_ts_ops: Optional[List[str]] = None,
    available_ts_ops_params: Optional[List[str]] = None
) -> Optional[Node]:
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
    if max_mutation_depth == 0: new_subtree_flag = 0
    else: new_subtree_flag = random.choice([0, 1, 2, 3])
    replacement_subtree_root = depth_one_tree(
        flag=new_subtree_flag, available_terminals=available_terminals,
        available_unary_ops=available_unary_ops, available_binary_ops=available_binary_ops,
        available_ts_ops=available_ts_ops, available_ts_ops_params=available_ts_ops_params
    )
    logger.debug(f"变异操作：生成替换子树 {replacement_subtree_root!r}")
    node_to_mutate.value = replacement_subtree_root.value
    node_to_mutate.left = replacement_subtree_root.left
    node_to_mutate.right = replacement_subtree_root.right
    logger.info(f"节点 (在副本中) 已变异。新值为 '{node_to_mutate.value}'。")
    return mutated_tree_root

def crossover(parent1_root: Node, parent2_root: Node) -> Tuple[Optional[Node], Optional[Node]]:
    if parent1_root is None or parent2_root is None:
        logger.error("交叉操作：一个或两个父树为空。返回原始树（的副本，如果非空）。")
        return (copy_tree(parent1_root), copy_tree(parent2_root))
    child1_root = copy_tree(parent1_root)
    child2_root = copy_tree(parent2_root)
    if child1_root is None or child2_root is None:
        logger.error("交叉操作中复制父树失败。")
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

# 主测试块
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG) # 设置日志级别为 DEBUG 以查看详细输出
    logger.info("--- 开始遗传编程算法模块测试 (DEV-009 to DEV-012) ---")

    # 测试树生成 (DEV-011)
    logger.info("\n--- 测试树生成函数 ---")
    try:
        d1_tree_term = depth_one_tree(0) # 终端
        logger.info(f"深度1树 (终端): {d1_tree_term!r}, 表达式: {tree_to_alpha(d1_tree_term)}")
        d1_tree_unary = depth_one_tree(1) # 一元
        logger.info(f"深度1树 (一元): {d1_tree_unary!r}, 表达式: {tree_to_alpha(d1_tree_unary)}")

        d2_tree_binary = depth_two_tree(1) # 二元根
        logger.info(f"深度2树 (二元根): {d2_tree_binary!r}, 表达式: {tree_to_alpha(d2_tree_binary)}")

        d3_tree_ts = depth_three_tree(2) # 时间序列根
        logger.info(f"深度3树 (TS根): {d3_tree_ts!r}, 表达式: {tree_to_alpha(d3_tree_ts)}")
    except Exception as e:
        logger.error(f"树生成测试中发生错误: {e}", exc_info=True)

    # 测试 tree_to_alpha (DEV-010) 和 alpha_to_tree (DEV-012)
    logger.info("\n--- 测试 tree_to_alpha 和 alpha_to_tree ---")
    tree1_leaf1 = Node("close")
    tree1_unary1 = Node("rank", left=tree1_leaf1)
    tree1_leaf2 = Node("vwap")
    tree1_leaf3 = Node("20")
    tree1_ts_op1 = Node("ts_rank", left=tree1_leaf2, right=tree1_leaf3)
    tree1_root = Node("add", left=tree1_unary1, right=tree1_ts_op1)

    expr1 = tree_to_alpha(tree1_root)
    expected_expr1 = "add(rank(close),ts_rank(vwap,20))"
    logger.info(f"源树生成的表达式: '{expr1}' (期望: '{expected_expr1}')")
    assert expr1 == expected_expr1, f"tree_to_alpha 失败: 得到 '{expr1}', 期望 '{expected_expr1}'"

    parsed_tree1 = alpha_to_tree(expr1)
    logger.info(f"alpha_to_tree 将 '{expr1}' 解析回树...")
    if parsed_tree1:
        logger.info(f"解析得到的树 (repr): {parsed_tree1!r}")
        re_expr1 = tree_to_alpha(parsed_tree1)
        logger.info(f"解析后的树再转回表达式: '{re_expr1}' (期望: '{expr1}')")
        assert re_expr1 == expr1, f"alpha_to_tree 双向转换失败: 得到 '{re_expr1}', 期望 '{expr1}'"
    else:
        logger.error(f"alpha_to_tree 未能解析表达式: '{expr1}'")
        assert False, f"alpha_to_tree 解析失败: '{expr1}'"

    test_expressions = {
        "log(adv20)": True,
        "close": True,
        "ts_zscore(open,60)": True,
        "add(vwap,cap)": True, # 移除了空格以匹配tokenizer输出
        "subtract(rank(high),rank(low))": True,
        "multiply(ts_delta(close,20),-1)": True,
        "add(rank(close)": False,
        "unknown_op(close)": False,
        "add(close,,open)": False,
        "add(close,open,high)": False,
        "rank()": False,
        "rank(close,open)": False,
    }

    for expr, should_succeed in test_expressions.items():
        logger.info(f"--- 测试表达式: '{expr}' (期望成功: {should_succeed}) ---")
        parsed_tree = alpha_to_tree(expr)
        if should_succeed:
            assert parsed_tree is not None, f"表达式 '{expr}' 本应解析成功，但失败了。"
            if parsed_tree:
                re_expr = tree_to_alpha(parsed_tree)
                # 简单的规范化：移除所有空格进行比较，因为原始测试用例中有些表达式包含空格
                assert re_expr.replace(" ", "") == expr.replace(" ", ""), f"双向转换不一致 for '{expr}': got '{re_expr}'"
                logger.info(f"'{expr}' 解析并重构为 '{re_expr}' 成功。")
        else:
            assert parsed_tree is None, f"表达式 '{expr}' 本应解析失败，但成功了。({parsed_tree!r})"
            logger.info(f"'{expr}' 按预期解析失败。")

    # 测试 fitness_fun (DEV-010 占位符)
    logger.info("\n--- 测试 fitness_fun (占位符) ---")
    fitness_score = fitness_fun(expr1)
    logger.info(f"表达式 '{expr1}' 的伪适应度分数: {fitness_score}")
    assert isinstance(fitness_score, float), "适应度分数应为 float 类型"

    # 测试遗传操作 (DEV-011)
    logger.info("\n--- 测试遗传操作 ---")
    parent1 = depth_three_tree(1) # 二元根的深度3树
    parent2 = depth_three_tree(0) # 一元根的深度3树
    logger.info(f"父代1: {tree_to_alpha(parent1)}")
    logger.info(f"父代2: {tree_to_alpha(parent2)}")

    # 变异
    mutated_child = mutate_random_node(parent1)
    if mutated_child:
        logger.info(f"父代1变异后: {tree_to_alpha(mutated_child)}")
    else:
        logger.error("变异操作返回 None")


    # 交叉
    child1, child2 = crossover(parent1, parent2)
    if child1 and child2:
        logger.info(f"交叉子代1: {tree_to_alpha(child1)}")
        logger.info(f"交叉子代2: {tree_to_alpha(child2)}")
    else:
        logger.error("交叉操作返回 None")

    logger.info("--- 遗传编程算法模块测试结束 ---")
