@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
 py -3 app.py
) else (
 python app.py
)
if errorlevel 1 (
 echo Install Python 3.10 or newer and enable Add Python to PATH. Then try again.
 pause
)
