"""
Meeting AI Analyser - AI analysis module
Reads transcription every 60s and runs Claude to analyze the ongoing meeting
"""
import glob
import json
import os
import subprocess
import sys
import threading
import time

from paths import TRANSCRIPTION_FILE, ANALYSIS_FILE, LOG_FILE, TEMP_PROMPT


def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")


# Timing state (exposed for server.py)
analyst_status = {"state": "idle", "last_run": 0, "next_run": 0, "interval": 60, "paused": False, "conversation_id": ""}

# Events for manual trigger and pause control
_trigger_event = threading.Event()
_pause_lock = threading.Lock()


def trigger_now():
    """Trigger an immediate analysis (called from server.py)"""
    _trigger_event.set()


def set_paused(paused):
    """Pause or resume automatic analysis"""
    analyst_status["paused"] = paused


def set_conversation_id(cid):
    analyst_status["conversation_id"] = cid


def get_conversation_id():
    return analyst_status["conversation_id"]


def _find_claude_projects_dir():
    """Find .claude/projects/ trying multiple locations"""
    candidates = [
        os.path.join(os.path.expanduser("~"), ".claude", "projects"),
        os.path.join(os.environ.get("USERPROFILE", ""), ".claude", "projects"),
        os.path.join(os.environ.get("HOMEDRIVE", "C:"), os.environ.get("HOMEPATH", "\\Users"), ".claude", "projects"),
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return None


def list_conversations(limit=50):
    """Scan all projects in .claude/projects/ for conversation JSONL files"""
    claude_dir = _find_claude_projects_dir()
    if not claude_dir:
        return {"conversations": [], "base_path": None}
    files = glob.glob(os.path.join(claude_dir, "**", "*.jsonl"), recursive=True)
    files.sort(key=os.path.getmtime, reverse=True)
    results = []
    for fpath in files[:limit]:
        sid = os.path.splitext(os.path.basename(fpath))[0]
        raw_project = os.path.basename(os.path.dirname(fpath))
        if raw_project == "subagents":
            continue
        # Clean: strip drive prefix (C-- or c--), keep rest as-is
        project = raw_project
        if project[:3].lower() == "c--":
            project = project[3:]
        mtime = os.path.getmtime(fpath)
        date_str = time.strftime("%m/%d %H:%M", time.localtime(mtime))
        preview = ""
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line_num, raw_line in enumerate(f):
                    if line_num > 20:
                        break
                    entry = json.loads(raw_line)
                    # Format 1: type=user with message.content[].text
                    if entry.get("type") == "user":
                        msg = entry.get("message", {})
                        content_blocks = msg.get("content", []) if isinstance(msg, dict) else []
                        if isinstance(content_blocks, list):
                            for block in content_blocks:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    preview = block.get("text", "").strip()[:80]
                                    break
                        elif isinstance(content_blocks, str):
                            preview = content_blocks.strip()[:80]
                        if preview:
                            break
                    # Format 2: queue-operation with content
                    if entry.get("type") == "queue-operation" and entry.get("content"):
                        raw_content = entry["content"]
                        for text_line in raw_content.split("\n"):
                            s = text_line.strip()
                            if s and not s.startswith("===") and not s.startswith("INSTRUCTION"):
                                preview = s[:80]
                                break
                        if preview:
                            break
        except Exception:
            pass
        if not preview:
            preview = sid[:16]
        results.append({"id": sid, "project": project, "date": date_str, "preview": preview})
    return {"conversations": results, "base_path": claude_dir}


_last_content_lock = threading.Lock()
_last_content_ref = {"value": ""}


def reset_content():
    """Reset last_content so next analysis isn't skipped after a reset"""
    with _last_content_lock:
        _last_content_ref["value"] = ""

PROMPT = """You are a real-time meeting assistant. Here is the live transcription of an ongoing meeting.

INSTRUCTIONS:
1. Summarize the topics discussed
2. List decisions made
3. Identify open questions
4. Suggest technical solutions if relevant
5. List action items (who does what)

Be concise and structured. Markdown format.

TRANSCRIPTION:
{transcription}
"""


def read_transcription():
    if not os.path.exists(TRANSCRIPTION_FILE):
        return None
    with open(TRANSCRIPTION_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def analyze_with_claude(text):
    prompt = PROMPT.format(transcription=text)

    # Write prompt to temp file to avoid Windows quote issues
    prompt_file = TEMP_PROMPT
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt)

    # Find claude in known paths
    claude_cmd = "claude"
    for path in [
        os.path.expanduser("~/AppData/Roaming/npm/claude.cmd"),
        "C:/Program Files/nodejs/claude.cmd",
    ]:
        if os.path.exists(path):
            claude_cmd = path
            break

    log(f"Using claude: {claude_cmd}")
    try:
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        cmd = [claude_cmd, "--print"]
        cid = analyst_status["conversation_id"]
        if cid:
            cmd += ["--resume", cid]
        log(f"Calling {' '.join(cmd)} (prompt length: {len(prompt)})")
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            env=env,
        )
        log(f"Return code: {result.returncode}")
        log(f"Stdout length: {len(result.stdout)}")
        if result.stderr:
            log(f"Stderr: {result.stderr[:500]}")
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            log(f"FAIL: no output or bad return code")
            return None
    except FileNotFoundError:
        log(f"ERROR: claude not found at {claude_cmd}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        log("ERROR: claude timed out (120s)")
        return None
    except Exception as e:
        log(f"ERROR: {type(e).__name__}: {e}")
        return None
    finally:
        if os.path.exists(prompt_file):
            os.remove(prompt_file)


def start(stop_event, interval=60):
    """Entry point for module mode (called from main.py as thread)"""
    _run(stop_event=stop_event, interval=interval)


def _run(stop_event=None, interval=60):
    """Main analysis logic"""
    _last_content_ref["value"] = ""

    log("=== ANALYST STARTED ===")
    log(f"Interval: {interval}s")
    analyst_status["interval"] = interval
    analyst_status["next_run"] = time.time() + interval
    print("[ANALYST] AI analysis module started")
    print(f"[ANALYST] Interval: {interval}s")

    while True:
        if stop_event and stop_event.is_set():
            break

        # Check for manual trigger
        manual = _trigger_event.is_set()
        if manual:
            _trigger_event.clear()

        # Skip auto-analysis if paused (but allow manual triggers)
        if analyst_status["paused"] and not manual:
            analyst_status["state"] = "paused"
            analyst_status["next_run"] = 0
            # Wait 1s or until triggered/unpaused
            if stop_event:
                stop_event.wait(1)
            else:
                time.sleep(1)
            continue

        # Re-check paused after waking up (user may have paused during sleep)
        if analyst_status["paused"] and not manual:
            continue

        content = read_transcription()

        if content and len(content) > 50 and (content != _last_content_ref["value"] or manual):
            _last_content_ref["value"] = content
            timestamp = time.strftime("%H:%M:%S")
            trigger_label = " (manual)" if manual else ""
            log(f"New transcription ({len(content)} chars), launching analysis...{trigger_label}")
            print(f"[{timestamp}] Analyzing{trigger_label}...")

            analyst_status["state"] = "analyzing"
            analysis = analyze_with_claude(content)
            analyst_status["state"] = "paused" if analyst_status["paused"] else "idle"
            analyst_status["last_run"] = time.time()

            if analysis:
                with open(ANALYSIS_FILE, "w", encoding="utf-8") as f:
                    f.write(f"# Meeting Analysis - {time.strftime('%Y-%m-%d %H:%M')}\n\n")
                    f.write(analysis)
                    f.write("\n")

                print(f"[{timestamp}] Analysis saved to {ANALYSIS_FILE}")
            else:
                print(f"[{timestamp}] No analysis returned.")
        else:
            timestamp = time.strftime("%H:%M:%S")
            if manual:
                print(f"[{timestamp}] Manual trigger: no new transcription to analyze.")
            else:
                print(f"[{timestamp}] Waiting for new transcription...")

        analyst_status["next_run"] = time.time() + interval
        if stop_event:
            stop_event.wait(interval)
        else:
            time.sleep(interval)

    print("[ANALYST] Analysis module stopped.")


def main():
    """Standalone entry point"""
    print("=" * 60)
    print("  MEETING AI ANALYSER - Analysis Module")
    print(f"  Reading from: {TRANSCRIPTION_FILE}")
    print(f"  Output to: {ANALYSIS_FILE}")
    print("  Ctrl+C to stop")
    print("=" * 60 + "\n")
    try:
        _run()
    except KeyboardInterrupt:
        print("\n[STOP] Analysis stopped.")


if __name__ == "__main__":
    main()
