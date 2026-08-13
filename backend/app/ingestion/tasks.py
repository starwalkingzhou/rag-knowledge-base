"""Celery 入库任务。

Worker 是同步进程，业务链路是 async：任务内用 asyncio.run 拉起独立事件循环
执行 pipeline。

任务签名只传两个 UUID 字符串，不传 ORM / session / 文件内容：
1. Celery broker 用 JSON 序列化，复杂对象无法跨进程传递
2. Worker 是独立进程，文件系统 / DB / Redis 必须用 ID 自行再取
"""

from uuid import UUID

from app.celery_app import celery_app
from app.ingestion.pipeline import run_ingest_sync, run_reindex_sync


@celery_app.task(bind=True, name="ingest_document")
def ingest_document_task(self, document_id: str, task_id: str) -> None:
    """首次入库任务。"""
    run_ingest_sync(UUID(document_id), UUID(task_id))


@celery_app.task(bind=True, name="reindex_document")
def reindex_document_task(self, document_id: str, task_id: str) -> None:
    """增量重建任务。"""
    run_reindex_sync(UUID(document_id), UUID(task_id))
