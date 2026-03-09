# Case-to-txt 逻辑: 旧数据存库时需要，新数据不适用
import os
import sys

# 允许直接运行/调试该文件时找到项目根目录下的 app 包
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.rag.schemas import ExceptionSuggestionRag
from db_manage.db_utils import db_connector
from app.rag.field_extractors import extract_exception_suggestion_fields
from app.core.schema import ExceptionSuggestionRequest


def build_exception_suggestion_case(temp: dict) -> ExceptionSuggestionRag:
    """
    【旧数据适配器】：将 SQL 捞出来的字典转化为标准 RAG 对象
    """
    return ExceptionSuggestionRag(
        order_no=temp.get("orderNo"),
        material_name=temp.get("materialName"),
        spec=temp.get("materialSpecs"),
        supplier_name=temp.get("supplierName"),
        customer=temp.get("customerDept"),
        bucket=extract_exception_suggestion_fields(temp)
    )


def build_case_from_dto(dto: ExceptionSuggestionRequest) -> ExceptionSuggestionRag:
    """
    【新数据适配器】：将 外部（java） 传来的 DTO 转化为标准 RAG 对象
    用于：1. 生成检索用的向量；2. (以后) 将新数据存入向量库
    """
    # 1. 转化为字典，以便复用 extract_exception_suggestion_fields
    temp = dto.model_dump()
    
    # 2. 映射为标准对象
    return ExceptionSuggestionRag(
        order_no=dto.orderNo,
        material_code=dto.materialCode,
        material_name=dto.materialName,
        spec=dto.spec,
        supplier_name=dto.supplierName,
        customer=dto.customer,
        defect_rate=float(dto.u9ArriveQty or 0), # 这里的逻辑根据实际业务字段调整
        bucket=extract_exception_suggestion_fields(temp) # 核心：使用同一套语义逻辑
    )
        

def get_old_iqc_case():
    """
    从数据库中捞出数据
    """
    with db_connector.get_connection('032_TJZT') as conn_TJZT:
        with conn_TJZT.cursor() as cursor_TJZT:
            getMainAndDetailData = """
                SELECT 
                    a.qcd01 as orderNo,                 
                    b.Name as materialName, 
                    CAST(b.SPECS AS VARCHAR(100)) as materialSpecs,   
                    a.qcd05 as supplierName,
                    c.qcab08 as customerDept,
                    a.qcd08 as arriveQty,
                    a.qcd09 as samplingQty,
                    a.qcd17 as defectRate,
                    a.qcd19 as ngReasonOverall,
                    a.qcd15 as handleSuggestion,         

                    CASE WHEN d.qcda03 > 0 THEN 1 ELSE 0 END as isTool,
                    d.qcda05 as itemName,
                    d.qcda06 as content,
                    d.qcda061 as dimensionLowerLimit,
                    d.qcda062 as dimensionUpperLimit,
                    d.qcda07 as toolName,
                    d.qcda08 as measurement1, 
                    d.qcda09 as measurement2, 
                    d.qcda10 as measurement3, 
                    d.qcda11 as measurement4, 
                    d.qcda12 as measurement5,
                    d.qcda14 as detailInspectionResult,
                    d.qcda15 as defectDegree,
                    d.qcda17 as detailReason,
                    d.qcda19 as defectQty
                FROM LHQ_QCD a 
                LEFT JOIN CBO_ItemMaster b ON b.code = a.QCD07 AND b.org = a.qcdorg 
                LEFT JOIN (
                    SELECT QCAB02, qcaborg, MAX(qcab08) as qcab08 
                    FROM LHQ_QCA_B 
                    GROUP BY QCAB02, qcaborg
                ) c ON c.QCAB02 = a.QCD07 AND c.qcaborg = a.qcdorg
                LEFT JOIN LHQ_QCD_A d ON d.qcda01 = a.qcd00 AND d.qcda14 = 'NG'
                WHERE a.qcd11 = 'NG'            
                  AND a.qcd15 IS NOT NULL      
                  AND a.qcd15 <> ''
                ORDER BY a.qcd01  
            """
            cursor_TJZT.execute(getMainAndDetailData)
            columns = [column[0] for column in cursor_TJZT.description]
            raw_rows = [dict(zip(columns, row)) for row in cursor_TJZT.fetchall()]
            
    # 将扁平数据转换为嵌套数组结构
    grouped_data = {}
    for row in raw_rows:
        mid = row['orderNo']
        # 如果这个 orderNo 第一次出现，初始化主表信息
        if mid not in grouped_data:
            grouped_data[mid] = {
                "orderNo": row['orderNo'],
                "materialName": row['materialName'],
                "materialSpecs": row['materialSpecs'],
                "supplierName": row['supplierName'],
                "customerDept": row['customerDept'],
                "arriveQty": row['arriveQty'],
                "samplingQty": row['samplingQty'],
                "defectRate": row['defectRate'],
                "ngReasonOverall": row['ngReasonOverall'],
                "handleSuggestion": row['handleSuggestion'],
                "details": []
            }
        
        # 如果含具体明细，则塞进 details 数组
        if row['itemName']:
            grouped_data[mid]['details'].append({
                "isTool": row['isTool'],
                "itemName": row['itemName'],
                "content": row['content'],
                "dimensionLowerLimit": row['dimensionLowerLimit'],
                "dimensionUpperLimit": row['dimensionUpperLimit'],
                "toolName": row['toolName'],
                "measurements": [
                    row['measurement1'], 
                    row['measurement2'], 
                    row['measurement3'], 
                    row['measurement4'], 
                    row['measurement5']
                ],
                "detailInspectionResult": row['detailInspectionResult'],
                "defectDegree": row['defectDegree'],
                "detailReason": row['detailReason'],
                "defectQty": row['defectQty']
            })

    return [build_exception_suggestion_case(data) for data in grouped_data.values()]




if __name__ == '__main__':
    old_cases = get_old_iqc_case()
    i = 0
    for case in old_cases:
        if case.bucket is not None:
            i += 1
            if i < 10 :
                print("----第{}条----".format(i))
                print(case)

    print("总共捞取到 {} 条旧 IQC 异常建议案例。".format(len(old_cases)))