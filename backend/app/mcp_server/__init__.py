"""MCP Server 入口模块。

按 MCP 标准工具协议，把知识库核心能力（问答 / 文档上传 / 列表 / 状态查询 / 统计）
暴露给外部 Agent。鉴权重用前序阶段的 JWT；工具实现统一调用
`app.services.*` 与 `app.workflows.*`，不重写业务逻辑。
"""

from app.mcp_server.server import knowledge_mcp

__all__ = ["knowledge_mcp"]
