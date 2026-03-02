"""
Meeting AI Analyser - Single entry point
Launches transcription + Claude analysis + web server in threads
"""
import argparse
import multiprocessing
import os
import signal
import sys
import threading
import time
import traceback
import webbrowser

from paths import DATA_DIR
from version import __version__
import license as lic_mod
import updater

CRASH_LOG = os.path.join(DATA_DIR, "crash.log")


def _log_crash(module, error):
    with open(CRASH_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {module} CRASH:\n{error}\n\n")


# Global loading status
app_status = {
    "server": False,
    "whisper": False,
    "transcription": False,
    "analysis": False,
    "ready": False,
    "message": "Starting...",
    "version": __version__,
    "access_mode": "checking",
    "trial_days_left": 0,
    "licensed": False,
    "license_info": None,
    "update_available": False,
    "update_info": None,
}


def main():
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="Meeting AI Analyser")
    parser.add_argument("--port", type=int, default=5555, help="Web server port")
    parser.add_argument("--mic-device", type=int, default=None, help="Microphone ID")
    parser.add_argument("--model", type=str, default="small",
                        help="Whisper model: tiny, base, small, medium, large-v3")
    parser.add_argument("--language", type=str, default="en", help="Language code")
    parser.add_argument("--segment", type=int, default=10, help="Segment duration (seconds)")
    parser.add_argument("--no-mic", action="store_true", help="Disable microphone")
    parser.add_argument("--no-analysis", action="store_true", help="Disable Claude analysis")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser")
    args = parser.parse_args()

    app_status["language"] = args.language
    app_status["model"] = args.model

    stop_event = threading.Event()

    def shutdown(sig=None, frame=None):
        print("\n[MAIN] Shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("=" * 60)
    print(f"  Meeting AI Analyser v{__version__}")
    print("=" * 60)

    # Check license/trial
    access = lic_mod.check_access()
    app_status["access_mode"] = access["mode"]
    app_status["trial_days_left"] = access.get("days_left", 0)
    app_status["licensed"] = access["mode"] == "licensed"
    app_status["license_info"] = access.get("license_info")
    print(f"[MAIN] Access: {access['mode']}" + (f" ({access.get('days_left', 0)} days left)" if access['mode'] == 'trial' else ""))

    # 1. Web server FIRST (starts fast)
    import server
    server.app_status = app_status
    t_server = threading.Thread(
        target=server.start,
        args=(stop_event, args.port),
        name="server",
        daemon=True,
    )
    t_server.start()
    app_status["server"] = True
    app_status["message"] = "Web server started"
    print(f"[MAIN] Web server started on http://localhost:{args.port}")

    # 2. Open browser IMMEDIATELY (shows loader)
    if not args.no_browser:
        time.sleep(1)
        webbrowser.open(f"http://localhost:{args.port}")

    # 3. Transcription (loads Whisper = slow)
    app_status["message"] = "Loading Whisper model..."
    import live_transcribe

    def _run_transcribe():
        try:
            live_transcribe.start(
                stop_event,
                mic_device=args.mic_device,
                segment=args.segment,
                model_size=args.model,
                language=args.language,
                no_mic=args.no_mic,
            )
        except Exception:
            _log_crash("TRANSCRIPTION", traceback.format_exc())

    t_transcribe = threading.Thread(target=_run_transcribe, name="transcription", daemon=True)
    t_transcribe.start()
    app_status["transcription"] = True
    app_status["message"] = "Transcription started"
    print("[MAIN] Transcription started")

    # 4. Claude analysis (optional, gated by license)
    if access["mode"] == "expired":
        app_status["analysis"] = False
        print("[MAIN] Claude analysis disabled (license expired)")
    elif not args.no_analysis:
        import analyst

        def _run_analyst():
            try:
                analyst.start(stop_event)
            except Exception:
                _log_crash("ANALYST", traceback.format_exc())

        t_analyst = threading.Thread(target=_run_analyst, name="analyst", daemon=True)
        t_analyst.start()
        app_status["analysis"] = True
        app_status["message"] = "Claude analysis started"
        print("[MAIN] Claude analysis started")
    else:
        app_status["analysis"] = True
        print("[MAIN] Claude analysis disabled")

    # 5. Check for updates (background)
    def _check_update():
        try:
            info = updater.check_for_update()
            app_status["update_available"] = info.get("update_available", False)
            app_status["update_info"] = info if info.get("update_available") else None
            if info.get("update_available"):
                print(f"[MAIN] Update available: v{info.get('latest_version')}")
        except Exception:
            pass

    threading.Thread(target=_check_update, name="updater", daemon=True).start()

    app_status["ready"] = True
    app_status["message"] = "Ready"
    print("\n[MAIN] All systems running. Ctrl+C to stop.\n")

    try:
        while not stop_event.is_set():
            stop_event.wait(1)
    except KeyboardInterrupt:
        shutdown()

    print("[MAIN] Closing...")
    time.sleep(1)
    os._exit(0)


if __name__ == "__main__":
    main()
