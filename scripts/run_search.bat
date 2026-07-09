@echo off
cd /d C:\Users\ParkEunJin\admeta-hub\backend
echo ============================================================
echo   admeta search server
echo.
echo   Wait for:  Uvicorn running on http://127.0.0.1:8000
echo   Then open in browser:  http://localhost:8000
echo.
echo   Stop with Ctrl+C or close this window.
echo ============================================================
echo.
py -3 -m uvicorn admeta.api.app:app --port 8000
echo.
echo [Server stopped. If there is a red error above, copy it to me.]
pause
