import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.exception_suggestion import router as exception_suggestion_router
from app.embedding.bge_manager import BgeManager
from app.storage.chroma_manager import ChromaManager
from app.core.config import settings



@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up the application...")
    start_time = time.time()
    _ = BgeManager(settings.BGE_MODEL_PATH)
    _ = ChromaManager(settings.CHROMA_PERSIST_PATH)

    duration = time.time() - start_time
    print(f"Application started in {duration:.2f} seconds.", flush=True)
    yield
    print("Shutting down the application...")


app = FastAPI(
    title="IQC-AI",
    description="基于 RAG 架构与 DeepSeek/Qwen 的AI辅助",
    version="1.0.0",
    lifespan=lifespan
)


# 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(exception_suggestion_router)


# 健康检查
@app.get("/health", tags=["System"])
async def health_check():
    """检测服务是否在线"""
    return {
        "status": "online",
        "device": "NVIDIA GeForce RTX 4060",
        "timestamp": time.time()
    }

@app.get("/", tags=["System"])
async def root():
    return {"message": "Welcome to IQC AI Service. Please use /docs to view API."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=10086, reload=True)
