from fastapi import APIRouter, HTTPException

from app.core.schema import ExceptionSuggestionRequest, ExceptionSuggestionResponse
from app.services.exception_suggestion_service import ExceptionSuggestionService
from openai import AuthenticationError, APIConnectionError

router = APIRouter(prefix="/ai", tags=["ai"])  # 统一 AI 接口前缀


@router.post("/exception_suggestion", response_model=ExceptionSuggestionResponse)
async def exception_suggestion(payload: ExceptionSuggestionRequest) -> ExceptionSuggestionResponse:
    # 异常单处理建议入口：接收 Java 端 DTO JSON，返回结构化建议
    try:
        return await ExceptionSuggestionService.generate(payload)
    except AuthenticationError as e:
        raise HTTPException(status_code=503, detail="AI 授权失效，请联系管理员或切换人工")
    except APIConnectionError as e:
        raise HTTPException(status_code=503, detail="AI 算力链路中断，请检查代理设置")
    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail="系统内部错误")
