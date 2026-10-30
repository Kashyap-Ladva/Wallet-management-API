import logging
import os
import re
import time
from uuid import uuid4
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, Request, status

from app.core.dependencies import get_current_user
from app.core.redis import get_redis_client
from app.models import User

logger = logging.getLogger("app.rate_limit")

# Lua script for sliding window rate limiting
# KEYS[1]: rate limit key
# ARGV[1]: max requests limit
# ARGV[2]: window size in seconds
# ARGV[3]: current timestamp (float as string or int)
# ARGV[4]: unique member identifier (e.g. timestamp-uuid)
# Returns: {allowed (1 or 0), remaining, retry_after_seconds}
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local member = ARGV[4]
local clearBefore = now - window

-- Remove entries outside current sliding window
redis.call('ZREMRANGEBYSCORE', key, '-inf', clearBefore)

-- Count current requests in window
local currentRequests = redis.call('ZCARD', key)

if currentRequests < limit then
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, math.ceil(window))
    local remaining = limit - currentRequests - 1
    return {1, remaining, 0}
else
    -- Find oldest entry in window to compute retry_after
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retryAfter = math.ceil(window)
    if oldest and #oldest >= 2 then
        local oldestScore = tonumber(oldest[2])
        retryAfter = math.ceil(oldestScore + window - now)
        if retryAfter < 1 then
            retryAfter = 1
        end
    end
    return {0, 0, retryAfter}
end
"""


def parse_rate_limit(limit_str: str) -> Tuple[int, int]:
    """
    Parse a rate limit string like '5/minute', '3/hour', '30/second', '100/day'.
    Returns (limit_count, window_seconds).
    """
    match = re.match(r"^(\d+)\s*/\s*([a-zA-Z]+)$", limit_str.strip())
    if not match:
        raise ValueError(f"Invalid rate limit format: '{limit_str}'. Expected '<count>/<unit>'")

    count = int(match.group(1))
    unit = match.group(2).lower()

    unit_multipliers = {
        "s": 1,
        "sec": 1,
        "second": 1,
        "seconds": 1,
        "m": 60,
        "min": 60,
        "minute": 60,
        "minutes": 60,
        "h": 3600,
        "hr": 3600,
        "hour": 3600,
        "hours": 3600,
        "d": 86400,
        "day": 86400,
        "days": 86400,
    }

    if unit not in unit_multipliers:
        raise ValueError(f"Unknown time unit '{unit}' in rate limit '{limit_str}'")

    window = unit_multipliers[unit]
    return count, window


def get_client_ip(request: Request) -> str:
    """
    Resolve client IP address with secure proxy handling.
    Does NOT blindly trust X-Forwarded-For unless the direct peer IP is in TRUSTED_PROXIES.
    """
    direct_ip = request.client.host if request.client else "127.0.0.1"
    trusted_env = os.getenv("TRUSTED_PROXIES", "").strip()

    if trusted_env:
        trusted = {p.strip() for p in trusted_env.split(",") if p.strip()}
        if direct_ip in trusted or "*" in trusted:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                # First element is original client IP
                client_ip = forwarded.split(",")[0].strip()
                if client_ip:
                    return client_ip
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip.strip()

    return direct_ip


async def _execute_rate_limit(key: str, limit_expr: str, name: str) -> None:
    client = get_redis_client()
    fail_open = os.getenv("RATE_LIMIT_FAIL_OPEN", "true").lower() in ("true", "1", "yes")
    limit, window = parse_rate_limit(limit_expr)
    now = time.time()
    member = f"{now}-{uuid4().hex[:8]}"

    if client is None:
        if fail_open:
            logger.warning("Redis unavailable for rate limiter '%s' (%s). Failing open.", name, key)
            return
        else:
            logger.error("Redis unavailable for rate limiter '%s' (%s). Failing closed.", name, key)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiting service temporarily unavailable",
            )

    try:
        res = await client.eval(
            SLIDING_WINDOW_LUA,
            1,
            key,
            str(limit),
            str(window),
            str(now),
            member,
        )
        allowed = bool(res[0])
        retry_after = int(res[2]) if len(res) > 2 else window

        if not allowed:
            logger.warning(
                "Rate limit '%s' exceeded for %s. Retry-After: %ds",
                name,
                key,
                retry_after,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Please try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Rate limiter Redis execution failed for %s: %s", key, exc)
        if fail_open:
            logger.warning("Failing open for rate limiter '%s' due to backend error.", name)
            return
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiting service temporarily unavailable",
            )


async def rate_limit_login(request: Request) -> None:
    expr = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
    client_ip = get_client_ip(request)
    key = f"ratelimit:login:ip:{client_ip}"
    await _execute_rate_limit(key, expr, "login")


async def rate_limit_register(request: Request) -> None:
    expr = os.getenv("RATE_LIMIT_REGISTER", "3/hour")
    client_ip = get_client_ip(request)
    key = f"ratelimit:register:ip:{client_ip}"
    await _execute_rate_limit(key, expr, "register")


async def rate_limit_read(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> None:
    expr = os.getenv("RATE_LIMIT_READ", "120/minute")
    key = f"ratelimit:read:u{current_user.id}"
    await _execute_rate_limit(key, expr, "read")


async def rate_limit_write(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> None:
    expr = os.getenv("RATE_LIMIT_WRITE", "30/minute")
    key = f"ratelimit:write:u{current_user.id}"
    await _execute_rate_limit(key, expr, "write")
