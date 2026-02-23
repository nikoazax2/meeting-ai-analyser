"""
Meeting AI Analyser - Local web server
Live transcription interface + AI meeting analysis
Runs on http://localhost:5555
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

# Global status (injected by main.py)
app_status = {"ready": False, "message": "Starting...", "language": "en", "model": "small"}

# Heartbeat: browser pings every 5s, if no ping for 15s -> shutdown
_last_heartbeat = time.time()
_stop_event_ref = None


def _heartbeat_watcher():
    """Thread that monitors heartbeat and triggers shutdown if browser is closed"""
    while True:
        time.sleep(5)
        if time.time() - _last_heartbeat > 15 and _stop_event_ref:
            print("[SERVER] Browser disconnected, shutting down...")
            _stop_event_ref.set()
            time.sleep(1)
            os._exit(0)


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


@app.route("/images/<path:filename>")
def serve_images(filename):
    return send_from_directory(os.path.join(SCRIPT_DIR, "images"), filename)


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
    """List audio input devices (microphones)"""
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
        # Detect active mic (shared variable in thread mode, or cmdline in process mode)
        active_mic = None
        try:
            import live_transcribe
            active_mic = live_transcribe.active_mic_id
        except Exception:
            pass
        if active_mic is None:
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
    """Restart live_transcribe.py with a new mic device"""
    data = request.get_json() or {}
    mic_id = data.get("micDevice")
    # Kill current live_transcribe process
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
    # Relaunch with new mic
    cmd = [sys.executable, TRANSCRIBE_SCRIPT]
    if mic_id is not None:
        cmd += ["--mic-device", str(mic_id)]
    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
    return {"status": "restarted", "micDevice": mic_id, "killed": killed}


@app.route("/api/reset", methods=["POST"])
def reset():
    """Clear transcription and analysis files"""
    import datetime
    with open(TRANSCRIPTION_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== Live Transcription - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
    with open(ANALYSIS_FILE, "w", encoding="utf-8") as f:
        f.write("")
    return {"status": "reset"}


@app.route("/api/stop")
def stop():
    """Stop all Meeting AI Analyser Python processes"""
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
    # Kill self after delay
    threading.Timer(1, lambda: os._exit(0)).start()
    return {"status": "stopped"}


@app.route("/api/language", methods=["POST"])
def set_language():
    data = request.get_json() or {}
    lang = data.get("language")
    if not lang:
        return {"error": "missing language"}, 400
    try:
        import live_transcribe
        live_transcribe.active_language = lang
    except Exception:
        pass
    app_status["language"] = lang
    return {"status": "ok", "language": lang}


@app.route("/api/analyst")
def analyst_info():
    try:
        import analyst
        s = analyst.analyst_status
        now = time.time()
        remaining = max(0, s["next_run"] - now)
        progress = 1 - (remaining / s["interval"]) if s["interval"] > 0 else 1
        return {"state": s["state"], "remaining": round(remaining), "progress": round(progress, 3), "interval": s["interval"]}
    except Exception:
        return {"state": "unknown", "remaining": 0, "progress": 0, "interval": 60}


@app.route("/api/levels")
def levels():
    try:
        import live_transcribe
        return live_transcribe.audio_levels
    except Exception:
        return {"loopback": 0.0, "mic": 0.0}


@app.route("/api/status")
def status():
    return app_status


@app.route("/api/heartbeat")
def heartbeat():
    global _last_heartbeat
    _last_heartbeat = time.time()
    return {"status": "ok"}


@app.route("/api/stream")
def stream():
    """SSE endpoint for real-time streaming"""
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
    """Entry point for module mode (called from main.py as thread)"""
    global _stop_event_ref, _last_heartbeat
    _stop_event_ref = stop_event
    _last_heartbeat = time.time()
    # Start heartbeat watcher
    t = threading.Thread(target=_heartbeat_watcher, daemon=True)
    t.start()
    print(f"[SERVER] Meeting AI Analyser available at http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    app_status["ready"] = True
    app_status["message"] = "Ready"
    print(f"[SERVER] Meeting AI Analyser available at http://localhost:5555")
    app.run(host="127.0.0.1", port=5555, debug=False, use_reloader=False)
