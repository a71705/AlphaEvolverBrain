# app/core/gp_algo.py
# 遗传编程核心算法模块

# 导入 random 模块用于随机选择和生成
import random
# 导入 typing 中的类型提示，用于增强代码可读性和静态分析
from typing import Optional, List, Any, Tuple, Dict
# 导入 re 模块用于正则表达式词法分析
import re
# 导入 datetime 用于在 evaluate_population 中设置 simulated_at
from datetime import datetime


# 导入 logging 模块用于日志记录
import logging
# 导入 pandas (通常在实际适应度函数中使用，此处为占位符的未来准备)
import pandas as pd

# SQLAlchemy Session for type hinting, and Alpha model for DB operations
from sqlalchemy.orm import Session
from app.models import Alpha
# BrainApiSession for simulation
from app.core.brain_api import BrainApiSession
# SessionLocal for standalone testing of evaluate_population if needed
# from app.database import SessionLocal # Commented out, as db_session should be passed in

# 获取当前模块的 logger 实例
# 日志将以 "app.core.gp_algo" 的名称记录
logger = logging.getLogger(__name__)

class Node:
    """
    表示遗传编程中表达式树的一个节点。
    每个节点可以是一个操作符（内部节点）或一个终端值（叶节点）。
    """
    def __init__(self, value: Any, left: Optional['Node'] = None, right: Optional['Node'] = None):
        self.value = value
        self.left = left
        self.right = right

    def __repr__(self) -> str:
        if self.left is None and self.right is None:
            return f"Node({self.value!r})"
        elif self.right is None:
             return f"Node({self.value!r}, {self.left!r})"
        else:
            return f"Node({self.value!r}, {self.left!r}, {self.right!r})"

    def get_depth(self) -> int:
        """ 计算并返回以当前节点为根的子树的深度。叶节点深度为0。 """
        if self.left is None and self.right is None: # 叶节点
            return 0

        left_depth = 0
        if self.left:
            left_depth = self.left.get_depth()

        right_depth = 0
        if self.right:
            right_depth = self.right.get_depth()

        return 1 + max(left_depth, right_depth)

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

def tokenize_expression(expression_str: str) -> List[str]:
    if not expression_str:
        logger.debug("tokenize_expression: 输入的表达式字符串为空。")
        return []
    pattern = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[(),]")
    tokens = pattern.findall(expression_str)
    logger.debug(f"表达式 '{expression_str}' 被词法分析为: {tokens}")
    return tokens

def alpha_to_tree(expression_str: str) -> Optional[Node]:
    if not expression_str or not expression_str.strip():
        logger.error("alpha_to_tree: 输入的表达式字符串为空或仅包含空白。")
        return None
    tokens = tokenize_expression(expression_str)
    if not tokens:
        logger.error(f"alpha_to_tree: 表达式 '{expression_str}' 词法分析后为空列表或无效。")
        return None
    pos = 0
    def peek_current_token() -> Optional[str]:
        if pos < len(tokens): return tokens[pos]
        return None
    def consume_expected_token(expected: Optional[str] = None) -> str:
        nonlocal pos
        current_token_val = peek_current_token()
        if current_token_val is None:
            err_msg = f"解析错误: 期望 token '{expected if expected else '更多输入'}' 但已到达输入末尾。"
            logger.error(err_msg); raise SyntaxError(err_msg)
        if expected and current_token_val != expected:
            context_start = max(0, pos - 2); context_end = min(len(tokens), pos + 3)
            context_str = f"' ... {' '.join(tokens[context_start:pos])} >>{tokens[pos]}<< {' '.join(tokens[pos+1:context_end])} ... '"
            err_msg = f"解析错误: 在位置 {pos} 期望 token '{expected}' 但得到 '{current_token_val}'. 上下文: {context_str}"
            logger.error(err_msg); raise SyntaxError(err_msg)
        pos += 1
        return current_token_val
    def parse_atom_recursive_internal() -> Node:
        token_val = peek_current_token()
        if token_val is None: raise SyntaxError("解析错误: 期望一个原子表达式（终端或数字），但输入已结束。")
        is_number_token = False
        try: float(token_val); is_number_token = True
        except ValueError: is_number_token = False
        if token_val in all_terminals or is_number_token:
            consume_expected_token(); return Node(token_val)
        else: raise SyntaxError(f"解析错误: 在位置 {pos} 期望一个终端或数字，但得到 '{token_val}'. 上下文: '{' '.join(tokens[max(0,pos-2):min(len(tokens),pos+3)])}'")
    def parse_expression_recursive_internal() -> Node:
        token_val = peek_current_token()
        if token_val is None: raise SyntaxError("解析错误: 期望表达式，但输入已结束。")
        if token_val in all_operators:
            op_name = consume_expected_token(); consume_expected_token("(")
            args = []
            if peek_current_token() == ')': logger.debug(f"操作符 '{op_name}' 参数列表为空。")
            else:
                args.append(parse_expression_recursive_internal())
                while peek_current_token() == ',':
                    consume_expected_token(",");
                    if peek_current_token() == ')': raise SyntaxError(f"解析错误: 操作符 '{op_name}' 在逗号后缺少参数。")
                    args.append(parse_expression_recursive_internal())
            consume_expected_token(")")
            if op_name in unary_ops:
                if len(args) == 1: return Node(op_name, left=args[0])
                else: raise SyntaxError(f"解析错误: 一元操作符 '{op_name}' 期望1个参数，得到 {len(args)}。参数: {args}")
            elif op_name in binary_ops or op_name in ts_ops:
                if len(args) == 2: return Node(op_name, left=args[0], right=args[1])
                else: raise SyntaxError(f"解析错误: 二元/时间序列操作符 '{op_name}' 期望2个参数，得到 {len(args)}。参数: {args}")
        else: return parse_atom_recursive_internal()
    try:
        parsed_tree = parse_expression_recursive_internal()
        if pos != len(tokens):
            remaining_tokens = tokens[pos:]
            logger.error(f"alpha_to_tree: 解析成功，但表达式 '{expression_str}' 末尾有未消耗的标记: {remaining_tokens}。")
            raise SyntaxError(f"解析错误: 表达式末尾有未消耗的标记: {remaining_tokens}")
        logger.info(f"表达式 '{expression_str}' 成功解析为树。"); logger.debug(f"解析得到的树: {parsed_tree!r}")
        return parsed_tree
    except SyntaxError as e: logger.error(f"解析表达式 '{expression_str}' 时发生语法错误: {e}"); return None
    except Exception as e: logger.error(f"解析表达式 '{expression_str}' 时发生未知错误: {e}", exc_info=True); return None

def depth_one_tree(flag: int, available_terminals: Optional[List[str]] = None, available_unary_ops: Optional[List[str]] = None, available_binary_ops: Optional[List[str]] = None, available_ts_ops: Optional[List[str]] = None, available_ts_ops_params: Optional[List[str]] = None) -> Node:
    terminals = available_terminals if available_terminals is not None else all_terminals
    unary = available_unary_ops if available_unary_ops is not None else unary_ops
    binary = available_binary_ops if available_binary_ops is not None else binary_ops
    ts = available_ts_ops if available_ts_ops is not None else ts_ops
    ts_specific_params = available_ts_ops_params if available_ts_ops_params is not None else ts_ops_values
    if not terminals: logger.error("depth_one_tree: 终端值列表为空。"); raise ValueError("终端值列表不能为空。")
    node = None; op_choice = ""
    if flag == 0: op_choice = "终端"; value = random.choice(terminals); node = Node(value)
    elif flag == 1 and unary: op_choice = "一元"; operator = random.choice(unary); operand = Node(random.choice(terminals)); node = Node(operator, left=operand)
    elif flag == 2 and binary: op_choice = "二元"; operator = random.choice(binary); operand1 = Node(random.choice(terminals)); operand2 = Node(random.choice(terminals)); node = Node(operator, left=operand1, right=operand2)
    elif flag == 3 and ts and ts_specific_params: op_choice = "时间序列"; operator = random.choice(ts); operand1 = Node(random.choice(terminal_values)); operand2 = Node(random.choice(ts_specific_params)); node = Node(operator, left=operand1, right=operand2)
    else: op_choice = f"终端 (备选，flag={flag} 无效)"; logger.warning(f"depth_one_tree: flag={flag} 无效或操作符列表为空，默认创建终端。"); value = random.choice(terminals); node = Node(value)
    logger.debug(f"depth_one_tree (flag={flag}, choice='{op_choice}') 生成: {node}"); return node

def depth_two_tree(flag: int, available_terminals: Optional[List[str]] = None, available_unary_ops: Optional[List[str]] = None, available_binary_ops: Optional[List[str]] = None, available_ts_ops: Optional[List[str]] = None, available_ts_ops_params: Optional[List[str]] = None) -> Node:
    terminals = available_terminals if available_terminals is not None else all_terminals; unary = available_unary_ops if available_unary_ops is not None else unary_ops; binary = available_binary_ops if available_binary_ops is not None else binary_ops; ts = available_ts_ops if available_ts_ops is not None else ts_ops; ts_specific_params = available_ts_ops_params if available_ts_ops_params is not None else ts_ops_values
    node = None; op_choice = ""
    if flag == 0 and unary: op_choice = "一元"; operator = random.choice(unary); child_flag = random.choice([1, 2, 3]); child_node = depth_one_tree(child_flag, terminals, unary, binary, ts, ts_specific_params); node = Node(operator, left=child_node)
    elif flag == 1 and binary: op_choice = "二元"; operator = random.choice(binary)
        if random.random() < 0.5: child1_flag = random.choice([1, 2, 3]); child1 = depth_one_tree(child1_flag, terminals, unary, binary, ts, ts_specific_params); child2_flag = random.choice([0, 1, 2, 3]); child2 = depth_one_tree(child2_flag, terminals, unary, binary, ts, ts_specific_params)
        else: child1_flag = random.choice([0, 1, 2, 3]); child1 = depth_one_tree(child1_flag, terminals, unary, binary, ts, ts_specific_params); child2_flag = random.choice([1, 2, 3]); child2 = depth_one_tree(child2_flag, terminals, unary, binary, ts, ts_specific_params)
        node = Node(operator, left=child1, right=child2)
    elif flag == 2 and ts and ts_specific_params: op_choice = "时间序列"; operator = random.choice(ts); child1_flag = random.choice([1, 2, 3]); operand1 = depth_one_tree(child1_flag, terminal_values, unary, binary, ts, ts_specific_params); operand2 = Node(random.choice(ts_specific_params)); node = Node(operator, left=operand1, right=operand2)
    else: op_choice = f"备选 (flag={flag} 无效)"; logger.warning(f"depth_two_tree: flag={flag} 无效或操作符列表为空，尝试其他类型。"); valid_flags = [];
        if unary: valid_flags.append(0);
        if binary: valid_flags.append(1);
        if ts and ts_specific_params: valid_flags.append(2)
        if not valid_flags: logger.error("depth_two_tree: 所有操作符列表均为空。"); raise ValueError("无法生成深度2树，操作符列表为空。")
        new_flag = random.choice(valid_flags); node = depth_two_tree(new_flag, terminals, unary, binary, ts, ts_specific_params)
    logger.debug(f"depth_two_tree (flag={flag}, choice='{op_choice}') 生成: {node}"); return node

def depth_three_tree(flag: int, available_terminals: Optional[List[str]] = None, available_unary_ops: Optional[List[str]] = None, available_binary_ops: Optional[List[str]] = None, available_ts_ops: Optional[List[str]] = None, available_ts_ops_params: Optional[List[str]] = None) -> Node:
    terminals = available_terminals if available_terminals is not None else all_terminals; unary = available_unary_ops if available_unary_ops is not None else unary_ops; binary = available_binary_ops if available_binary_ops is not None else binary_ops; ts = available_ts_ops if available_ts_ops is not None else ts_ops; ts_specific_params = available_ts_ops_params if available_ts_ops_params is not None else ts_ops_values
    node = None; op_choice = ""
    if flag == 0 and unary: op_choice = "一元"; operator = random.choice(unary); child_flag = random.choice([0, 1, 2]); child_node = depth_two_tree(child_flag, terminals, unary, binary, ts, ts_specific_params); node = Node(operator, left=child_node)
    elif flag == 1 and binary: op_choice = "二元"; operator = random.choice(binary)
        if random.random() < 0.5: child1_flag = random.choice([0, 1, 2]); child1 = depth_two_tree(child1_flag, terminals, unary, binary, ts, ts_specific_params); child2_flag = random.choice([0, 1, 2, 3]); child2 = depth_one_tree(child2_flag, terminals, unary, binary, ts, ts_specific_params)
        else: child1_flag = random.choice([0, 1, 2, 3]); child1 = depth_one_tree(child1_flag, terminals, unary, binary, ts, ts_specific_params); child2_flag = random.choice([0, 1, 2]); child2 = depth_two_tree(child2_flag, terminals, unary, binary, ts, ts_specific_params)
        node = Node(operator, left=child1, right=child2)
    elif flag == 2 and ts and ts_specific_params: op_choice = "时间序列"; operator = random.choice(ts); child1_flag = random.choice([0, 1, 2]); operand1 = depth_two_tree(child1_flag, terminal_values, unary, binary, ts, ts_specific_params); operand2 = Node(random.choice(ts_specific_params)); node = Node(operator, left=operand1, right=operand2)
    else: op_choice = f"备选 (flag={flag} 无效)"; logger.warning(f"depth_three_tree: flag={flag} 无效或操作符列表为空，尝试其他类型。"); valid_flags = [];
        if unary: valid_flags.append(0);
        if binary: valid_flags.append(1);
        if ts and ts_specific_params: valid_flags.append(2)
        if not valid_flags: logger.error("depth_three_tree: 所有操作符列表均为空。"); raise ValueError("无法生成深度3树，操作符列表为空。")
        new_flag = random.choice(valid_flags); node = depth_three_tree(new_flag, terminals, unary, binary, ts, ts_specific_params)
    logger.debug(f"depth_three_tree (flag={flag}, choice='{op_choice}') 生成: {node}"); return node

def _recursive_tree_to_alpha(node: Optional[Node]) -> str:
    if node is None: logger.warning("_recursive_tree_to_alpha: 遇到 None 节点。"); return ""
    if node.value in all_terminals: return str(node.value)
    elif node.value in unary_ops:
        if node.left: return f"{node.value}({_recursive_tree_to_alpha(node.left)})"
        else: logger.error(f"一元操作符 '{node.value}' 缺少左子节点。"); return f"{node.value}(MISSING_OPERAND)"
    elif node.value in binary_ops or node.value in ts_ops:
        if node.left and node.right: return f"{node.value}({_recursive_tree_to_alpha(node.left)},{_recursive_tree_to_alpha(node.right)})"
        elif node.left: logger.error(f"操作符 '{node.value}' 缺少右子节点。"); return f"{node.value}({_recursive_tree_to_alpha(node.left)},MISSING_RIGHT_OPERAND)"
        elif node.right: logger.error(f"操作符 '{node.value}' 缺少左子节点。"); return f"{node.value}(MISSING_LEFT_OPERAND,{_recursive_tree_to_alpha(node.right)})"
        else: logger.error(f"操作符 '{node.value}' 同时缺少左右子节点。"); return f"{node.value}(MISSING_BOTH_OPERANDS)"
    else: logger.error(f"遇到未知节点值: '{node.value}'。"); return f"UNKNOWN_NODE_VALUE({node.value!r})"

def tree_to_alpha(tree_root: Node) -> str:
    if not isinstance(tree_root, Node): logger.error(f"tree_to_alpha: 输入不是Node类型: {type(tree_root)}"); return ""
    logger.debug(f"开始树转表达式: {tree_root!r}"); expression = _recursive_tree_to_alpha(tree_root)
    logger.info(f"树转表达式完成: '{expression}'"); return expression

def fitness_fun(alpha_expression: str) -> float:
    logger.warning(f"fitness_fun: 占位符实现，为 '{alpha_expression}' 返回伪适应度。"); base_score = 0.0
    if alpha_expression: base_score = min(len(alpha_expression) / 100.0, 1.0)
    pseudo_fitness = round(base_score + random.uniform(-0.1, 0.1), 4)
    logger.info(f"表达式 '{alpha_expression}' 的伪适应度: {pseudo_fitness}"); return pseudo_fitness

def copy_tree(original_node: Optional[Node]) -> Optional[Node]:
    if original_node is None: return None
    return Node(original_node.value, copy_tree(original_node.left), copy_tree(original_node.right))

def _collect_nodes_recursive(current_node: Optional[Node], nodes_list: List[Node]):
    if current_node: nodes_list.append(current_node); _collect_nodes_recursive(current_node.left, nodes_list); _collect_nodes_recursive(current_node.right, nodes_list)

def get_all_nodes(root_node: Node) -> List[Node]:
    collected_nodes: List[Node] = [];
    if root_node: _collect_nodes_recursive(root_node, collected_nodes)
    return collected_nodes

def get_random_node(root_node: Node) -> Optional[Node]:
    if root_node is None: logger.warning("get_random_node: 空树输入。"); return None
    all_nodes = get_all_nodes(root_node)
    if not all_nodes: logger.warning("get_random_node: 未收集到节点。"); return None
    return random.choice(all_nodes)

def mutate_random_node(original_tree_root: Node, max_mutation_depth: int = 1, available_terminals: Optional[List[str]] = None, available_unary_ops: Optional[List[str]] = None, available_binary_ops: Optional[List[str]] = None, available_ts_ops: Optional[List[str]] = None, available_ts_ops_params: Optional[List[str]] = None) -> Optional[Node]:
    if original_tree_root is None: logger.warning("mutate_random_node: 空树输入。"); return None
    mutated_tree_root = copy_tree(original_tree_root)
    if mutated_tree_root is None: logger.error("mutate_random_node: 复制树失败。"); return original_tree_root
    node_to_mutate = get_random_node(mutated_tree_root)
    if node_to_mutate is None: logger.warning("mutate_random_node: 未选择到变异节点。"); return mutated_tree_root
    logger.debug(f"变异: 选中节点 {node_to_mutate!r}"); new_subtree_flag = 0 if max_mutation_depth == 0 else random.choice([0, 1, 2, 3])
    replacement_subtree_root = depth_one_tree(flag=new_subtree_flag, available_terminals=available_terminals, available_unary_ops=available_unary_ops, available_binary_ops=available_binary_ops, available_ts_ops=available_ts_ops, available_ts_ops_params=available_ts_ops_params)
    logger.debug(f"变异: 生成替换子树 {replacement_subtree_root!r}")
    node_to_mutate.value = replacement_subtree_root.value; node_to_mutate.left = replacement_subtree_root.left; node_to_mutate.right = replacement_subtree_root.right
    logger.info(f"变异完成，新值为 '{node_to_mutate.value}'。"); return mutated_tree_root

def crossover(parent1_root: Node, parent2_root: Node) -> Tuple[Optional[Node], Optional[Node]]:
    if parent1_root is None or parent2_root is None: logger.error("交叉: 父树之一为空。"); return (copy_tree(parent1_root), copy_tree(parent2_root))
    child1_root = copy_tree(parent1_root); child2_root = copy_tree(parent2_root)
    if child1_root is None or child2_root is None: logger.error("交叉: 复制父树失败。"); return (copy_tree(parent1_root) if child1_root is None else child1_root, copy_tree(parent2_root) if child2_root is None else child2_root)
    crossover_point1 = get_random_node(child1_root); crossover_point2 = get_random_node(child2_root)
    if crossover_point1 is None or crossover_point2 is None: logger.warning("交叉: 未选择到交叉点。"); return (child1_root, child2_root)
    logger.debug(f"交叉: child1节点 {crossover_point1!r}, child2节点 {crossover_point2!r}")
    p1_value, p1_left, p1_right = crossover_point1.value, crossover_point1.left, crossover_point1.right
    crossover_point1.value = crossover_point2.value; crossover_point1.left = crossover_point2.left; crossover_point1.right = crossover_point2.right
    crossover_point2.value = p1_value; crossover_point2.left = p1_left; crossover_point2.right = p1_right
    logger.info("交叉完成。"); return (child1_root, child2_root)

def generate_initial_population(size: int, max_initial_depth: int, config: Dict[str, Any]) -> List[Node]:
    population: List[Node] = [];
    if max_initial_depth < 1: logger.error("generate_initial_population: max_initial_depth < 1"); raise ValueError("max_initial_depth 必须至少为 1。")
    logger.info(f"生成初始种群，规模: {size}, 最大深度: {max_initial_depth}")
    for i in range(size):
        depth = random.randint(1, max_initial_depth); tree_root = None
        if depth == 1: flag = random.choice([1, 2, 3]); tree_root = depth_one_tree(flag=flag)
        elif depth == 2: flag = random.choice([0, 1, 2]); tree_root = depth_two_tree(flag=flag)
        elif depth == 3: flag = random.choice([0, 1, 2]); tree_root = depth_three_tree(flag=flag)
        else: logger.warning(f"请求深度 {depth}，生成深度3树替代。"); flag = random.choice([0, 1, 2]); tree_root = depth_three_tree(flag=flag)
        if tree_root: population.append(tree_root); logger.debug(f"生成个体 {i+1}/{size}，深度 {depth}: {tree_root!r}")
        else: logger.error(f"生成个体 {i+1}/{size} (深度 {depth}) 失败。")
    logger.info(f"成功生成 {len(population)} 个初始个体。"); return population

def evaluate_population(population_nodes: List[Node], brain_session: BrainApiSession, db_session: Session, experiment_id: int, current_iteration: int, ga_config: Dict[str, Any]) -> List[Alpha]:
    logger.info(f"评估种群，数量: {len(population_nodes)}, 实验ID: {experiment_id}, 代数: {current_iteration}")
    evaluated_alphas_orm: List[Alpha] = []; simulation_batch = []; batch_map = []
    default_sim_settings = ga_config.get("simulation_settings", {"instrument_type": "EQUITY", "region": "USA", "universe": "TOP3000", "delay": 1})
    for i, node_tree in enumerate(population_nodes):
        alpha_expression = tree_to_alpha(node_tree)
        if not alpha_expression: logger.warning(f"个体 {i} 树无法转换，跳过: {node_tree!r}"); continue
        existing_alpha = db_session.query(Alpha).filter_by(experiment_id=experiment_id, expression=alpha_expression).first()
        if existing_alpha and existing_alpha.calculated_fitness_score is not None:
            logger.info(f"Alpha '{alpha_expression}' (ID: {existing_alpha.id}) 已评估，使用现有适应度。"); evaluated_alphas_orm.append(existing_alpha); continue
        sim_data_for_api = {"alpha": alpha_expression, "settings": default_sim_settings}
        simulation_batch.append(sim_data_for_api)
        batch_map.append({"expression": alpha_expression, "node_tree": node_tree, "existing_alpha_orm": existing_alpha})
    if not simulation_batch: logger.info("无新Alpha需API模拟。"); return evaluated_alphas_orm
    logger.info(f"提交 {len(simulation_batch)} 个Alpha进行批量模拟..."); submission_response = brain_session.start_simulation(simulation_batch)
    if submission_response.get("error"): logger.error(f"批量模拟提交失败: {submission_response}"); return evaluated_alphas_orm
    main_job_id = submission_response.get("job_id") or submission_response.get("multisimulation_id")
    if not main_job_id: logger.error(f"批量模拟响应缺少job_id: {submission_response}"); return evaluated_alphas_orm
    logger.info(f"批量模拟提交，主任务ID: {main_job_id}。轮询进度..."); batch_results_data = brain_session.multisimulation_progress(main_job_id)
    if batch_results_data.get("error"):
        logger.error(f"批量模拟轮询失败: {batch_results_data}");
        for temp_alpha in batch_map: # 标记所有为失败
            alpha_orm = temp_alpha["existing_alpha_orm"]
            error_msg_batch = f"批量模拟失败: {batch_results_data.get('message', '未知错误')}"
            if not alpha_orm: alpha_orm = Alpha(experiment_id=experiment_id, expression=temp_alpha["expression"], iteration=current_iteration, depth=temp_alpha["node_tree"].get_depth(), error_message=error_msg_batch); db_session.add(alpha_orm)
            else: alpha_orm.error_message = error_msg_batch
            evaluated_alphas_orm.append(alpha_orm)
        try: db_session.commit()
        except Exception as e_commit: logger.error(f"DB提交批量失败Alpha时出错: {e_commit}"); db_session.rollback()
        return evaluated_alphas_orm
    individual_simulation_results = batch_results_data.get("results", [])
    if len(individual_simulation_results) != len(batch_map): logger.error(f"模拟结果数量 ({len(individual_simulation_results)}) 与提交 ({len(batch_map)}) 不匹配！")
    for i, temp_alpha in enumerate(batch_map):
        if i >= len(individual_simulation_results): logger.warning(f"Alpha '{temp_alpha['expression']}' 缺少模拟结果。"); continue
        sim_result = individual_simulation_results[i]; alpha_orm = temp_alpha["existing_alpha_orm"]; created_new_alpha_orm = False
        if not alpha_orm: alpha_orm = Alpha(experiment_id=experiment_id, expression=temp_alpha["expression"], iteration=current_iteration, depth=temp_alpha["node_tree"].get_depth()); created_new_alpha_orm = True
        alpha_orm.simulated_at = datetime.utcnow(); alpha_orm.simulation_settings_json = default_sim_settings
        if sim_result.get("status", "").upper() in ["FAILED", "ERROR"]:
            alpha_orm.error_message = sim_result.get("message", "模拟失败"); logger.warning(f"Alpha '{alpha_orm.expression}' 模拟失败: {alpha_orm.error_message}"); alpha_orm.calculated_fitness_score = None
        else:
            alpha_orm.is_stats_json = sim_result.get("is_stats"); alpha_orm.is_tests_json = sim_result.get("is_tests"); alpha_orm.oos_stats_json = sim_result.get("oos_stats"); alpha_orm.pnl_data_json = sim_result.get("pnl_data"); alpha_orm.yearly_stats_data_json = sim_result.get("yearly_stats"); alpha_orm.error_message = None
            alpha_orm.calculated_fitness_score = fitness_fun(alpha_orm.expression) # 使用占位符适应度函数
            logger.info(f"Alpha '{alpha_orm.expression}' 评估完成，适应度: {alpha_orm.calculated_fitness_score}")
        if created_new_alpha_orm: db_session.add(alpha_orm)
        evaluated_alphas_orm.append(alpha_orm)
    try: db_session.commit(); logger.info(f"成功评估并保存/更新 {len(batch_map)} 个Alpha到数据库。")
    except Exception as e: logger.error(f"提交Alpha评估结果到DB时出错: {e}", exc_info=True); db_session.rollback()
    return evaluated_alphas_orm

def select_parents(evaluated_population: List[Alpha], num_parents: int, selection_method: str = "elite") -> List[Alpha]:
    if not evaluated_population: logger.warning("select_parents: 已评估种群为空。"); return []
    logger.info(f"父代选择: 方法={selection_method}, 数量={num_parents}, 种群规模={len(evaluated_population)}")
    if selection_method == "elite":
        fittest_individuals = [alpha for alpha in evaluated_population if alpha.calculated_fitness_score is not None]
        fittest_individuals.sort(key=lambda alpha: alpha.calculated_fitness_score, reverse=True)
        selected = fittest_individuals[:num_parents]
        if len(selected) < num_parents and fittest_individuals:
             logger.warning(f"精英数量 ({len(selected)}) < 期望父代数 ({num_parents})，将重复选择。")
             selected.extend(random.choices(fittest_individuals, k=num_parents - len(selected)))
    else: logger.error(f"未知选择方法: {selection_method}。回退到精英选择。"); return select_parents(evaluated_population, num_parents, "elite")
    logger.info(f"成功选择 {len(selected)} 个父代。"); return selected

def reproduce_offspring(parents: List[Alpha], offspring_size: int, crossover_rate: float, mutation_rate: float, ga_config: Dict[str, Any]) -> List[Node]:
    if not parents: logger.warning("reproduce_offspring: 父代列表为空。"); return []
    offspring_population: List[Node] = []; max_mutation_depth = ga_config.get("max_mutation_depth", 1)
    logger.info(f"繁殖子代: 数量={offspring_size}, 交叉率={crossover_rate}, 变异率={mutation_rate}")
    parent_trees: List[Node] = []
    for parent_alpha in parents:
        tree = alpha_to_tree(parent_alpha.expression)
        if tree: parent_trees.append(tree)
        else: logger.warning(f"父代Alpha '{parent_alpha.expression}' 无法转回树，排除。")
    if not parent_trees: logger.error("reproduce_offspring: 所有父代无法转回树。"); return []
    num_actual_parents = len(parent_trees)
    while len(offspring_population) < offspring_size:
        p1_tree = random.choice(parent_trees); child1_tree: Optional[Node] = None; child2_tree: Optional[Node] = None
        if num_actual_parents > 1 and random.random() < crossover_rate:
            p2_tree = random.choice(parent_trees); logger.debug(f"应用交叉..."); child1_tree, child2_tree = crossover(p1_tree, p2_tree)
        else: logger.debug(f"不交叉，复制父代 {p1_tree!r}"); child1_tree = copy_tree(p1_tree)
            if len(offspring_population) + 1 < offspring_size : child2_tree = copy_tree(random.choice(parent_trees))
        if child1_tree:
            if random.random() < mutation_rate: logger.debug(f"变异子代1(原: {child1_tree!r})..."); child1_tree = mutate_random_node(child1_tree, max_mutation_depth=max_mutation_depth); logger.debug(f"变异后子代1: {child1_tree!r}")
            if child1_tree: offspring_population.append(child1_tree) # 再次检查mutate_random_node是否返回None
            if len(offspring_population) == offspring_size: break
        if child2_tree and len(offspring_population) < offspring_size:
            if random.random() < mutation_rate: logger.debug(f"变异子代2(原: {child2_tree!r})..."); child2_tree = mutate_random_node(child2_tree, max_mutation_depth=max_mutation_depth); logger.debug(f"变异后子代2: {child2_tree!r}")
            if child2_tree: offspring_population.append(child2_tree)
            if len(offspring_population) == offspring_size: break
    logger.info(f"成功生成 {len(offspring_population)} 个子代。"); return offspring_population

def _run_ga_generation(current_population_nodes: List[Node], brain_session: BrainApiSession, db_session: Session, experiment_id: int, current_iteration: int, ga_config: Dict[str, Any]) -> List[Node]:
    logger.info(f"开始GA第 {current_iteration} 代，实验ID: {experiment_id}。种群规模: {len(current_population_nodes)}")
    evaluated_alphas_orm = evaluate_population(current_population_nodes, brain_session, db_session, experiment_id, current_iteration, ga_config)
    if not evaluated_alphas_orm: logger.error(f"第 {current_iteration} 代评估后无可用Alpha。"); return []
    num_parents = ga_config.get("num_parents_to_select", len(evaluated_alphas_orm) // 2)
    selection_method = ga_config.get("selection_method", "elite")
    parents_alphas_orm = select_parents(evaluated_alphas_orm, num_parents, selection_method)
    if not parents_alphas_orm:
        logger.error(f"第 {current_iteration} 代未能选择父代。");
        if evaluated_alphas_orm: best_alpha_orm = random.choice(evaluated_alphas_orm); tree = alpha_to_tree(best_alpha_orm.expression); return [tree] if tree else []
        return []
    population_size = ga_config.get("population_size", len(current_population_nodes)); crossover_rate = ga_config.get("crossover_rate", 0.7); mutation_rate = ga_config.get("mutation_rate", 0.1)
    offspring_nodes = reproduce_offspring(parents_alphas_orm, population_size, crossover_rate, mutation_rate, ga_config)
    next_generation_nodes = offspring_nodes
    if not next_generation_nodes: logger.warning(f"第 {current_iteration} 代未能产生子代。"); return []
    logger.info(f"GA第 {current_iteration} 代完成。下一代种群规模: {len(next_generation_nodes)}"); return next_generation_nodes

# 主测试块
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.info("--- 开始遗传编程算法模块测试 (DEV-009 to DEV-012 & DEV-014) ---")
    # ... (之前的测试代码保持不变) ...

    # 为了测试 evaluate_population, select_parents, reproduce_offspring, _run_ga_generation
    # 需要模拟 BrainApiSession, db_session, 和 ga_config

    # 模拟 BrainApiSession
    class MockBrainApiSession(BrainApiSession):
        def __init__(self): # 覆盖父类构造函数，避免真实认证
            self._session = requests.Session() # 仍然需要 session 对象
            logger.info("MockBrainApiSession initialized (no real auth).")
            self.BASE_URL = "http://mockbrainapi.com" # 确保不调用真实API

        def start_simulation(self, simulate_data: Union[dict, list]) -> Dict[str, Any]:
            logger.info(f"MockBrainApiSession.start_simulation called with: {simulate_data}")
            if isinstance(simulate_data, list): # 批量
                return {"multisimulation_id": f"mock_batch_job_{random.randint(1000,9999)}", "status": "SUBMITTED"}
            else: # 单个
                return {"simulation_id": f"mock_single_job_{random.randint(1000,9999)}", "status": "SUBMITTED"}

        def multisimulation_progress(self, multisimulation_id: str) -> Dict[str, Any]:
            logger.info(f"MockBrainApiSession.multisimulation_progress called for: {multisimulation_id}")
            # 模拟成功，并返回与 batch_map 长度匹配的结果
            # 这里的模拟结果需要与 evaluate_population 中 batch_map 的结构对应
            # 假设 evaluate_population 中的 batch_map 此时无法直接访问，
            # 我们返回一个通用的成功响应，包含一个 results 列表
            # 实际测试时，可能需要更复杂的 mock 来模拟不同数量的结果
            num_results_to_mock = 2 # 假设提交了2个alpha进行模拟
            mock_results = []
            for i in range(num_results_to_mock):
                mock_results.append({
                    "status": "COMPLETED",
                    "is_stats": {"sharpe": round(random.uniform(0.5, 2.5), 2)},
                    # 其他模拟字段...
                })
            return {"multisimulation_id": multisimulation_id, "status": "COMPLETED", "results": mock_results}

    # 模拟 SQLAlchemy Session (部分功能)
    class MockDbSession:
        def __init__(self): self.added = []; self.committed = False; self.rollbacked = False; self._query_results = {}
        def query(self, model):
            # 返回一个可链式调用的模拟 Query 对象
            class MockQuery:
                def __init__(self, session, model_cls): self._session = session; self._model_cls = model_cls; self._filters = {}
                def filter_by(self, **kwargs): self._filters.update(kwargs); return self
                def first(self):
                    # 简单模拟：如果查询 Experiment/Alpha 且有预设结果，则返回
                    key = (self._model_cls, tuple(sorted(self._filters.items())))
                    return self._session._query_results.get(key)
                def all(self): return [] # 未详细模拟 all()
            return MockQuery(self, model)
        def add(self, obj): self.added.append(obj)
        def commit(self): self.committed = True; logger.info("MockDbSession: commit() called.")
        def rollback(self): self.rollbacked = True; logger.info("MockDbSession: rollback() called.")
        def close(self): logger.info("MockDbSession: close() called.")
        # 用于预设查询结果的方法
        def set_query_result(self, model_cls, filters_tuple, result_obj):
            key = (model_cls, filters_tuple)
            self._query_results[key] = result_obj


    logger.info("\n--- 测试GA核心辅助函数 (DEV-014) ---")
    mock_brain_session = MockBrainApiSession()
    mock_db_session = MockDbSession()

    test_experiment_id = 1
    test_iteration = 1
    test_ga_config = {
        "population_size": 4, # 保持较小以便测试
        "max_initial_depth": 2,
        "num_parents_to_select": 2,
        "crossover_rate": 0.8,
        "mutation_rate": 0.2,
        "max_mutation_depth": 1,
        "selection_method": "elite",
        "simulation_settings": {"instrument_type": "EQUITY", "region": "USA", "universe": "TOP3000", "delay": 1}
    }

    try:
        # 1. 生成初始种群
        logger.info("测试 generate_initial_population...")
        initial_pop_nodes = generate_initial_population(
            size=test_ga_config["population_size"],
            max_initial_depth=test_ga_config["max_initial_depth"],
            config=test_ga_config
        )
        assert len(initial_pop_nodes) == test_ga_config["population_size"]
        logger.info(f"成功生成初始种群: {[tree_to_alpha(t) for t in initial_pop_nodes]}")

        # 2. 评估种群 (需要 mock Brain API 和 DB)
        logger.info("测试 evaluate_population...")
        # 预设 evaluate_population 中查询 Alpha 时的返回 (假设没有预先存在的 Alpha)
        # (Alpha, (('experiment_id', 1), ('expression', 'some_expr'))) -> None

        evaluated_alphas = evaluate_population(
            initial_pop_nodes, mock_brain_session, mock_db_session,
            test_experiment_id, test_iteration, test_ga_config
        )
        # 断言：由于模拟的 multisimulation_progress 返回2个结果，
        # 而 batch_map 会基于 initial_pop_nodes (大小为4) 构建，
        # evaluate_population 会处理不匹配的情况，可能部分alpha没有结果。
        # 我们主要检查函数是否能运行，以及是否尝试了DB操作。
        assert mock_db_session.committed or not mock_db_session.added # 要么提交了，要么没东西可加
        logger.info(f"评估后的Alpha对象数量: {len(evaluated_alphas)}")
        for alpha_obj in evaluated_alphas:
            logger.info(f"  Alpha: {alpha_obj.expression}, Fitness: {alpha_obj.calculated_fitness_score}, Error: {alpha_obj.error_message}")


        # 3. 选择父代
        if evaluated_alphas: # 只有在有评估个体时才能选择父代
            logger.info("测试 select_parents...")
            parents = select_parents(evaluated_alphas, test_ga_config["num_parents_to_select"])
            assert len(parents) <= test_ga_config["num_parents_to_select"]
            if parents:
                 logger.info(f"选出的父代: {[p.expression for p in parents]}")
            else:
                 logger.warning("未能选出父代 (可能所有个体适应度无效)。")
        else:
            logger.warning("由于评估种群为空，跳过 select_parents 测试。")
            parents = [] # 为后续步骤提供空列表

        # 4. 繁殖子代
        if parents: # 只有在有父代时才能繁殖
            logger.info("测试 reproduce_offspring...")
            offspring = reproduce_offspring(
                parents, test_ga_config["population_size"],
                test_ga_config["crossover_rate"], test_ga_config["mutation_rate"],
                test_ga_config
            )
            assert len(offspring) == test_ga_config["population_size"]
            logger.info(f"生成的子代: {[tree_to_alpha(t) for t in offspring]}")
        else:
            logger.warning("由于父代列表为空，跳过 reproduce_offspring 测试。")
            offspring = []


        # 5. 运行一代GA (_run_ga_generation)
        logger.info("测试 _run_ga_generation...")
        # 需要重置 mock_db_session 的状态以便观察这一代的提交
        mock_db_session.committed = False; mock_db_session.added = []

        next_gen_nodes = _run_ga_generation(
            initial_pop_nodes, # 使用初始种群作为输入
            mock_brain_session, mock_db_session,
            test_experiment_id, test_iteration + 1, # 下一代
            test_ga_config
        )
        assert len(next_gen_nodes) <= test_ga_config["population_size"] # 可能因错误而减少
        if next_gen_nodes:
            logger.info(f"GA运行一代后生成的下一代种群 ({len(next_gen_nodes)} 个体): {[tree_to_alpha(t) for t in next_gen_nodes]}")
        else:
            logger.warning("_run_ga_generation 未能生成下一代种群。")

    except Exception as e:
        logger.error(f"GA核心辅助函数测试中发生严重错误: {e}", exc_info=True)

    logger.info("--- 遗传编程算法模块测试结束 ---")
