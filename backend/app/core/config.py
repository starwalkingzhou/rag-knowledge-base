""" 应用配置：从根目录 .env 读取环境变量并暴露settings 单例 """

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "rag-knowledge-base"
    log_level: str = "INFO"

    # 新增的数据库配置
    database_url: str = "postgresql+asyncpg://rag:rag@localhost:5432/rag_kb"

    cos_secret_id: str = ""
    cos_secret_key: str = ""
    cos_region: str = "ap-guangzhou"
    cos_bucket: str = ""

    @property
    def cos_configured(self) -> bool:
        return bool(self.cos_secret_id and self.cos_secret_key and self.cos_bucket)

    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ==== Embedding(DashScope OpenAI 兼容协议) ====
    embedding_api_key: str = ""
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "text-embedding-v3"
    # 维度需与 alembic 迁移中 Vector(N)保持一致;改维度需要重建表
    embedding_dim: int = 1024
    embedding_batch_size: int = 10

    # ===== 文档上传与切分 ====
    upload_max_size_mb: int = 50
    chunk_size: int = 600
    chunk_overlap: int = 60

    # ==== Chat 模型(DashScope OpenAI 兼容协议) ====
    # 默认与 embedding 同 base_ur1
    chat_api_key: str = ""
    chat_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    chat_model: str = "qwen-plus"

    # ==== 检索与问答 ====
    # 检索 Top - K: 交给 LLM 的候选 chunk 数量
    retrieval_top_k: int = 5
    # 拒答阈值:cosine similarity(=1- cosine_distance)的下限
    # Top-K 中最高分仍低于此值,直接拒答,不调 LLM
    retrieval_min_score: float = 0.6
    # 多轮窗口:load_context 节点取最近多少轮塞进 prompt
    chat_history_window: int = 5

    # ==== Query优化(第5章) ====
    # 关掉后 route_query 节点强制走 original,方便对比有/无路由的效果
    query_route_enabled: bool = True
    # Multi-Query 策略生成的子查询数量,过大会增加 embedding 成本
    multi_query_count: int = 3


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
