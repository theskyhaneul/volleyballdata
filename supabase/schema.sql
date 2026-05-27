-- 배구 데이터 변환기 — users 테이블
-- Supabase 대시보드 → SQL Editor → New query → 붙여넣기 → Run

CREATE TABLE IF NOT EXISTS public.users (
    id            BIGSERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_approved   BOOLEAN NOT NULL DEFAULT FALSE,
    is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON public.users (username);

-- 확인용 (실행 후 Table Editor에서 users 가 보이면 성공)
-- SELECT * FROM public.users;
