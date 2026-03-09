from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field
from typing import Union


class IncomingInspectionOrderBasicDetail(BaseModel):
    itemName: Optional[str] = None
    toolName: Optional[str] = None
    content: Optional[str] = None
    defectQty: Optional[float] = None
    defectRate: Optional[float] = None
    samplingQty: Optional[float] = None
    inspectionResult: Optional[str] = None
    defectDegree: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class IncomingInspectionOrderDimensionDetail(BaseModel):
    itemName: Optional[str] = None
    toolName: Optional[str] = None
    requirement: Optional[str] = None
    dimensionLowerLimit: Optional[float] = None
    dimensionUpperLimit: Optional[float] = None
    measurement1: Optional[float] = None
    measurement2: Optional[float] = None
    measurement3: Optional[float] = None
    measurement4: Optional[float] = None
    measurement5: Optional[float] = None
    inspectionResult: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class IncomingInspectionOrderExceptionHandling(BaseModel):
    departmentName: Optional[str] = None
    isSpecialAccept: Optional[str] = None
    isReturn: Optional[str] = None
    isProcessOrSelect: Optional[str] = None
    remark: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ExceptionSuggestionRequest(BaseModel):
    # 基础单据信息
    orderNo: Optional[str] = None
    materialCode: Optional[str] = None
    materialName: Optional[str] = None
    spec: Optional[str] = None
    customer: Optional[str] = None
    model: Optional[str] = None
    supplierName: Optional[str] = None
    u9ArriveQty: Optional[float] = None
    samplingQty: Optional[float] = None
    inspectionResultOverall: Optional[str] = None
    environmentalStatus: Optional[str] = None
    reliabilityStatus: Optional[str] = None

    # AQL 接受/拒收阈值
    aClassAc: Optional[int] = None
    aClassRe: Optional[int] = None
    bClassAc: Optional[int] = None
    bClassRe: Optional[int] = None
    cClassAc: Optional[int] = None
    cClassRe: Optional[int] = None

    # 明细数据
    basicDetails: Optional[List[IncomingInspectionOrderBasicDetail]] = None
    dimensionDetails: Optional[List[IncomingInspectionOrderDimensionDetail]] = None
    exceptionHandlings: Optional[List[IncomingInspectionOrderExceptionHandling]] = None



    model_config = ConfigDict(extra="allow")


class SuggestionItem(BaseModel):
    # option: 建议处理方式（特采/退货/加工选用）
    # remark: 给前端展示的建议理由/说明
    option: str
    remark: str


class ExceptionSuggestionResponse(BaseModel):
    purchase: SuggestionItem  # 采购部
    planning: SuggestionItem  # 计调部
    production: SuggestionItem  # 生产部
    engineering: SuggestionItem  # 工程部
    quality: SuggestionItem  # 品管部
    evidence: Optional[List[str]] = Field(default_factory=list)
