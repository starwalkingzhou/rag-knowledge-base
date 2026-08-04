"""LangSmith 可观测性接入。

设计意图:
- 把 LangSmith SDK 的具体调用收敛到本文件,业务代码只看到两个稳定符号:
  @traceable 装饰器 和 get_current_trace_id()。
- 启动阶段把 settings 同步到 LangSmith 官方环境变量。LangSmith SDK 内部读的是
  环境变量(LANGSMITH_TRACING / LANGSMITH_API_KEY 等),而不是我们的 Settings,
  所以必须在 create_app 阶段显式同步一次。
- 未启用时强制 LANGSMITH_TRACING=false,避免 SDK 在缺 key 时尝试上报、刷错误日志。
"""

from __future__ import annotations

import os

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def configure_observability() -> None:
    """把 settings 写到 LangSmith 官方环境变量，应用启动时调用一次即可。

    - 启用：写 LANGSMITH_TRACING=true + API key / project / endpoint
    - 关闭：强制写 LANGSMITH_TRACING=false，避免 SDK 走默认开启路径
    """
    if settings.observability_enabled:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
        logger.info(
            "LangSmith tracing enabled: project=%s endpoint=%s",
            settings.langsmith_project,
            settings.langsmith_endpoint,
        )
    else:
        os.environ["LANGSMITH_TRACING"] = "false"
        logger.info(
            "LangSmith tracing disabled (no LANGSMITH_API_KEY or switch off)"
        )


def get_current_trace_id() -> str | None:
    """返回当前活跃 run 的 trace id；未启用或无活跃 run 时返回 None。"""
    if not settings.observability_enabled:
        return None
    try:
        from langsmith.run_helpers import get_current_run_tree

        run = get_current_run_tree()
        if run is None:
            return None
        # root run 的 id 即 trace_id
        root = run
        while getattr(root, "parent_run", None) is not None:
            root = root.parent_run  # type: ignore[assignment]
        run_id = getattr(root, "id", None) or getattr(run, "trace_id", None)
        return str(run_id) if run_id else None
    except Exception:
        logger.exception("get_current_trace_id failed")
        return None


def build_trace_url(trace_id: str | None) -> str | None:
    """用配置的 URL 前缀拼出前端可跳转的 LangSmith run 链接。

    未配置 prefix 或缺少 trace_id 时返回 None（前端只显示复制按钮）。
    """
    if not trace_id:
        return None
    prefix = (settings.langsmith_run_url_prefix or "").rstrip("/")
    if not prefix:
        return None
    return f"{prefix}/r/{trace_id}"
