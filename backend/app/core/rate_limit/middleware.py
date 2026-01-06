import time
from datetime import datetime, timedelta, timezone
from typing import Tuple

import jwt
from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.app.core.config import settings
from backend.app.core.db import engine
from backend.app.core.logging import get_logger
from backend.app.core.rate_limit.config import (
    DEFAULT_RATE_LIMITS,
    RATE_LIMIT_WHITELIST,
    RateLimitConfig,
)
from backend.app.core.rate_limit.models import RateLimitLog

logger = get_logger()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware kiểm soát rate limiting cho toàn bộ request HTTP.

    Chức năng:
    - Giới hạn số request theo IP / User / Endpoint
    - Dùng Redis để đếm request (hiệu năng cao)
    - Ghi log vi phạm rate limit vào database
    - Trả header chuẩn X-RateLimit-* cho client
    """

    def __init__(self, app: ASGIApp):
        """
        Khởi tạo middleware và kết nối Redis.
        Redis dùng để lưu counter rate limit theo key.
        """
        super().__init__(app)
        try:
            from redis import Redis

            self.redis_client = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
            )
            # Kiểm tra kết nối Redis ngay khi khởi động app
            self.redis_client.ping()
            logger.info("Successfully connected to Redis for rate limiting")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def _get_rate_limit_key(self, request: Request, endpoint: str) -> str:
        """
        Tạo key rate limit duy nhất cho mỗi request.

        Ưu tiên theo thứ tự:
        - endpoint + IP + user_id (nếu có JWT hợp lệ)
        - endpoint + IP (nếu anonymous hoặc token lỗi)
        """
        try:
            ip = request.client.host if request.client else "anonymous"
            access_token = request.cookies.get(settings.COOKIE_ACCESS_NAME)

            if access_token:
                try:
                    payload = jwt.decode(
                        access_token,
                        settings.SIGNING_KEY,
                        algorithms=[settings.JWT_ALGORITHM],
                    )
                    user_id = payload.get("id")
                    return f"ratelimit:{endpoint}:{ip}:{user_id}"
                except jwt.InvalidTokenError:
                    # Token lỗi → fallback theo IP
                    return f"ratelimit:{endpoint}:{ip}"

            return f"ratelimit:{endpoint}:{ip}"
        except Exception:
            # Fallback an toàn, không làm crash middleware
            return f"ratelimit:{endpoint}:unknown"

    async def _get_limit_config(self, endpoint: str) -> RateLimitConfig:
        """
        Lấy cấu hình rate limit cho endpoint.
        Nếu endpoint chưa cấu hình → dùng default.
        """
        return DEFAULT_RATE_LIMITS.get(endpoint, DEFAULT_RATE_LIMITS["default"])

    async def _check_rate_limit(
        self, key: str, config: RateLimitConfig
    ) -> Tuple[bool, int | None, datetime | None]:
        """
        Kiểm tra rate limit trong Redis.

        Trả về:
        - is_limited: Có bị giới hạn hay không
        - current_count: Số request hiện tại
        - blocked_until: Thời điểm hết block (nếu có)
        """
        try:
            pipe = self.redis_client.pipeline()

            # Lấy số request hiện tại
            current_count = int(str(self.redis_client.get(key) or 0))
            ttl = self.redis_client.ttl(key)

            # Nếu vượt quá giới hạn
            if current_count >= config.max_requests:
                if config.block_on_exceed:
                    block_until = datetime.now(timezone.utc) + timedelta(
                        seconds=(
                            float(str(ttl))
                            if float(str(ttl)) > 0
                            else config.window_seconds
                        )
                    )
                    return True, current_count, block_until
                return True, current_count, None

            # Nếu key chưa tồn tại → tạo mới với TTL
            if ttl == -2:
                pipe.setex(key, config.window_seconds, 1)
            else:
                # Nếu đã tồn tại → tăng counter
                pipe.incr(key)

            pipe.execute()
            return False, current_count + 1, None

        except Exception as e:
            logger.error(f"Rate limit check failed: {str(e)}")
            # Fail-open: không chặn request khi Redis lỗi
            return False, None, None

    async def _log_violation(
        self,
        request: Request,
        endpoint: str,
        count: int,
        blocked_until: datetime | None,
        session: AsyncSession,
    ):
        """
        Ghi log vi phạm rate limit vào database.
        Phục vụ audit, security monitoring và debug.
        """
        try:
            user_id = None
            access_token = request.cookies.get(settings.COOKIE_ACCESS_NAME)

            # Giải mã user_id từ JWT (nếu có)
            if access_token:
                try:
                    payload = jwt.decode(
                        access_token,
                        settings.SIGNING_KEY,
                        algorithms=[settings.JWT_ALGORITHM],
                    )
                    user_id = payload.get("id")
                except jwt.InvalidTokenError:
                    pass

            window_start = datetime.now(timezone.utc)
            window_end = (
                blocked_until if blocked_until else window_start + timedelta(hours=1)
            )

            violation_log = RateLimitLog(
                ip_address=request.client.host if request.client else "unknown",
                user_id=user_id,
                endpoint=endpoint,
                request_count=count,
                request_method=str(request.method),
                request_path=str(request.url.path),
                window_start=window_start,
                window_end=window_end,
                blocked_until=blocked_until,
            )

            session.add(violation_log)
            await session.commit()
            await session.refresh(violation_log)

            logger.info(
                f"Rate limit violation logged | IP={violation_log.ip_address} | "
                f"User={violation_log.user_id} | Endpoint={violation_log.endpoint}"
            )

        except Exception as e:
            logger.error(f"Failed to log rate limit violation: {str(e)}")
            await session.rollback()
            raise

    async def dispatch(self, request: Request, call_next):
        """
        Hàm chính intercept mọi request HTTP.
        """
        try:
            endpoint = request.url.path

            # Bỏ qua rate limit cho whitelist
            if endpoint in RATE_LIMIT_WHITELIST:
                response = await call_next(request)
                response.headers["X-RateLimit-Limit"] = "unlimited"
                response.headers["X-RateLimit-Remaining"] = "unlimited"
                return response

            # Lấy cấu hình rate limit
            config = await self._get_limit_config(endpoint)

            # Tạo key rate limit
            key = await self._get_rate_limit_key(request, endpoint)

            # Kiểm tra rate limit
            is_limited, count, blocked_until = await self._check_rate_limit(key, config)

            # Header chuẩn rate limit
            headers = {
                "X-RateLimit-Limit": str(config.max_requests),
                "X-RateLimit-Remaining": str(
                    max(0, config.max_requests - (count or 0))
                ),
                "X-RateLimit-Reset": str(
                    int(time.time() + config.window_seconds)
                ),
            }

            # Nếu bị giới hạn
            if is_limited:
                async with AsyncSession(engine) as session:
                    await self._log_violation(
                        request, endpoint, count or 0, blocked_until, session
                    )

                response = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "status": "error",
                        "message": "Too many requests",
                        "action": "Please wait before trying again",
                        "retry_after": f"{config.window_seconds} seconds",
                    },
                )

                for k, v in headers.items():
                    response.headers[k] = v

                if blocked_until:
                    response.headers["Retry-After"] = str(config.window_seconds)

                return response

            # Nếu chưa vượt giới hạn → cho request đi tiếp
            response = await call_next(request)

            for k, v in headers.items():
                response.headers[k] = v

            return response

        except Exception as e:
            # Không để middleware làm sập request
            logger.error(f"Rate limit middleware error: {str(e)}")
            return await call_next(request)
