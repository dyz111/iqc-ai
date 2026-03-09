# 本地 Embedding 模型加载。将文字压缩成向量。

import os
import sys
import threading  # 导入线程锁模块
import asyncio

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import torch
from sentence_transformers import SentenceTransformer
from typing import List
from app.core.config import settings

class BgeManager:
    _instance = None  # 单例实例
    _lock = threading.Lock()  # 创建线程锁

    def __init__(self, model_name: str):
        with BgeManager._lock:  # 使用锁来确保线程安全
            if BgeManager._instance is None:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                print(f"Loading BGE model '{model_name}' on device '{device}'...")
                self.model = SentenceTransformer(model_name, device=device)
                BgeManager._instance = self.model
            else:
                self.model = BgeManager._instance
    
    async def encode(self, sentences: List[str]):
        return await asyncio.to_thread(
                self.model.encode, 
                sentences, 
                batch_size=32, 
                normalize_embeddings=True, 
                show_progress_bar=True
            )
            
    async def _encode_sync(self, sentences: List[str], batch_size: int, normalize_embeddings: bool, show_progress_bar: bool):
        return await self.model.encode(sentences, batch_size=batch_size, normalize_embeddings=normalize_embeddings, show_progress_bar=show_progress_bar)
    


# 主程序执行示例
if __name__ == "__main__":
    bge_manager = BgeManager("./app/weights/bge-m3")
    sentences = ["Hello, world!", "This is a test sentence."]
    vector = asyncio.run(bge_manager.encode(sentences))
    print(vector.shape)  # 访问实际的向量数据属性
    print(vector[0])  # 打印第一个向量数据
