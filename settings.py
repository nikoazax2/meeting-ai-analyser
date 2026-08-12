"""
Meeting AI Analyser - user settings store.
Persists analysis preferences (CLI vs bring-your-own-API-key) in data/settings.json.
The Anthropic API key is stored locally only and never sent anywhere except api.anthropic.com.
"""
import json
import threading

from paths import SETTINGS_FILE

_lock = threading.Lock()

_DEFAULTS = {
    "analysis_mode": "cli",            # "cli" (Claude Code CLI) | "api" (bring-your-own Anthropic API key)
    "api_key": "",                     # Anthropic API key, local only
    "api_model": "claude-opus-4-8",    # model used in API mode
    "telemetry": True,                 # anonymous usage events, opt-out (never audio or transcripts)
}

# Allowlist of models the UI exposes (kept in sync with the dropdown in index.html)
ALLOWED_MODELS = ("claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5")


def _read_raw():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load():
    """Return the full settings dict, defaults filled in."""
    with _lock:
        data = _read_raw()
        merged = dict(_DEFAULTS)
        for k in _DEFAULTS:
            if k in data:
                merged[k] = data[k]
        return merged


def save(updates):
    """Persist the given keys (only known keys are kept) and return the merged settings."""
    with _lock:
        data = _read_raw()
        for k, v in updates.items():
            if k in _DEFAULTS:
                data[k] = v
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        merged = dict(_DEFAULTS)
        merged.update({k: v for k, v in data.items() if k in _DEFAULTS})
        return merged


def get(key):
    return load().get(key)
