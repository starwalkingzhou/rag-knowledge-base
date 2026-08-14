"""FastMCP 实例入口；工具注册见 tools.py。

部署形态选择：
- stateless_http=True：每次工具调用独立，不维护会话；契合 RAG 一次性问答，便于水平扩展
- json_response=True：直接 JSON 响应而非 SSE，降低浏览器 / Agent 客户端接入成本
- streamable_http_path="/"：挂载到 /mcp 后入口即为 /mcp，避免默认的 /mcp/mcp
"""

from mcp.server.fastmcp import FastMCP

from app.mcp_server.tools import register_tools

knowledge_mcp = FastMCP(
    "rag-knowledge-base",
    instructions=(
        "企业知识库 MCP Server。"
        "直接问答请用 ask_knowledge_base；"
        "查看库内文档用 list_documents / get_document_status / get_knowledge_base_stats；"
        "管理员可用 upload_document 上传新文件。"
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
)

register_tools(knowledge_mcp)
