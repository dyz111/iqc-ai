# 封装 ChromaDB。负责持久化存储向量，支持 Metadata 快速过滤。

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import chromadb
from typing import List
from app.rag.schemas import ExceptionSuggestionRag



class ChromaManager:
    def __init__(self, persist_path: str):
        """初始化 ChromaDB 管理"""

        # 1. 离线持久化
        self.client = chromadb.PersistentClient(path=persist_path)

        # 2. 创建或获取集合, 设置距离算法为 cosine
        self.collection = self.client.get_or_create_collection(
            name="iqc_exception_cases",
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_cases(self, cases: List[ExceptionSuggestionRag], embeddings: List[List[float]]):
        """
        批量入库 ChromaDB 要求的格式：OrderNos, Metadatas, Documents, Embeddings
        """
        orderNos = []
        metadatas = []
        documents = []

        for case in cases:
            orderNos.append(case.order_no or "unknown")

            metadatas.append({
                "order_no": case.order_no or "",
                "material_name": case.material_name or "",
                "spec": case.spec or "",
                "supplier_name": case.supplier_name or "",
                "customer": case.customer or ""
            })

            documents.append(case.bucket)

        self.collection.upsert(
            ids=orderNos,
            metadatas=metadatas,
            documents=documents,
            embeddings=embeddings
        )
        print(f"--- 成功将 {len(orderNos)} 条案例存入向量库 ---")

    
    def search_similar_cases(self, query_embedding: List[float], n_results: int = 3):
        """
        基于向量相似度搜索相关案例
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )
        return results
    

if __name__ == "__main__":
    manager = ChromaManager(persist_path="app/storage/chroma_db")
    print(f"目前库里共有 {manager.collection.count()} 条案例。")
