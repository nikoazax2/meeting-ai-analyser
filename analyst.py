"""
Meeting AI Analyser - AI analysis module
Reads transcription every 60s and runs Claude to analyze the ongoing meeting
"""
import os
import subprocess
import sys
import time

from paths import TRANSCRIPTION_FILE, ANALYSIS_FILE, LOG_FILE, TEMP_PROMPT


def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")


# Timing state (exposed for server.py)
analyst_status = {"state": "idle", "last_run": 0, "next_run": 0, "interval": 60}

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
        log(f"Calling claude --print (prompt length: {len(prompt)})")
        result = subprocess.run(
            [claude_cmd, "--print"],
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
    last_content = ""

    log("=== ANALYST STARTED ===")
    log(f"Interval: {interval}s")
    analyst_status["interval"] = interval
    analyst_status["next_run"] = time.time() + interval
    print("[ANALYST] AI analysis module started")
    print(f"[ANALYST] Interval: {interval}s")

    while True:
        if stop_event and stop_event.is_set():
            break

        content = read_transcription()

        if content and content != last_content and len(content) > 50:
            last_content = content
            timestamp = time.strftime("%H:%M:%S")
            log(f"New transcription ({len(content)} chars), launching analysis...")
            print(f"[{timestamp}] New transcription detected, analyzing...")

            analyst_status["state"] = "analyzing"
            analysis = analyze_with_claude(content)
            analyst_status["state"] = "idle"
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
