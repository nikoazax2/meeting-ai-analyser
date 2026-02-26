"""
Centralized path resolution for Meeting AI Analyser.
Handles PyInstaller one-file mode vs normal Python execution.
"""
import os
import sys


def _get_base_dir():
    """Directory where the .exe lives (or the script dir in dev mode)"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _get_bundle_dir():
    """Directory where bundled resources are extracted (PyInstaller temp dir)"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


# App dir: where output files go (next to the .exe, or script dir in dev)
APP_DIR = _get_base_dir()

# Bundle dir: where embedded resources live (index.html, images)
BUNDLE_DIR = _get_bundle_dir()

# Output files (written next to the exe)
TRANSCRIPTION_FILE = os.path.join(APP_DIR, "transcription_live.txt")
TRANSCRIPTION_LATEST = os.path.join(APP_DIR, "transcription_latest.txt")
ANALYSIS_FILE = os.path.join(APP_DIR, "analyse_reunion.md")
LOG_FILE = os.path.join(APP_DIR, "analyst_debug.log")
AUDIO_TEMP = os.path.join(APP_DIR, "temp_segment.wav")
TEMP_PROMPT = os.path.join(APP_DIR, "temp_prompt.txt")
