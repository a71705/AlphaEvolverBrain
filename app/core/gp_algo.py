# 导入 random 模块，用于在遗传编程操作中进行随机选择，例如选择操作符、终端或交叉点。
import random
# 从 typing 模块导入 Optional 和 List 类型提示，用于增强代码的可读性和静态分析能力。
# Optional[X] 表示一个参数或返回值可以是 X 类型，也可以是 None。
# List[X] 表示一个列表，其所有元素都是 X 类型。
from typing import Optional, List, Dict, Any, Tuple
import logging # 导入 logging 模块
import pandas as pd # 导入 pandas 用于数据处理，特别是 fitness_fun 中的 DataFrame 操作
import re # 导入正则表达式模块
from collections import Counter # DEV-044: 用于统计频率

# 导入 BrainApiSession 用于与 Brain API 交互，动态获取数据字段
from app.core.brain_api import BrainApiSession
# from app.models import Alpha # 概念上需要，但避免直接DB操作，不在此文件导入

logger = logging.getLogger(__name__)

class Node:
    """
    表示遗传编程中表达式树的一个节点。
    每个节点可以是一个操作符（例如 '+'、'ts_rank'）、一个终端（例如 'close', 'vwap'）或一个常量值。
    """
    def __init__(self, value: str, left: Optional['Node'] = None, right: Optional['Node'] = None):
        self.value: str = value
        self.left: Optional['Node'] = left
        self.right: Optional['Node'] = right

    def __repr__(self) -> str:
        left_repr = repr(self.left) if self.left else 'None'
        right_repr = repr(self.right) if self.right else 'None'
        if self.left is None and self.right is None:
            return f"Node('{self.value}')"
        elif self.right is None:
            return f"Node('{self.value}', left={left_repr})"
        else:
            return f"Node('{self.value}', left={left_repr}, right={right_repr})"

DEFAULT_TERMINAL_VALUES: List[str] = [
    "close", "open", "high", "low", "vwap", "adv20", "volume", "cap", "returns"
]
ts_ops: List[str] = [
    "ts_zscore", "ts_rank", "ts_arg_max", "ts_arg_min", "ts_backfill",
    "ts_delta", "ts_ir", "ts_mean", "ts_median", "ts_product", "ts_std_dev"
]
binary_ops: List[str] = [
    "add", "subtract", "divide", "multiply", "max", "min"
]
ts_ops_values: List[str] = [
    "20", "40", "60", "120", "240"
]
unary_ops: List[str] = [
    "rank", "zscore", "winsorize", "normalize", "rank_by_side",
    "sigmoid", "pasteurize", "log"
]

OPERATOR_ARITY = {
    **{op: 1 for op in unary_ops},
    **{op: 2 for op in binary_ops},
    **{op: 2 for op in ts_ops},
}

def _is_node_semantically_valid(node: Node) -> bool:
    if node is None: return True
    node_val_str = str(node.value)
    expected_arity = OPERATOR_ARITY.get(node_val_str)
    if expected_arity is not None:
        actual_children_count = (1 if node.left else 0) + (1 if node.right else 0)
        if actual_children_count != expected_arity:
            logger.warning(f"语义错误: 操作符 '{node_val_str}' 参数数量 {actual_children_count}, 期望 {expected_arity}. Node: {node!r}")
            return False
        if node_val_str in ts_ops:
            if not node.right:
                logger.warning(f"语义错误: ts_op '{node_val_str}' 缺少右子节点. Node: {node!r}")
                return False
            if node.right.left is not None or node.right.right is not None:
                logger.warning(f"语义错误: ts_op '{node_val_str}' 第二参数 '{node.right.value}' 必须是叶节点. Actual: {node.right!r}")
                return False
            if not (str(node.right.value) in ts_ops_values or re.fullmatch(r'\d+', str(node.right.value))):
                logger.warning(f"语义错误: ts_op '{node_val_str}' 第二参数 '{node.right.value}' 无效. Node: {node!r}")
                return False
    return True

def _recursive_tree_to_alpha(node: Optional[Node]) -> str:
    # ... (Implementation from DEV-041) ...
    if node is None: return ""
    node_value_str = str(node.value)
    is_unary,is_binary,is_ts_op = node_value_str in unary_ops, node_value_str in binary_ops, node_value_str in ts_ops
    is_known_operator = is_unary or is_binary or is_ts_op
    if not is_known_operator:
        if node.left or node.right: logger.error(f"结构错误:值'{node_value_str}'非操作符但有子节点.{node!r}"); return ""
        return node_value_str
    if is_unary:
        if node.left and not node.right:
            left_expr = _recursive_tree_to_alpha(node.left)
            if not left_expr: logger.warning(f"一元操作'{node_value_str}'左子表达式无效.{node!r}"); return ""
            return f"{node_value_str}({left_expr})"
        logger.error(f"结构错误:一元操作符'{node_value_str}'子节点结构不正确.{node!r}"); return ""
    elif is_binary:
        if node.left and node.right:
            left_expr,right_expr = _recursive_tree_to_alpha(node.left),_recursive_tree_to_alpha(node.right)
            if not left_expr or not right_expr: logger.warning(f"二元操作'{node_value_str}'子表达式无效.L:'{left_expr}',R:'{right_expr}'.{node!r}"); return ""
            return f"{node_value_str}({left_expr},{right_expr})"
        logger.error(f"结构错误:二元操作符'{node_value_str}'子节点数不正确.{node!r}"); return ""
    elif is_ts_op:
        if node.left and node.right:
            left_expr,time_window_expr = _recursive_tree_to_alpha(node.left),_recursive_tree_to_alpha(node.right)
            if not left_expr: logger.warning(f"ts_op'{node_value_str}'主表达式无效.{node!r}"); return ""
            if not(node.right.left is None and node.right.right is None and time_window_expr in ts_ops_values):
                 logger.warning(f"ts_op'{node_value_str}'时间窗口参数'{time_window_expr}'无效.{node.right!r}"); return ""
            return f"{node_value_str}({left_expr},{time_window_expr})"
        logger.error(f"结构错误:ts_op'{node_value_str}'子节点数不正确.{node!r}"); return ""
    logger.error(f"代码逻辑缺陷或未知节点类型:'{node_value_str}'.{node!r}"); return ""


def tree_to_alpha(tree: Optional[Node]) -> str:
    if tree is None: logger.info("tree_to_alpha:空树对象,返回空字符串."); return ""
    if not isinstance(tree, Node): logger.error(f"tree_to_alpha:输入非Node对象:{type(tree)}.返回空字符串."); return ""
    expression_str = _recursive_tree_to_alpha(tree)
    if not expression_str: logger.warning(f"树(根:{tree.value})生成Alpha表达式为空或无效.")
    else:
        if not _validate_alpha_syntax(expression_str): logger.warning(f"最终Alpha表达式'{expression_str}'未通过语法验证.")
        else: logger.info(f"树成功转换为Alpha表达式:'{expression_str}'")
    return expression_str

_tokenizer_tokens_list: List[str] = []
_tokenizer_current_token_index: int = 0

def _tokenize_expression(expression_str: str) -> Optional[List[str]]:
    # ... (Implementation from DEV-042) ...
    if not expression_str: return []
    sorted_ops = sorted(unary_ops + binary_ops + ts_ops, key=len, reverse=True)
    ops_pattern = "|".join(r"\b" + re.escape(op) + r"\b" for op in sorted_ops)
    token_specification = [('OPERATOR',r'(?:'+ops_pattern+r')'),('IDENTIFIER',r'[a-zA-Z_][a-zA-Z0-9_]*'),('NUMBER',r'-?\d+(?:\.\d+)?'),('LPAREN',r'\('),('RPAREN',r'\)'),('COMMA',r','),('WHITESPACE',r'\s+'),('MISMATCH',r'.')]
    tok_regex = '|'.join('(?P<%s>%s)'%pair for pair in token_specification)
    tokens = [mo.group() for mo in re.finditer(tok_regex,expression_str) if mo.lastgroup not in ['WHITESPACE','MISMATCH']]
    if any(re.fullmatch(tok_regex,expression_str)[i].lastgroup=='MISMATCH' for i in range(len(re.fullmatch(tok_regex,expression_str)))): # Simplified error check, might need finditer
        logger.error(f"词法分析错误：表达式'{expression_str}'含未知字符."); return None
    return tokens


def _parse_atom() -> Optional[Node]:
    # ... (Implementation from DEV-042, with semantic check from DEV-045) ...
    global _tokenizer_current_token_index, _tokenizer_tokens_list
    if _tokenizer_current_token_index>=len(_tokenizer_tokens_list):logger.error("解析错误(atom):意外结尾");return None
    token=_tokenizer_tokens_list[_tokenizer_current_token_index]
    is_unary,is_binary,is_ts_op=token in unary_ops,token in binary_ops,token in ts_ops
    if is_unary or is_binary or is_ts_op:
        _tokenizer_current_token_index+=1;op_node=Node(token)
        if _tokenizer_current_token_index>=len(_tokenizer_tokens_list)or _tokenizer_tokens_list[_tokenizer_current_token_index]!='(':logger.error(f"解析错误:操作符'{token}'后缺'('");return None
        _tokenizer_current_token_index+=1;args:List[Node]=[]
        if _tokenizer_current_token_index<len(_tokenizer_tokens_list)and _tokenizer_tokens_list[_tokenizer_current_token_index]==')':pass
        else:
            while True:
                arg_node=_parse_atom()
                if arg_node is None:logger.error(f"解析错误:操作符'{token}'参数解析失败");return None
                args.append(arg_node)
                if _tokenizer_current_token_index>=len(_tokenizer_tokens_list):logger.error(f"解析错误:表达式在参数列表末尾意外结束(操作符'{token}')");return None
                next_token_in_list=_tokenizer_tokens_list[_tokenizer_current_token_index]
                if next_token_in_list==')':break
                elif next_token_in_list==',':_tokenizer_current_token_index+=1
                else:logger.error(f"解析错误:操作符'{token}'参数后期望','或')',得到'{next_token_in_list}'");return None
        if _tokenizer_current_token_index>=len(_tokenizer_tokens_list)or _tokenizer_tokens_list[_tokenizer_current_token_index]!=')':logger.error(f"解析错误:操作符'{token}'参数列表后缺')'");return None
        _tokenizer_current_token_index+=1
        expected_arity=OPERATOR_ARITY.get(token)
        if expected_arity is not None and len(args)!=expected_arity:logger.error(f"参数数量错误:操作符'{token}'期望{expected_arity}个参数,得到{len(args)}个");return None
        if is_unary:op_node.left=args[0]
        elif is_binary or is_ts_op:op_node.left,op_node.right=args[0],args[1]
        if is_ts_op:
            if not(op_node.right and op_node.right.left is None and op_node.right.right is None and (op_node.right.value in ts_ops_values or re.fullmatch(r'\d+',op_node.right.value))):
                logger.error(f"参数类型错误:ts_op'{token}'的第二参数'{op_node.right.value if op_node.right else 'None'}'必须是预定义时间窗口值且为叶节点");return None
        return op_node
    elif re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*',token)or re.fullmatch(r'-?\d+(?:\.\d+)?',token)or token in ts_ops_values:
        _tokenizer_current_token_index+=1;return Node(token)
    else:logger.error(f"解析错误(atom):未知Token'{token}'");return None

def alpha_to_tree(expression_str: str) -> Optional[Node]:
    # ... (Implementation from DEV-042) ...
    global _tokenizer_current_token_index, _tokenizer_tokens_list
    if not expression_str or not isinstance(expression_str, str): logger.warning("alpha_to_tree:空或非字符串表达式"); return None
    logger.info(f"开始解析表达式为树: '{expression_str}'")
    _tokenizer_tokens_list = _tokenize_expression(expression_str)
    if _tokenizer_tokens_list is None: logger.error(f"表达式'{expression_str}'词法分析失败"); return None
    if not _tokenizer_tokens_list: logger.info(f"表达式'{expression_str}'为空或只含空格"); return None
    _tokenizer_current_token_index = 0
    try:
        parsed_tree = _parse_atom()
        if parsed_tree is not None and _tokenizer_current_token_index < len(_tokenizer_tokens_list):
            logger.error(f"解析错误:有未消耗Tokens:'{_tokenizer_tokens_list[_tokenizer_current_token_index:]}'"); parsed_tree = None
    except Exception as e: logger.error(f"解析表达式'{expression_str}'时意外错误:{e}", exc_info=True); parsed_tree = None
    finally: _tokenizer_tokens_list = []; _tokenizer_current_token_index = 0
    if parsed_tree is None: logger.error(f"表达式'{expression_str}'解析为树失败")
    else: logger.info(f"表达式'{expression_str}'成功解析为树.根:{parsed_tree.value}")
    return parsed_tree

def _validate_alpha_syntax(expression_str: str) -> bool:
    # ... (Implementation from DEV-025) ...
    if not expression_str: return False # Already logged by caller or tree_to_alpha
    open_b,close_b=expression_str.count('('),expression_str.count(')')
    if open_b!=close_b:logger.warning(f"表达式'{expression_str}'括号不匹配({open_b}vs{close_b})");return False
    if open_b>0:
        s_expr=expression_str.strip()
        if not s_expr:logger.warning(f"表达式'{expression_str}'剥离空格后为空");return False
        if s_expr[0]==')'or s_expr[-1]=='(':logger.warning(f"表达式'{expression_str}'首尾括号问题");return False
    if any(s in expression_str for s in [",,","(,",",)"]):logger.warning(f"表达式'{expression_str}'含无效逗号组合");return False
    return True


def get_tree_depth(node: Optional[Node]) -> int:
    if node is None: return 0
    return max(get_tree_depth(node.left), get_tree_depth(node.right)) + 1

def count_nodes(node: Optional[Node]) -> int:
    if node is None: return 0
    return 1 + count_nodes(node.left) + count_nodes(node.right)

def fitness_fun(Data: pd.DataFrame, n: int) -> List[str]:
    logger.info(f"fitness_fun: DataFrame行数 {len(Data)}, n: {n}")
    if Data.empty: return []
    return ["sharpe_ratio:1.0", "total_return:0.1"]

def copy_tree(original_node: Optional[Node]) -> Optional[Node]:
    if original_node is None: return None
    return Node(original_node.value, copy_tree(original_node.left), copy_tree(original_node.right))

def _get_all_nodes_with_parent(node: Optional[Node], parent: Optional[Node]=None) -> List[Tuple[Node, Optional[Node]]]:
    if node is None: return []
    return [(node,parent)] + _get_all_nodes_with_parent(node.left,node) + _get_all_nodes_with_parent(node.right,node)

def _get_random_non_root_node_and_parent(tree: Node) -> Optional[Tuple[Node, Node]]:
    if tree is None or (tree.left is None and tree.right is None): return None
    eligible_nodes=[(n,p) for n,p in _get_all_nodes_with_parent(tree) if p is not None]
    return random.choice(eligible_nodes) if eligible_nodes else None

def _get_random_node(tree: Node) -> Optional[Node]:
    if tree is None: return None
    all_nodes=[n for n,p in _get_all_nodes_with_parent(tree)]
    return random.choice(all_nodes) if all_nodes else None

def _replace_child(parent: Node, old_child: Node, new_child: Optional[Node]) -> bool:
    if parent.left==old_child: parent.left=new_child; return True
    elif parent.right==old_child: parent.right=new_child; return True
    return False

# --- DEV-050: Selection Strategies ---
def tournament_selection(
    population_with_fitness: List[Tuple[Node, float]],
    num_selections: int,
    tournament_size: int,
    higher_fitness_is_better: bool = True
) -> List[Node]:
    """
    【DEV-050】执行锦标赛选择。
    """
    if not population_with_fitness:
        logger.warning("锦标赛选择：种群为空。")
        return []
    if num_selections <= 0:
        logger.warning("锦标赛选择：选择数量非正。")
        return []

    actual_tournament_size = min(tournament_size, len(population_with_fitness))
    if actual_tournament_size <= 0:
        logger.warning(f"锦标赛选择：实际锦标赛规模为 {actual_tournament_size} (种群大小 {len(population_with_fitness)})，无法选择。")
        return []

    selected_individuals: List[Node] = []

    for i in range(num_selections):
        try:
            tournament_contenders = random.sample(population_with_fitness, actual_tournament_size)
        except ValueError:
            logger.warning(f"锦标赛选择：无法选择 {actual_tournament_size} 个参与者从大小为 {len(population_with_fitness)} 的种群中，使用整个种群。")
            tournament_contenders = list(population_with_fitness)
            if not tournament_contenders:
                logger.error("锦标赛选择：即使使用整个种群，参与者列表仍为空。")
                continue

        winner: Optional[Tuple[Node, float]] = None
        if higher_fitness_is_better:
            winner = max(tournament_contenders, key=lambda item: item[1], default=None)
        else:
            winner = min(tournament_contenders, key=lambda item: item[1], default=None)

        if winner and winner[0] is not None:
            selected_individuals.append(copy_tree(winner[0]))
        else:
            logger.warning(f"锦标赛 {i+1}/{num_selections} 未能决出胜者。")
            if tournament_contenders:
                random_choice = random.choice(tournament_contenders)
                if random_choice[0] is not None: selected_individuals.append(copy_tree(random_choice[0]))
            elif population_with_fitness:
                 random_choice_from_pop = random.choice(population_with_fitness)
                 if random_choice_from_pop[0] is not None: selected_individuals.append(copy_tree(random_choice_from_pop[0]))

    logger.info(f"锦标赛选择完成，选出 {len(selected_individuals)} 个个体 (期望 {num_selections} 个)。")
    return selected_individuals

def roulette_wheel_selection(
    population_with_fitness: List[Tuple[Node, float]],
    num_selections: int,
    higher_fitness_is_better: bool = True
) -> List[Node]:
    """
    【DEV-050】执行轮盘赌选择。
    """
    if not population_with_fitness:
        logger.warning("轮盘赌选择：种群为空。")
        return []
    if num_selections <= 0:
        logger.warning("轮盘赌选择：选择数量非正。")
        return []

    selected_individuals: List[Node] = []
    population_nodes = [ind_node for ind_node, fit_val in population_with_fitness]
    fitness_scores = [fit_val for ind_node, fit_val in population_with_fitness]

    num_individuals = len(population_nodes)
    if num_individuals == 0: return []

    adjusted_fitness: List[float] = []
    min_fit = min(fitness_scores) if fitness_scores else 0
    max_fit = max(fitness_scores) if fitness_scores else 0

    if higher_fitness_is_better:
        if min_fit == max_fit: adjusted_fitness = [1.0] * num_individuals
        else:
            shift = 0.0
            if min_fit <= 0: shift = abs(min_fit) + 1e-9
            adjusted_fitness = [(f + shift) for f in fitness_scores]
    else:
        if min_fit == max_fit: adjusted_fitness = [1.0] * num_individuals
        else:
            shift = 1e-9
            adjusted_fitness = [(max_fit - f + shift) for f in fitness_scores]

    total_adjusted_fitness = sum(adjusted_fitness)

    if total_adjusted_fitness <= 1e-9: # Check against a small epsilon
        logger.warning("轮盘赌选择：总调整适应度接近零，退化为随机选择。")
        return [copy_tree(random.choice(population_nodes)) for _ in range(num_selections)] if population_nodes else []

    for _ in range(num_selections):
        pick = random.uniform(0, total_adjusted_fitness)
        current_sum = 0
        chosen_index = -1
        for i in range(num_individuals):
            current_sum += adjusted_fitness[i]
            if current_sum >= pick:
                chosen_index = i
                break

        if chosen_index != -1:
            selected_individuals.append(copy_tree(population_nodes[chosen_index]))
        else:
            logger.error("轮盘赌选择在选择索引时发生意外错误，随机选择一个替代。")
            if population_nodes: # Ensure population_nodes is not empty
                 selected_individuals.append(copy_tree(random.choice(population_nodes)))

    logger.info(f"轮盘赌选择完成，选出 {len(selected_individuals)} 个个体 (期望 {num_selections} 个)。")
    return selected_individuals


# --- Genetic Operators (Crossover & Mutate - from DEV-045, ensure they use ga_config for constraints) ---
def crossover(parent1: Node, parent2: Node, ga_config: Dict[str, Any]) -> Tuple[Node, Node]:
    # ... (Implementation from DEV-045, unchanged) ...
    if parent1 is None or parent2 is None: logger.warning("Crossover:空父代"); return (copy_tree(parent1) if parent1 else Node("empty_p1")),(copy_tree(parent2) if parent2 else Node("empty_p2"))
    child1,child2 = copy_tree(parent1),copy_tree(parent2)
    if child1 is None or child2 is None: logger.error("Crossover:拷贝父代失败"); return parent1,parent2
    s1=_get_random_non_root_node_and_parent(child1);s2=_get_random_non_root_node_and_parent(child2)
    if not s1 or not s2: logger.debug("Crossover:父代树太小"); return child1,child2
    n1,p_n1=s1; n2,p_n2=s2
    n1_copy,n2_copy = copy_tree(n1),copy_tree(node2)
    if n1_copy is None or n2_copy is None: logger.error("Crossover:拷贝子树失败"); return copy_tree(parent1),copy_tree(parent2)
    r1,r2 = _replace_child(p_n1,n1,n2_copy),_replace_child(p_n2,n2,n1_copy)
    if not(r1 and r2): logger.error("Crossover:替换子节点失败"); return copy_tree(parent1),copy_tree(parent2)

    final_c1,final_c2 = child1,child2
    max_d,max_n = ga_config.get('max_alpha_depth',7),ga_config.get('max_nodes_per_alpha',50)
    if not _is_node_semantically_valid(p_n1) or get_tree_depth(child1)>max_d or count_nodes(child1)>max_n:
        logger.debug(f"Crossover:子1语义无效或超限.PD:{p_n1.value}.D:{get_tree_depth(child1)}/{max_d},N:{count_nodes(child1)}/{max_n}");final_c1=copy_tree(parent1)
        if final_c1 is None: final_c1=Node("err_p1_copy")
    if not _is_node_semantically_valid(p_n2) or get_tree_depth(child2)>max_d or count_nodes(child2)>max_n:
        logger.debug(f"Crossover:子2语义无效或超限.PD:{p_n2.value}.D:{get_tree_depth(child2)}/{max_d},N:{count_nodes(child2)}/{max_n}");final_c2=copy_tree(parent2)
        if final_c2 is None: final_c2=Node("err_p2_copy")
    logger.info(f"Crossover:Node'{n1.value}'(P1)与Node'{n2.value}'(P2)子树交换(已验证).")
    return final_c1,final_c2


def mutate_random_node(
    original_tree: Node, ga_config: Dict[str, Any],
    terminal_list: List[str], unary_op_list: List[str],
    binary_op_list: List[str], ts_op_list: List[str],
    ts_op_value_list: List[str]
) -> Node:
    # ... (Implementation from DEV-045, unchanged) ...
    if original_tree is None: return Node("mut_err_empty")
    max_attempts=ga_config.get('max_mutation_attempts_per_node',10)
    for attempt in range(max_attempts):
        tree_copy=copy_tree(original_tree)
        if tree_copy is None: logger.error(f"Mutate:拷贝树失败(att:{attempt+1})"); continue
        node_to_mut=_get_random_node(tree_copy)
        if node_to_mut is None: logger.warning("Mutate:无法选择节点"); return copy_tree(original_tree)
        orig_val_log=node_to_mut.value
        new_sub_flag=random.randint(0,3)
        try:
            new_node_content=depth_one_trees(terminal_list,binary_op_list,ts_op_list,ts_op_value_list,unary_op_list,new_sub_flag,ga_config)
            if new_node_content is None: logger.debug(f"Mutate:depth_one_trees返回None(att:{attempt+1})"); continue
        except ValueError as e: logger.warning(f"Mutate:生成替换子树出错:{e}(att:{attempt+1})"); continue
        node_to_mut.value,node_to_mut.left,node_to_mut.right = new_node_content.value,new_node_content.left,new_node_content.right
        logger.debug(f"Mutate:尝试节点'{orig_val_log}'为'{node_to_mut.value}'.")
        curr_d,curr_n=get_tree_depth(tree_copy),count_nodes(tree_copy)
        max_d,max_n=ga_config.get('max_alpha_depth',7),ga_config.get('max_nodes_per_alpha',50)
        if curr_d<=max_d and curr_n<=max_n:
            if _is_node_semantically_valid(node_to_mut):
                logger.info(f"Mutate:节点'{orig_val_log}'成功变为'{node_to_mut.value}'.D:{curr_d},N:{curr_n}.")
                return tree_copy
            else: logger.debug(f"Mutate:新子树根'{node_to_mut.value}'语义无效(att:{attempt+1}).")
        else: logger.debug(f"Mutate:树超限(D:{curr_d}/{max_d},N:{curr_n}/{max_n})(att:{attempt+1}).")
    logger.warning(f"Mutate:节点'{original_tree.value}'经{max_attempts}次尝试未成功,返原拷贝.")
    return copy_tree(original_tree)

def _get_dynamic_terminal_values(
    brain_api_session: BrainApiSession, strategy: str,
    strategy_params: dict, source_params: dict,
    dynamic_weights_map: Optional[Dict[str, float]] = None,
    ga_config: Optional[Dict[str, Any]] = None
) -> List[str]:
    # ... (Implementation from DEV-044, unchanged) ...
    logger.info(f"动态获取终端值。策略: {strategy}, 动态权重是否启用: {ga_config.get('use_dynamic_field_weights', False) if ga_config else 'N/A'}")
    try:
        all_fields_df = brain_api_session.get_datafields(instrument_type=source_params.get('instrument_type', 'EQUITY'), region=source_params.get('region', 'USA'), delay=source_params.get('delay', 1), universe=source_params.get('universe', 'TOP3000'), dataset_id=source_params.get('dataset_id', ''))
    except Exception as e:
        logger.error(f"调用 Brain API get_datafields 失败: {e}", exc_info=True); logger.warning("将返回默认终端值列表。"); return DEFAULT_TERMINAL_VALUES
    if all_fields_df is None or all_fields_df.empty: logger.warning("API返回数据字段列表为空。将使用默认。"); return DEFAULT_TERMINAL_VALUES
    if 'name' not in all_fields_df.columns: logger.error("API返回DataFrame缺少'name'列。将使用默认。"); return DEFAULT_TERMINAL_VALUES
    available_field_names = all_fields_df['name'].dropna().unique().tolist()
    if not available_field_names: logger.warning("提取的数据字段名列表为空。将使用默认。"); return DEFAULT_TERMINAL_VALUES
    num_selected_fields = strategy_params.get('num_selected_fields', 10); selected_fields: List[str] = []
    if strategy == "weighted_random":
        weights_to_use = None; source_of_weights = "无"
        if ga_config and ga_config.get('use_dynamic_field_weights', False) and dynamic_weights_map:
            filtered_dynamic_weights = {f: w for f, w in dynamic_weights_map.items() if f in available_field_names and isinstance(w, (int, float)) and w > 0}
            if filtered_dynamic_weights: weights_to_use = filtered_dynamic_weights; source_of_weights = "动态算法维护"
            else: logger.warning("动态权重映射无效。")
        if weights_to_use is None and strategy_params.get('weights'):
            static_weights = strategy_params.get('weights')
            if isinstance(static_weights, dict):
                 filtered_static_weights = {f: w for f, w in static_weights.items() if f in available_field_names and isinstance(w, (int, float)) and w > 0}
                 if filtered_static_weights: weights_to_use = filtered_static_weights; source_of_weights = "GA配置静态"
                 else: logger.warning("GA配置静态权重无效。")
            else: logger.warning(f"GA配置静态权重格式无效: {static_weights}")
        if weights_to_use:
            logger.info(f"加权随机使用'{source_of_weights}'的权重。"); fields_for_choice = list(weights_to_use.keys()); field_actual_weights = [weights_to_use[f] for f in fields_for_choice]
            if not fields_for_choice: logger.warning("加权随机：无有效带权重字段，退化。"); strategy = "random"
            else:
                if num_selected_fields >= len(fields_for_choice): selected_fields = fields_for_choice; logger.info(f"加权随机：可选({len(fields_for_choice)}) <= 请求({num_selected_fields})，全选。")
                else:
                    temp_selected_set = set(); attempts = 0; max_attempts = num_selected_fields * 5
                    while len(temp_selected_set) < num_selected_fields and attempts < max_attempts:
                        chosen = random.choices(fields_for_choice, weights=field_actual_weights, k=1)[0]; temp_selected_set.add(chosen); attempts += 1
                        if len(temp_selected_set) == len(fields_for_choice): break
                    selected_fields = list(temp_selected_set)
                    if len(selected_fields) < num_selected_fields:
                        remaining_to_select = num_selected_fields - len(selected_fields); potential_pool = [f for f in fields_for_choice if f not in selected_fields]
                        if potential_pool: selected_fields.extend(random.sample(potential_pool, min(remaining_to_select, len(potential_pool))))
                    logger.info(f"加权随机：尝试选{num_selected_fields},实际选{len(selected_fields)}.")
        else: logger.warning("加权随机：无有效权重，退化。"); strategy = "random"
    if strategy == "whitelist":
        whitelist = strategy_params.get('whitelist', []);
        if not isinstance(whitelist, list): logger.warning(f"白名单参数类型错误。退化。"); strategy = "random"
        else:
            selected_fields = [f for f in whitelist if f in available_field_names]
            if len(selected_fields) < len(whitelist): logger.warning(f"白名单部分字段无效: {set(whitelist) - set(selected_fields)}")
            if not selected_fields: logger.error("白名单策略无结果。退化。"); strategy = "random" # Force random if whitelist fails
            else: selected_fields = selected_fields[:num_selected_fields]
    if strategy == "blacklist":
        blacklist = strategy_params.get('blacklist', []);
        if not isinstance(blacklist, list): logger.warning(f"黑名单参数类型错误。退化。"); strategy = "random"
        else:
            candidate_fields = [f for f in available_field_names if f not in blacklist]
            if not candidate_fields: logger.warning("黑名单策略后无候选。退化。"); strategy = "random"
            elif len(candidate_fields) <= num_selected_fields: selected_fields = candidate_fields
            else: selected_fields = random.sample(candidate_fields, num_selected_fields)
    if strategy == "random" or not selected_fields:
        if strategy != "random" and not selected_fields : logger.info(f"策略'{strategy}'无结果，退化为随机。")
        if not available_field_names: logger.error("随机选择：无可用字段。返回默认。"); return DEFAULT_TERMINAL_VALUES
        if len(available_field_names) <= num_selected_fields: selected_fields = available_field_names
        else: selected_fields = random.sample(available_field_names, num_selected_fields)
    if not selected_fields: logger.error(f"所有策略失败。返回默认。"); return DEFAULT_TERMINAL_VALUES
    logger.info(f"最终选择动态终端值({len(selected_fields)}个,策略:{strategy}): {selected_fields}")
    return selected_fields

def _get_terminals_from_tree(node: Optional[Node], current_terminals: List[str], all_defined_terminals: List[str]) -> None:
    # ... (Implementation from DEV-044, unchanged) ...
    if node is None: return
    is_op = node.value in unary_ops or node.value in binary_ops or node.value in ts_ops
    is_ts_val = node.value in ts_ops_values
    if not is_op and not is_ts_val and node.left is None and node.right is None:
        if node.value in all_defined_terminals: current_terminals.append(str(node.value))
    _get_terminals_from_tree(node.left, current_terminals, all_defined_terminals)
    _get_terminals_from_tree(node.right, current_terminals, all_defined_terminals)

def _update_data_field_weights(
    current_dynamic_weights: Dict[str, float], elite_alpha_expressions: List[str],
    all_available_datafields: List[str], ga_config: Dict[str, Any]
) -> Dict[str, float]:
    # ... (Implementation from DEV-044, unchanged) ...
    if not ga_config.get('use_dynamic_field_weights',False)or not elite_alpha_expressions:return current_dynamic_weights
    logger.info(f"开始更新数据字段动态权重,基于{len(elite_alpha_expressions)}个优秀Alpha.")
    learning_rate=float(ga_config.get('dynamic_weight_learning_rate',0.1))
    decay_factor=float(ga_config.get('dynamic_weight_decay',0.01))
    min_weight=float(ga_config.get('dynamic_weight_min',0.1))
    max_weight=float(ga_config.get('dynamic_weight_max',10.0))
    field_counts=Counter()
    for expr_str in elite_alpha_expressions:
        tree_root=alpha_to_tree(expr_str)
        if tree_root:
            terminals_in_expr:List[str]=[]
            _get_terminals_from_tree(tree_root,terminals_in_expr,all_available_datafields)
            field_counts.update(terminals_in_expr)
        else:logger.warning(f"动态权重更新:无法解析表达式'{expr_str[:100]}...'")
    if not field_counts:logger.info("优秀Alpha中未统计到数据字段,权重本次不作大幅调整,仅应用衰减.")
    updated_weights=current_dynamic_weights.copy()
    for field_name in all_available_datafields:
        current_weight=updated_weights.get(field_name,1.0)
        frequency_score=field_counts.get(field_name,0)
        if frequency_score > 0:new_weight=current_weight*(1+learning_rate*frequency_score)
        else:new_weight=current_weight*(1-decay_factor)
        new_weight=max(min_weight,min(new_weight,max_weight))
        updated_weights[field_name]=new_weight
    sample_weights_log={k:round(v,3)for i,(k,v)in enumerate(updated_weights.items())if i<10 and k in field_counts}
    if not sample_weights_log and updated_weights:sample_weights_log={k:round(v,3)for i,(k,v)in enumerate(updated_weights.items())if i<5}
    logger.info(f"数据字段动态权重已更新.部分权重示例:{sample_weights_log if sample_weights_log else'无变化或无字段'},总字段数:{len(updated_weights)}")
    return updated_weights

def depth_one_trees(
    terminal_vals: List[str], bin_ops_list: List[str],
    time_series_ops_list: List[str], time_series_op_vals_list: List[str],
    un_ops_list: List[str], flag: int,
    ga_config: Optional[Dict[str, Any]] = None
) -> Optional[Node]:
    # ... (Implementation from DEV-045, unchanged) ...
    max_generation_attempts=ga_config.get('max_generation_attempts_d1',5)if ga_config else 5
    for attempt in range(max_generation_attempts):
        root_node:Optional[Node]=None
        if flag==0:
            if not terminal_vals:raise ValueError("depth_one_trees:终端值列表为空.")
            root_node=Node(random.choice(terminal_vals))
        elif flag==1:
            if not unary_ops:logger.warning("一元操作符列表为空...");return None
            if not terminal_vals:raise ValueError("depth_one_trees:终端值列表为空(一元子节点).")
            op=random.choice(unary_ops);term=Node(random.choice(terminal_vals));root_node=Node(op,left=term)
        elif flag==2:
            if not binary_ops:logger.warning("二元操作符列表为空...");return None
            if not terminal_vals:raise ValueError("depth_one_trees:终端值列表为空(二元子节点).")
            op=random.choice(binary_ops);term1=Node(random.choice(terminal_vals));term2=Node(random.choice(terminal_vals));root_node=Node(op,left=term1,right=term2)
        elif flag==3:
            if not ts_ops:logger.warning("时间序列操作符列表为空...");return None
            if not terminal_vals:raise ValueError("depth_one_trees:终端值列表为空(TS数据子节点).")
            if not ts_ops_values:raise ValueError("depth_one_trees:时间序列参数值列表为空.")
            op=random.choice(ts_ops);term_data=Node(random.choice(terminal_vals));term_val=Node(random.choice(ts_ops_values));root_node=Node(op,left=term_data,right=term_val)
        else:
            if not terminal_vals:raise ValueError("depth_one_trees:终端值列表为空(默认情况).")
            root_node=Node(random.choice(terminal_vals))
        if root_node is None:logger.error(f"depth_one_trees:未能为flag {flag}生成节点(尝试{attempt+1}).");continue
        if not _is_node_semantically_valid(root_node):logger.debug(f"depth_one_trees:生成节点'{root_node.value}'语义无效(尝试{attempt+1}).");continue
        if ga_config:
            max_d=ga_config.get('max_alpha_depth',1 if flag==0 else 2);max_n=ga_config.get('max_nodes_per_alpha',1 if flag==0 else 3)
            if get_tree_depth(root_node)>max_d or count_nodes(root_node)>max_n:logger.debug(f"depth_one_trees:生成节点'{root_node.value}'超限(尝试{attempt+1}).D:{get_tree_depth(root_node)}/{max_d},N:{count_nodes(root_node)}/{max_n}");continue
        return root_node
    logger.warning(f"depth_one_trees:达最大尝试{max_generation_attempts},未能生成有效树(flag={flag}).");return None


def depth_two_tree(tree1: Node, tree2: Node, time_series_op_vals_list: List[str], time_series_ops_list: List[str], flag: int ) -> Node: # Add ga_config if needed
    # ... (Implementation from DEV-045, largely unchanged but semantic check added) ...
    root_node: Optional[Node] = None
    if flag == 0:
        if not binary_ops: raise ValueError("全局二元操作符列表 binary_ops 不能为空。")
        selected_operator = random.choice(binary_ops); root_node = Node(selected_operator, left=tree1, right=tree2)
    elif flag == 1:
        if not ts_ops: raise ValueError("时间序列操作符列表不能为空 (ts_ops)。")
        if not ts_ops_values: raise ValueError("时间序列操作参数值列表不能为空 (ts_ops_values)。")
        selected_operator = random.choice(ts_ops); period_child_value = random.choice(ts_ops_values)
        root_node = Node(selected_operator, left=tree1, right=Node(period_child_value))
    else:
        logger.warning(f"depth_two_tree 收到未识别或未完全支持的 flag: {flag}。将默认使用二元操作符。")
        if not binary_ops: raise ValueError("全局二元操作符列表 binary_ops 不能为空。")
        selected_operator = random.choice(binary_ops); root_node = Node(selected_operator, left=tree1, right=tree2)
    if root_node is None: raise RuntimeError(f"未能为 flag {flag} 创建有效的深度二树节点。")
    if not _is_node_semantically_valid(root_node):
        logger.warning(f"depth_two_tree 生成的节点 '{root_node.value}' 语义无效。")
    return root_node

def depth_three_tree(sub_trees: List[Node], flag: int) -> Node: # Add ga_config if needed
    # ... (Implementation from DEV-045, largely unchanged but semantic check added) ...
    root_node: Optional[Node] = None
    if not sub_trees: raise ValueError("子树列表 sub_trees 不能为空。")
    if flag == 0:
        if not binary_ops: raise ValueError("全局二元操作符列表 binary_ops 不能为空。")
        selected_operator = random.choice(binary_ops); left_child: Node = random.choice(sub_trees); right_child: Node
        if len(sub_trees) > 1:
            temp_selectable_rights = [t for t in sub_trees if t is not left_child]
            if temp_selectable_rights: right_child = random.choice(temp_selectable_rights)
            else: right_child = random.choice(sub_trees)
        else:
            logger.info("depth_three_tree (flag 0): sub_trees 只有一个元素或需要新右子树...")
            right_child_flag = random.randint(0,3)
            try:
                right_child = depth_one_trees(DEFAULT_TERMINAL_VALUES, binary_ops, ts_ops, ts_ops_values, unary_ops, right_child_flag, {}) # Pass empty ga_config or derive
            except ValueError as e:
                logger.error(f"depth_three_tree: 生成右子树时出错: {e}。", exc_info=True)
                if not DEFAULT_TERMINAL_VALUES: raise ValueError("默认终端值列表为空...") from e
                right_child = Node(random.choice(DEFAULT_TERMINAL_VALUES))
        root_node = Node(selected_operator, left=left_child, right=right_child)
    elif flag == 1:
        if not ts_ops: raise ValueError("全局时间序列操作符列表 ts_ops 不能为空。")
        if not ts_ops_values: raise ValueError("全局时间序列操作参数值列表 ts_ops_values 不能为空。")
        selected_operator = random.choice(ts_ops); data_child: Node = random.choice(sub_trees)
        period_child_value = random.choice(ts_ops_values); root_node = Node(selected_operator, left=data_child, right=Node(period_child_value))
    elif flag == 2:
        if not unary_ops: logger.warning("一元操作符列表为空..."); flag = 0
        else: selected_operator = random.choice(unary_ops); child_node: Node = random.choice(sub_trees); root_node = Node(selected_operator, left=child_node)
    if flag != 2 or root_node is None :
        if flag !=0 and flag !=1 : logger.warning(f"depth_three_tree 收到未识别的 flag: {flag} 或因 unary_ops 为空而退化...")
        if not binary_ops: raise ValueError("全局二元操作符列表 binary_ops 不能为空。")
        selected_operator = random.choice(binary_ops); left_child = random.choice(sub_trees)
        current_terminals_for_subtree = DEFAULT_TERMINAL_VALUES
        right_child_flag = random.randint(0,3)
        try:
            right_child = depth_one_trees(current_terminals_for_subtree, binary_ops, ts_ops, ts_ops_values, unary_ops, right_child_flag, {})
        except ValueError as e:
            logger.error(f"depth_three_tree (default): 生成右子树时出错: {e}。", exc_info=True)
            if not DEFAULT_TERMINAL_VALUES: raise ValueError("默认终端值列表为空...") from e
            right_child = Node(random.choice(DEFAULT_TERMINAL_VALUES))
        root_node = Node(selected_operator, left=left_child, right=right_child)
    if root_node is None: raise RuntimeError(f"未能为 flag {flag} 和提供的子树创建有效的深度三树节点。")
    if not _is_node_semantically_valid(root_node):
        logger.warning(f"depth_three_tree 生成的节点 '{root_node.value}' 语义无效。")
    return root_node

def best_d1_alphas( brain_api: 'BrainApiSession', db: Session, experiment_id: int, ga_config: Dict[str, Any]) -> List[dict]:
    # ... (Implementation from DEV-044, with depth_one_trees call updated in DEV-045) ...
    data_field_dynamic_weights: Optional[Dict[str, float]] = None; all_available_datafields_from_api: List[str] = []
    try:
        all_fields_df = brain_api.get_datafields(instrument_type=ga_config.get('data_source_params', {}).get('instrument_type', 'EQUITY'), region=ga_config.get('data_source_params', {}).get('region', 'USA'), delay=ga_config.get('data_source_params', {}).get('delay', 1), universe=ga_config.get('data_source_params', {}).get('universe', 'TOP3000'))
        if all_fields_df is not None and not all_fields_df.empty and 'name' in all_fields_df.columns: all_available_datafields_from_api = all_fields_df['name'].dropna().unique().tolist()
        else: logger.warning("未能从API获取可用数据字段列表。"); all_available_datafields_from_api = DEFAULT_TERMINAL_VALUES.copy()
    except Exception as e: logger.error(f"获取所有可用数据字段失败: {e}", exc_info=True); all_available_datafields_from_api = DEFAULT_TERMINAL_VALUES.copy()
    if ga_config.get('use_dynamic_field_weights', False):
        data_field_dynamic_weights = {}; initial_weights_config = ga_config.get('datafield_selection_params', {}).get('weights', {})
        if initial_weights_config and isinstance(initial_weights_config, dict):
            logger.info("使用GA配置中的初始权重初始化动态权重。")
            for field in all_available_datafields_from_api: data_field_dynamic_weights[field] = float(initial_weights_config.get(field, 1.0))
        else:
            logger.info("为所有可用数据字段设置默认初始动态权重1.0。")
            for field in all_available_datafields_from_api: data_field_dynamic_weights[field] = 1.0
        logger.debug(f"初始动态权重 (部分): {dict(list(data_field_dynamic_weights.items())[:5])}")
    current_generation_terminals = _get_dynamic_terminal_values(brain_api, ga_config.get('datafield_selection_strategy', 'random'), ga_config.get('datafield_selection_params', {}), ga_config.get('data_source_params', {}), dynamic_weights_map=data_field_dynamic_weights, ga_config=ga_config)
    if not current_generation_terminals: logger.error(f"实验 {experiment_id}: 未能获取动态终端值列表"); raise ValueError("无法获取终端值列表")
    logger.info(f"实验 {experiment_id}: 本代使用的终端值 ({len(current_generation_terminals)}个): {current_generation_terminals}")
    max_depth = ga_config.get('max_alpha_depth', 7); max_nodes = ga_config.get('max_nodes_per_alpha', 50); population_size = ga_config.get('population_size', 50); total_iterations_this_depth = ga_config.get("iterations_at_depth_0", ga_config.get("iterations_per_depth", 10))
    logger.info(f"实验 {experiment_id}: 开始执行遗传算法阶段 best_d1_alphas。迭代次数: {total_iterations_this_depth}。")
    population: List[Node] = []; attempts = 0; max_attempts_per_individual = ga_config.get('max_generation_attempts_initial_pop', 20)
    while len(population) < population_size and attempts < population_size * max_attempts_per_individual :
        flag = random.randint(0, 3)
        try:
            tree = depth_one_trees(current_generation_terminals, binary_ops, ts_ops, ts_ops_values, unary_ops, flag, ga_config)
            if tree: population.append(tree)
        except ValueError as e: logger.warning(f"生成初始树ValueError: {e}", exc_info=True)
        except Exception as e_general: logger.error(f"生成初始树Exception: {e_general}", exc_info=True)
        attempts += 1
    if len(population) < population_size: logger.warning(f"实验 {experiment_id}: 初始种群数量 ({len(population)}) 少于预期 ({population_size})。");
    logger.info(f"实验 {experiment_id}: 初始种群生成完毕，数量 {len(population)}。")
    # ... (Placeholder GA loop including calls to new selection methods) ...
    return [{"expression": "placeholder_d1_alpha_1", "fitness": 0.5}]


def best_d2_alphas( brain_api: 'BrainApiSession', db: Session, experiment_id: int, ga_config: dict, previous_generation_alphas: List[dict]) -> List[dict]:
    logger.info(f"实验 {experiment_id}: best_d2_alphas (选择策略、语义/复杂性检查待完整实现)...")
    # Conceptual: Population with fitness from previous_generation_alphas
    # population_with_fitness = [(alpha_to_tree(alpha['expression']), alpha['fitness']) for alpha in previous_generation_alphas if alpha_to_tree(alpha['expression'])]
    # selected_parents = select_parents_for_reproduction(population_with_fitness, ga_config)
    # ... crossover, mutate ...
    return [{"expression": f"placeholder_d2_exp{experiment_id}_alpha_1", "fitness": 0.7}]

def best_d3_alpha( brain_api: 'BrainApiSession', db: Session, experiment_id: int, ga_config: dict, previous_generation_alphas: List[dict]) -> List[dict]:
    logger.info(f"实验 {experiment_id}: best_d3_alpha (选择策略、语义/复杂性检查待完整实现)...")
    return [{"expression": f"placeholder_d3_exp{experiment_id}_alpha_final", "fitness": 0.9}]

import time

def combine_alphas(alpha_expressions: List[str], method: str = "add") -> str:
    # ... (Implementation from DEV-026, unchanged) ...
    if not alpha_expressions: logger.warning("Alpha表达式列表为空..."); return ""
    valid_expressions = [str(expr) for expr in alpha_expressions if expr and isinstance(expr, (str,int,float))]
    valid_expressions = [expr for expr in valid_expressions if expr.strip()]
    if not valid_expressions: logger.warning("有效Alpha表达式列表为空..."); return ""
    num_expressions = len(valid_expressions)
    if num_expressions == 1:
        if not _validate_alpha_syntax(valid_expressions[0]): logger.warning(f"单个表达式'{valid_expressions[0]}'语法验证失败.")
        return valid_expressions[0]
    current_expr = valid_expressions[0]
    if method=="add":
        for i in range(1,num_expressions):current_expr=f"add({current_expr},{valid_expressions[i]})"
    elif method=="mean":
        for i in range(1,num_expressions):current_expr=f"add({current_expr},{valid_expressions[i]})"
        current_expr=f"divide({current_expr},{num_expressions})"
    else:logger.error(f"不支持组合方法:'{method}'.");return""
    if not _validate_alpha_syntax(current_expr):logger.warning(f"组合后表达式'{current_expr}'语法验证失败.")
    logger.info(f"Alpha表达式组合完成:'{current_expr}'.")
    return current_expr
