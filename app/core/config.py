from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


#  (环境变量管理)
class Settings(BaseSettings):
    # deepseek配置
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEFAULT_MODEL: str = "deepseek-chat"

    # 本地llm配置
    OLLAMA_BASE_URL: str = ""
    OLLAMA_MODEL: str = "qwen2.5:7b"

    ACTIVE_LLM_STRATEGY: Literal["cloud", "local"] = "cloud"

    BGE_MODEL_PATH: str = str(ROOT_DIR / "app" / "weights" / "bge-m3")
    CHROMA_PERSIST_PATH: str = str(ROOT_DIR / "app" / "storage" / "chroma_db")

    # --- Pydantic 配置 ---
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
print(f"DEBUG: ACTIVE_STRATEGY={settings.ACTIVE_LLM_STRATEGY}")
