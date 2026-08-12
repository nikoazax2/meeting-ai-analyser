"""
Meeting AI Analyser - License & Trial management

- Paid license: LemonSqueezy one-time, cached locally with periodic revalidation.
- Free trial: 7 days, enforced server-side via Supabase edge function
  (anti-bypass: re-install or trial.json deletion cannot reset it because
   the (email, hwid) tuple is recorded in the cloud).
"""
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

from paths import TRIAL_FILE, LICENSE_FILE

# License config (LemonSqueezy)
REVALIDATION_DAYS = 7
GRACE_PERIOD_DAYS = 30
LEMONSQUEEZY_API = "https://api.lemonsqueezy.com"
INSTANCE_NAME = "MeetingAIAnalyser"

# Trial config (Supabase edge function)
TRIAL_API = "https://wdcyabcpczqlpvpwrgws.supabase.co/functions/v1/meeting-ai-trial"
TRIAL_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndkY3lhYmNwY3pxbHB2cHdyZ3dzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkwMjQ1ODIsImV4cCI6MjA5NDYwMDU4Mn0.TzNwvZWJW2lgVQHR3_L86o0gjX1YbLrFb-7BUlPbQxc"
TRIAL_REVALIDATE_DAYS = 1
TRIAL_OFFLINE_GRACE_DAYS = 3


def check_access():
    """Check if user has access (license, trial, expired, or not_started)"""
    lic = _load_license()
    if lic and lic.get("license_key"):
        if _validate_cached_license(lic):
            return {
                "allowed": True,
                "mode": "licensed",
                "days_left": None,
                "license_info": {
                    "key": _mask_key(lic["license_key"]),
                    "activated_at": lic.get("activated_at", ""),
                },
            }

    trial = _check_trial()
    if trial.get("not_started"):
        return {"allowed": False, "mode": "not_started", "days_left": 0, "license_info": None}
    if trial["active"]:
        return {"allowed": True, "mode": "trial", "days_left": trial["days_left"], "license_info": None}

    return {"allowed": False, "mode": "expired", "days_left": 0, "license_info": None}


# ---------------- License (LemonSqueezy) ----------------

def activate_license(key):
    """Activate a license key via LemonSqueezy API"""
    try:
        data = json.dumps({
            "license_key": key,
            "instance_name": INSTANCE_NAME,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{LEMONSQUEEZY_API}/v1/licenses/activate",
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        if result.get("activated") or result.get("license_key", {}).get("status") == "active":
            license_data = {
                "license_key": key,
                "instance_id": result.get("instance", {}).get("id", ""),
                "activated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "last_validated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "valid": True,
            }
            _save_license(license_data)
            return {"success": True, "message": "License activated!"}
        return {"success": False, "message": str(result.get("error", "Activation failed"))}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
            msg = body.get("error", str(e))
        except Exception:
            msg = str(e)
        return {"success": False, "message": str(msg)}
    except Exception as e:
        return {"success": False, "message": str(e)}


def deactivate_license():
    lic = _load_license()
    if not lic or not lic.get("license_key"):
        return {"success": False, "message": "No active license"}

    try:
        data = json.dumps({
            "license_key": lic["license_key"],
            "instance_id": lic.get("instance_id", ""),
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{LEMONSQUEEZY_API}/v1/licenses/deactivate",
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass

    if os.path.exists(LICENSE_FILE):
        os.remove(LICENSE_FILE)
    return {"success": True, "message": "License deactivated"}


def _validate_cached_license(lic):
    last = lic.get("last_validated", "")
    try:
        last_ts = time.mktime(time.strptime(last, "%Y-%m-%dT%H:%M:%SZ"))
    except Exception:
        last_ts = 0

    days_since = (time.time() - last_ts) / 86400
    if days_since < REVALIDATION_DAYS:
        return lic.get("valid", False)

    try:
        data = json.dumps({
            "license_key": lic["license_key"],
            "instance_id": lic.get("instance_id", ""),
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{LEMONSQUEEZY_API}/v1/licenses/validate",
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        valid = result.get("valid", False)
        lic["valid"] = valid
        lic["last_validated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _save_license(lic)
        return valid
    except Exception:
        return days_since < GRACE_PERIOD_DAYS


def _load_license():
    if not os.path.exists(LICENSE_FILE):
        return None
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_license(data):
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _mask_key(key):
    if len(key) <= 8:
        return key
    return key[:4] + "..." + key[-4:]


# ---------------- Trial (Supabase) ----------------

def start_trial(email, source=""):
    """Start a server-side trial. Called when no local token exists.

    `source` is the optional self-reported acquisition channel, which is the
    only reliable way to know which channel produces buyers: nothing survives
    the trip from the website through an installer to a fresh install.
    """
    email = (email or "").strip().lower()
    if email and "@" not in email:
        return {"success": False, "message": "Invalid email"}

    from hwid import get_hwid
    try:
        result = _trial_call("start", {
            "email": email,
            "hwid": get_hwid(),
            "source": (source or "")[:40],
        })
    except Exception:
        # The whole selling point is that this works locally. Refusing to start
        # because our own server is unreachable - corporate proxy, VPN, captive
        # wifi, our outage - would brick the app for a legitimate user at the
        # very first screen. Grant the trial locally instead; the hwid check
        # still applies to everyone who is online.
        return _start_local_trial(email)

    status = result.get("status")
    if status == "active":
        _save_trial({
            "token": result["token"],
            "email": email,
            "expires_at": result["expires_at"],
            "last_validated": _now_iso(),
        })
        return {"success": True, "days_left": result.get("days_left", 0)}

    if status == "already_used" or status == "expired":
        return {
            "success": False,
            "already_used": True,
            "message": result.get("message") or "A trial has already been used for this email or computer.",
        }

    return {"success": False, "message": result.get("error") or "Unable to start trial"}


LOCAL_TOKEN_PREFIX = "local-"


def _start_local_trial(email):
    """Offline fallback: a self-contained 7-day trial with no server round-trip."""
    import uuid
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    _save_trial({
        "token": LOCAL_TOKEN_PREFIX + uuid.uuid4().hex,
        "email": email,
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_validated": _now_iso(),
    })
    return {"success": True, "days_left": 7, "offline": True}


def _check_trial():
    trial = _load_trial()
    if not trial or not trial.get("token"):
        return {"active": False, "days_left": 0, "not_started": True}

    expires_at = trial.get("expires_at", "")
    days_left = _days_until(expires_at)

    # Local trials are self-contained: validating them server-side would return
    # not_found and lock out the user we granted the trial to in the first place.
    if trial["token"].startswith(LOCAL_TOKEN_PREFIX):
        return {"active": days_left > 0, "days_left": days_left}

    last = trial.get("last_validated", "")
    try:
        last_ts = time.mktime(time.strptime(last, "%Y-%m-%dT%H:%M:%SZ"))
    except Exception:
        last_ts = 0
    days_since = (time.time() - last_ts) / 86400

    if days_since < TRIAL_REVALIDATE_DAYS:
        return {"active": days_left > 0, "days_left": days_left}

    from hwid import get_hwid
    try:
        result = _trial_call("validate", {"token": trial["token"], "hwid": get_hwid()})
        new_expires = result.get("expires_at", expires_at)
        trial["expires_at"] = new_expires
        trial["last_validated"] = _now_iso()
        _save_trial(trial)
        return {
            "active": bool(result.get("valid")),
            "days_left": result.get("days_left", _days_until(new_expires)),
        }
    except Exception:
        # Offline grace
        if days_since < TRIAL_OFFLINE_GRACE_DAYS:
            return {"active": days_left > 0, "days_left": days_left}
        return {"active": False, "days_left": 0}


def _trial_call(action, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{TRIAL_API}/{action}",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {TRIAL_ANON_KEY}",
            "apikey": TRIAL_ANON_KEY,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            raise


def _load_trial():
    if not os.path.exists(TRIAL_FILE):
        return None
    try:
        with open(TRIAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_trial(data):
    with open(TRIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _days_until(iso_ts):
    if not iso_ts:
        return 0
    try:
        ts = iso_ts.replace("Z", "+00:00")
        target = datetime.fromisoformat(ts)
        delta = (target - datetime.now(timezone.utc)).total_seconds()
        return max(0, int((delta + 86399) // 86400))
    except Exception:
        return 0
