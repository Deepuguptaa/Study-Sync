@echo off
echo ========================================
echo   SyncSphere - Starting Server...
echo ========================================
echo.
echo [1] Installing new dependencies...
pip install pymongo PyJWT

echo.
echo [2] Starting Flask Server...
python app.py
pause
