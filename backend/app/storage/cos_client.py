"""腾讯云 cos 客户端封装"""

import asyncio

from app.core.config import settings
from app.core.exceptions import ConfigurationError
from app.core.logging import get_logger
from qcloud_cos import CosConfig, CosS3Client
from qcloud_cos.cos_exception import CosClientError, CosServiceError

logger = get_logger(__name__)


class CosClient:

    def __init__(self) -> None:
        if not settings.cos_configured:
            raise ConfigurationError("腾讯云 COS 未配置,请在.env 中填写 cos _* 变量")

        config = CosConfig(
            Region=settings.cos_region,
            SecretId=settings.cos_secret_id,
            SecretKey=settings.cos_secret_key,
        )

        self._client = CosS3Client(config)
        self._bucket = settings.cos_bucket

    @property
    def bucket(self) -> str:
        return self._bucket

    @property
    def region(self) -> str:
        return settings.cos_region

    async def ping(self) -> bool:
        """通过head_bucket验证凭据与桶可达性。"""
        try:
            await asyncio.to_thread(self._client.head_bucket, Bucket=self._bucket)
            return True
        except (CosClientError, CosServiceError) as exc:
            logger.warning("COS ping failed: %s", exc)
            return False

    async def put_object(self, *, key: str, body: bytes, content_type: str) -> None:
        """“上传字节流到指定 object key。同名覆盖。"""
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    async def get_object(self, key: str) -> bytes:
        """读取object全部字节。"""

        def _read() -> bytes:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            # SDK 返回的 Body 是流式对象,get_raw_stream 拿到原始 stream
            return response["Body"].get_raw_stream().read()

        return await asyncio.to_thread(_read)

    async def delete_object(self, key: str) -> None:
        """删除指定object。腾讯云SDK删除不存在的key不会抛404, 天然幂等。"""
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._bucket, Key=key
        )


_cos_client: CosClient | None = None


def get_cos_client() -> CosClient:
    """惰性构造:未配置时直接抛 ConfigurationError,由全局错误处理器转 503。"""
    global _cos_client
    if _cos_client is None:
        _cos_client = CosClient()
    return _cos_client
