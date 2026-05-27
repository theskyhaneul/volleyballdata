@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo [1] 패키지 설치 확인 중...
pip install -r requirements.txt -q

echo.
echo [2] 서버 시작 중...
echo     브라우저에서 http://localhost:8000 으로 접속하세요
echo     종료하려면 이 창에서 Ctrl+C 를 누르세요
echo.
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
