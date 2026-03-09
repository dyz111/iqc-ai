from __future__ import annotations

import json
import time
import asyncio

from app.core.llm_factory import LLMFactory
from app.core.schema import ExceptionSuggestionRequest, ExceptionSuggestionResponse, SuggestionItem
from app.core.config import settings

from app.embedding.bge_manager import BgeManager
from app.storage.chroma_manager import ChromaManager
from app.rag.field_extractors import extract_exception_suggestion_fields

semaphore = asyncio.Semaphore(5)

DEPTS = ["purchase", "planning", "production", "engineering", "quality"]


async def _invoke_llm(llm, system: str, user: str) -> str:
    response = await llm.ainvoke(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )
    return response.content.strip()


def _parse_json_safely(text: str) -> dict:
    # 去重键：同对象内重复字段取首次出现值
    def _no_dup_object(pairs):
        obj = {}
        for k, v in pairs:
            if k not in obj:
                obj[k] = v
        return obj

    return json.loads(text, object_pairs_hook=_no_dup_object)


def _extract_json(text: str) -> str:
    # 优先抽取标记内的 JSON
    begin = "---BEGIN JSON---"
    end = "---END JSON---"
    if begin in text and end in text:
        return text.split(begin, 1)[1].split(end, 1)[0].strip()
    # 兼容 ```json ... ``` 或 ``` ... ``` 包裹的情况
    if "```" not in text:
        return text.strip()
    lines = [line.strip() for line in text.splitlines()]
    if lines and lines[0].startswith("```"):
        if lines[-1].startswith("```"):
            lines = lines[1:-1]
        else:
            lines = lines[1:]
    return "\n".join(lines).strip()


class ExceptionSuggestionService:
    # 总入口：仅使用 LLM，失败则抛错（由上层提示“生成失败”）
    @staticmethod
    async def generate(req: ExceptionSuggestionRequest) -> ExceptionSuggestionResponse:
        try:
            return await ExceptionSuggestionService._llm_generate(req)
        except Exception as exc:
            print(f"ERROR [Order: {req.orderNo}]: {str(exc)}")
            raise exc

    @staticmethod
    async def _llm_generate(req: ExceptionSuggestionRequest) -> ExceptionSuggestionResponse | None:
        # LLM 生成建议：调用 LLM 接口获取建议
        llm_strategy = settings.ACTIVE_LLM_STRATEGY  # 获取当前是 cloud 还是 local
        llm = LLMFactory.get_instance()

        # 1. 统一提取业务事实 
        # 无论是 RAG 检索还是 LLM 判定，都可基于这个 extract 出来的文本
        payload_dict = req.model_dump()
        current_fact = extract_exception_suggestion_fields(payload_dict)

        # === Step A: RAG 检索逻辑 (给 AI 提供记忆) ===
        history_context = "暂无历史处理建议记录"
        try:
            bge = BgeManager(settings.BGE_MODEL_PATH)
            chroma = ChromaManager(settings.CHROMA_PERSIST_PATH)

            vectors = await bge.encode([current_fact]) 
            query_vector = vectors[0].tolist()
            search_results = chroma.search_similar_cases(query_vector, n_results=3)
            print(f"RAG 检索到 {search_results} ")

            if search_results and search_results['documents']:
                cases = []
                for i in range(len(search_results['ids'][0])):
                    doc = search_results['documents'][0][i]
                    score = 1 - search_results['distances'][0][i]
                    order_id = search_results['ids'][0][i]
                    cases.append(f"【参考案卷{i+1} | 编号：{order_id} | 相似度：{score:.2f}】\n结论逻辑：{doc}")
                history_context = "\n\n".join(cases)
        except Exception as rag_err:
            print(f"RAG 检索分流失败: {rag_err}")

        # === Step B: 强化 Prompt (注入历史记忆) ===
        # pydantic 的模型对象 -> dict（用于传给 LLM，保持字段结构一致）

        # deepseek
        if llm_strategy == "cloud":
            system = (
                "# Role: 品质管理专家 (IQC领域)\n"
                "## 核心任务：\n"
                "分析当前单据中的【尺寸偏差数值】或【外观缺陷描述】，结合【历史案例】，给出极具技术含量的处置建议。\n\n"
                "## 部门建议(Remark)思维导图（禁止复读，必须体现专业性）：\n"
                "1. **拒绝空话**：必须点出具体问题（如：实测12.5mm超上限0.2mm、表面划伤长2mm等）。\n"
                "2. **因果逻辑**：说明为什么这个偏差可以接受或必须退货（如：非装配位、影响气密性等）。\n"
                "3. **采购部**：侧重供应商管理。考虑交付周期、商务扣款、供应商历史诚信、退货对订单的影响。\n"
                "4. **计调部**：侧重停工风险。考虑当前库存水位、生产紧急度、缺料导致的断线损失。\n"
                "5. **生产部**：侧重现场执行。考虑返工/挑选的人力成本、产线节拍影响、现场隔离可行性。\n"
                "6. **工程部**：侧重功能评估。从装配干涉、可靠性风险、图纸公差余量、设计意图进行专业判定。\n"
                "7. **品管部**：侧重风险闭环。考虑AQL判定标准、SCAR纠正预防、后续加严检验、品质趋势分析。\n\n"
                "## 格式约束：\n"
                "1. 严格输出 JSON，包裹在 ---BEGIN JSON--- 和 ---END JSON--- 之间。\n"
                "2. option 只能取: [特采, 退货, 加工/选用]。\n"
                "3. evidence 必须是精炼的 3 条逻辑（1.现状数据; 2.历史对标; 3.风险评估）。\n"
                "## 证据(evidence)三条准则：\n"
                "1. **现状描述**：必须包含具体不合格项、不良率、以及具体超差了多少。\n"
                "2. **历史对标**：必须综合参考提供的 Top 3 案例单号。总结它们的处理共性（如：3个案例中2个特采1个退货，说明风险可控）。\n"
                "3. **风险评估**：给出最终的工程判定逻辑。\n"
            )
            example_json = {
                "purchase": {"option": "...", "remark": "[从供应商关系和交付成本角度给出建议]"},
                "planning": {"option": "...", "remark": "[从排产计划和缺料停线风险角度给出建议]"},
                "production": {"option": "...", "remark": "[从产线操作可行性和返工成本角度给出建议]"},
                "engineering": {"option": "...", "remark": "[从产品功能、规格极限和装配风险角度给出建议]"},
                "quality": {"option": "...", "remark": "[从质量标准合规性和风险防范角度给出建议]"},
                "evidence": [
                    "1. 现状：[描述当前物料不合格项的严重程度]",
                    "2. 历史：[总结历史案例的处理共性]",
                    "3. 评估：[给出最终的工程与品质风险定论]"
                ]
            }
            # 组装用户输入
            user = f"""
            ### 1. 历史相似案例参考 (你必须参考这些历史结论的逻辑, 尤其是):
            {history_context}
            ### 2. 当前待处理异常数据:
            {json.dumps(payload_dict, ensure_ascii=False)}
            ### 3. 输出格式示例 (严格按此结构返回):
            ---BEGIN JSON---
            {json.dumps(example_json, ensure_ascii=False)}
            ---END JSON---

            请开始输出（禁止提到任何与当前数据无关的零件名称）：
            """

        # local ollama
        else:
            system = (
                "# Role: 品质判定员\n"
                "## 任务：根据提供的[事实清单]和[历史参考]，填写 JSON 建议。\n"
                "## 铁律：\n"
                "1. option 只能从 [特采, 退货, 加工/选用] 中三选一。\n"
                "2. 严禁提到螺纹、壁厚等数据中没有的词汇。当前物料是：左耳壳。\n"
                "3. remark 必须包含[事实清单]中的具体不良数或不良率。\n"
                "4. 必须输出 evidence 数组（包含3条逻辑）。"
            )
            example_json = {
                "purchase": {"option": "...", "remark": "针对[物料名]的[具体NG问题]，建议..."},
                "planning": {"option": "...", "remark": "考虑到订单紧急，针对[具体NG问题]建议..."},
                "production": {"option": "...", "remark": "产线针对[具体NG项]可以进行[动作]..."},
                "engineering": {"option": "...", "remark": "技术评估：[具体实测值]虽不合格但..."},
                "quality": {"option": "...", "remark": "判定NG，对比历史单号...建议..."},
                "evidence": ["现状描述", "历史对标", "风险评估"]
            }
            user = f"""
            ### 1. 事实清单 (必须基于此内容):
            {current_fact}

            ### 2. 历史参考案例:
            {history_context}

            ### 3. 任务：将事实填入以下模版，禁止提到“螺纹”等无关词汇。
            ---BEGIN JSON---
            {json.dumps(example_json, ensure_ascii=False)}
            ---END JSON---
            """
        

        # 调用 LLM（失败时重试一次）
        async with semaphore:  # 控制并发任务数目
            print("LLM user prompt:\n", user)
            start_time = time.time()
            content = await _invoke_llm(llm, system, user)
            cleaned = _extract_json(content)
            print(f"LLM 处理耗时: {time.time() - start_time:.2f}秒")
            print(f"LLM 原始输出:\n{content}\n")
            try:
                result = _parse_json_safely(cleaned)
            except Exception as e:
                strict_user = "上次输出格式错误，请严格输出 JSON。\n\n" + user
                content = await _invoke_llm(llm, system, strict_user)
                cleaned = _extract_json(content)
                result = _parse_json_safely(cleaned)
                print(f"FATAL ERROR IN LLM CALL: {type(e).__name__} - {str(e)}")
                raise e


        return ExceptionSuggestionResponse(
            purchase=SuggestionItem(**result["purchase"]),
            planning=SuggestionItem(**result["planning"]),
            production=SuggestionItem(**result["production"]),
            engineering=SuggestionItem(**result["engineering"]),
            quality=SuggestionItem(**result["quality"]),
            evidence=result.get("evidence", [
                "1. 现状：数据已获取，但 AI 未能生成结构化证据。",
                "2. 历史：请参考历史案卷全文进行人工判定。",
                "3. 评估：建议人工审核当前处置风险。"
            ])
        )

