import httpx
from langchain_openai import ChatOpenAI
from app.core.config import settings

class LLMFactory:
    _cloud_client: httpx.AsyncClient = None
    _local_client: httpx.AsyncClient = None

    @staticmethod
    def _create_clean_client(timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            proxy=None,
            trust_env=False,  
            timeout=timeout  
        )

    @staticmethod
    def _initialize_clients():
        if LLMFactory._cloud_client is None:
            LLMFactory._cloud_client = LLMFactory._create_clean_client(60.0)
            print("DEBUG: Cloud Client (Direct-Link) Active.")
        
        if LLMFactory._local_client is None:
            LLMFactory._local_client = LLMFactory._create_clean_client(300.0)
            print("DEBUG: Local Client (Direct-Link) Active.")


    @staticmethod
    def get_instance(strategy: str = None):
        LLMFactory._initialize_clients()
        strategy = strategy or settings.ACTIVE_LLM_STRATEGY
        
        if strategy == "cloud":
            return ChatOpenAI(
                model_name=settings.DEFAULT_MODEL,
                openai_api_key=settings.DEEPSEEK_API_KEY,
                openai_api_base=settings.DEEPSEEK_BASE_URL,
                temperature=0.0,
                # 重点：注入异步 Client，彻底解决全局环境变量污染
                http_async_client=LLMFactory._cloud_client 
            )
        else:
            return ChatOpenAI(
                model=settings.OLLAMA_MODEL,
                api_key="ollama",
                base_url=settings.OLLAMA_BASE_URL,
                temperature=0.0,
                http_async_client=LLMFactory._local_client
            )