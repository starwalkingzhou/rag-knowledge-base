import json
from dataclasses import dataclass

from app.core.logging import get_logger
from app.llm.models import get_chat_model
from app.llm.prompts import build_verify_answer_messages, format_context
from app.retrieval.vector_retriever import RetrievedChunk

logger = get_logger(__name__)


@dataclass(frozen=True)
class VerifyResult:
    """answer_verifier 单次校验结果。

    verified=True 时 reason 可能是空字符串（不需要解释为什么通过）。
    """

    verified: bool
    reason: str


class AnswerVerifier:
    """LLM 答案可信度校验器。"""

    async def verify(
        self,
        question: str,
        answer: str,
        chunks: list[RetrievedChunk],
    ) -> VerifyResult:
        # 没有引用候选时不做校验：要么是拒答场景（service 已经标 refused），
        # 要么是异常路径，校验也没有参考片段可对照
        if not chunks or not answer.strip():
            return VerifyResult(verified=True, reason="")

        messages = build_verify_answer_messages(
            question=question,
            answer=answer,
            chunks_text=format_context(chunks),
        )
        try:
            response = await get_chat_model().ainvoke(messages)
            raw = _extract_text(response.content).strip()
            return _parse_result(raw)
        except Exception:
            # 校验失败不阻断主流程：降级为通过，让用户仍能看到答案
            logger.exception("answer verifier 调用失败，降级通过: question=%r", question)
            return VerifyResult(verified=True, reason="verifier_exception")


_verifier: AnswerVerifier | None = None


def get_answer_verifier() -> AnswerVerifier:
    global _verifier
    if _verifier is None:
        _verifier = AnswerVerifier()
    return _verifier


def _parse_result(raw: str) -> VerifyResult:
    """解析 LLM JSON 输出。任何字段非法 -> 降级 verified=True。"""
    # 容错：模型偶尔会包一层 ```json ... ```
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("answer verifier JSON 解析失败，降级 verified=True: raw=%r", raw)
        return VerifyResult(verified=True, reason="verifier_parse_failed")

    if not isinstance(data, dict):
        return VerifyResult(verified=True, reason="verifier_parse_failed")

    verified_raw = data.get("verified")
    # 严格要求布尔；字符串 "true" / 数字 1 一律拒绝，避免歧义
    if not isinstance(verified_raw, bool):
        logger.warning(
            "answer verifier 返回 verified 字段非布尔，降级 verified=True: raw=%r",
            raw,
        )
        return VerifyResult(verified=True, reason="verifier_invalid_verified")

    reason = str(data.get("reason") or "").strip()
    return VerifyResult(verified=verified_raw, reason=reason)


def _extract_text(content: str | list[str | dict]) -> str:
    """兼容 langchain ChatModel 的 content 联合类型。"""
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))
