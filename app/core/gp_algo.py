# 导入 random 模块，用于在遗传编程操作中进行随机选择，例如选择操作符、终端或交叉点。
import random
# 从 typing 模块导入 Optional 和 List 类型提示，用于增强代码的可读性和静态分析能力。
# Optional[X] 表示一个参数或返回值可以是 X 类型，也可以是 None。
# List[X] 表示一个列表，其所有元素都是 X 类型。
from typing import Optional, List, Dict, Any # Any for combine_alphas
import logging # 导入 logging 模块
import pandas as pd # 导入 pandas 用于数据处理，特别是 fitness_fun 中的 DataFrame 操作
import re # 导入正则表达式模块
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
# 注意：实际的 terminal_values 列表会在运行时通过 _get_dynamic_terminal_values 获取
# 上面的 DEFAULT_TERMINAL_VALUES 仅作为无法从API获取时的备用。
# 在树转换 (_recursive_tree_to_alpha) 和树解析 (_parse_expression_recursive) 中，
# 我们依赖于这样一个假设：在树构建时，叶子节点的值已经是有效的终端字符串或数值字符串。
# 词法分析器 (_tokenize_expression) 会尝试识别这些，而解析器会根据上下文构建。
# 全局的 terminal_values 列表主要在树生成函数 (depth_one_trees等) 中作为候选终端池使用。

ts_ops: List[str] = [
    "ts_zscore", "ts_rank", "ts_arg_max", "ts_arg_min", "ts_backfill",
    "ts_delta", "ts_ir", "ts_mean", "ts_median", "ts_product", "ts_std_dev"
]
binary_ops: List[str] = [
    "add", "subtract", "divide", "multiply", "max", "min"
]
ts_ops_values: List[str] = [ # 这些是作为参数（叶子节点）出现的数值型字符串
    "20", "40", "60", "120", "240"
]
unary_ops: List[str] = [
    "rank", "zscore", "winsorize", "normalize", "rank_by_side",
    "sigmoid", "pasteurize", "log"
]

# --- DEV-041: Refactored _recursive_tree_to_alpha ---
def _recursive_tree_to_alpha(node: Optional[Node]) -> str:
    """
    【强制重构版】递归地将表达式树（Node对象）转换为Alpha表达式字符串。
    此函数旨在处理任意深度和结构（符合预定义构建块）的树。

    参数:
        node (Optional[Node]): 当前要转换的树节点。

    返回:
        str: 该节点及其子树对应的Alpha表达式字符串。
             如果节点无效或无法转换，则返回空字符串。
    """
    if node is None:
        logger.debug("递归树转表达式遇到None节点，返回空字符串。") # Changed to debug for less noise
        return ""

    node_value_str = str(node.value)

    # 1. 叶节点处理: 终端值 或 时间序列操作的数值参数 (如 "20")
    #    假设：如果一个节点不是已定义的操作符，且没有子节点，则它是一个终端或参数。
    #    或者，如果它的值在ts_ops_values中，它也是一个叶节点。
    is_unary = node_value_str in unary_ops
    is_binary = node_value_str in binary_ops
    is_ts_op = node_value_str in ts_ops
    is_known_operator = is_unary or is_binary or is_ts_op

    if not is_known_operator:
        # 如果不是已知操作符，它必须是叶节点 (没有子节点) 才能被视为终端或参数
        if node.left is not None or node.right is not None:
            logger.error(f"结构错误: 节点值 '{node_value_str}' 不是已知操作符，但不符合叶节点结构 (有子节点)。节点: {node!r}")
            return ""
        # logger.debug(f"叶节点 (终端/参数): {node_value_str}")
        return node_value_str # 直接返回其值 (例如 "close", "vwap", "20")

    # 2. 一元操作符处理
    if is_unary:
        if node.left is not None and node.right is None:
            left_expr = _recursive_tree_to_alpha(node.left)
            if not left_expr:
                logger.warning(f"一元操作 '{node_value_str}' 的左子表达式无效。节点: {node!r}")
                return ""
            return f"{node_value_str}({left_expr})"
        else:
            logger.error(f"结构错误: 一元操作符 '{node_value_str}' 子节点数量/结构不正确 (应为1个左子节点，无右子节点)。节点: {node!r}")
            return ""

    # 3. 二元操作符处理
    elif is_binary:
        if node.left is not None and node.right is not None:
            left_expr = _recursive_tree_to_alpha(node.left)
            right_expr = _recursive_tree_to_alpha(node.right)
            if not left_expr or not right_expr:
                logger.warning(f"二元操作 '{node_value_str}' 的子表达式存在无效部分。左: '{left_expr}', 右: '{right_expr}'. 节点: {node!r}")
                return ""
            return f"{node_value_str}({left_expr},{right_expr})"
        else:
            logger.error(f"结构错误: 二元操作符 '{node_value_str}' 子节点数量不正确 (应为左右两个子节点)。节点: {node!r}")
            return ""

    # 4. 时间序列操作符处理
    elif is_ts_op:
        if node.left is not None and node.right is not None:
            left_expr = _recursive_tree_to_alpha(node.left)
            time_window_expr = _recursive_tree_to_alpha(node.right)

            if not left_expr:
                logger.warning(f"时间序列操作 '{node_value_str}' 的主表达式参数无效。节点: {node!r}")
                return ""
            # 验证时间窗口参数是否是预期的叶节点且其值在ts_ops_values中
            if node.right.left is not None or node.right.right is not None or time_window_expr not in ts_ops_values:
                logger.warning(f"时间序列操作 '{node_value_str}' 的时间窗口参数 '{time_window_expr}' 无效 (结构错误或值不在预定义列表 {ts_ops_values} 中)。右子节点: {node.right!r}")
                return ""

            return f"{node_value_str}({left_expr},{time_window_expr})"
        else:
            logger.error(f"结构错误: 时间序列操作符 '{node_value_str}' 子节点数量不正确 (应为表达式和时间窗口两个参数)。节点: {node!r}")
            return ""

    # 此处理论上不应到达，因为所有已知操作符都已处理
    logger.error(f"代码逻辑缺陷或未知节点类型: '{node_value_str}' 未被任何规则匹配。节点: {node!r}")
    return ""

# --- DEV-041: Refactored tree_to_alpha (Main Interface) ---
def tree_to_alpha(tree: Optional[Node]) -> str:
    """
    【强制重构版的主接口】将整个表达式树转换为Alpha表达式字符串。
    此函数调用 _recursive_tree_to_alpha 来执行实际的转换。

    参数:
        tree (Optional[Node]): 表达式树的根节点。可以是 None。

    返回:
        str: 完整的Alpha表达式字符串。如果树无效或为空，则返回空字符串。
    """
    if tree is None:
        logger.info("tree_to_alpha 接收到空的树对象 (None)，返回空字符串。")
        return ""

    if not isinstance(tree, Node):
        logger.error(f"tree_to_alpha 接收到的输入不是有效的 Node 对象或 None: {type(tree)}。将返回空字符串。")
        return ""

    # logger.debug(f"开始将树转换为 Alpha 表达式 (根节点值: {tree.value})") # Less verbose
    expression_str = _recursive_tree_to_alpha(tree)

    if not expression_str:
        logger.warning(f"从树 (根节点值: {tree.value}) 生成的Alpha表达式为空或无效。")
    else:
        if not _validate_alpha_syntax(expression_str):
            logger.warning(f"最终生成的Alpha表达式 '{expression_str}' 未通过顶层语法验证。")
            # Consider returning "" if validation fails strictly, or log and return as is.
            # For now, returning the string with a warning.
        else:
            logger.info(f"树成功转换为 Alpha 表达式: '{expression_str}'")

    return expression_str

# --- DEV-042: Tokenizer and Parser for alpha_to_tree ---
# 存储词法单元和当前处理位置的模块级变量 (递归下降解析器常用技巧)
# 注意: 这使得 alpha_to_tree 和其辅助函数不是线程安全的，也不可重入。
# 如果需要在并发环境中使用，应将这些状态封装到类实例中或作为参数传递。
# 对于 RQ worker (通常单线程处理任务)，这种方式是可接受的。
_tokenizer_tokens_list: List[str] = []
_tokenizer_current_token_index: int = 0

def _tokenize_expression(expression_str: str) -> Optional[List[str]]:
    """
    【DEV-042】将Alpha表达式字符串分解为Token列表。
    Token可以是：操作符、数据字段、数值、括号、逗号。
    """
    if not expression_str:
        logger.debug("表达式为空，词法分析返回空列表。")
        return []

    # 操作符列表，按长度降序排序以优先匹配长操作符 (例如 'ts_rank' 先于 'rank')
    # 这有助于避免正则表达式部分匹配问题
    # 同时对正则表达式特殊字符进行转义 (虽然当前操作符列表不含此类字符)
    # \b 用于确保全词匹配
    sorted_ops = sorted(unary_ops + binary_ops + ts_ops, key=len, reverse=True)
    ops_pattern = "|".join(r"\b" + re.escape(op) + r"\b" for op in sorted_ops)

    # 模式解释:
    # 1. 匹配已知操作符 (已排序和转义)
    # 2. 匹配标识符 (数据字段/终端，字母开头，后跟字母、数字或下划线)
    # 3. 匹配数值 (整数或浮点数，可选负号)
    # 4. 匹配括号或逗号 (分隔符)
    # 5. \S 匹配任何其他非空白字符 (用于错误检测)
    # (?P<NAME>...) 创建命名捕获组
    token_specification = [
        ('OPERATOR',  r'(?:' + ops_pattern + r')'),
        ('IDENTIFIER',r'[a-zA-Z_][a-zA-Z0-9_]*'),      # 包括终端和ts_ops_values中的数字字符串
        ('NUMBER',    r'-?\d+(?:\.\d+)?'),          # 整数或浮点数
        ('LPAREN',    r'\('),
        ('RPAREN',    r'\)'),
        ('COMMA',     r','),
        ('WHITESPACE',r'\s+'),                       # 匹配空格，后续会忽略
        ('MISMATCH',  r'.')                         # 任何其他字符视为不匹配 (错误)
    ]

    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
    tokens: List[str] = []

    for mo in re.finditer(tok_regex, expression_str):
        kind = mo.lastgroup
        value = mo.group()

        if kind == 'OPERATOR':
            tokens.append(value)
        elif kind == 'IDENTIFIER': # 包括终端和 ts_ops_values (如 "20", "close")
            tokens.append(value)
        elif kind == 'NUMBER': # 纯数值 (如 -1.5, 100)
            tokens.append(value)
        elif kind == 'LPAREN':
            tokens.append('(')
        elif kind == 'RPAREN':
            tokens.append(')')
        elif kind == 'COMMA':
            tokens.append(',')
        elif kind == 'WHITESPACE':
            continue # 忽略空白
        elif kind == 'MISMATCH':
            logger.error(f"词法分析错误：在表达式 '{expression_str}' 中遇到未知字符 '{value}' 在位置 {mo.start()}。")
            return None # 词法分析失败

    # logger.debug(f"表达式 '{expression_str}' 被分解为 tokens: {tokens}")
    return tokens

def _parse_atom() -> Optional[Node]:
    """【DEV-042】解析一个原子表达式：一个终端、一个数值，或者一个完整的函数调用。"""
    global _tokenizer_current_token_index, _tokenizer_tokens_list

    if _tokenizer_current_token_index >= len(_tokenizer_tokens_list):
        logger.error("解析错误 (atom): 意外的表达式结尾，缺少Token。")
        return None

    token = _tokenizer_tokens_list[_tokenizer_current_token_index]

    # 检查是否是终端、ts_ops_value 或纯数字
    # 动态终端值列表 (terminal_values) 在此函数中不可直接访问。
    # _tokenize_expression 将它们识别为 IDENTIFIER 或 NUMBER。
    # 假设：如果一个 token 不是已知操作符且后面没有 '(', 它就是终端/数值。

    is_unary = token in unary_ops
    is_binary = token in binary_ops
    is_ts_op = token in ts_ops

    if is_unary or is_binary or is_ts_op: # Token 是一个操作符，期望函数调用形式
        _tokenizer_current_token_index += 1 # 消耗操作符Token
        op_node = Node(token)

        # 期望 '('
        if _tokenizer_current_token_index >= len(_tokenizer_tokens_list) or                 _tokenizer_tokens_list[_tokenizer_current_token_index] != '(':
            logger.error(f"解析错误: 操作符 '{token}' 后缺少 '('。")
            return None
        _tokenizer_current_token_index += 1 # 消耗 '('

        args: List[Node] = []
        # 检查是否立即遇到 ')' (例如，对于一个错误的 op() 调用)
        if _tokenizer_current_token_index < len(_tokenizer_tokens_list) and                _tokenizer_tokens_list[_tokenizer_current_token_index] == ')':
            pass # 参数列表为空，将在后面根据操作符类型进行验证
        else: # 解析参数
            while True:
                arg_node = _parse_atom() # 递归解析参数表达式
                if arg_node is None:
                    logger.error(f"解析错误: 操作符 '{token}' 的参数解析失败。")
                    return None
                args.append(arg_node)

                if _tokenizer_current_token_index >= len(_tokenizer_tokens_list):
                    logger.error(f"解析错误: 表达式在参数列表末尾意外结束 (操作符 '{token}')，缺少 ')'。")
                    return None

                next_token_in_list = _tokenizer_tokens_list[_tokenizer_current_token_index]
                if next_token_in_list == ')':
                    break # 参数列表结束
                elif next_token_in_list == ',':
                    _tokenizer_current_token_index += 1 # 消耗 ','
                else:
                    logger.error(f"解析错误: 操作符 '{token}' 的参数后期望是 ',' 或 ')'，但得到 '{next_token_in_list}'。")
                    return None

        # 消耗最终的 ')'
        if _tokenizer_current_token_index >= len(_tokenizer_tokens_list) or                _tokenizer_tokens_list[_tokenizer_current_token_index] != ')':
            logger.error(f"解析错误: 操作符 '{token}' 的参数列表后缺少 ')'。")
            return None
        _tokenizer_current_token_index += 1 # 消耗 ')'

        # 根据操作符类型和参数数量验证并构建子节点
        if is_unary:
            if len(args) == 1: op_node.left = args[0]
            else: logger.error(f"参数数量错误: 一元操作符 '{token}' 需要1个参数，得到 {len(args)} 个。"); return None
        elif is_binary:
            if len(args) == 2: op_node.left, op_node.right = args[0], args[1]
            else: logger.error(f"参数数量错误: 二元操作符 '{token}' 需要2个参数，得到 {len(args)} 个。"); return None
        elif is_ts_op:
            if len(args) == 2:
                op_node.left, op_node.right = args[0], args[1]
                # 验证 ts_ops 的第二个参数 (op_node.right) 是否是叶节点且其值在 ts_ops_values 中
                # （_tokenize_expression 将 ts_ops_values 识别为 IDENTIFIER 或 NUMBER）
                if op_node.right.left is not None or op_node.right.right is not None or                         not (op_node.right.value in ts_ops_values or re.fullmatch(r'\d+', op_node.right.value)):
                    logger.error(f"参数类型错误: 时间序列操作符 '{token}' 的第二个参数 '{op_node.right.value}' "
                                 f"必须是预定义的时间窗口值 (来自 {ts_ops_values}) 且为叶节点。实际节点: {op_node.right!r}")
                    return None
            else: logger.error(f"参数数量错误: 时间序列操作符 '{token}' 需要2个参数，得到 {len(args)} 个。"); return None
        return op_node

    # Token 不是已知操作符 -> 假定为终端或数值 (叶节点)
    # _tokenize_expression 已经将数值和标识符区分为 NUMBER 或 IDENTIFIER
    # 进一步验证 IDENTIFIER 是否在动态的 terminal_values 中可以在此进行，如果 terminal_values 可访问。
    # 目前，我们信任词法分析器，并假设任何非操作符的token都是合法的叶节点值。
    elif re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', token) or \
         re.fullmatch(r'-?\d+(?:\.\d+)?', token) or \
         token in ts_ops_values: # ts_ops_values 中的值是字符串化的数字
        _tokenizer_current_token_index += 1 # 消耗终端/数值Token (在 _parse_atom 开始时已消耗)
        return Node(token)
    else:
        # 如果token不是已知操作符，也不是合法的标识符/数值模式，则词法分析器应已捕获
        # 但为防万一，这里加一道保险
        logger.error(f"解析错误 (atom): 未知或非预期的Token '{token}' 作为原子表达式。")
        # _current_token_index -=1 # 回退token? 不，让它失败
        return None

# --- DEV-042: Refactored alpha_to_tree (Main Interface) ---
def alpha_to_tree(expression_str: str) -> Optional[Node]:
    """
    【强制重构版】将Alpha表达式字符串转换为内部树结构 (Node对象)。
    使用词法分析器 (_tokenize_expression) 和递归下降解析器 (_parse_atom) 构建树。

    参数:
        expression_str (str): 要解析的Alpha表达式字符串。

    返回:
        Optional[Node]: 构建的表达式树的根节点，如果解析失败则返回None。
    """
    global _tokenizer_current_token_index, _tokenizer_tokens_list

    if not expression_str or not isinstance(expression_str, str):
        logger.warning("alpha_to_tree 接收到空或非字符串表达式，返回 None。")
        return None

    logger.info(f"开始将表达式字符串解析为树: '{expression_str}'")

    # 1. 词法分析
    _tokenizer_tokens_list = _tokenize_expression(expression_str)
    if _tokenizer_tokens_list is None:
        logger.error(f"表达式 '{expression_str}' 的词法分析失败，无法构建树。")
        return None
    if not _tokenizer_tokens_list:
        logger.info(f"表达式 '{expression_str}' 为空或只包含空格，解析返回空树 (None)。")
        return None

    _tokenizer_current_token_index = 0 # 初始化解析器状态

    # 2. 语法分析 (递归下降)
    try:
        parsed_tree = _parse_atom() # 整个表达式应该是一个原子表达式 (可能嵌套)

        # 3. 检查是否所有tokens都被消耗
        if parsed_tree is not None and _tokenizer_current_token_index < len(_tokenizer_tokens_list):
            logger.error(f"解析错误: 表达式成功解析一部分，但仍有未消耗的Tokens: "
                         f"'{_tokenizer_tokens_list[_tokenizer_current_token_index:]}'。输入表达式可能存在结构问题或尾随字符。")
            parsed_tree = None # 标记为解析失败

    except Exception as e: # 捕获解析过程中任何未预料的错误
        logger.error(f"解析表达式 '{expression_str}' 时发生意外的内部错误: {e}", exc_info=True)
        parsed_tree = None
    finally:
        # 清理模块级状态，以便下次调用是干净的
        _tokenizer_tokens_list = []
        _tokenizer_current_token_index = 0

    if parsed_tree is None:
        logger.error(f"表达式 '{expression_str}' 解析为树失败。")
    else:
        logger.info(f"表达式 '{expression_str}' 成功解析为树。根节点值: {parsed_tree.value}")

    return parsed_tree
# --- 旧的 alpha_to_tree, parse_expression, _build_tree_from_tokens 已被替换 ---


# --- 其他现有函数 (fitness_fun, copy_tree, _collect_nodes, mutate_random_node, crossover, _get_dynamic_terminal_values, best_dX_alphas, depth_X_trees, combine_alphas) ---
# (此处省略这些函数的完整代码以保持简洁，它们与DEV-041中的版本基本一致)
# (确保它们现在使用的是新的 tree_to_alpha 或 alpha_to_tree 如果有需要)

def fitness_fun(Data: pd.DataFrame, n: int) -> List[str]:
    logger.info(f"开始执行 fitness_fun (示意性实现)。输入 DataFrame 行数: {len(Data)}, n: {n}")
    if Data.empty:
        logger.warning("fitness_fun 接收到空的 DataFrame，返回空列表。")
        return []
    returns_col = 'daily_returns'
    benchmark_returns_col = 'benchmark_daily_returns'
    annualization_factor = 252
    sharpe_str = "sharpe_ratio:N/A"
    if returns_col in Data.columns:
        try:
            mean_return = Data[returns_col].mean()
            std_return = Data[returns_col].std()
            if std_return is not None and std_return > 1e-9:
                simulated_sharpe = (mean_return / std_return) * (annualization_factor ** 0.5)
                sharpe_str = f"sharpe_ratio:{simulated_sharpe:.4f}"
            elif std_return is not None and std_return <= 1e-9 and std_return >= 0 :
                sharpe_str = "sharpe_ratio:波动过小" if mean_return == 0 else "sharpe_ratio:波动为零但有均值"
            else:
                sharpe_str = "sharpe_ratio:波动无法计算"
        except Exception as e:
            logger.error(f"计算夏普比率时出错: {e}", exc_info=True)
            sharpe_str = "sharpe_ratio:计算错误"
    total_return_str = "total_return:N/A"
    if returns_col in Data.columns:
        try:
            data_subset = Data
            if n > 0 and n <= len(Data): data_subset = Data.head(n)
            elif n > len(Data): logger.warning(f"fitness_fun: n ({n}) 大于 DataFrame 行数 ({len(Data)})，将使用所有数据计算总收益率。")
            if not data_subset.empty:
                total_ret = (1 + data_subset[returns_col]).prod() - 1
                total_return_str = f"total_return:{total_ret:.4f}"
            else: total_return_str = "total_return:无数据计算"
        except Exception as e:
            logger.error(f"计算总收益率时出错: {e}", exc_info=True)
            total_return_str = "total_return:计算错误"
    n_based_metric_str = f"n_param_value:{n}"
    results_list = [sharpe_str, total_return_str, n_based_metric_str]
    if benchmark_returns_col in Data.columns and returns_col in Data.columns:
        try:
            alpha_val = (Data[returns_col] - Data[benchmark_returns_col]).mean() * annualization_factor
            results_list.append(f"alpha_vs_benchmark:{alpha_val:.4f}")
        except Exception as e:
            logger.warning(f"计算相对基准Alpha时出错: {e}", exc_info=True)
            results_list.append("alpha_vs_benchmark:计算错误")
    logger.info(f"fitness_fun (示意性实现) 计算完成，结果: {results_list}")
    return results_list

def copy_tree(original_node: Optional[Node]) -> Optional[Node]:
    if original_node is None: return None
    left_copy = copy_tree(original_node.left)
    right_copy = copy_tree(original_node.right)
    copied_node = Node(original_node.value, left=left_copy, right=right_copy)
    return copied_node

def _collect_nodes(node: Optional[Node], nodes_list: List[Node]) -> None:
    if node is None: return
    nodes_list.append(node)
    if node.left: _collect_nodes(node.left, nodes_list)
    if node.right: _collect_nodes(node.right, nodes_list)

def mutate_random_node(
    original_node: Node, terminal_vals: List[str], un_ops: List[str],
    bin_ops: List[str], ts_ops_list: List[str], ts_op_vals: List[str]
) -> Node:
    if not isinstance(original_node, Node):
        raise TypeError("mutate_random_node 的 original_node 参数必须是一个 Node 对象。")
    copied_tree_root = copy_tree(original_node)
    if copied_tree_root is None:
        logger.error("mutate_random_node: 复制原始树失败，返回原始树的副本（可能为None）。")
        return copied_tree_root
    nodes_in_copied_tree: List[Node] = []
    _collect_nodes(copied_tree_root, nodes_in_copied_tree)
    if not nodes_in_copied_tree:
        logger.warning("mutate_random_node: 复制的树中没有收集到任何节点，返回原始树的副本。")
        return copied_tree_root
    node_to_mutate = random.choice(nodes_in_copied_tree)
    new_subtree_flag = random.randint(0, 3)
    try:
        new_subtree_root = depth_one_trees(
            terminal_vals, bin_ops, ts_ops_list, ts_op_vals, un_ops, new_subtree_flag
        )
    except ValueError as e:
        logger.error(f"mutate_random_node: 生成新子树时出错 ({e})。将使用随机终端值作为备用。")
        if not terminal_vals:
            logger.critical("mutate_random_node: 终端值列表 (terminal_vals) 为空，无法生成备用变异节点。", exc_info=True)
            raise ValueError("mutate_random_node: 终端值列表 (terminal_vals) 为空，无法生成备用变异节点。") from e
        new_subtree_root = Node(random.choice(terminal_vals))
    except Exception as e_main:
        logger.error(f"mutate_random_node: 生成新替换子树时发生未知错误: {e_main}", exc_info=True)
        if not terminal_vals:
             logger.critical("mutate_random_node: 终端值列表 (terminal_vals) 为空，无法生成备用变异节点。", exc_info=True)
             raise ValueError("mutate_random_node: 终端值列表 (terminal_vals) 为空，无法生成备用变异节点。") from e_main
        new_subtree_root = Node(random.choice(terminal_vals))
    node_to_mutate.value = new_subtree_root.value
    node_to_mutate.left = new_subtree_root.left
    node_to_mutate.right = new_subtree_root.right
    return copied_tree_root

def crossover(parent1: Node, parent2: Node) -> tuple[Node, Node]:
    if not isinstance(parent1, Node) or not isinstance(parent2, Node):
        raise TypeError("crossover 函数的 parent1 和 parent2 参数都必须是 Node 对象。")
    child1 = copy_tree(parent1)
    child2 = copy_tree(parent2)
    if child1 is None or child2 is None:
        logger.warning("crossover: 复制父节点失败或父节点为 None，返回原始副本。")
        return child1, child2
    if random.random() < 0.5:
        if child1.left is not None and child2.left is not None:
            logger.debug(f"交叉操作：交换 {child1.value} 的左子节点 ({child1.left.value if child1.left else 'None'}) 与 {child2.value} 的左子节点 ({child2.left.value if child2.left else 'None'})。")
            temp_left_child = child1.left
            child1.left = child2.left
            child2.left = temp_left_child
        else: logger.info("交叉操作：尝试交换左子节点，但一个或两个子代缺少左子节点，未执行交换。")
    else:
        if child1.right is not None and child2.right is not None:
            logger.debug(f"交叉操作：交换 {child1.value} 的右子节点 ({child1.right.value if child1.right else 'None'}) 与 {child2.value} 的右子节点 ({child2.right.value if child2.right else 'None'})。")
            temp_right_child = child1.right
            child1.right = child2.right
            child2.right = temp_right_child
        else: logger.info("交叉操作：尝试交换右子节点，但一个或两个子代缺少右子节点，未执行交换。")
    if child1 is None or child2 is None:
        logger.error(f"交叉操作后至少一个子代为 None (不应发生若父代有效)。Child1: {child1}, Child2: {child2}", exc_info=True)
        return copy_tree(parent1), copy_tree(parent2)
    return child1, child2

def _get_dynamic_terminal_values(
    brain_api_session: BrainApiSession, strategy: str,
    strategy_params: dict, source_params: dict
) -> List[str]:
    logger.info(f"开始动态获取终端值。策略: {strategy}, 策略参数: {strategy_params}, 数据源参数: {source_params}")
    try:
        all_fields_df = brain_api_session.get_datafields(
            instrument_type=source_params.get('instrument_type', 'EQUITY'),
            region=source_params.get('region', 'USA'),
            delay=source_params.get('delay', 1),
            universe=source_params.get('universe', 'TOP3000'),
            dataset_id=source_params.get('dataset_id', '')
        )
    except Exception as e:
        logger.error(f"调用 Brain API get_datafields 失败: {e}", exc_info=True)
        logger.warning("由于API错误，_get_dynamic_terminal_values 将返回默认终端值列表。")
        return DEFAULT_TERMINAL_VALUES
    if all_fields_df is None or all_fields_df.empty:
        logger.warning("从 Brain API 获取的数据字段列表为空或为None。将使用默认终端值列表。")
        return DEFAULT_TERMINAL_VALUES
    if 'name' not in all_fields_df.columns:
        logger.error("Brain API 返回的 DataFrame 中缺少 'name' 列。将使用默认终端值列表。")
        return DEFAULT_TERMINAL_VALUES
    available_field_names = all_fields_df['name'].dropna().unique().tolist()
    if not available_field_names:
        logger.warning("从DataFrame提取的数据字段名称列表为空。将使用默认终端值列表。")
        return DEFAULT_TERMINAL_VALUES
    logger.info(f"从 Brain API 获取到 {len(available_field_names)} 个可用数据字段。")
    num_selected_fields = strategy_params.get('num_selected_fields', 10)
    selected_fields: List[str] = []
    if strategy == "whitelist":
        whitelist = strategy_params.get('whitelist', [])
        if not isinstance(whitelist, list): logger.warning(f"白名单参数类型错误 (应为list): {whitelist}。退化为随机选择。"); strategy = "random"
        else:
            selected_fields = [f for f in whitelist if f in available_field_names]
            if len(selected_fields) < len(whitelist): logger.warning(f"白名单中的某些字段不在可用字段列表中: {set(whitelist) - set(selected_fields)}")
            if not selected_fields:
                logger.error("白名单策略未能选择任何字段。将尝试从所有可用字段中随机选择。")
                if len(available_field_names) <= num_selected_fields: selected_fields = available_field_names
                else: selected_fields = random.sample(available_field_names, num_selected_fields)
            else: selected_fields = selected_fields[:num_selected_fields]
    elif strategy == "blacklist":
        blacklist = strategy_params.get('blacklist', [])
        if not isinstance(blacklist, list): logger.warning(f"黑名单参数类型错误 (应为list): {blacklist}。退化为随机选择。"); strategy = "random"
        else:
            candidate_fields = [f for f in available_field_names if f not in blacklist]
            if not candidate_fields:
                logger.warning("黑名单策略后没有候选字段。将尝试从所有可用字段中随机选择。")
                if len(available_field_names) <= num_selected_fields: selected_fields = available_field_names
                else: selected_fields = random.sample(available_field_names, num_selected_fields)
            elif len(candidate_fields) <= num_selected_fields: selected_fields = candidate_fields
            else: selected_fields = random.sample(candidate_fields, num_selected_fields)
    elif strategy == "weighted_random":
        weights_dict = strategy_params.get('weights', {})
        if not isinstance(weights_dict, dict): logger.warning(f"权重参数类型错误 (应为dict): {weights_dict}。退化为随机选择。"); strategy = "random"
        else:
            valid_fields_with_weights = {f: weights_dict[f] for f in available_field_names if f in weights_dict and isinstance(weights_dict[f], (int, float)) and weights_dict[f] > 0}
            if not valid_fields_with_weights: logger.warning("加权随机策略：没有字段同时存在于可用字段、权重配置中且权重为正数。退化为随机选择。"); strategy = "random"
            else:
                fields_for_choice = list(valid_fields_with_weights.keys())
                field_actual_weights = [valid_fields_with_weights[f] for f in fields_for_choice]
                if num_selected_fields >= len(fields_for_choice): selected_fields = fields_for_choice; logger.info(f"加权随机：可选字段数 ({len(fields_for_choice)}) 小于等于请求数 ({num_selected_fields})，已全选。")
                else:
                    temp_selected_set = set()
                    attempts = 0; max_attempts = num_selected_fields * 5
                    while len(temp_selected_set) < num_selected_fields and attempts < max_attempts:
                        chosen = random.choices(fields_for_choice, weights=field_actual_weights, k=1)[0]
                        temp_selected_set.add(chosen); attempts += 1
                        if len(temp_selected_set) == len(fields_for_choice): break
                    selected_fields = list(temp_selected_set)
                    if len(selected_fields) < num_selected_fields:
                        remaining_to_select = num_selected_fields - len(selected_fields)
                        potential_pool = [f for f in fields_for_choice if f not in selected_fields]
                        if potential_pool: selected_fields.extend(random.sample(potential_pool, min(remaining_to_select, len(potential_pool))))
                    logger.info(f"加权随机：尝试选择 {num_selected_fields} 个，实际选择 {len(selected_fields)} 个。")
    if strategy == "random" or not selected_fields:
        if strategy != "random": logger.info(f"策略 '{strategy}' 执行后无结果或出错，退化为随机选择策略。")
        if not available_field_names: logger.error("随机选择策略：可用字段列表为空。返回默认终端列表。"); return DEFAULT_TERMINAL_VALUES
        if len(available_field_names) <= num_selected_fields: selected_fields = available_field_names
        else: selected_fields = random.sample(available_field_names, num_selected_fields)
    if not selected_fields:
        logger.error(f"所有策略执行完毕后，未能选择任何终端字段。返回默认列表: {DEFAULT_TERMINAL_VALUES}")
        return DEFAULT_TERMINAL_VALUES
    logger.info(f"最终选择的动态终端值 ({len(selected_fields)}个): {selected_fields}")
    return selected_fields

def best_d1_alphas(
    brain_api: 'BrainApiSession', db: Session, experiment_id: int, ga_config: dict
) -> List[dict]:
    dynamic_terminal_values = _get_dynamic_terminal_values(
        brain_api, ga_config.get('datafield_selection_strategy', 'random'),
        ga_config.get('datafield_selection_params', {}), ga_config.get('data_source_params', {})
    )
    if not dynamic_terminal_values:
        logger.error(f"实验 {experiment_id}: 未能获取动态终端值列表，无法继续 best_d1_alphas。")
        if not dynamic_terminal_values: raise ValueError("无法获取终端值，且默认终端值列表也为空。")
    logger.info(f"实验 {experiment_id}: 使用的终端值 ({len(dynamic_terminal_values)}个): {dynamic_terminal_values}")
    max_depth = ga_config.get('max_alpha_depth', 7)
    max_nodes = ga_config.get('max_nodes_per_alpha', 50)
    population_size = ga_config.get('population_size', 50)
    total_iterations_this_depth = ga_config.get("iterations_at_depth_0", ga_config.get("iterations_per_depth", 10))
    logger.info(f"实验 {experiment_id}: 开始执行遗传算法阶段 best_d1_alphas。配置迭代次数: {total_iterations_this_depth}。")
    logger.debug(f"GA 配置: population_size={population_size}, max_depth={max_depth}, max_nodes={max_nodes}")
    population: List[Node] = []
    attempts = 0
    max_attempts_per_individual = 10
    while len(population) < population_size and attempts < population_size * max_attempts_per_individual :
        flag = random.randint(0, 3)
        try:
            tree = depth_one_trees(
                dynamic_terminal_values, binary_ops, ts_ops,
                ts_ops_values, unary_ops, flag
            )
            current_depth = get_tree_depth(tree)
            current_nodes = count_nodes(tree)
            if current_depth <= max_depth and current_nodes <= max_nodes: population.append(tree)
            else: logger.debug(f"生成的初始树深度 {current_depth} (>{max_depth}) 或节点数 {current_nodes} (>{max_nodes}) 超出约束，丢弃。")
        except ValueError as e:
            logger.warning(f"生成初始树时发生值错误: {e}。尝试继续...", exc_info=True)
        except Exception as e_general:
            logger.error(f"生成初始树时发生意外错误: {e_general}。尝试继续...", exc_info=True)
        attempts += 1
    if len(population) < population_size and attempts >= population_size * max_attempts_per_individual:
        logger.warning(f"实验 {experiment_id}: 达到最大尝试次数后，未能生成足够的符合约束的初始种群 (实际: {len(population)}, 预期: {population_size})。")
        if not population:
             logger.critical(f"实验 {experiment_id}: 无法生成任何有效的初始种群个体。请检查配置和终端/操作符列表。", exc_info=True)
             raise RuntimeError(f"实验 {experiment_id}: 无法生成任何有效的初始种群个体。")
    elif len(population) < population_size:
         logger.warning(f"实验 {experiment_id}: 最终生成的初始种群数量 ({len(population)}) 少于预期 ({population_size}) 但仍将继续。")
    logger.info(f"实验 {experiment_id}: 已生成初始种群，数量: {len(population)}，使用动态终端值并应用了复杂性约束。")
    # ... (placeholder GA loop with Alpha simulation error handling comments from DEV-034) ...
    time.sleep(1)
    logger.info(f"实验 {experiment_id}: 遗传算法阶段 best_d1_alphas (占位符逻辑部分) 完成。")
    return [
        {"expression": f"placeholder_d1_exp{experiment_id}_alpha_1", "fitness": 0.5, "details": "来自best_d1_alphas占位符"},
        {"expression": f"placeholder_d1_exp{experiment_id}_alpha_2", "fitness": 0.4, "details": "来自best_d1_alphas占位符"}
    ]

def best_d2_alphas(
    brain_api: 'BrainApiSession', db: Session, experiment_id: int, ga_config: dict,
    previous_generation_alphas: List[dict]
) -> List[dict]:
    dynamic_terminal_values = _get_dynamic_terminal_values(
        brain_api, ga_config.get('datafield_selection_strategy', 'random'),
        ga_config.get('datafield_selection_params', {}), ga_config.get('data_source_params', {})
    )
    if not dynamic_terminal_values:
        logger.error(f"实验 {experiment_id}: 未能获取动态终端值列表，无法继续 best_d2_alphas。")
        if not dynamic_terminal_values: raise ValueError("无法获取终端值，且默认终端值列表也为空。")
    logger.info(f"实验 {experiment_id}: best_d2_alphas 使用的终端值 ({len(dynamic_terminal_values)}个): {dynamic_terminal_values}")
    max_depth = ga_config.get('max_alpha_depth', 7)
    max_nodes = ga_config.get('max_nodes_per_alpha', 50)
    total_iterations_this_depth = ga_config.get("iterations_at_depth_1", ga_config.get("iterations_per_depth", 10))
    logger.info(f"实验 {experiment_id}: 开始执行遗传算法阶段 best_d2_alphas。配置迭代次数: {total_iterations_this_depth}。")
    logger.debug(f"接收到上一代 Alpha 数量: {len(previous_generation_alphas)}")
    logger.debug(f"GA 配置: max_depth={max_depth}, max_nodes={max_nodes}")
    time.sleep(1)
    logger.info(f"实验 {experiment_id}: 遗传算法阶段 best_d2_alphas (占位符逻辑) 完成。")
    return [{"expression": f"placeholder_d2_exp{experiment_id}_alpha_1", "fitness": 0.7, "details": "来自best_d2_alphas占位符"}]

def best_d3_alpha(
    brain_api: 'BrainApiSession', db: Session, experiment_id: int, ga_config: dict,
    previous_generation_alphas: List[dict]
) -> List[dict]:
    dynamic_terminal_values = _get_dynamic_terminal_values(
        brain_api, ga_config.get('datafield_selection_strategy', 'random'),
        ga_config.get('datafield_selection_params', {}), ga_config.get('data_source_params', {})
    )
    if not dynamic_terminal_values:
        logger.error(f"实验 {experiment_id}: 未能获取动态终端值列表，无法继续 best_d3_alpha。")
        if not dynamic_terminal_values: raise ValueError("无法获取终端值，且默认终端值列表也为空。")
    logger.info(f"实验 {experiment_id}: best_d3_alpha 使用的终端值 ({len(dynamic_terminal_values)}个): {dynamic_terminal_values}")
    max_depth = ga_config.get('max_alpha_depth', 7)
    max_nodes = ga_config.get('max_nodes_per_alpha', 50)
    total_iterations_this_depth = ga_config.get("iterations_at_depth_2", ga_config.get("iterations_per_depth", 10))
    logger.info(f"实验 {experiment_id}: 开始执行遗传算法阶段 best_d3_alpha。配置迭代次数: {total_iterations_this_depth}。")
    logger.debug(f"接收到上一代 Alpha 数量: {len(previous_generation_alphas)}")
    logger.debug(f"GA 配置: max_depth={max_depth}, max_nodes={max_nodes}")
    time.sleep(1)
    logger.info(f"实验 {experiment_id}: 遗传算法阶段 best_d3_alpha (占位符逻辑) 完成。")
    return [{"expression": f"placeholder_d3_exp{experiment_id}_alpha_final", "fitness": 0.9, "details": "来自best_d3_alpha占位符"}]

import time

def depth_one_trees(
    terminal_vals: List[str], bin_ops_list: List[str],
    time_series_ops_list: List[str], time_series_op_vals_list: List[str],
    un_ops_list: List[str], flag: int
) -> Node:
    root_node: Optional[Node] = None
    if flag == 0:
        if not terminal_vals: raise ValueError("终端值列表不能为空 (terminal_vals)")
        selected_terminal = random.choice(terminal_vals); root_node = Node(selected_terminal)
    elif flag == 1:
        if not unary_ops: logger.warning("一元操作符列表为空..."); if not terminal_vals: raise ValueError("..."); return Node(random.choice(terminal_vals))
        if not terminal_vals: raise ValueError("终端值列表不能为空...")
        selected_operator = random.choice(unary_ops); selected_terminal_child = random.choice(terminal_vals)
        root_node = Node(selected_operator, left=Node(selected_terminal_child))
    elif flag == 2:
        if not binary_ops: logger.warning("二元操作符列表为空..."); if not terminal_vals: raise ValueError("..."); return Node(random.choice(terminal_vals))
        if not terminal_vals : raise ValueError("终端值列表不能为空...")
        selected_operator = random.choice(binary_ops); left_child = Node(random.choice(terminal_vals)); right_child = Node(random.choice(terminal_vals))
        root_node = Node(selected_operator, left=left_child, right=right_child)
    elif flag == 3:
        if not ts_ops: logger.warning("时间序列操作符列表为空..."); if not terminal_vals: raise ValueError("..."); return Node(random.choice(terminal_vals))
        if not terminal_vals: raise ValueError("终端值列表不能为空...")
        if not ts_ops_values: raise ValueError("时间序列操作参数值列表不能为空...")
        selected_operator = random.choice(ts_ops); data_child = Node(random.choice(terminal_vals)); period_child = Node(random.choice(ts_ops_values))
        root_node = Node(selected_operator, left=data_child, right=period_child)
    else:
        if not terminal_vals: raise ValueError("终端值列表不能为空...")
        selected_terminal = random.choice(terminal_vals); root_node = Node(selected_terminal)
    if root_node is None: raise RuntimeError(f"未能为 flag {flag} 创建有效的深度一树节点。")
    return root_node

def depth_two_tree(
    tree1: Node, tree2: Node, time_series_op_vals_list: List[str],
    time_series_ops_list: List[str], flag: int
) -> Node:
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
    return root_node

def depth_three_tree(sub_trees: List[Node], flag: int) -> Node:
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
                right_child = depth_one_trees(DEFAULT_TERMINAL_VALUES, binary_ops, ts_ops, ts_ops_values, unary_ops, right_child_flag)
            except ValueError as e:
                logger.error(f"depth_three_tree: 生成右子树时出错: {e}。将尝试仅使用终端值。", exc_info=True)
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
            right_child = depth_one_trees(current_terminals_for_subtree, binary_ops, ts_ops, ts_ops_values, unary_ops, right_child_flag)
        except ValueError as e:
            logger.error(f"depth_three_tree (default): 生成右子树时出错: {e}。", exc_info=True)
            if not DEFAULT_TERMINAL_VALUES: raise ValueError("默认终端值列表为空...") from e
            right_child = Node(random.choice(DEFAULT_TERMINAL_VALUES))
        root_node = Node(selected_operator, left=left_child, right=right_child)
    if root_node is None: raise RuntimeError(f"未能为 flag {flag} 和提供的子树创建有效的深度三树节点。")
    return root_node

# --- Alpha 表达式组合功能 ---
def combine_alphas(alpha_expressions: List[str], method: str = "add") -> str:
    if not alpha_expressions: logger.warning("Alpha表达式列表为空，无法进行组合."); return ""
    valid_expressions = [str(expr) for expr in alpha_expressions if expr and isinstance(expr, (str, int, float))]
    valid_expressions = [expr for expr in valid_expressions if expr.strip()]
    if not valid_expressions: logger.warning("有效的Alpha表达式列表为空..."); return ""
    num_expressions = len(valid_expressions)
    if num_expressions == 1:
        logger.info(f"只有一个有效的Alpha表达式 '{valid_expressions[0]}', 直接返回。")
        if not _validate_alpha_syntax(valid_expressions[0]): logger.warning(f"单个表达式 '{valid_expressions[0]}' 未通过语法验证。")
        return valid_expressions[0]
    combined_expr = ""
    logger.info(f"开始组合 {num_expressions} 个Alpha表达式，使用方法: '{method}'. 表达式: {valid_expressions}")
    if method == "add":
        current_expr = valid_expressions[0]
        for i in range(1, num_expressions): current_expr = f"add({current_expr},{valid_expressions[i]})"
        combined_expr = current_expr
    elif method == "mean":
        sum_expr = valid_expressions[0]
        for i in range(1, num_expressions): sum_expr = f"add({sum_expr},{valid_expressions[i]})"
        combined_expr = f"divide({sum_expr},{num_expressions})"
    else:
        logger.error(f"不支持的Alpha组合方法: '{method}'. 可用方法: 'add', 'mean'.")
        return ""
    if not _validate_alpha_syntax(combined_expr):
        logger.warning(f"组合后的表达式 '{combined_expr}' 未通过基本语法验证。请检查组合逻辑或输入表达式。")
    logger.info(f"Alpha表达式组合完成: '{combined_expr}'.")
    return combined_expr

# (DEV-041: End of file, ensuring no old d*tree_to_alpha functions remain implicitly)
# (Typing import at the top was already List, Optional, Dict, added Any for combine_alphas)
# (Tuple was not needed for this refactoring)
