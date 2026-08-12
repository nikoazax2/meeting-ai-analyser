@echo off
title Meeting AI Analyser - Build
echo ============================================
echo   Meeting AI Analyser - Build .exe + Setup
echo ============================================
echo.

cd /d "%~dp0"

echo [1/5] Generation de l'icone...
python build_icon.py
if errorlevel 1 (
    echo ERREUR: generation icone echouee
    pause
    exit /b 1
)

echo.
echo [2/5] Nettoyage du build precedent...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo.
echo [3/5] Build PyInstaller (cela peut prendre quelques minutes)...
python -m PyInstaller build.spec --noconfirm
if errorlevel 1 (
    echo ERREUR: build PyInstaller echoue
    pause
    exit /b 1
)

echo.
echo [4/5] Signature du code...
rem Definis SIGN_TOOL dans ton environnement pour activer la signature.
rem Exemple (Certum SimplySign) :
rem   set SIGN_TOOL=signtool.exe sign /fd SHA256 /tr http://time.certum.pl /td SHA256 /n "TON NOM" $f
rem Sans SIGN_TOOL le build reste possible, mais Windows affichera
rem "Editeur inconnu" a chaque telechargement. Voir SIGNING.md.

if defined SIGN_TOOL (
    rem Inno remplace $f par le fichier a signer ; ici on substitue a la volee.
    rem Substitution + call sur une seule ligne : une variable posee dans un bloc
    rem ne serait pas relue dans le meme bloc sans delayed expansion.
    echo     Signature de dist\MeetingAIAnalyser.exe...
    call %SIGN_TOOL:$f=dist\MeetingAIAnalyser.exe%
    if errorlevel 1 (
        echo ERREUR: signature de l'exe echouee
        pause
        exit /b 1
    )
) else (
    echo     [!] SIGN_TOOL non defini - build NON SIGNE.
    echo         Windows SmartScreen affichera un avertissement aux telechargeurs.
)

echo.
echo [5/5] Build installeur Inno Setup...

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
rem winget installe Inno Setup par utilisateur, pas dans Program Files
if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
    echo [!] Inno Setup non trouve. Installeur non genere.
    echo     Telecharge https://jrsoftware.org/isdl.php puis relance build.bat
    echo     L'exe seul est dispo dans dist\MeetingAIAnalyser.exe
    pause
    exit /b 0
)

for /f "delims=" %%v in ('python -c "from version import __version__; print(__version__)"') do set "APPVER=%%v"

if defined SIGN_TOOL (
    "%ISCC%" /DAppVersion=%APPVER% /DSign "/Smeetingai=%SIGN_TOOL%" installer.iss
) else (
    "%ISCC%" /DAppVersion=%APPVER% installer.iss
)
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
