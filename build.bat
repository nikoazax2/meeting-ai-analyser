@echo off
title Meeting AI Analyser - Build
echo ============================================
echo   Meeting AI Analyser - Build .exe + Setup
echo ============================================
echo.

cd /d "%~dp0"

echo [1/4] Generation de l'icone...
python build_icon.py
if errorlevel 1 (
    echo ERREUR: generation icone echouee
    pause
    exit /b 1
)

echo.
echo [2/4] Nettoyage du build precedent...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo.
echo [3/4] Build PyInstaller (cela peut prendre quelques minutes)...
python -m PyInstaller build.spec --noconfirm
if errorlevel 1 (
    echo ERREUR: build PyInstaller echoue
    pause
    exit /b 1
)

echo.
echo [4/4] Build installeur Inno Setup...

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
    echo [!] Inno Setup non trouve. Installeur non genere.
    echo     Telecharge https://jrsoftware.org/isdl.php puis relance build.bat
    echo     L'exe seul est dispo dans dist\MeetingAIAnalyser.exe
    pause
    exit /b 0
)

for /f "delims=" %%v in ('python -c "from version import __version__; print(__version__)"') do set "APPVER=%%v"

"%ISCC%" /DAppVersion=%APPVER% installer.iss
if errorlevel 1 (
    echo ERREUR: build installeur echoue
    pause
    exit /b 1
)

echo.
echo ============================================
echo   BUILD TERMINE
echo   Executable: dist\MeetingAIAnalyser.exe
echo   Installeur: dist\MeetingAIAnalyser-Setup.exe
echo ============================================
echo.

dir dist\MeetingAIAnalyser*.exe

pause
