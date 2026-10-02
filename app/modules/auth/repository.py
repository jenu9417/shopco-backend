import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import RefreshToken, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        return (await self.session.scalars(select(User).where(User.email == email))).first()

    def add(self, user: User) -> None:
        self.session.add(user)


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, token: RefreshToken) -> None:
        self.session.add(token)

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return (await self.session.scalars(stmt)).first()

    async def revoke_family(self, family_id: uuid.UUID, now: datetime) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
