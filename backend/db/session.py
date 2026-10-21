"""
db/session.py
Async SQLAlchemy session factory and database engine setup.
Uses asyncpg driver as specified in spec §3.1 (SQLAlchemy 2.0 async + asyncpg).
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import get_settings

settings = get_settings()

import socket

# Ensure IPv4 resolution priority for asyncpg on dual-stack networks with broken IPv6 routing
_orig_getaddrinfo = socket.getaddrinfo

def _ipv4_preferred_getaddrinfo(host, port, *args, **kwargs):
    if len(args) > 0 and args[0] == socket.AF_UNSPEC:
        args = (socket.AF_INET,) + args[1:]
    elif kwargs.get("family") == socket.AF_UNSPEC:
        kwargs["family"] = socket.AF_INET
    return _orig_getaddrinfo(host, port, *args, **kwargs)

socket.getaddrinfo = _ipv4_preferred_getaddrinfo

engine_kwargs = {"echo": settings.debug}
if "sqlite" in settings.database_url.lower():
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = settings.db_pool_size
    engine_kwargs["max_overflow"] = settings.db_max_overflow
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 300
    engine_kwargs["connect_args"] = {
        "timeout": 30.0,
        "command_timeout": 30.0,
    }

engine = create_async_engine(
    settings.database_url,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            if session.is_active:
                await session.commit()
        except Exception:
            try:
                await session.rollback()
            except Exception:
                pass
            raise
