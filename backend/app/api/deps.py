"""FastAPI 依赖项定义。"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import PermissionDeniedError, UnauthorizedError
from app.core.rate_limiter import get_rate_limiter
from app.core.security import decode_access_token
from app.db.models import User, UserStatus
from app.db.repositories.user_repo import UserRepository
from app.db.session import get_session
from app.services.permission_service import is_admin

DbSession = Annotated[AsyncSession, Depends(get_session)]


def _parse_bearer_token(authorization: str | None) -> str:
    """从 Authorization header 取出 Bearer token；缺失或格式错误统一 401。"""
    if not authorization:
        raise UnauthorizedError("请先登录")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("无效的访问凭证")
    return token


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> User:
    """解析 Bearer token，查表拿到 User。

    每个请求都重新查一次而不是把信息塞进 token：
    - 角色 / 状态变更后立即生效，不必等 token 自然过期
    - token 内只放 user_id，泄露 token 也拿不到额外用户信息
    """
    token = _parse_bearer_token(authorization)
    subject = decode_access_token(token)
    try:
        user_id = UUID(subject)
    except (ValueError, TypeError) as exc:
        raise UnauthorizedError("无效的访问凭证") from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("用户不存在或已被删除")
    if user.status != UserStatus.ACTIVE:
        raise UnauthorizedError("账号已禁用")
    return user


async def get_current_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """仅 admin 可通过。普通用户 403。"""
    if not is_admin(user):
        raise PermissionDeniedError("仅管理员可访问")
    return user


async def enforce_rate_limit(
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """基于 user_id 的滑动窗口限流，每分钟最多 RATE_LIMIT_PER_MINUTE 次。

    挂在写接口（chat / 上传 / 重新索引）；读接口（list / get）不要挂，
    否则前端 3 秒轮询文档列表会被误伤。
    """
    if not settings.rate_limit_enabled:
        return
    await get_rate_limiter().check(f"user:{user.id}")


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
RateLimited = Annotated[None, Depends(enforce_rate_limit)]
