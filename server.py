"""
Meeting AI Analyser - Local web server
Live transcription interface + AI meeting analysis
Runs on http://localhost:5555
"""
import json
import os
import shutil
import threading
import time

import subprocess
import sys

import psutil
from flask import Flask, Response, request, send_from_directory

from paths import TRANSCRIPTION_FILE, ANALYSIS_FILE, BUNDLE_DIR, APP_DIR

TRANSCRIBE_SCRIPT = os.path.join(APP_DIR, "live_transcribe.py")

app = Flask(__name__, static_folder=BUNDLE_DIR)

# Global status (injected by main.py)
app_status = {"ready": False, "message": "Starting...", "language": "en", "model": "small"}

# Heartbeat: browser pings every 5s, if no ping for 15s -> shutdown
_last_heartbeat = time.time()
_stop_event_ref = None

# SSE change notification: set by transcribe/analyst when files are updated
content_changed = threading.Event()


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
    return send_from_directory(BUNDLE_DIR, "index.html")


@app.route("/images/<path:filename>")
def serve_images(filename):
    return send_from_directory(os.path.join(BUNDLE_DIR, "images"), filename)


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
    """Clear transcription and analysis files completely"""
    with open(TRANSCRIPTION_FILE, "w", encoding="utf-8") as f:
        f.write("")
    with open(ANALYSIS_FILE, "w", encoding="utf-8") as f:
        f.write("")
    # Reset analyst memory so next analysis isn't skipped
    try:
        import analyst
        analyst.reset_content()
    except Exception:
        pass
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
        s = analyst.get_status_snapshot()
        now = time.time()
        remaining = max(0, s["next_run"] - now) if s["next_run"] > 0 else 0
        progress = 1 - (remaining / s["interval"]) if s["interval"] > 0 and not s["paused"] else 0
        return {"state": s["state"], "remaining": round(remaining), "progress": round(progress, 3), "interval": s["interval"], "paused": s["paused"], "conversation_id": s.get("conversation_id", "")}
    except Exception:
        return {"state": "unknown", "remaining": 0, "progress": 0, "interval": 60, "paused": False}


@app.route("/api/conversations")
def list_conversations():
    """List available Claude conversation sessions from all projects"""
    try:
        import analyst
        data = analyst.list_conversations()
        return data
    except Exception as e:
        return {"conversations": [], "base_path": None, "error": str(e)}


@app.route("/api/analyst/conversation", methods=["POST"])
def analyst_conversation():
    """Set or clear the Claude conversation ID for --resume"""
    try:
        import analyst
        data = request.get_json() or {}
        cid = data.get("conversation_id", "")
        analyst.set_conversation_id(cid)
        return {"conversation_id": cid}
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/api/analyst/toggle", methods=["POST"])
def analyst_toggle():
    """Pause or resume automatic analysis"""
    try:
        import analyst
        new_paused = not analyst.analyst_status["paused"]
        analyst.set_paused(new_paused)
        return {"paused": new_paused}
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/api/analyst/trigger", methods=["POST"])
def analyst_trigger():
    """Trigger an immediate analysis"""
    try:
        import analyst
        if analyst.analyst_status["state"] == "analyzing":
            return {"status": "already_analyzing"}
        analyst.trigger_now()
        return {"status": "triggered"}
    except Exception as e:
        return {"error": str(e)}, 500


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


@app.route("/api/license")
def get_license():
    import license as lic_mod
    access = lic_mod.check_access()
    return access


@app.route("/api/license/activate", methods=["POST"])
def activate_license():
    import license as lic_mod
    data = request.get_json() or {}
    key = data.get("key", "").strip()
    if not key:
        return {"success": False, "message": "No license key provided"}, 400
    result = lic_mod.activate_license(key)
    if result["success"]:
        access = lic_mod.check_access()
        app_status["access_mode"] = access["mode"]
        app_status["licensed"] = True
        app_status["license_info"] = access.get("license_info")
        app_status["trial_days_left"] = access.get("days_left", 0)
        _start_analyst_if_needed()
    return result


@app.route("/api/trial/start", methods=["POST"])
def start_trial_route():
    import license as lic_mod
    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    if not email:
        return {"success": False, "message": "Email required"}, 400
    result = lic_mod.start_trial(email)
    if result.get("success"):
        access = lic_mod.check_access()
        app_status["access_mode"] = access["mode"]
        app_status["trial_days_left"] = access.get("days_left", 0)
        _start_analyst_if_needed()
    return result


@app.route("/api/license/deactivate", methods=["POST"])
def deactivate_license():
    import license as lic_mod
    result = lic_mod.deactivate_license()
    if result["success"]:
        access = lic_mod.check_access()
        app_status["access_mode"] = access["mode"]
        app_status["licensed"] = False
        app_status["license_info"] = None
        app_status["trial_days_left"] = access.get("days_left", 0)
    return result


@app.route("/api/update")
def get_update():
    return {
        "update_available": app_status.get("update_available", False),
        "update_info": app_status.get("update_info"),
    }


def _start_analyst_if_needed():
    """Start analyst thread if not already running (after mid-session activation)"""
    if app_status.get("analysis"):
        return
    try:
        import analyst
        import traceback

        def _run():
            try:
                analyst.start(_stop_event_ref)
            except Exception:
                pass

        t = threading.Thread(target=_run, name="analyst", daemon=True)
        t.start()
        app_status["analysis"] = True
    except Exception:
        pass


@app.route("/api/claude-check")
def claude_check():
    """Check if Claude Code CLI is installed"""
    for path in [
        os.path.expanduser("~/AppData/Roaming/npm/claude.cmd"),
        "C:/Program Files/nodejs/claude.cmd",
    ]:
        if os.path.exists(path):
            return {"found": True, "path": path}
    which = shutil.which("claude")
    if which:
        return {"found": True, "path": which}
    return {"found": False, "path": None}


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
        try:
            while True:
                content_changed.wait(timeout=5)
                content_changed.clear()

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

                # Heartbeat to detect broken connections
                yield ": heartbeat\n\n"
        except GeneratorExit:
            pass

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
