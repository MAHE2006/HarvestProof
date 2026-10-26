@echo off
cd /d "%~dp0"

echo Starting HarvestProof...

call "..\.venv\Scripts\activate.bat"

if errorlevel 1 (
    echo ERROR: Could not activate the virtual environment.
    pause
    exit /b 1
)

python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

pause