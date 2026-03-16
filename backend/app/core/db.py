import asyncio
from typing import AsyncGenerator
from backend.app.core.config import settings
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.logging import get_logger



logger = get_logger()

engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=AsyncAdaptedQueuePool,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    )

async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

def _is_http_error(exc: BaseException) -> bool:
    """True nếu là lỗi HTTP (401, 403, 500...) — không log nhầm thành lỗi DB."""
    if isinstance(exc, HTTPException):
        return True
    code = getattr(exc, "status_code", None)
    if code is not None and 400 <= code < 600:
        return True
    return False


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session = async_session()
    try:
        yield session
    except BaseException as e:
        if _is_http_error(e):
            raise
        logger.error(f"Lỗi phiên làm việc với cơ sở dữ liệu: {e}")
        if session:
            try:
                await session.rollback()
                logger.info("Đã rollback phiên làm việc thành công sau khi xảy ra lỗi")
            except Exception as rollback_error:
                logger.error(f"Lỗi khi rollback phiên làm việc với cơ sở dữ liệu: {rollback_error}")
        raise
    finally:
        if session:
            try:
                await session.close()
                logger.debug("Đã đóng phiên làm việc với cơ sở dữ liệu thành công")
            except Exception as close_error:
                logger.error(f"Lỗi khi đóng phiên làm việc với cơ sở dữ liệu: {close_error}")
        
async def init_db() -> None:
    try:
        # load_models()
        # logger.info("Models loaded successfully")

        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                async with engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
                logger.info("Đã xác minh kết nối cơ sở dữ liệu thành công")
                break
            except Exception:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Không thể xác minh kết nối cơ sở dữ liệu sau {max_retries} lần thử"
                    )
                    raise
                logger.warning(f"Thử kết nối cơ sở dữ liệu lần {attempt + 1}")

                await asyncio.sleep(retry_delay * (attempt + 1))

    except Exception as e:
        logger.error(f"Khởi tạo cơ sở dữ liệu thất bại: {e}")
        raise