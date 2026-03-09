# 抽取字段/特征（从主表/明细表提取）

from typing import List, Optional
from app.rag.schemas import ExceptionSuggestionRag


def extract_exception_suggestion_fields(temp: dict) -> str:
    """
    语义提取： 结构化数据 to 语义化文本
    接收: temp (dict): 兼容旧系统SQL字典及新系统Java DTO（ExceptionSuggestionRequest） 
    返回: str: 格式化的长文本，包含  案卷指纹 + 异常现象 + 测量逻辑  
    注意: Embedding模型仅对该函数返回的字符串进行向量化计算，类中的其他属性（如Metadata）不参与语义匹配。
    """
    
    # 1. 只有桶里的才会被检索到
    m_name = temp.get("materialName") or "未知物料"
    spec = temp.get("materialSpecs") or temp.get("spec") or "无规格"
    supplier = temp.get("supplierName") or "未知供应商"
    reason = temp.get("ngReasonOverall") or "未记录描述"
    header = f"【案卷指纹】品名：{m_name} | 规格：{spec} | 供应商：{supplier}"


    # 2. 兼容新旧字段名
    all_details = []

    # 情况 A：处理旧 SQL 数据（数据已经全在 details 里了）
    if "details" in temp:
        all_details = temp["details"]

    # 情况 B：处理新 DTO 数据（需要从两个 Key 里捞，并手动补齐 isTool）
    else:
        for d in temp.get("basicDetails", []):
            d["isTool"] = 0
            all_details.append(d)
        for d in temp.get("dimensionDetails", []):
            d["isTool"] = 1
            all_details.append(d)
    
    # 3. 兜底：如果没有明细
    if not all_details:
        rate = (temp.get('defectRate') or 0) * 100
        return f"{header} | 现象：{reason} | 详情：总不良率{rate:.2f}%，无明细。"

    # 4. 寻找最严重的明细
    # 优先找 NG 的项，如果没有 NG（比如是抽检合格单入库），就按 defectQty 排序
    try:
        # 先过滤出 NG 的项
        ng_list = [d for d in all_details if d.get("inspectionResult") == "NG"]
        target_list = ng_list if ng_list else all_details
        max_detail = max(target_list, key=lambda x: x.get("defectQty") or 0)
    except:
        max_detail = all_details[0]

    # --- 5. 判定逻辑（根据我们手动补齐的 isTool） ---
    def get_level(r):
            if r > 20: return "严重异常"
            if r > 2: return "显著异常"
            return "轻微异常"

    if max_detail.get("isTool") == 1:
        # 工具类检验项
        total_rate = (temp.get("defectRate") or 0) * 100
        total_level = get_level(total_rate)

        # 兼容处理实测值：DTO 是平铺字段，SQL 是 measurements 列表
        measures = max_detail.get("measurements")
        if not measures:
            measures = [max_detail.get(f"measurement{i}") for i in range(1, 6) if max_detail.get(f"measurement{i}") is not None]

        detail_qty = 0
        detailReasons = []
        for meas in (measures or []):
            upper = max_detail.get("dimensionUpperLimit") or 0
            lower = max_detail.get("dimensionLowerLimit") or 0
            if meas > upper:
                detail_qty += 1
                detailReasons.append(f"实测{meas}>上限{upper}")
            if meas < lower:
                detail_qty += 1
                detailReasons.append(f"实测{meas}<下限{lower}")

        dr = "；".join(detailReasons) if detailReasons else "实测值均在上下限范围内"
        detail_rate = (detail_qty / len(measures) * 100) if measures else 0
        detail_level = get_level(detail_rate)

        return (
            f"{header} | 【工具详情】项目：{max_detail.get('itemName')}，内容：{max_detail.get('content')}，"
            f"工具：{max_detail.get('toolName')}。最终处理结果：{temp.get('handleSuggestion', '未知')}，"
            f"总异常情况：{total_level}({total_rate:.2f}%)，"
            f"最严重明细：{detail_level}({detail_rate:.2f}%)，"
            f"程度：{max_detail.get('defectDegree')}，原因：{dr}。"
        )
    
    else:
        # 非工具类检验项
        total_rate = (temp.get("defectRate") or 0) * 100
        total_level = get_level(total_rate)
        detail_rate = ((max_detail.get("defectQty") or 0) / (temp.get("samplingQty") or 1)) * 100
        detail_level = get_level(detail_rate)
        return (
            f"{header} | 【基础详情】项目：{max_detail.get('itemName')}，内容：{max_detail.get('content')}，"
            f"工具：{max_detail.get('toolName')}。最终处理结果：{temp.get('handleSuggestion', '未知')}，"
            f"总异常情况：{total_level}({total_rate:.2f}%)；"
            f"最严重明细：{detail_level}({detail_rate:.2f}%)，"
            f"程度：{max_detail.get('defectDegree')}。"
        )