"""FastAPI dependencies: session, auth, role checks."""

from collections.abc import AsyncGenerator

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import async_session
from web.auth import COOKIE_NAME, decode_session_token


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session, auto-close on exit."""
    async with async_session() as session:
        yield session


async def get_current_user(
    request: Request,
    ct_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> dict:
    """Extract current user from session cookie.

    Returns {"role": "admin"|"teamlead"|"model"}.
    Raises 401 if no valid session.
    """
    if not ct_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    data = decode_session_token(ct_session)
    if data is None:
        raise HTTPException(status_code=401, detail="Session expired")

    return data


def require_role(*allowed_roles: str):
    """Factory: creates a dependency that checks user has one of allowed_roles."""

    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return _check
