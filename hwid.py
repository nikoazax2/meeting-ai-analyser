"""
Stable hardware ID for Windows.
Derives from HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid, hashed.
"""
import hashlib
import socket
import subprocess

_CACHED = None
_CREATE_NO_WINDOW = 0x08000000


def get_hwid():
    global _CACHED
    if _CACHED:
        return _CACHED

    guid = _read_machine_guid()
    if guid:
        h = hashlib.sha256(("maa:" + guid).encode("utf-8")).hexdigest()
    else:
        h = hashlib.sha256(("maa-fb:" + socket.gethostname()).encode("utf-8")).hexdigest()

    _CACHED = h
    return h


def _read_machine_guid():
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value).strip()
    except Exception:
        pass

    try:
        out = subprocess.check_output(
            ["reg", "query", r"HKLM\SOFTWARE\Microsoft\Cryptography", "/v", "MachineGuid"],
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW,
        ).decode("utf-8", errors="ignore")
        for line in out.splitlines():
            if "MachineGuid" in line:
                parts = line.split()
                return parts[-1].strip()
    except Exception:
        pass

    return None
