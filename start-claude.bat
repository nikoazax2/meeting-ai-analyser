@echo off
cd /d "%~dp0"
echo Demarrage de Claude dans %CD%...
claude --dangerously-skip-permissions %*
if %errorlevel% neq 0 (
    echo.
    echo Erreur code: %errorlevel%
    pause
)
pause
