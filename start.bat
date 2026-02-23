@echo off
title Meeting AI Analyser - Neoteem
echo.
echo ============================================
echo   Meeting AI Analyser - Neoteem
echo ============================================
echo.
echo Capture audio systeme + transcription + analyse IA
echo Ctrl+C pour arreter
echo.
python "%~dp0live_transcribe.py" %*
pause
