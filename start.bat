@echo off
echo ==========================================
echo   ReClip Antigravity Edition - Starting...
echo ==========================================
echo Checking dependencies...
python -m pip install -r requirements.txt
echo.
echo Starting server at http://localhost:8899
echo.
python app.py
pause
