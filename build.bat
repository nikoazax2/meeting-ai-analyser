@echo off
title Meeting AI Analyser - Build
echo.
echo ============================================
echo   Meeting AI Analyser - Build .exe
echo ============================================
echo.

cd /d "%~dp0"

echo [1/5] Installation des dependances...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERREUR: installation des dependances echouee
    pause
    exit /b 1
)

echo.
echo [2/5] Installation des outils de build...
pip install pyinstaller Pillow
if errorlevel 1 (
    echo ERREUR: installation pyinstaller/Pillow echouee
    pause
    exit /b 1
)

echo.
echo [3/5] Generation de l'icone...
python build_icon.py
if errorlevel 1 (
    echo ERREUR: generation icone echouee
    pause
    exit /b 1
)

echo.
echo [4/5] Nettoyage du build precedent...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo.
echo [5/5] Build PyInstaller (cela peut prendre quelques minutes)...
pyinstaller build.spec --noconfirm
if errorlevel 1 (
    echo ERREUR: build echoue
    pause
    exit /b 1
)

echo.
echo ============================================
echo   BUILD TERMINE
echo   Executable: dist\MeetingAIAnalyser.exe
echo ============================================
echo.

dir dist\MeetingAIAnalyser.exe

pause
