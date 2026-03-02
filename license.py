"""
Meeting AI Analyser - License & Trial management
LemonSqueezy one-time payment with 7-day free trial
"""
import json
import os
import time
import urllib.request
import urllib.error

from paths import TRIAL_FILE, LICENSE_FILE

TRIAL_DAYS = 7
REVALIDATION_DAYS = 7
GRACE_PERIOD_DAYS = 30
LEMONSQUEEZY_API = "https://api.lemonsqueezy.com"
INSTANCE_NAME = "MeetingAIAnalyser"


def check_access():
    """Check if user has access (trial or license)"""
    # 1. Check cached license first
    lic = _load_license()
    if lic and lic.get("license_key"):
        valid = _validate_cached_license(lic)
        if valid:
            return {
                "allowed": True,
                "mode": "licensed",
                "days_left": None,
                "license_info": {
                    "key": _mask_key(lic["license_key"]),
                    "activated_at": lic.get("activated_at", ""),
                },
            }

    # 2. Check trial
    trial = _check_trial()
    if trial["active"]:
        return {
            "allowed": True,
            "mode": "trial",
            "days_left": trial["days_left"],
            "license_info": None,
        }

    # 3. Expired
    return {
        "allowed": False,
        "mode": "expired",
        "days_left": 0,
        "license_info": None,
    }


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
        else:
            err = result.get("error", "Activation failed")
            return {"success": False, "message": str(err)}
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
    """Deactivate the current license"""
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


def _check_trial():
    """Check trial status, init if first launch"""
    if not os.path.exists(TRIAL_FILE):
        _init_trial()

    try:
        with open(TRIAL_FILE, "r", encoding="utf-8") as f:
            trial = json.load(f)
        started = trial.get("started_at", "")
        started_ts = time.mktime(time.strptime(started, "%Y-%m-%dT%H:%M:%SZ"))
        elapsed = time.time() - started_ts
        days_elapsed = elapsed / 86400
        days_left = max(0, TRIAL_DAYS - int(days_elapsed))
        return {"active": days_left > 0, "days_left": days_left}
    except Exception:
        _init_trial()
        return {"active": True, "days_left": TRIAL_DAYS}


def _init_trial():
    """Create trial.json on first launch"""
    trial = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with open(TRIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(trial, f)


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


def _validate_cached_license(lic):
    """Re-validate online every REVALIDATION_DAYS, grace period offline"""
    last = lic.get("last_validated", "")
    try:
        last_ts = time.mktime(time.strptime(last, "%Y-%m-%dT%H:%M:%SZ"))
    except Exception:
        last_ts = 0

    days_since = (time.time() - last_ts) / 86400

    if days_since < REVALIDATION_DAYS:
        return lic.get("valid", False)

    # Try online re-validation
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
        # Offline: allow grace period
        return days_since < GRACE_PERIOD_DAYS


def _mask_key(key):
    if len(key) <= 8:
        return key
    return key[:4] + "..." + key[-4:]
