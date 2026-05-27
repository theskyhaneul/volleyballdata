"""관리자 전용 API: 사용자 목록 조회, 승인/거부/삭제."""

from __future__ import annotations

from fastapi import APIRouter, Request

from database import get_conn
from deps import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(request: Request):
    require_admin(request)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, username, is_approved, is_admin, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/users/{user_id}/approve")
def approve_user(user_id: int, request: Request):
    require_admin(request)
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_approved = 1 WHERE id = ?", (user_id,))
        conn.commit()
    return {"message": "승인 완료"}


@router.post("/users/{user_id}/reject")
def reject_user(user_id: int, request: Request):
    require_admin(request)
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_approved = 0 WHERE id = ?", (user_id,))
        conn.commit()
    return {"message": "승인 취소"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, request: Request):
    require_admin(request)
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    return {"message": "삭제 완료"}
