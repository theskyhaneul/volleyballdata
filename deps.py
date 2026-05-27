"""공통 의존성."""

from __future__ import annotations

from fastapi import HTTPException, Request

from auth import decode_token

COOKIE_NAME = "access_token"


def get_token(request: Request) -> str | None:
    return request.cookies.get(COOKIE_NAME)


def get_current_user(request: Request) -> dict | None:
    token = get_token(request)
    if not token:
        return None
    return decode_token(token)


def require_login(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return user


def require_admin(request: Request) -> dict:
    user = require_login(request)
    if not user.get("admin"):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return user
