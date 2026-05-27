"""공통 의존성."""

from __future__ import annotations

import os

from fastapi import HTTPException, Request, Response

from auth import decode_token

COOKIE_NAME = "access_token"


def is_production() -> bool:
    """Render 등 HTTPS 배포 환경 여부."""
    return bool(os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_URL"))


def set_auth_cookie(response: Response, token: str) -> None:
    """HTTPS 배포 시 secure 쿠키 필수 (Render 로그인 유지)."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=is_production(),
        max_age=60 * 60 * 8,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        samesite="lax",
        secure=is_production(),
    )


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
