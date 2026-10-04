@echo off
cd /d "%~dp0"
echo GrantFiller AI Options
echo Finish any running grant job before switching.
echo.
echo 1. Faster - 3B model
echo 2. More detail - 7B model
echo.
choice /c 12 /n /m "Choose 1 or 2: "
if errorlevel 2 goto quality
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0upgrade-ai-windows.ps1" -Model "qwen2.5:3b-instruct"
goto done
:quality
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0upgrade-ai-windows.ps1" -Model "qwen2.5:7b-instruct"
:done
pause
