import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
)
from app.modules.auth.models import RefreshToken, Role, User
from app.modules.auth.repository import RefreshTokenRepository, UserRepository
from app.modules.auth.schemas import RegisterRequest, UpdateProfileRequest


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


def _aware(dt: datetime) -> datetime:
    # SQLite returns naive datetimes; Postgres returns aware ones.
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)
        self.settings = get_settings()

    async def register(self, data: RegisterRequest) -> tuple[User, TokenPair]:
        if await self.users.get_by_email(data.email):
            raise ConflictError("Email is already registered", code="email_already_registered")
        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            role=Role.customer,
        )
        self.users.add(user)
        try:
            await self.session.flush()
        except IntegrityError:  # race: same email registered concurrently
            await self.session.rollback()
            raise ConflictError(
                "Email is already registered", code="email_already_registered"
            ) from None
        tokens = self._issue_tokens(user, family_id=uuid.uuid4())
        await self.session.commit()
        return user, tokens

    async def login(self, email: str, password: str) -> tuple[User, TokenPair]:
        user = await self.users.get_by_email(email)
        if user is None:
            verify_password(DUMMY_HASH, password)  # equalise timing
            raise UnauthorizedError("Invalid email or password", code="invalid_credentials")
        if not verify_password(user.password_hash, password):
            raise UnauthorizedError("Invalid email or password", code="invalid_credentials")
        if not user.is_active:
            raise ForbiddenError("This account is disabled", code="account_disabled")
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        user.last_login_at = datetime.now(UTC)
        tokens = self._issue_tokens(user, family_id=uuid.uuid4())
        await self.session.commit()
        return user, tokens

    async def refresh(self, raw_token: str | None) -> tuple[User, TokenPair]:
        if not raw_token:
            raise UnauthorizedError("Missing refresh token", code="refresh_token_missing")
        record = await self.tokens.get_by_hash(hash_token(raw_token))
        if record is None:
            raise UnauthorizedError("Invalid refresh token", code="invalid_refresh_token")
        now = datetime.now(UTC)
        if record.revoked_at is not None:
            # A rotated/revoked token was replayed: assume theft, kill the whole family.
            await self.tokens.revoke_family(record.family_id, now)
            await self.session.commit()
            raise UnauthorizedError("Refresh token reuse detected", code="refresh_token_reused")
        if _aware(record.expires_at) <= now:
            raise UnauthorizedError("Refresh token expired", code="refresh_token_expired")
        user = await self.users.get_by_id(record.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("Account unavailable", code="invalid_refresh_token")
        record.revoked_at = now  # rotate: old token is single-use
        tokens = self._issue_tokens(user, family_id=record.family_id)
        await self.session.commit()
        return user, tokens

    async def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        record = await self.tokens.get_by_hash(hash_token(raw_token))
        if record is not None:
            await self.tokens.revoke_family(record.family_id, datetime.now(UTC))
            await self.session.commit()

    async def update_profile(self, user: User, data: UpdateProfileRequest) -> User:
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(user, key, value)
        await self.session.commit()
        return user

    def _issue_tokens(self, user: User, family_id: uuid.UUID) -> TokenPair:
        access, expires_in = create_access_token(user.id, user.role.value)
        raw_refresh = generate_refresh_token()
        self.tokens.add(
            RefreshToken(
                token_hash=hash_token(raw_refresh),
                user_id=user.id,
                family_id=family_id,
                expires_at=datetime.now(UTC) + timedelta(days=self.settings.refresh_token_ttl_days),
            )
        )
        return TokenPair(access_token=access, refresh_token=raw_refresh, expires_in=expires_in)
