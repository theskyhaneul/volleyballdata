"""회원가입 / 로그인 / 로그아웃 API."""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Response, Cookie
from typing import Annotated

from auth import create_access_token, hash_password, verify_password
from database import get_conn
from deps import clear_auth_cookie, set_auth_cookie

router = APIRouter(prefix="/auth", tags=["auth"])

# 쿠키 이름
COOKIE_NAME = "access_token"


@router.post("/register")
def register(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    password2: Annotated[str, Form()],
):
    username = username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="아이디는 3자 이상이어야 합니다.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="비밀번호는 6자 이상이어야 합니다.")
    if password != password2:
        raise HTTPException(status_code=400, detail="비밀번호가 일치하지 않습니다.")

    with get_conn() as conn:
        exists = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if exists:
            raise HTTPException(status_code=400, detail="이미 사용 중인 아이디입니다.")

        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hash_password(password)),
        )
        conn.commit()

    return {"message": "가입 완료. 관리자 승인 후 로그인이 가능합니다."}


@router.post("/login")
def login(
    response: Response,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()

    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    if not row["is_approved"]:
        raise HTTPException(status_code=403, detail="관리자 승인 대기 중입니다. 승인 후 로그인해 주세요.")

    token = create_access_token(username=row["username"], is_admin=bool(row["is_admin"]))
    set_auth_cookie(response, token)
    return {"message": "로그인 성공", "is_admin": bool(row["is_admin"])}


@router.post("/logout")
def logout(response: Response):
    clear_auth_cookie(response)
    return {"message": "로그아웃 완료"}
