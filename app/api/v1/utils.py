# app/api/v1/utils.py
import logging
import os
import datetime # 确保导入 datetime
from typing import List, Dict, Any, Optional
import uuid # 用于处理 Alpha ID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import requests # 用于捕获 BrainApiSession 可能抛出的请求异常

from app.database import get_db
from app.models import Alpha as AlphaModel # 使用别名以区分 schema
from app.schemas import (
    AlphaCombinationRequest,
    AlphaCombinationResponse,
    CombinedAlphaSimulatedData, # 确保这个也被导入
    AlphaExportResponse
)
from app.core.brain_api import BrainApiSession, get_brain_api_session # 确保 get_brain_api_session 可用
from app.core.gp_algo import combine_alphas # 从DEV-026导入

logger = logging.getLogger(__name__)
router = APIRouter() # 不需要 prefix 和 tags 在这里，将在 __init__.py 中添加

@router.post("/combine_alphas", response_model=AlphaCombinationResponse)
async def combine_alphas_api(
    request_data: AlphaCombinationRequest,
    db: Session = Depends(get_db),
    brain_api: BrainApiSession = Depends(get_brain_api_session)
):
    """
    组合多个Alpha表达式，对新生成的表达式进行模拟，并返回结果。
    """
    alpha_expressions_to_combine: List[str] = []
    alpha_ids_to_combine_uuids: List[uuid.UUID] = []

    # 验证并转换 Alpha ID 为 UUID
    for alpha_id_str in request_data.alpha_ids:
        try:
            alpha_ids_to_combine_uuids.append(uuid.UUID(alpha_id_str))
        except ValueError:
            logger.warning(f"提供的Alpha ID '{alpha_id_str}' 不是有效的UUID格式。")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Alpha ID '{alpha_id_str}' 格式无效。"
            )

    # 从数据库获取指定ID的Alpha表达式
    # 使用 in_ 操作符进行批量查询
    found_alphas = db.query(AlphaModel).filter(AlphaModel.id.in_(alpha_ids_to_combine_uuids)).all()

    # 检查是否所有请求的ID都找到了
    if len(found_alphas) != len(set(alpha_ids_to_combine_uuids)): # 使用 set 来处理可能的重复输入ID
        found_ids_set = {str(a.id) for a in found_alphas}
        missing_ids = [str(uid) for uid in alpha_ids_to_combine_uuids if str(uid) not in found_ids_set]
        logger.warning(f"以下请求的Alpha ID在数据库中未找到: {missing_ids}")
        # 选择报错或继续处理已找到的Alpha
        if not found_alphas: # 如果一个都没找到
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"提供的Alpha ID均未找到: {missing_ids}")
        # 如果部分找到，可以选择继续或报错，这里选择继续处理找到的
        logger.info(f"将仅组合找到的 {len(found_alphas)} 个Alpha。")


    alpha_expressions_to_combine = [alpha.expression for alpha in found_alphas if alpha.expression]

    if not alpha_expressions_to_combine:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未能从提供的ID列表中获取任何有效的Alpha表达式进行组合 (可能所有找到的Alpha表达式都为空)。"
        )

    # 调用核心组合逻辑
    try:
        combined_expression_str = combine_alphas(
            alpha_expressions=alpha_expressions_to_combine,
            method=request_data.method
        )
    except ValueError as ve: # combine_alphas 内部可能抛出 ValueError
        logger.error(f"调用 combine_alphas 时发生配置或参数错误: {ve}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"组合Alpha时发生错误: {ve}")
    except Exception as e:
        logger.error(f"调用 combine_alphas 时发生未知错误: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"组合Alpha时发生内部错误: {e}")

    if not combined_expression_str:
        logger.warning(f"Alpha组合结果为空字符串，方法: {request_data.method}, 输入表达式数量: {len(alpha_expressions_to_combine)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, # 或者 400
            detail="Alpha组合未能生成有效表达式 (可能由于输入或组合逻辑问题)。"
        )

    logger.info(f"成功组合Alpha表达式: {combined_expression_str}")

    # 对组合后的 Alpha 进行模拟
    # 模拟配置：这里用一个标准化的默认配置。实际应用中可能需要更复杂的逻辑来决定配置。
    default_simulation_settings = {
        "instrumentType": "EQUITY",
        "region": "USA",
        "universe": "TOP3000", # WQB 区分大小写，TOP3000
        "delay": 1,
        "truncation": 0.01,
        "pasteurize": "ON",
        "regularization": 0.0, # 确保是浮点数
        "nanHandling": "OFF" # 通常是 OFF 或 WINSORIZE
    }

    simulation_payload = {
        "settings": default_simulation_settings,
        "regularAlpha": combined_expression_str
    }

    sim_details_for_response: Optional[CombinedAlphaSimulatedData] = None
    try:
        logger.info(f"开始模拟组合后的Alpha: '{combined_expression_str}' 使用配置: {default_simulation_settings}")

        # 假设 brain_api.start_simulation 和 brain_api.simulation_progress 已在 DEV-006 实现
        # 并且 simulation_progress 返回一个包含模拟结果的字典或能转换为 CombinedAlphaSimulatedData 的结构
        simulation_results_dict = brain_api.run_simulation_and_get_results(simulate_data=simulation_payload)

        # 将 brain_api 返回的字典映射到 CombinedAlphaSimulatedData 模型
        # simulation_results_dict 结构需要与 CombinedAlphaSimulatedData 字段匹配
        # 例如, simulation_results_dict 可能包含 'is_stats', 'is_tests', 'pnl_data', 'error_message' 等
        sim_details_for_response = CombinedAlphaSimulatedData(
            is_stats=simulation_results_dict.get('is_stats'),
            is_tests=simulation_results_dict.get('is_tests'),
            pnl_data=simulation_results_dict.get('pnl_data_json'), # 假设API返回的是pnl_data_json
            yearly_stats_data=simulation_results_dict.get('yearly_stats_data_json'), # 假设API返回的是yearly_stats_data_json
            status=simulation_results_dict.get('status', 'UNKNOWN'), # 模拟状态
            error_message=simulation_results_dict.get('error_message')
        )

        if sim_details_for_response.error_message:
            logger.error(f"组合Alpha '{combined_expression_str}' 的模拟失败: {sim_details_for_response.error_message}")
        else:
            logger.info(f"组合Alpha '{combined_expression_str}' 模拟完成。状态: {sim_details_for_response.status}")

    except requests.exceptions.RequestException as req_err:
        logger.error(f"模拟组合Alpha '{combined_expression_str}' 时请求失败: {req_err}", exc_info=True)
        sim_details_for_response = CombinedAlphaSimulatedData(status="FAILED", error_message=f"API请求失败: {req_err}")
    except Exception as e: # 其他来自 brain_api 或内部逻辑的错误
        logger.error(f"模拟组合Alpha '{combined_expression_str}' 时发生未知错误: {e}", exc_info=True)
        sim_details_for_response = CombinedAlphaSimulatedData(status="FAILED", error_message=f"模拟过程中发生未知错误: {str(e)}") # 使用 str(e) 避免复杂对象

    # (可选) 保存这个组合出来的 Alpha 和它的模拟结果到数据库。本任务不实现保存。
    # new_alpha_id_str: Optional[str] = None

    return AlphaCombinationResponse(
        combined_expression=combined_expression_str,
        simulation_details=sim_details_for_response
        # new_alpha_id=new_alpha_id_str
    )


@router.get("/export_alpha/{alpha_id_str}", response_model=AlphaExportResponse)
async def export_alpha_api(alpha_id_str: str = Path(..., description="要导出的Alpha的UUID"), db: Session = Depends(get_db)):
    """
    根据Alpha ID导出其表达式和原始模拟配置。
    使用 'alpha_id_str' 作为路径参数名，以明确其为字符串类型，后续转换为UUID。
    """
    try:
        alpha_uuid = uuid.UUID(alpha_id_str)
    except ValueError:
        logger.warning(f"请求导出的Alpha ID '{alpha_id_str}' 不是有效的UUID格式。")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Alpha ID '{alpha_id_str}' 格式无效。")

    alpha_db = db.query(AlphaModel).filter(AlphaModel.id == alpha_uuid).first()

    if not alpha_db:
        logger.warning(f"请求导出的Alpha ID '{alpha_uuid}' 在数据库中未找到。")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alpha ID '{alpha_uuid}' 未找到。")

    logger.info(f"成功导出Alpha ID '{alpha_db.id}' 的数据。")
    return AlphaExportResponse(
        alpha_id=str(alpha_db.id),
        expression=alpha_db.expression,
        simulation_settings_json=alpha_db.simulation_settings_json,
        experiment_id=str(alpha_db.experiment_id) if alpha_db.experiment_id else None,
        created_at=alpha_db.created_at,
        description=alpha_db.description
    )

# 需要在 app/api/v1/__init__.py 中注册这个 router
# from fastapi import Path # 用于路径参数的更详细定义 (如果需要)
# 在 export_alpha_api 中，alpha_id: str 已经足够，FastAPI会自动从路径中提取
# 如果要添加更多验证，如UUID格式，可以使用 Path(..., regex=...) 或自定义依赖项
# 为了清晰，我将 alpha_id 改为 alpha_id_str 并在函数内转换/验证
from fastapi import Path # 导入 Path
