import dataclasses
from typing import Any

import httpx
from langsmith import traceable

from app.core.config import settings
from app.core.exceptions import ConfigurationError
from app.core.logging import get_logger
from app.retrieval.vector_retriever import RetrievedChunk

logger = get_logger(__name__)


class Reranker:
    """DashScope qwen3-rerank 客户端。

    用单例 httpx.AsyncClient 持有连接池。
    rerank 挂在问答同步链路上,延迟敏感,超时比 chat 更短(默认 8s)。
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=settings.rerank_timeout)
        return self._client

    @traceable(name="Reranker.rerank", run_type="tool")
    async def rerank(
        self, query: str, candidates: list[RetrievedChunk]
    ) -> list[RetrievedChunk]:
        if len(candidates) <= 1:
            return candidates

        api_key = settings.effective_rerank_api_key
        if not api_key:
            raise ConfigurationError(
                "未配置 rerank API key,请在 .env 中设置 RERANK_API_KEY 或 CHAT_API_KEY"
            )

        try:
            scores = await self._fetch_scores(query, candidates, api_key)
        except Exception:
            logger.exception("rerank 调用失败,降级回原序")
            return candidates

        ranked = [
            dataclasses.replace(chunk, rerank_score=score)
            for chunk, score in zip(candidates, scores, strict=True)
        ]
        ranked.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)
        return ranked

    async def _fetch_scores(
        self, query: str, candidates: list[RetrievedChunk], api_key: str
    ) -> list[float]:
        """调用 DashScope rerank 端点。

        接口按相关度降序返回 results,每条带 index 指回输入 documents 数组。
        这里按 index 把分数写回原始顺序,保证 candidates[i] ↔ scores[i]。
        """
        payload = {
            "model": settings.rerank_model,
            "query": query,
            "documents": [c.content for c in candidates],
            "top_n": len(candidates),
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        client = self._get_client()
        response = await client.post(
            settings.rerank_base_url,
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        results = body.get("results")
        if not isinstance(results, list) or not results:
            raise ValueError("rerank 响应缺少 results")

        scores = [0.0] * len(candidates)
        for item in results:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            score = item.get("relevance_score")
            if isinstance(idx, int) and isinstance(score, (int, float)):
                if 0 <= idx < len(scores):
                    scores[idx] = float(score)
        return scores


_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker
