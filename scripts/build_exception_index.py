# 批量提取旧数据并转化为“文字案卷”。将生成的文字案卷灌入本地向量库(ChromaDB)。

import os
import sys
import time
from tqdm import tqdm

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.rag.case_builder import get_old_iqc_case
from app.embedding.bge_manager import BgeManager
from app.storage.chroma_manager import ChromaManager
from app.core.config import settings

async def build_exception_index():
    # 1. 初始化 BGE Manager
    print("=== 正在初始化算力引擎与存储基座 ===")
    model_path = settings.BGE_MODEL_PATH
    bge_manager = BgeManager(model_name=model_path)
    # 向量持久化
    chroma_manager = ChromaManager(persist_path=settings.CHROMA_PERSIST_PATH)

    # 2. 获取旧案卷数据
    print("=== 正在提取旧案卷数据 ===")
    all_cases = get_old_iqc_case()
    valid_cases = [c for c in all_cases if c.bucket and c.order_no]  # 过滤无效数据

    # 3. 分批处理
    batch_size = 100
    for i in tqdm(range(0, len(valid_cases), batch_size)):
        batch_cases = valid_cases[i:i+batch_size]
        batch_texts = [case.bucket for case in batch_cases]

        try:
            batch_manager = await bge_manager.encode(batch_texts)
            chroma_manager.upsert_cases(batch_cases, batch_manager.tolist())

        except Exception as e:
            print(f"Error encoding batch starting at index {i}: {e}")
            continue


if __name__ == "__main__":
    build_exception_index()