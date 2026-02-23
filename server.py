"""
Meeting AI Analyser - Serveur web local
Interface de transcription live + analyse IA des reunions
Lance sur http://localhost:5555
"""
import json
import os
import threading
import time

import subprocess
import sys

import psutil
from flask import Flask, Response, request, send_from_directory

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPTION_FILE = os.path.join(SCRIPT_DIR, "transcription_live.txt")
ANALYSIS_FILE = os.path.join(SCRIPT_DIR, "analyse_reunion.md")
TRANSCRIBE_SCRIPT = os.path.join(SCRIPT_DIR, "live_transcribe.py")

app = Flask(__name__, static_folder=SCRIPT_DIR)


def read_file_safe(filepath):
    if not os.path.exists(filepath):
        return ""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


@app.route("/")
def index():
    return send_from_directory(SCRIPT_DIR, "index.html")


@app.route("/api/transcription")
def get_transcription():
    content = read_file_safe(TRANSCRIPTION_FILE)
    mtime = os.path.getmtime(TRANSCRIPTION_FILE) if os.path.exists(TRANSCRIPTION_FILE) else 0
    return {"content": content, "mtime": mtime}


@app.route("/api/analysis")
def get_analysis():
    content = read_file_safe(ANALYSIS_FILE)
    mtime = os.path.getmtime(ANALYSIS_FILE) if os.path.exists(ANALYSIS_FILE) else 0
    return {"content": content, "mtime": mtime}


@app.route("/api/devices")
def get_devices():
    """Liste les peripheriques audio d'entree (micros)"""
    try:
        import pyaudiowpatch as pyaudio
        p = pyaudio.PyAudio()
        devices = []
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            if dev["maxInputChannels"] > 0 and not dev.get("isLoopbackDevice", False):
                devices.append({
                    "id": i,
                    "name": dev["name"],
                    "channels": dev["maxInputChannels"],
                    "sampleRate": int(dev["defaultSampleRate"]),
                })
        p.terminate()
        # Detecter le mic actif (lire la cmdline du process live_transcribe)
        active_mic = None
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = proc.info["cmdline"] or []
                cmd_str = " ".join(cmdline)
                if "live_transcribe" in cmd_str and "--mic-device" in cmd_str:
                    idx = cmdline.index("--mic-device")
                    active_mic = int(cmdline[idx + 1])
                    break
            except Exception:
                pass
        return {"devices": devices, "active": active_mic}
    except Exception as e:
        return {"devices": [], "active": None, "error": str(e)}


@app.route("/api/restart", methods=["POST"])
def restart_transcription():
    """Relance live_transcribe.py avec un nouveau mic device"""
    data = request.get_json() or {}
    mic_id = data.get("micDevice")
    # Tuer le process live_transcribe actuel
    my_pid = os.getpid()
    killed = False
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmd_str = " ".join(proc.info["cmdline"] or [])
            if "live_transcribe" in cmd_str and proc.info["pid"] != my_pid:
                proc.kill()
                killed = True
        except Exception:
            pass
    # Relancer avec le nouveau mic
    cmd = [sys.executable, TRANSCRIBE_SCRIPT]
    if mic_id is not None:
        cmd += ["--mic-device", str(mic_id)]
    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
    return {"status": "restarted", "micDevice": mic_id, "killed": killed}


@app.route("/api/reset", methods=["POST"])
def reset():
    """Vide les fichiers de transcription et d'analyse"""
    import datetime
    with open(TRANSCRIPTION_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== Transcription Live - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
    with open(ANALYSIS_FILE, "w", encoding="utf-8") as f:
        f.write("")
    return {"status": "reset"}


@app.route("/api/stop")
def stop():
    """Arrete tous les processus Python Meeting AI Analyser"""
    subprocess.run(
        'taskkill /F /FI "WINDOWTITLE eq Meeting*" >nul 2>&1',
        shell=True,
    )
    my_pid = os.getpid()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = " ".join(proc.info["cmdline"] or [])
            if ("meeting-ai-analyser" in cmdline or "live_transcribe" in cmdline or "analyst.py" in cmdline) and proc.info["pid"] != my_pid:
                proc.kill()
        except Exception:
            pass
    # Se tuer soi-meme apres un delai
    threading.Timer(1, lambda: os._exit(0)).start()
    return {"status": "stopped"}


@app.route("/api/stream")
def stream():
    """SSE endpoint pour le streaming en temps reel"""
    def generate():
        last_trans_mtime = 0
        last_analysis_mtime = 0
        while True:
            trans_mtime = os.path.getmtime(TRANSCRIPTION_FILE) if os.path.exists(TRANSCRIPTION_FILE) else 0
            analysis_mtime = os.path.getmtime(ANALYSIS_FILE) if os.path.exists(ANALYSIS_FILE) else 0

            if trans_mtime != last_trans_mtime:
                last_trans_mtime = trans_mtime
                content = read_file_safe(TRANSCRIPTION_FILE)
                data = json.dumps({"type": "transcription", "content": content})
                yield f"data: {data}\n\n"

            if analysis_mtime != last_analysis_mtime:
                last_analysis_mtime = analysis_mtime
                content = read_file_safe(ANALYSIS_FILE)
                data = json.dumps({"type": "analysis", "content": content})
                yield f"data: {data}\n\n"

            time.sleep(2)

    return Response(generate(), mimetype="text/event-stream")


def start(stop_event=None, port=5555):
    """Point d'entree pour le mode module (appele depuis main.py en thread)"""
    print(f"[SERVER] Meeting AI Analyser disponible sur http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    print(f"[SERVER] Meeting AI Analyser disponible sur http://localhost:5555")
    app.run(host="127.0.0.1", port=5555, debug=False, use_reloader=False)
