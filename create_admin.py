"""최초 관리자 계정 생성 스크립트.

사용법:
    python create_admin.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import get_conn, init_db
from auth import hash_password

init_db()

print("=== 관리자 계정 생성 ===")
username = input("관리자 아이디: ").strip()
password = input("관리자 비밀번호: ").strip()

if len(username) < 3:
    print("아이디는 3자 이상이어야 합니다.")
    sys.exit(1)
if len(password) < 6:
    print("비밀번호는 6자 이상이어야 합니다.")
    sys.exit(1)

with get_conn() as conn:
    exists = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if exists:
        conn.execute(
            "UPDATE users SET is_admin = 1, is_approved = 1 WHERE username = ?",
            (username,),
        )
        print(f"기존 계정 '{username}'에 관리자 권한을 부여했습니다.")
    else:
        conn.execute(
            "INSERT INTO users (username, password_hash, is_approved, is_admin) VALUES (?, ?, 1, 1)",
            (username, hash_password(password)),
        )
        print(f"관리자 계정 '{username}'이 생성되었습니다.")
    conn.commit()
