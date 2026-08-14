"""MCP 工具鉴权：解析 Bearer JWT，校验用户状态与 admin 权限。"""

from uuid import UUID

from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError

from app.core.exceptions import AppException, UnauthorizedError
from app.core.security import decode_access_token
from app.db.models import User, UserStatus
from app.db.repositories.user_repo import UserRepository
from app.db.session import AsyncSessionLocal
from app.services.permission_service import is_admin


def _parse_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise UnauthorizedError("请先登录")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("无效的访问凭证")
    return token


async def resolve_current_user(ctx: Context) -> User:
    """对齐 REST 的 get_current_user；MCP 无 HTTP 401，统一抬升为 ToolError。"""
    request = getattr(ctx.request_context, "request", None)
    if request is None:
        # stdio 等无 HTTP 上下文的传输拿不到 Authorization
        raise ToolError("当前传输不支持鉴权")

    try:
        authorization = request.headers.get("authorization")
        token = _parse_bearer_token(authorization)
        subject = decode_access_token(token)
        user_id = UUID(subject)
    except (AppException, ValueError, TypeError) as exc:
        raise ToolError(
            _user_facing_message(exc, default="无效的访问凭证")
        ) from exc

    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_id(user_id)
        if user is None:
            raise ToolError("用户不存在或已被删除")
        if user.status != UserStatus.ACTIVE:
            raise ToolError("账号已被禁用")
        return user


def require_admin(user: User) -> None:
    """admin-only 工具入口处调用；非 admin 直接 ToolError。"""
    if not is_admin(user):
        raise ToolError("仅管理员可调用此工具")


def _user_facing_message(exc: Exception, *, default: str) -> str:
    """统一把 AppException.message 透传给 Agent；其它异常用兜底文案。"""
    if isinstance(exc, AppException):
        return exc.message
    return default
