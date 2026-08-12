"""
Meeting AI Analyser - anonymous product telemetry.

What it sends: an event name (from a fixed list), the app version, the hardware
id already used for trial enforcement, and the trial email so a trial can be
tied to its own funnel step.

What it never sends: audio, transcripts, analyses, meeting content, file paths,
IP-derived data. Nothing is read from the transcription pipeline at all.

Fully opt-out via Settings (`telemetry: false`), never blocks the UI, never
raises. If the network is down the event is dropped - this is a metrics
channel, not a queue.
"""
import json
import threading
import urllib.request
import urllib.error

from paths import TRIAL_FILE
from version import __version__

EVENTS_API = "https://wdcyabcpczqlpvpwrgws.supabase.co/functions/v1/meeting-ai-events"
ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndkY3lhYmNwY3pxbHB2cHdyZ3dzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkwMjQ1ODIsImV4cCI6MjA5NDYwMDU4Mn0.TzNwvZWJW2lgVQHR3_L86o0gjX1YbLrFb-7BUlPbQxc"

_TIMEOUT = 6
_sent_this_session = set()


def track(event, props=None, once=True):
    """Fire-and-forget an event. `once=True` de-duplicates within the session."""
    if once:
        if event in _sent_this_session:
            return
        _sent_this_session.add(event)

    t = threading.Thread(target=_send, args=(event, props or {}), daemon=True)
    t.start()


def _send(event, props):
    try:
        import settings
        if settings.load().get("telemetry") is False:
            return

        from hwid import get_hwid

        payload = {
            "hwid": get_hwid(),
            "event": event,
            "props": props,
            "app_version": __version__,
        }
        email = _trial_email()
        if email:
            payload["email"] = email

        req = urllib.request.Request(
            EVENTS_API,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {ANON_KEY}",
                "apikey": ANON_KEY,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT):
            pass
    except Exception:
        pass  # telemetry must never affect the app


def _trial_email():
    try:
        with open(TRIAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("email")
    except Exception:
        return None
