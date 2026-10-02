from fastapi import APIRouter, Cookie, Depends, Response

from app.core.config import get_settings
from app.core.ratelimit import RateLimiter
from app.db.session import DbSession
from app.modules.auth.deps import CurrentUser
from app.modules.auth.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UpdateProfileRequest,
    UserOut,
)
from app.modules.auth.service import AuthService, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])

_settings = get_settings()


def _set_refresh_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        key=s.refresh_cookie_name,
        value=token,
        max_age=s.refresh_token_ttl_days * 86400,
        httponly=True,  # JS cannot read it -> XSS cannot steal it
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,
        domain=s.cookie_domain,
        path=s.refresh_cookie_path,  # only sent to /auth/* endpoints
    )


def _clear_refresh_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(
        key=s.refresh_cookie_name,
        path=s.refresh_cookie_path,
        domain=s.cookie_domain,
        secure=s.cookie_secure,
        httponly=True,
        samesite=s.cookie_samesite,
    )


def _auth_response(user, tokens: TokenPair) -> AuthResponse:
    return AuthResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=201,
    summary="Create a customer account and log in",
    dependencies=[Depends(RateLimiter(10, 3600, "register"))],
)
async def register(body: RegisterRequest, response: Response, db: DbSession):
    user, tokens = await AuthService(db).register(body)
    _set_refresh_cookie(response, tokens.refresh_token)
    return _auth_response(user, tokens)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Log in (customers, staff and admins)",
    dependencies=[Depends(RateLimiter(10, 60, "login"))],
)
async def login(body: LoginRequest, response: Response, db: DbSession):
    user, tokens = await AuthService(db).login(body.email, body.password)
    _set_refresh_cookie(response, tokens.refresh_token)
    return _auth_response(user, tokens)


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Exchange the refresh cookie for a new access token (rotates the cookie)",
    dependencies=[Depends(RateLimiter(60, 60, "refresh"))],
)
async def refresh(
    response: Response,
    db: DbSession,
    refresh_token: str | None = Cookie(default=None, alias=_settings.refresh_cookie_name),
):
    user, tokens = await AuthService(db).refresh(refresh_token)
    _set_refresh_cookie(response, tokens.refresh_token)
    return _auth_response(user, tokens)


@router.post("/logout", status_code=204, summary="Revoke the refresh token and clear the cookie")
async def logout(
    response: Response,
    db: DbSession,
    refresh_token: str | None = Cookie(default=None, alias=_settings.refresh_cookie_name),
):
    await AuthService(db).logout(refresh_token)
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserOut, summary="Current user")
async def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserOut, summary="Update own profile")
async def update_me(body: UpdateProfileRequest, user: CurrentUser, db: DbSession):
    return await AuthService(db).update_profile(user, body)
