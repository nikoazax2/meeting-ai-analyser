"""
Meeting AI Analyser - Auto-update checker
Checks GitHub Releases for new versions
"""
import json
import urllib.request
import urllib.error

from version import __version__

GITHUB_REPO = "nikoazax2/meeting-ai-analyser"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def check_for_update():
    """Check GitHub for a newer release"""
    try:
        req = urllib.request.Request(
            GITHUB_API,
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "MeetingAIAnalyser"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        tag = data.get("tag_name", "").lstrip("v")
        if not tag:
            return {"update_available": False}

        if _version_newer(tag, __version__):
            # Prefer the Setup installer over a bare exe
            download_url = ""
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if name.lower().endswith(".exe") and "setup" in name.lower():
                    download_url = asset.get("browser_download_url", "")
                    break
            if not download_url:
                for asset in data.get("assets", []):
                    if asset.get("name", "").endswith(".exe"):
                        download_url = asset.get("browser_download_url", "")
                        break
            if not download_url:
                download_url = data.get("html_url", "")
            return {
                "update_available": True,
                "latest_version": tag,
                "download_url": download_url,
                "release_notes": data.get("body", ""),
            }
        return {"update_available": False, "latest_version": tag}
    except Exception:
        return {"update_available": False}


def _version_newer(remote, local):
    """Compare semver: return True if remote > local"""
    try:
        r = [int(x) for x in remote.split(".")]
        l = [int(x) for x in local.split(".")]
        return r > l
    except Exception:
        return False
