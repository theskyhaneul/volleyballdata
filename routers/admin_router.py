"""관리자 전용 API: 사용자 목록 조회, 승인/거부/삭제."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, HTTPException
from typing import Annotated

from auth import decode_token
from database import get_conn

router = APIRouter(prefix="/admin", tags=["admin"])

COOKIE_NAME = "access_token"


def _require_admin(token: str | None) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    payload = decode_token(token)
    if not payload or not payload.get("admin"):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return payload


@router.get("/users")
def list_users(access_token: Annotated[str | None, Cookie()] = None):
    _require_admin(access_token)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, username, is_approved, is_admin, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/users/{user_id}/approve")
def approve_user(user_id: int, access_token: Annotated[str | None, Cookie()] = None):
    _require_admin(access_token)
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_approved = 1 WHERE id = ?", (user_id,))
        conn.commit()
    return {"message": "승인 완료"}


@router.post("/users/{user_id}/reject")
def reject_user(user_id: int, access_token: Annotated[str | None, Cookie()] = None):
    _require_admin(access_token)
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_approved = 0 WHERE id = ?", (user_id,))
        conn.commit()
    return {"message": "승인 취소"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, access_token: Annotated[str | None, Cookie()] = None):
    _require_admin(access_token)
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    return {"message": "삭제 완료"}
