# 导入 random 模块，用于在遗传编程操作中进行随机选择，例如选择操作符、终端或交叉点。
import random
# 从 typing 模块导入 Optional 和 List 类型提示，用于增强代码的可读性和静态分析能力。
# Optional[X] 表示一个参数或返回值可以是 X 类型，也可以是 None。
# List[X] 表示一个列表，其所有元素都是 X 类型。
from typing import Optional, List
import logging # 导入 logging 模块

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
