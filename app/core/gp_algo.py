# 导入 random 模块，用于在遗传编程操作中进行随机选择，例如选择操作符、终端或交叉点。
import random
# 从 typing 模块导入 Optional 和 List 类型提示，用于增强代码的可读性和静态分析能力。
# Optional[X] 表示一个参数或返回值可以是 X 类型，也可以是 None。
# List[X] 表示一个列表，其所有元素都是 X 类型。
from typing import Optional, List
import logging # 导入 logging 模块
import pandas as pd # 导入 pandas 用于数据处理，特别是 fitness_fun 中的 DataFrame 操作

logger = logging.getLogger(__name__) # 获取 logger 实例，以便使用 logger.warning

class Node:
    """
    表示遗传编程中表达式树的一个节点。
    每个节点可以是一个操作符（例如 '+'、'ts_rank'）、一个终端（例如 'close', 'vwap'）或一个常量值。
    """
    def __init__(self, value: str, left: Optional['Node'] = None, right: Optional['Node'] = None):
        """
        初始化一个树节点。

        参数:
            value (str): 节点存储的值，例如操作符名称、终端符号或常量。
            left (Optional['Node']): 左子节点。对于一元操作符或终端，可能为 None。
                                     默认为 None。
            right (Optional['Node']): 右子节点。对于一元操作符、二元操作符的第一个操作数或终端，可能为 None。
                                      默认为 None。
        """
        self.value: str = value  # 节点的值 (操作符、终端或常量)
        self.left: Optional['Node'] = left    # 左子节点
        self.right: Optional['Node'] = right  # 右子节点

    def __repr__(self) -> str:
        """
        返回节点的字符串表示形式，方便调试和可视化。
        例如：Node('add', Node('close'), Node('open'))
        """
        # 构建子节点的表示
        left_repr = repr(self.left) if self.left else 'None'
        right_repr = repr(self.right) if self.right else 'None'

        # 如果没有子节点（即终端节点）
        if self.left is None and self.right is None:
            return f"Node('{self.value}')"
        # 如果只有左子节点（可能是一元操作符，或不完整的树）
        elif self.right is None:
            return f"Node('{self.value}', left={left_repr})"
        # 如果有左右子节点（可能是二元操作符）
        # (注意：严格来说，一元操作符不应该有right，但这里repr更通用)
        else:
            return f"Node('{self.value}', left={left_repr}, right={right_repr})"

    # 后续可能会添加其他与节点操作相关的方法，例如计算节点深度、复制节点等。

# --- Alpha 表达式构建块 (Alpha Expression Building Blocks) ---
# 这些列表定义了遗传编程算法在构建 Alpha 表达式树时可以使用的基本元素。

# 终端值 (Terminal Values): 这些是表达式树的叶子节点，通常代表原始数据字段或常量。
terminal_values: List[str] = [
    "close", "open", "high", "low", "vwap",  # 基本价格数据
    "adv20",  # 20日平均成交量 (average daily volume over 20 days)
    "volume", # 当日成交量
    "cap",    # 市值 (market capitalization)
    "returns",# 收益率 (通常是日收益率)
    "dividend"# 股息 (可能需要特定处理，如作为因子或过滤条件)
]
# 注释：终端值列表可以根据实际可用的数据字段进行扩展。

# 时间序列操作符 (Time-Series Operators): 这些操作符通常作用于一个或多个时间序列数据。
# 格式通常是 op(data, period) 或 op(data1, data2, period) 等。
ts_ops: List[str] = [
    "ts_zscore",  # 时间序列 Z-score (标准化)
    "ts_rank",    # 时间序列排名百分比
    "ts_arg_max", # 时间序列最大值位置
    "ts_arg_min", # 时间序列最小值位置
    "ts_backfill",# 时间序列数据回填 (处理NaN)
    "ts_delta",   # 时间序列差分 (例如，今天的某个值 - 昨天的某个值)
    "ts_ir",      # 信息比率 (Information Ratio)
    "ts_mean",    # 时间序列移动平均
    "ts_median",  # 时间序列移动中位数
    "ts_product", # 时间序列累乘
    "ts_std_dev"  # 时间序列标准差
]
# 注释：具体 ts_ops 的参数数量和类型需要与 WorldQuant Brain API 的定义一致。

# 二元操作符 (Binary Operators): 这些操作符接收两个操作数。
binary_ops: List[str] = [
    "add",      # 加法: op(A, B) -> A + B
    "subtract", # 减法: op(A, B) -> A - B
    "divide",   # 除法: op(A, B) -> A / B (需注意除零错误处理)
    "multiply", # 乘法: op(A, B) -> A * B
    "max",      # 最大值: op(A, B) -> max(A, B)
    "min"       # 最小值: op(A, B) -> min(A, B)
]

# 时间序列操作符的参数值 (Time-Series Operator Values/Periods):
# 这些通常是时间序列操作符（如 ts_mean, ts_rank）所需的时间窗口参数。
ts_ops_values: List[str] = [
    "20", "40", "60", "120", "240" # 例如，代表20天、40天等周期
]
# 注释：这些值在生成表达式树时，通常作为某些 ts_ops 的第二个参数（叶子节点）。

# 一元操作符 (Unary Operators): 这些操作符接收一个操作数。
unary_ops: List[str] = [
    "rank",        # 横截面排名百分比
    "zscore",      # 横截面 Z-score (标准化)
    "winsorize",   # Winsorize 处理 (去极值)
    "normalize",   # 归一化处理
    "rank_by_side",# 按边排名 (例如，多头组合按升序，空头按降序)
    "sigmoid",     # Sigmoid 函数变换
    "pasteurize",  # Pasteurize 处理 (一种去极值或平滑方法)
    "log"          # 自然对数: op(A) -> ln(A) (需注意定义域，A > 0)
]

def _recursive_tree_to_alpha(node: Optional[Node]) -> str:
    """
    递归辅助函数，将以 'node' 为根的表达式树转换为 Alpha 表达式字符串。

    参数:
        node (Optional[Node]): 当前要转换的树节点。如果为 None，则表示空子树。

    返回:
        str: 该节点及其子树对应的 Alpha 表达式字符串。
             如果节点为 None 或无效，则返回空字符串。
    """
    if node is None:
        logger.warning("_recursive_tree_to_alpha 接收到 None 节点，返回空字符串。")
        return "" # 处理空子树的情况

    node_value_str = str(node.value) # 确保节点值是字符串

    # 检查节点值是否是终端值或时间序列操作的参数值 (通常是数字字符串)
    # 这些类型的节点是递归的终点，直接返回其值。
    if node_value_str in terminal_values or node_value_str in ts_ops_values:
        return node_value_str

    # 检查节点值是否是一元操作符
    elif node_value_str in unary_ops:
        if node.left:
            # 递归转换左子树，并格式化为 "op(left_child_expr)"
            left_expr = _recursive_tree_to_alpha(node.left)
            return f"{node_value_str}({left_expr})"
        else:
            # 一元操作符必须有左子节点
            logger.error(f"一元操作符 '{node_value_str}' 缺少左子节点。")
            return "" # 或根据错误处理策略抛出异常

    # 检查节点值是否是二元操作符
    elif node_value_str in binary_ops:
        if node.left and node.right:
            # 递归转换左右子树，并格式化为 "op(left_child_expr,right_child_expr)"
            left_expr = _recursive_tree_to_alpha(node.left)
            right_expr = _recursive_tree_to_alpha(node.right)
            return f"{node_value_str}({left_expr},{right_expr})"
        else:
            # 二元操作符必须有左右两个子节点
            logger.error(f"二元操作符 '{node_value_str}' 缺少一个或两个子节点。")
            return ""

    # 检查节点值是否是时间序列操作符
    # 时间序列操作符在结构上通常类似于二元操作符 (例如 ts_rank(data, period))
    elif node_value_str in ts_ops:
        if node.left and node.right:
            # 递归转换左右子树 (通常左边是数据字段树，右边是周期值节点)
            left_expr = _recursive_tree_to_alpha(node.left)
            right_expr = _recursive_tree_to_alpha(node.right)
            return f"{node_value_str}({left_expr},{right_expr})"
        else:
            # 时间序列操作符通常需要两个参数
            logger.error(f"时间序列操作符 '{node_value_str}' 缺少一个或两个子节点。")
            return ""

    else:
        # 如果节点值不属于任何已知的操作符或终端类型
        logger.error(f"未知的节点类型或值: '{node_value_str}'。无法转换为表达式。")
        return "" # 或者抛出异常，表示树结构不符合预期

def tree_to_alpha(tree: Node) -> str:
    """
    将给定的表达式树转换为 Alpha 表达式字符串。
    这是调用递归辅助函数 _recursive_tree_to_alpha 的公共接口。

    参数:
        tree (Node): 要转换的表达式树的根节点。

    返回:
        str: 转换后的 Alpha 表达式字符串。
             如果输入的树为空或无效，可能返回空字符串（取决于 _recursive_tree_to_alpha 的行为）。
    """
    if not isinstance(tree, Node):
        logger.error(f"tree_to_alpha 接收到的输入不是有效的 Node 对象: {type(tree)}。将返回空字符串。")
        return ""

    logger.debug(f"开始将树转换为 Alpha 表达式: {tree!r}") # 记录整个树的表示形式可能很长, 使用!r

    expression_str = _recursive_tree_to_alpha(tree)

    if not expression_str:
        logger.warning(f"树转换为 Alpha 表达式的结果为空字符串。可能原因：树为空、结构无效或包含未知节点。输入树: {tree!r}")
        # !r 用于获取 repr 表示，避免过长的日志

    logger.info(f"树成功转换为 Alpha 表达式: '{expression_str}'") # 记录生成的表达式
    return expression_str

# ... (后续将定义 fitness_fun 等) ...
# 确保 pandas 已导入:
# import pandas as pd # 应已在文件顶部

def fitness_fun(Data: pd.DataFrame, n: int) -> List[str]: # List 来自 typing
    """
    计算适应度函数（占位符/示意性实现）。

    注意：此函数的当前实现是高度示意性的，基于对常规适应度函数功能的猜测，
    并试图匹配任务描述中给出的非常规返回类型 (List[str])。
    实际的适应度计算逻辑需要根据 'code.py' 中的原始实现或具体项目需求来确定和替换。

    参数:
        Data (pd.DataFrame): 输入的 Pandas DataFrame。
                             假设此 DataFrame 包含评估 Alpha 表现所需的数据列，
                             例如 'returns' (收益率), 'sharpe_ratio' (夏普比率) 等。
                             列名和数据内容是假设的。
        n (int): 一个整数参数。其具体用途未知，取决于 'code.py' 的原始逻辑。
                 在此示意性实现中，可能会象征性地使用它，例如选择前 n 行或进行某种聚合。

    返回:
        List[str]: 一个字符串列表。根据任务描述的签名。
                   此列表的内容在此示意性实现中将是转换后的数值指标。
                   例如：["sharpe:1.5", "annual_return:0.12", "max_drawdown:-0.05"]
    """
    logger.info(f"开始执行 fitness_fun (示意性实现)。输入 DataFrame 行数: {len(Data)}, n: {n}")

    if Data.empty:
        logger.warning("fitness_fun 接收到空的 DataFrame，返回空列表。")
        return []

    # --- 以下为示意性计算逻辑 ---
    # 实际逻辑需要从 code.py 移植或根据需求重新定义。

    # 假设的列名，这些列需要在输入的 DataFrame 'Data' 中存在
    returns_col = 'daily_returns' # 假设有每日收益率列
    benchmark_returns_col = 'benchmark_daily_returns' # 假设有基准每日收益率列 (可选)
    annualization_factor = 252 # 假设一年252个交易日


    # 示例1：计算（年化）夏普比率的字符串表示
    # 这里只是非常粗略的计算，实际夏普比率计算更复杂
    sharpe_str = "sharpe_ratio:N/A"
    if returns_col in Data.columns:
        # 假设 n 代表回测期天数，如果不是，这个年化因子需要调整
        try:
            # 简单计算，未考虑无风险利率
            mean_return = Data[returns_col].mean()
            std_return = Data[returns_col].std()
            if std_return is not None and std_return > 1e-9: # 避免除以非常小的值或零
                # 假设 n 是用于选择前 n 条数据进行计算，或 n 是年化中的一部分
                # 这里简单地使用整个Data的均值和标准差
                simulated_sharpe = (mean_return / std_return) * (annualization_factor ** 0.5)
                sharpe_str = f"sharpe_ratio:{simulated_sharpe:.4f}"
            elif std_return is not None and std_return <= 1e-9 and std_return >= 0 : # 如果标准差非常接近0（但非负）
                sharpe_str = "sharpe_ratio:波动过小" if mean_return == 0 else "sharpe_ratio:波动为零但有均值"

            else: # std_return is None or NaN
                sharpe_str = "sharpe_ratio:波动无法计算"
        except Exception as e:
            logger.error(f"计算夏普比率时出错: {e}")
            sharpe_str = "sharpe_ratio:计算错误"

    # 示例2：计算总收益率的字符串表示
    total_return_str = "total_return:N/A"
    if returns_col in Data.columns:
        try:
            # 假设 n 是用于选择数据范围，这里使用 Data 的前 n 行 (如果 n 合法)
            # 如果 n 无效或未指定，则使用整个数据集
            data_subset = Data
            if n > 0 and n <= len(Data):
                data_subset = Data.head(n)
            elif n > len(Data):
                 logger.warning(f"fitness_fun: n ({n}) 大于 DataFrame 行数 ({len(Data)})，将使用所有数据计算总收益率。")
            # else n <= 0 or invalid, use all data

            if not data_subset.empty:
                total_ret = (1 + data_subset[returns_col]).prod() - 1
                total_return_str = f"total_return:{total_ret:.4f}"
            else:
                total_return_str = "total_return:无数据计算" # Should not happen if Data is not empty
        except Exception as e:
            logger.error(f"计算总收益率时出错: {e}")
            total_return_str = "total_return:计算错误"

    # 示例3：一个基于参数 n 的简单指标 (纯粹示意)
    n_based_metric_str = f"n_param_value:{n}"

    # 结果列表
    results_list = [sharpe_str, total_return_str, n_based_metric_str]

    # 假设还需要返回其他指标，例如相对于基准的表现（如果提供了基准数据）
    if benchmark_returns_col in Data.columns and returns_col in Data.columns:
        try:
            alpha_val = (Data[returns_col] - Data[benchmark_returns_col]).mean() * annualization_factor
            results_list.append(f"alpha_vs_benchmark:{alpha_val:.4f}")
        except Exception as e:
            logger.warning(f"计算相对基准Alpha时出错: {e}")
            results_list.append("alpha_vs_benchmark:计算错误")

    logger.info(f"fitness_fun (示意性实现) 计算完成，结果: {results_list}")
    return results_list

# ... (文件末尾)

def copy_tree(original_node: Optional[Node]) -> Optional[Node]:
    """
    深度复制一个表达式树。

    通过递归方式创建一个与原始树结构相同、节点值相同的新树。
    对副本的修改不会影响原始树。

    参数:
        original_node (Optional[Node]): 要复制的原始树的根节点。
                                         如果为 None，则表示空树。

    返回:
        Optional[Node]: 新创建的树的根节点副本。如果原始节点为 None，则返回 None。
    """
    # 基本情况：如果原始节点是 None (空树或叶子节点的子节点)，则副本也是 None。
    if original_node is None:
        return None

    # 递归复制左子树。
    left_copy = copy_tree(original_node.left)
    # 递归复制右子树。
    right_copy = copy_tree(original_node.right)

    # 创建当前节点的新副本，其值为原始节点的值，
    # 子节点为前面递归复制得到的左右子树副本。
    copied_node = Node(original_node.value, left=left_copy, right=right_copy)

    # logger.debug(f"已复制节点: {original_node!r} -> {copied_node!r}")
    return copied_node

def _collect_nodes(node: Optional[Node], nodes_list: List[Node]) -> None:
    """
    递归辅助函数，用于收集给定树中所有的节点。

    采用前序遍历（根-左-右）的方式将树中所有节点添加到一个列表中。
    这个列表可以用于后续操作，例如随机选择一个节点进行变异或交叉。

    参数:
        node (Optional[Node]): 当前正在访问的树节点。如果为 None，则不执行任何操作。
        nodes_list (List[Node]): 用于存储收集到的节点的列表。
                                 调用者应传入一个空列表，此函数会向其中填充节点。
                                 (注意：列表是可变对象，函数直接修改传入的列表)
    返回:
        None: 此函数不返回值，而是直接修改 `nodes_list`。
    """
    if node is None:
        return # 基本情况：如果节点为空，则结束当前路径的递归

    # 将当前节点添加到列表中 (前序遍历：先处理根节点)
    nodes_list.append(node)

    # 递归访问左子树
    if node.left: # 只有当左子节点存在时才递归
        _collect_nodes(node.left, nodes_list)

    # 递归访问右子树
    if node.right: # 只有当右子节点存在时才递归
        _collect_nodes(node.right, nodes_list)

    # 如果是中序遍历，则 append(node) 会在左右递归调用之间。
    # 如果是后序遍历，则 append(node) 会在左右递归调用之后。
    # 前序遍历通常对于获取所有节点（包括根）是直接且方便的。

def mutate_random_node(
    original_node: Node,
    # 以下参数用于生成新的替换子树 (通常是深度为一的树)
    # 与 depth_one_trees 的参数保持一致
    terminal_vals: List[str],
    un_ops: List[str],
    bin_ops: List[str],
    ts_ops_list: List[str], # 避免与全局变量 ts_ops 名称冲突
    ts_op_vals: List[str]
) -> Node:
    """
    对给定的表达式树进行随机节点变异。

    变异过程包括：
    1. 深度复制原始树，以避免修改原树。
    2. 从复制的树中随机选择一个节点。
    3. 生成一个新的随机子树（通常是深度为一的树）。
    4. 用新生成的子树替换选定节点的内容 (value, left, right)。
       这意味着选中的节点本身被新子树的根节点所取代。

    参数:
        original_node (Node): 要进行变异的原始树的根节点。
        terminal_vals (List[str]): 用于生成新子树的终端值列表。
        un_ops (List[str]): 用于生成新子树的一元操作符列表。
        bin_ops (List[str]): 用于生成新子树的二元操作符列表。
        ts_ops_list (List[str]): 用于生成新子树的时间序列操作符列表。
        ts_op_vals (List[str]): 用于生成新子树的时间序列操作参数值列表。

    返回:
        Node: 变异后产生的新树的根节点。
    """
    if not isinstance(original_node, Node):
        # 或者可以尝试复制，但如果不是Node，复制也可能失败
        raise TypeError("mutate_random_node 的 original_node 参数必须是一个 Node 对象。")

    # 1. 深度复制原始树
    copied_tree_root = copy_tree(original_node)
    if copied_tree_root is None: # original_node 本身就是 None 的罕见情况
        # 如果允许 original_node 为 None，则直接返回 None，或抛出错误
        # 但函数签名指定 Node，所以理论上 original_node 不应为 None
        # 为安全起见，如果 copy_tree 返回 None (例如 original_node.value 无效导致 Node 创建失败)
        logger.error("mutate_random_node: 复制原始树失败，返回原始树的副本（可能为None）。")
        return copied_tree_root # 或 raise

    # 2. 收集复制树中的所有节点
    nodes_in_copied_tree: List[Node] = []
    _collect_nodes(copied_tree_root, nodes_in_copied_tree)

    if not nodes_in_copied_tree:
        # 这通常不应该发生，除非原始树是一个无效的空 Node 对象 (不是 None，而是例如 Node(None) 且无子节点)
        logger.warning("mutate_random_node: 复制的树中没有收集到任何节点，返回原始树的副本。")
        return copied_tree_root

    # 3. 从节点列表中随机选择一个节点进行变异
    node_to_mutate = random.choice(nodes_in_copied_tree)
    # logger.debug(f"mutate_random_node: 选定进行变异的节点: {node_to_mutate!r}")

    # 4. 生成一个新的随机子树（这里选择生成深度为一的树作为替换）
    # 随机选择新子树的类型 (0:term, 1:unary, 2:binary, 3:ts_op)
    new_subtree_flag = random.randint(0, 3)
    try:
        # 使用传入的参数列表来生成新的深度一的树
        new_subtree_root = depth_one_trees(
            terminal_vals, bin_ops, ts_ops_list, ts_op_vals, un_ops, new_subtree_flag
        )
    except ValueError as e:
        # 如果 depth_one_trees 由于列表为空等原因失败，则创建一个简单的终端节点作为备用
        logger.error(f"mutate_random_node: 生成新子树时出错 ({e})。将使用随机终端值作为备用。")
        if not terminal_vals:
            # 这种情况非常严重，无法生成备用终端
            raise ValueError("mutate_random_node: 终端值列表 (terminal_vals) 为空，无法生成备用变异节点。") from e
        new_subtree_root = Node(random.choice(terminal_vals))

    # logger.debug(f"mutate_random_node: 生成的用于替换的新子树: {new_subtree_root!r}")

    # 5. 用新生成的子树的属性替换选定节点的属性
    # 这相当于将 node_to_mutate "变成" new_subtree_root
    node_to_mutate.value = new_subtree_root.value
    node_to_mutate.left = new_subtree_root.left
    node_to_mutate.right = new_subtree_root.right

    # logger.info(f"mutate_random_node: 节点已变异。变异后的树根: {copied_tree_root!r}")

    # 兼容性检查：
    # 当前的实现是替换整个节点（包括其子节点，如果新子树有的话）。
    # `depth_one_trees` 生成的树本身是符合基本结构的。
    # 例如，如果一个二元操作符被替换为一个终端，那么它原来的子节点就丢失了，
    # 这是变异的一种形式（子树替换）。
    # 如果要求更严格的“类型保持”变异（例如操作符只能替换为操作符），则需要更复杂的逻辑。
    # 验收标准提到“变异后的树结构有效”，当前方式通过用一个有效的（深度一）子树替换来保证。

    return copied_tree_root

def crossover(parent1: Node, parent2: Node) -> tuple[Node, Node]:
    """
    对两个父表达式树进行交叉操作，生成两个子代树。

    当前的实现是一个简化版本（基于任务DEV-011的代码片段提示）：
    随机选择交换两个父树副本的直接左子节点或直接右子节点。
    这并非通用的随机子树交叉，但为后续更复杂实现打下基础。

    参数:
        parent1 (Node): 第一个父树的根节点。
        parent2 (Node): 第二个父树的根节点。

    返回:
        tuple[Node, Node]: 一个包含两个新生成的子代树根节点的元组 (child1, child2)。
                           如果输入的父节点不适合进行此简化交叉（例如缺少子节点），
                           则子代可能与父代相同或部分相同。
    """
    if not isinstance(parent1, Node) or not isinstance(parent2, Node):
        raise TypeError("crossover 函数的 parent1 和 parent2 参数都必须是 Node 对象。")

    # 1. 深度复制父树，生成子代树的初始版本
    child1 = copy_tree(parent1)
    child2 = copy_tree(parent2)

    # 如果复制失败（例如原始父节点无效），或者父节点本身就是 None，则直接返回副本
    if child1 is None or child2 is None:
        logger.warning("crossover: 复制父节点失败或父节点为 None，返回原始副本。")
        return child1, child2 # type: ignore # mypy 可能抱怨 None，但copy_tree处理了Optional

    # 2. 实现简化版交叉：随机交换直接子节点
    #    这种交叉方式非常依赖于树的顶层结构。
    #    更通用的交叉会使用 _collect_nodes 选择任意子树。

    # 确保两个子代树都有可以交换的子节点
    # 为了简单起见，我们只考虑两层结构（根节点和其直接子节点）
    # 随机决定是交换左子节点还是右子节点
    if random.random() < 0.5: # 尝试交换左子节点
        # 确保双方都有左子节点可以交换
        if child1.left is not None and child2.left is not None:
            logger.debug(f"交叉操作：交换 {child1.value} 的左子节点 ({child1.left.value if child1.left else 'None'}) "
                         f"与 {child2.value} 的左子节点 ({child2.left.value if child2.left else 'None'})。")
            temp_left_child = child1.left
            child1.left = child2.left
            child2.left = temp_left_child
        else:
            logger.info("交叉操作：尝试交换左子节点，但一个或两个子代缺少左子节点，未执行交换。")
    else: # 尝试交换右子节点
        # 确保双方都有右子节点可以交换
        if child1.right is not None and child2.right is not None:
            logger.debug(f"交叉操作：交换 {child1.value} 的右子节点 ({child1.right.value if child1.right else 'None'}) "
                         f"与 {child2.value} 的右子节点 ({child2.right.value if child2.right else 'None'})。")
            temp_right_child = child1.right
            child1.right = child2.right
            child2.right = temp_right_child
        else:
            logger.info("交叉操作：尝试交换右子节点，但一个或两个子代缺少右子节点，未执行交换。")

    # 兼容性检查：
    # 当前的简化交叉直接交换子树引用，不进行显式的类型或语义兼容性检查。
    # 假设被交换的子树本身是有效的。
    # 验收标准中“子树结构有效”主要依赖于 copy_tree 和被交换子树的原始有效性。
    # “操作符不能替换为终端值”这类兼容性检查在更复杂的、节点级别值替换的变异或交叉中更突出。
    # 对于子树交换，只要确保父节点仍然是合法的操作符即可。

    # logger.info(f"crossover: 交叉完成。 Child1: {child1!r}, Child2: {child2!r}")
    return child1, child2

# ... (文件末尾) ...

def depth_one_trees(
    terminal_vals: List[str],  # 参数名修改以避免与全局变量混淆，下同
    bin_ops: List[str],
    time_series_ops: List[str],
    time_series_op_vals: List[str],
    un_ops: List[str],
    flag: int
) -> Node:
    """
    生成深度为一的表达式树 (或单个终端节点，视为深度零)。

    深度为一的树结构示例:
    - 单个终端: Node('close')
    - 一元操作: Node('rank', left=Node('open'))
    - 二元操作: Node('add', left=Node('close'), right=Node('high'))
    - 时间序列操作: Node('ts_rank', left=Node('vwap'), right=Node('20'))

    参数:
        terminal_vals (List[str]): 可用的终端值列表。
        bin_ops (List[str]): 可用的二元操作符列表。
        time_series_ops (List[str]): 可用的时间序列操作符列表。
        time_series_op_vals (List[str]): 可用的时间序列操作符参数值列表。
        un_ops (List[str]): 可用的一元操作符列表。
        flag (int): 控制生成树类型的标志。
                    - flag == 0: 随机选择一个终端值。
                    - flag == 1: 随机选择一个一元操作符，并为其随机选择一个终端子节点。
                    - flag == 2: 随机选择一个二元操作符，并为其随机选择两个终端子节点。
                    - flag == 3: 随机选择一个时间序列操作符，为其随机选择一个终端子节点
                                 和一个时间序列操作参数值子节点。
                    - 其他 flag 值: 默认行为，例如随机选择一个终端值。

    返回:
        Node: 生成的深度为一的树的根节点。
    """
    root_node: Optional[Node] = None

    if flag == 0:
        # 生成一个终端节点
        if not terminal_vals:
            raise ValueError("终端值列表不能为空 (terminal_vals)")
        selected_terminal = random.choice(terminal_vals)
        root_node = Node(selected_terminal)
        # logger.debug(f"创建深度一树 (flag 0 - 终端): {root_node}")

    elif flag == 1:
        # 生成一个带终端子节点的一元操作符树
        if not un_ops:
            raise ValueError("一元操作符列表不能为空 (un_ops)")
        if not terminal_vals:
            raise ValueError("终端值列表不能为空 (terminal_vals)")
        selected_operator = random.choice(un_ops)
        selected_terminal_child = random.choice(terminal_vals)
        root_node = Node(selected_operator, left=Node(selected_terminal_child))
        # logger.debug(f"创建深度一树 (flag 1 - 一元): {root_node}")

    elif flag == 2:
        # 生成一个带两个终端子节点的二元操作符树
        if not bin_ops:
            raise ValueError("二元操作符列表不能为空 (bin_ops)")
        if not terminal_vals or len(terminal_vals) < 2: # 需要至少两个终端值用于子节点，除非允许相同
             # 为了简化，这里允许选择相同的终端值作为左右子节点
            if not terminal_vals:
                raise ValueError("终端值列表不能为空 (terminal_vals)")

        selected_operator = random.choice(bin_ops)
        left_child = Node(random.choice(terminal_vals))
        right_child = Node(random.choice(terminal_vals))
        root_node = Node(selected_operator, left=left_child, right=right_child)
        # logger.debug(f"创建深度一树 (flag 2 - 二元): {root_node}")

    elif flag == 3:
        # 生成一个时间序列操作符树
        if not time_series_ops:
            raise ValueError("时间序列操作符列表不能为空 (time_series_ops)")
        if not terminal_vals:
            raise ValueError("终端值列表不能为空 (terminal_vals)")
        if not time_series_op_vals:
            raise ValueError("时间序列操作参数值列表不能为空 (time_series_op_vals)")

        selected_operator = random.choice(time_series_ops)
        data_child = Node(random.choice(terminal_vals)) # 第一个操作数是数据字段
        period_child = Node(random.choice(time_series_op_vals)) # 第二个操作数是周期值
        root_node = Node(selected_operator, left=data_child, right=period_child)
        # logger.debug(f"创建深度一树 (flag 3 - 时间序列): {root_node}")

    else: # 默认行为或未识别的 flag
        # logger.warning(f"depth_one_trees 收到未识别的 flag: {flag}，将默认创建一个终端节点。")
        if not terminal_vals:
            raise ValueError("终端值列表不能为空 (terminal_vals)")
        selected_terminal = random.choice(terminal_vals)
        root_node = Node(selected_terminal)

    if root_node is None: # 理论上不应发生，除非flag处理逻辑有误且没有默认行为
        raise RuntimeError(f"未能为 flag {flag} 创建有效的深度一树节点。")

    return root_node

# 后续将在此文件定义 Node 类、操作符/终端列表以及树生成函数。
# ... (后续将定义其他树生成函数) ...
# 需要导入 logger (import logging; logger = logging.getLogger(__name__)) 才能使用 logger.debug/warning
# 为保持与DEV-009任务描述一致，暂时不添加日志，但实际开发中建议添加。
# 实际使用时，应该在调用此函数的文件顶部进行日志配置。

def depth_two_tree(
    tree1: Node,
    tree2: Node,
    time_series_op_vals: List[str], # 参数名修改以与全局变量区分
    time_series_ops: List[str],     # 参数名修改以与全局变量区分
    # binary_ops 和 unary_ops 可以从全局作用域获取，或者作为参数传入
    # 为了与 depth_one_trees 的参数风格保持部分一致，这里假设它们可以从全局获取
    # 或者，如果严格要求，也应作为参数传入。
    # DEV-009 任务卡片中 depth_two_tree 的签名未包含 binary_ops, unary_ops
    # 但它们在逻辑上是需要的。这里将从全局作用域引用它们。
    flag: int
) -> Node:
    """
    将两个已有的树（通常是深度为一的树，tree1 和 tree2）组合成一个深度为二的树。

    参数:
        tree1 (Node): 第一个子树的根节点。
        tree2 (Node): 第二个子树的根节点。
        time_series_op_vals (List[str]): 可用的时间序列操作符参数值列表。
        time_series_ops (List[str]): 可用的时间序列操作符列表。
        flag (int): 控制组合方式和操作符类型的标志。
                    - flag == 0: 使用随机的二元操作符连接 tree1 和 tree2。
                                 例如: Node('add', left=tree1, right=tree2)
                    - flag == 1: 使用随机的时间序列操作符，tree1 作为数据输入，
                                 并从 time_series_op_vals 中随机选择一个值作为周期参数。
                                 例如: Node('ts_rank', left=tree1, right=Node(random.choice(time_series_op_vals)))
                    - flag == 2: （可选扩展）使用随机的一元操作符作用于 tree1 (忽略 tree2)。
                                 例如: Node('rank', left=tree1)
                                 (注意：原始签名只有 tree1, tree2, ts_ops_values, ts_ops。
                                  如果 flag==2 要使用 unary_ops，则 unary_ops 需可访问。)
                                 根据DEV-009提供的签名，此flag可能不直接支持一元操作，
                                 除非一元操作符也被包含在 ts_ops 列表中或有其他解释。
                                 这里，如果flag==2, 我们将默认使用二元操作。

    返回:
        Node: 生成的深度为二的树的根节点。

    注意:
        此函数依赖全局定义的 `binary_ops` 和 `unary_ops` 列表。
        如果希望函数更独立，可以将这些列表也作为参数传入。
    """
    root_node: Optional[Node] = None

    if flag == 0:
        # 使用二元操作符连接 tree1 和 tree2
        if not binary_ops: # 引用全局的 binary_ops
            raise ValueError("全局二元操作符列表 binary_ops 不能为空。")
        selected_operator = random.choice(binary_ops)
        root_node = Node(selected_operator, left=tree1, right=tree2)
        # logger.debug(f"创建深度二树 (flag 0 - 二元): {root_node}")

    elif flag == 1:
        # 使用时间序列操作符，tree1 作为数据，随机选择 ts_op_value 作为周期
        if not time_series_ops:
            raise ValueError("时间序列操作符列表不能为空 (time_series_ops)。")
        if not time_series_op_vals:
            raise ValueError("时间序列操作参数值列表不能为空 (time_series_op_vals)。")

        selected_operator = random.choice(time_series_ops)
        period_child_value = random.choice(time_series_op_vals)
        root_node = Node(selected_operator, left=tree1, right=Node(period_child_value))
        # logger.debug(f"创建深度二树 (flag 1 - 时间序列): {root_node}")

    # elif flag == 2: # 如果要支持一元操作符作用于 tree1
    #     if not unary_ops: # 引用全局的 unary_ops
    #         raise ValueError("全局一元操作符列表 unary_ops 不能为空。")
    #     selected_operator = random.choice(unary_ops)
    #     root_node = Node(selected_operator, left=tree1)
    #     # logger.debug(f"创建深度二树 (flag 2 - 一元): {root_node}")

    else: # 默认行为或未识别的 flag，例如 flag == 2 时按二元处理
        logger.warning(f"depth_two_tree 收到未识别或未完全支持的 flag: {flag} (或 unary_ops 未作为参数传入)。将默认使用二元操作符。")
        if not binary_ops:
            raise ValueError("全局二元操作符列表 binary_ops 不能为空。")
        selected_operator = random.choice(binary_ops)
        root_node = Node(selected_operator, left=tree1, right=tree2)

    if root_node is None:
        raise RuntimeError(f"未能为 flag {flag} 创建有效的深度二树节点。")

    return root_node

def depth_three_tree(
    # 根据任务卡片，参数名为 tree2，类型为 list[Node]
    # 这比较特殊，通常树生成函数会明确左右子树或生成子树的原材料
    # 假设 tree2 列表包含的是已经生成好的、可以作为操作数的子树 (可能是深度1或深度2的树)
    sub_trees: List[Node],
    flag: int
    # 此函数也可能需要访问全局的操作符列表 (binary_ops, unary_ops, ts_ops, ts_ops_values)
    # 或将它们作为参数传入。为与前一个函数风格一致，这里假设访问全局列表。
) -> Node:
    """
    将一个或多个已有的树（通常是深度一或深度二的树，来自 sub_trees 列表）
    组合成一个大致深度为三的树。

    参数:
        sub_trees (List[Node]): 一个包含预先构建好的子树根节点的列表。
                                函数将根据 flag 从此列表中选择子树。
        flag (int): 控制组合方式和顶层操作符类型的标志。
                    - flag == 0: 使用随机的二元操作符。如果 sub_trees 至少有两个元素，
                                 则从中选择两个作为子节点。如果只有一个，则可能需要
                                 额外生成一个深度一的树作为第二个子节点。
                    - flag == 1: 使用随机的时间序列操作符。如果 sub_trees 至少有一个元素，
                                 则选择一个作为数据输入，并随机生成一个 ts_op_value 作为周期。
                    - flag == 2: （可选扩展）使用随机的一元操作符作用于从 sub_trees 中选取的第一个树。
                    - 其他: 默认为 flag == 0 的行为。

    返回:
        Node: 生成的深度约为三的树的根节点。

    注意:
        - 此函数依赖全局定义的 `binary_ops`, `unary_ops`, `ts_ops`, `ts_ops_values`, `terminal_values` 列表。
        - “深度三”是目标，实际深度取决于 `sub_trees` 中树的深度和组合方式。
          例如，如果用二元操作符连接两个深度为二的树，结果树的深度将是三。
          如果连接一个深度二的树和一个深度一的树，结果也是深度三。
    """
    root_node: Optional[Node] = None

    if not sub_trees:
        raise ValueError("子树列表 sub_trees 不能为空。")

    if flag == 0: # 尝试使用二元操作符
        if not binary_ops:
            raise ValueError("全局二元操作符列表 binary_ops 不能为空。")

        selected_operator = random.choice(binary_ops)

        left_child: Node = random.choice(sub_trees) # 从提供的子树中随机选一个作为左孩子
        right_child: Node

        if len(sub_trees) > 1:
            # 如果有多个子树可选，从中再选一个 (可以是同一个，也可以是不同的)
            # 为确保多样性，可以尝试选择一个与 left_child 不同的 (如果可能)
            temp_selectable_rights = [t for t in sub_trees if t is not left_child]
            if temp_selectable_rights:
                right_child = random.choice(temp_selectable_rights)
            else: # 如果所有子树都与 left_child相同 (例如 sub_trees 只有一个元素被多次引用，或只有一个独特元素)
                right_child = random.choice(sub_trees)
        else:
            # 如果 sub_trees 只有一个元素，或者我们希望强制生成新的右子树
            logger.info("depth_three_tree (flag 0): sub_trees 只有一个元素或需要新右子树，将生成新的深度一树作为右孩子。")
            # 生成一个随机类型的深度一的树作为右孩子
            # 注意：这里直接调用了全局的操作符/终端列表
            right_child_flag = random.randint(0, 3) # 随机选择一种深度一树的类型
            try:
                right_child = depth_one_trees(terminal_values, binary_ops, ts_ops, ts_ops_values, unary_ops, right_child_flag)
            except ValueError as e:
                logger.error(f"depth_three_tree: 生成右子树时出错: {e}。将尝试仅使用终端值。")
                if not terminal_values: raise ValueError("全局终端值列表 terminal_values 不能为空以创建备用右子树。") from e
                right_child = Node(random.choice(terminal_values))

        root_node = Node(selected_operator, left=left_child, right=right_child)
        # logger.debug(f"创建深度三树 (flag 0 - 二元): {root_node}")

    elif flag == 1: # 尝试使用时间序列操作符
        if not ts_ops:
            raise ValueError("全局时间序列操作符列表 ts_ops 不能为空。")
        if not ts_ops_values:
            raise ValueError("全局时间序列操作参数值列表 ts_ops_values 不能为空。")

        selected_operator = random.choice(ts_ops)
        data_child: Node = random.choice(sub_trees) # 第一个操作数来自提供的子树
        period_child_value = random.choice(ts_ops_values)
        root_node = Node(selected_operator, left=data_child, right=Node(period_child_value))
        # logger.debug(f"创建深度三树 (flag 1 - 时间序列): {root_node}")

    elif flag == 2: # 尝试使用一元操作符
        if not unary_ops:
            raise ValueError("全局一元操作符列表 unary_ops 不能为空。")

        selected_operator = random.choice(unary_ops)
        child_node: Node = random.choice(sub_trees) # 操作数来自提供的子树
        root_node = Node(selected_operator, left=child_node)
        # logger.debug(f"创建深度三树 (flag 2 - 一元): {root_node}")

    else:
        logger.warning(f"depth_three_tree 收到未识别的 flag: {flag}。将默认按 flag 0 (二元操作) 处理。")
        # 递归或委托给 flag 0 的逻辑
        # 为避免代码重复，可以调用自身或提取公共逻辑，但这里简单重复以明确
        if not binary_ops: raise ValueError("全局二元操作符列表 binary_ops 不能为空。")
        selected_operator = random.choice(binary_ops)
        left_child = random.choice(sub_trees)
        right_child_flag = random.randint(0,3)
        try:
            right_child = depth_one_trees(terminal_values, binary_ops, ts_ops, ts_ops_values, unary_ops, right_child_flag)
        except ValueError as e:
            logger.error(f"depth_three_tree (default): 生成右子树时出错: {e}。将尝试仅使用终端值。")
            if not terminal_values: raise ValueError("全局终端值列表 terminal_values 不能为空以创建备用右子树。") from e
            right_child = Node(random.choice(terminal_values))
        root_node = Node(selected_operator, left=left_child, right=right_child)


    if root_node is None:
        raise RuntimeError(f"未能为 flag {flag} 和提供的子树创建有效的深度三树节点。")

    return root_node

# ... (文件末尾)
