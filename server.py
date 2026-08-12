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

import psutil
from flask import Flask, Response, request, send_from_directory

import telemetry
from paths import TRANSCRIPTION_FILE, ANALYSIS_FILE, BUNDLE_DIR

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
        if time.time() - _last_heartbeat > 30 and _stop_event_ref:
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
    """Signal the transcription thread to reopen its audio streams,
    optionally switching to a different microphone."""
    data = request.get_json() or {}
    mic_id = data.get("micDevice")
    try:
        import live_transcribe
        live_transcribe.request_restart(mic_id)
        return {"status": "restarted", "micDevice": mic_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}, 500


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
        return {
            "state": s["state"], "remaining": round(remaining), "progress": round(progress, 3),
            "interval": s["interval"], "paused": s["paused"],
            "conversation_id": s.get("conversation_id", ""),
            "error_code": s.get("error_code", ""),
            "error_message": s.get("error_message", ""),
            "error_action": s.get("error_action", ""),
        }
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
        telemetry.track("license_activated", once=False)
    return result


@app.route("/api/trial/start", methods=["POST"])
def start_trial_route():
    import license as lic_mod
    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    result = lic_mod.start_trial(email, source=(data.get("source") or "").strip())
    if result.get("success"):
        access = lic_mod.check_access()
        app_status["access_mode"] = access["mode"]
        app_status["trial_days_left"] = access.get("days_left", 0)
        _start_analyst_if_needed()
        telemetry.track("trial_started", once=False)
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


@app.route("/api/update/install", methods=["POST"])
def install_update():
    """Download the Setup installer and run it silently. The app exits so
    Inno Setup can overwrite the exe; the installer relaunches the app when done."""
    import tempfile
    import urllib.request

    info = app_status.get("update_info") or {}
    url = info.get("download_url", "")
    if not url or not url.lower().endswith(".exe"):
        return {"success": False, "error": "No installer asset available"}, 400
    if "setup" not in url.lower():
        return {"success": False, "error": "Latest release has no Setup installer (only a portable exe). Please download manually."}, 400

    try:
        tmp_dir = tempfile.gettempdir()
        setup_path = os.path.join(tmp_dir, "MeetingAIAnalyser-Setup.exe")
        req = urllib.request.Request(url, headers={"User-Agent": "MeetingAIAnalyser"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(setup_path, "wb") as f:
            shutil.copyfileobj(resp, f)

        # Wrapper batch: wait for our process to exit, then run the installer
        wrapper = os.path.join(tmp_dir, "MeetingAIAnalyser-Update.bat")
        with open(wrapper, "w", encoding="ascii") as f:
            f.write(
                "@echo off\r\n"
                "timeout /t 2 /nobreak >nul\r\n"
                f'"{setup_path}" /SILENT /SUPPRESSMSGBOXES /NORESTART\r\n'
            )
        subprocess.Popen(
            ["cmd.exe", "/c", wrapper],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            close_fds=True,
        )

        # Exit the app so Inno can replace the exe
        threading.Timer(1, lambda: os._exit(0)).start()
        return {"success": True, "message": "Installing update..."}
    except Exception as e:
        return {"success": False, "error": str(e)}, 500


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


@app.route("/api/settings", methods=["GET"])
def get_settings():
    """Return analysis settings. The API key is never returned in clear - only a masked preview."""
    import settings as settings_mod
    cfg = settings_mod.load()
    key = (cfg.get("api_key") or "").strip()
    preview = ""
    if key:
        preview = (key[:7] + "..." + key[-4:]) if len(key) > 14 else "set"
    return {
        "analysis_mode": cfg.get("analysis_mode", "cli"),
        "api_model": cfg.get("api_model", "claude-opus-4-8"),
        "api_key_set": bool(key),
        "api_key_preview": preview,
        "models": list(settings_mod.ALLOWED_MODELS),
        "telemetry": cfg.get("telemetry", True),
    }


@app.route("/api/settings", methods=["POST"])
def update_settings():
    """Update analysis settings. Only known keys are persisted; the API key is write-only."""
    import settings as settings_mod
    data = request.get_json() or {}
    updates = {}
    if data.get("analysis_mode") in ("cli", "api"):
        updates["analysis_mode"] = data["analysis_mode"]
    if data.get("api_model") in settings_mod.ALLOWED_MODELS:
        updates["api_model"] = data["api_model"]
    if data.get("clear_api_key"):
        updates["api_key"] = ""
    else:
        key = (data.get("api_key") or "").strip()
        if key:
            updates["api_key"] = key
    if isinstance(data.get("telemetry"), bool):
        updates["telemetry"] = data["telemetry"]
    cfg = settings_mod.save(updates)

    if (cfg.get("api_key") or "").strip() and cfg.get("analysis_mode") == "api":
        telemetry.track("claude_configured", {"mode": "api"})

    return {
        "status": "ok",
        "analysis_mode": cfg.get("analysis_mode"),
        "api_model": cfg.get("api_model"),
        "api_key_set": bool((cfg.get("api_key") or "").strip()),
        "telemetry": cfg.get("telemetry", True),
    }


@app.route("/api/track", methods=["POST"])
def track_event():
    """Let the UI report funnel events (buy clicked, expiry wall seen, ...)."""
    data = request.get_json() or {}
    event = (data.get("event") or "").strip()
    if event:
        telemetry.track(event, data.get("props") or {}, once=bool(data.get("once", True)))
    return {"ok": True}


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
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    app_status["ready"] = True
    app_status["message"] = "Ready"
    print(f"[SERVER] Meeting AI Analyser available at http://localhost:5555")
    app.run(host="127.0.0.1", port=5555, debug=False, use_reloader=False)
