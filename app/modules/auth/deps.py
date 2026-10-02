"""Auth dependencies - the public interface other modules use to protect routes.

    from app.modules.auth.deps import CurrentUser, StaffUser
"""

import uuid
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import DbSession
from app.modules.auth.models import Role, User
from app.modules.auth.repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False, description="Access token from POST /auth/login")


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    if creds is None:
        raise UnauthorizedError("Not authenticated", code="not_authenticated")
    try:
        payload = decode_access_token(creds.credentials)
        user_id = uuid.UUID(payload["sub"])
    except jwt.ExpiredSignatureError:
        # Frontend: on this exact code, call POST /auth/refresh once, then retry.
        raise UnauthorizedError("Access token expired", code="token_expired") from None
    except (jwt.PyJWTError, ValueError, KeyError):
        raise UnauthorizedError("Invalid access token", code="invalid_token") from None
    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid access token", code="invalid_token")
    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Account unavailable", code="invalid_token")
    return user


def require_roles(*roles: Role):
    async def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise ForbiddenError(
                "You do not have permission to perform this action", code="insufficient_permissions"
            )
        return user

    return checker


CurrentUser = Annotated[User, Depends(get_current_user)]
StaffUser = Annotated[User, Depends(require_roles(Role.staff, Role.admin))]
AdminUser = Annotated[User, Depends(require_roles(Role.admin))]
