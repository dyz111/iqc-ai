import os
import sys

# 1. 路径对齐
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.embedding.bge_manager import BgeManager
from app.storage.chroma_manager import ChromaManager
from app.core.config import settings
from app.rag.field_extractors import extract_exception_suggestion_fields

async def run_simulation():
    # 2. 初始化引擎
    bge = BgeManager(settings.BGE_MODEL_PATH)
    chroma = ChromaManager(settings.CHROMA_PERSIST_PATH)

    # 3. 模拟：这是一张来自 Java 端的、新鲜出炉的“异常单”
    # 场景：转轴套件出现刮痕，不良率显著
    mock_request = {
        "materialName": "转轴套件",
        "spec": "MB-8061B5",
        "supplierName": "东莞市乐泰五金制品有限公司",
        "defectRate": 0.08,  # 8% 不良
        "ngReasonOverall": "产品表面有明显线状刮痕，影响外观",
        "samplingQty": 100,
        "details": [
            {
                "itemName": "外观检验",
                "content": "表面不可有刮痕、脏污",
                "defectQty": 8,
                "defectDegree": "B",
                "toolName": "目测",
                "isTool": 0  # 基础类检验
            }
        ]
    }

    # 4. 【关键步骤】将新单据转化为“查询向量”
    # 我们调用和入库时一模一样的抽取逻辑，保证“语言风格”高度统一
    query_text = extract_exception_suggestion_fields(mock_request)
    print(f"\n[构造的查询文本]: \n{query_text}")

    # 5. 执行检索
    query_vector = await bge.encode([query_text])[0].tolist()
    # 搜 3 条最像的
    results = chroma.search_similar_cases(query_vector, n_results=3)
    print(f"\n[原始检索结果]: \n{results}")

    # 6. 结果深度复盘
    print("\n" + "="*50)
    print("🎯 深度检索结果（历史上的相似时刻）：")
    print("="*50)

    for i in range(len(results['ids'][0])):
        # 计算余弦相似度（1 - distance）
        score = 1 - results['distances'][0][i]
        
        print(f"\n【Top {i+1} 匹配】 相似度得分: {score:.4f}")
        print(f"历史单号: {results['metadatas'][0][i].get('order_no')}")
        print(f"历史供应商: {results['metadatas'][0][i].get('supplier_name')}")
        print(f"历史物料: {results['metadatas'][0][i].get('material_name')}")
        print(f"历史案卷全文: \n{results['documents'][0][i]}")
        print("-" * 30)

if __name__ == "__main__":
    run_simulation()