"""Data Volley → Dartfish 웹 변환기 (FastAPI)."""

from __future__ import annotations

import csv
import io
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import Cookie, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from typing import Annotated

from auth import decode_token
from database import init_db
from routers.auth_router import router as auth_router
from routers.admin_router import router as admin_router

from src.combination_parser import parse_attack_combinations
from src.dvw_parser import parse_dvw
from src.game_info_parser import parse_game_info_sections
from src.players_parser import parse_away_players, parse_home_players
from src.scout_parser import (
    compute_positions_from_first_row,
    compute_uniform_periods,
    parse_scout_rows,
)
from src.setter_parser import parse_setter_calls

# ── 앱 초기화 ─────────────────────────────────────
app = FastAPI(title="배구 데이터 변환기")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth_router)
app.include_router(admin_router)

init_db()

COOKIE_NAME = "access_token"


# ── 인증 헬퍼 ─────────────────────────────────────

def _get_current_user(token: str | None) -> dict | None:
    if not token:
        return None
    return decode_token(token)


# ── 페이지 라우트 ──────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    access_token: Annotated[str | None, Cookie()] = None,
):
    if _get_current_user(access_token):
        return RedirectResponse("/")
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    access_token: Annotated[str | None, Cookie()] = None,
):
    user = _get_current_user(access_token)
    if not user:
        return RedirectResponse("/login")
    if not user.get("admin"):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    access_token: Annotated[str | None, Cookie()] = None,
):
    if not _get_current_user(access_token):
        return RedirectResponse("/login")
    return templates.TemplateResponse("index.html", {"request": request})


# ── API: 현재 로그인 정보 ───────────────────────────

@app.post("/api/setup-admin")
async def setup_admin(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    setup_key: Annotated[str, Form()],
):
    """최초 관리자 계정 1회 생성용. SETUP_KEY 환경변수가 설정된 경우에만 동작."""
    expected = os.environ.get("SETUP_KEY", "")
    if not expected:
        raise HTTPException(status_code=403, detail="SETUP_KEY 환경변수가 설정되지 않았습니다.")
    if setup_key != expected:
        raise HTTPException(status_code=403, detail="설정 키가 올바르지 않습니다.")

    from auth import hash_password
    from database import get_conn

    username = username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="아이디는 3자 이상이어야 합니다.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="비밀번호는 6자 이상이어야 합니다.")

    with get_conn() as conn:
        exists = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if exists:
            conn.execute(
                "UPDATE users SET is_admin = 1, is_approved = 1 WHERE username = ?", (username,)
            )
            msg = f"'{username}' 계정에 관리자 권한을 부여했습니다."
        else:
            conn.execute(
                "INSERT INTO users (username, password_hash, is_approved, is_admin) VALUES (?, ?, 1, 1)",
                (username, hash_password(password)),
            )
            msg = f"관리자 계정 '{username}'이 생성되었습니다."
        conn.commit()

    return {"message": msg}


@app.get("/api/me")
async def me(access_token: Annotated[str | None, Cookie()] = None):
    user = _get_current_user(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return {"username": user["sub"], "is_admin": user.get("admin", False)}


# ── 공통 유틸 ─────────────────────────────────────

def _require_login(token: str | None) -> dict:
    user = _get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return user


def _dvw_from_upload(upload: UploadFile):
    suffix = Path(upload.filename or "file.dvw").suffix or ".dvw"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(upload.file.read())
        tmp_path = Path(tmp.name)
    try:
        return parse_dvw(tmp_path), upload.filename or "file.dvw"
    finally:
        tmp_path.unlink(missing_ok=True)


# ── API: DVW 파싱 ─────────────────────────────────

@app.post("/api/parse")
async def parse_file(
    file: UploadFile = File(...),
    access_token: Annotated[str | None, Cookie()] = None,
):
    _require_login(access_token)
    try:
        dvw, filename = _dvw_from_upload(file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"파일 파싱 오류: {exc}")

    # 게임정보
    game_info = []
    for section in parse_game_info_sections(dvw):
        block: dict = {"name": section.name, "title": section.title}
        if section.table_headers and section.table_rows:
            block["type"] = "table"
            block["headers"] = section.table_headers
            block["rows"] = section.table_rows
        else:
            block["type"] = "keyvalue"
            block["rows"] = [{"key": r.key, "value": r.value} for r in section.rows]
        game_info.append(block)

    # 게임데이터
    scout_rows = parse_scout_rows(dvw)
    game_data = [
        {
            "no": r.number,
            "team": r.team,
            "player": r.player_name,
            "skill": r.basic_skill,
            "shot": r.shot_type,
            "result": r.result,
            "combo": r.combo,
            "time": r.time or "-",
            "set": r.set_number or "-",
        }
        for r in scout_rows
    ]

    # 선수/세트점수
    home = parse_home_players(dvw)
    away = parse_away_players(dvw)

    def team_to_dict(t):
        return {
            "code": t.code,
            "name": t.name,
            "label": t.label,
            "set_count": t.set_count,
            "players": [
                {
                    "number": p.number,
                    "name": p.display_name,
                    "player_id": p.player_id,
                    "set_scores": p.set_scores,
                    "total": p.total,
                }
                for p in t.players
            ],
        }

    combinations = [
        {"code": r.code, "field": r.field, "description": r.description, "other": r.other}
        for r in parse_attack_combinations(dvw)
    ]
    setter_calls = [
        {"code": r.code, "description": r.description, "other": r.other}
        for r in parse_setter_calls(dvw)
    ]

    return {
        "filename": filename,
        "game_info": game_info,
        "game_data": game_data,
        "players": {"home": team_to_dict(home), "away": team_to_dict(away)},
        "combinations": combinations,
        "setter_calls": setter_calls,
    }


# ── API: CSV 다운로드 ──────────────────────────────

@app.post("/api/export-csv")
async def export_csv(
    file: UploadFile = File(...),
    base_length: int = Form(0),
    access_token: Annotated[str | None, Cookie()] = None,
):
    _require_login(access_token)
    try:
        dvw, filename = _dvw_from_upload(file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"파일 파싱 오류: {exc}")

    scout_rows = parse_scout_rows(dvw)
    applied = base_length > 0
    positions = compute_positions_from_first_row(scout_rows) if applied else []
    periods = compute_uniform_periods(len(scout_rows), base_length) if applied else []

    headers = ["No"]
    if applied:
        headers.extend(["위치", "기간"])
    headers.extend(["팀", "선수이름"])
    if applied:
        headers.append("이름")
    headers.extend(["기본기술", "타구유형", "결과", "콤비", "세트"])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for i, row in enumerate(scout_rows):
        values: list = [row.number]
        if applied:
            values.extend([positions[i], periods[i]])
        values.extend([row.team, row.player_name])
        if applied:
            values.append(row.player_name)
        values.extend([row.basic_skill, row.shot_type, row.result, row.combo, row.set_number or "-"])
        writer.writerow(values)

    output.seek(0)
    csv_filename = f"{Path(filename).stem}_게임데이터.csv"
    encoded_name = quote(csv_filename)
    content_disposition = (
        f'attachment; filename="game_data.csv"; filename*=UTF-8\'\'{encoded_name}'
    )

    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": content_disposition},
    )
