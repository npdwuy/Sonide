@echo off
cd /d "%~dp0"
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw note_sidebar.py
    exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw note_sidebar.py
    exit /b
)
where python >nul 2>nul
if %errorlevel%==0 (
    start "" python note_sidebar.py
    exit /b
)
echo Khong tim thay Python trong PATH.
pause
