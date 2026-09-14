"""Non-secret settings and Windows Credential Manager access for MaxRunway."""
from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import subprocess
from ctypes import wintypes
from pathlib import Path
from urllib.parse import urlparse


APP_NAME = "MaxRunway"
CREDENTIAL_TARGET = "MaxRunway/OmegaPlusApiKey"
RUNWAY_ENDPOINT = "https://mcp.runwayml.com/mcp"
OMEGA_ENDPOINT = "https://api.omegaplusapi.com/v1/chat/completions"
OMEGA_MODELS = (
    "omega-plus", "gpt-5.5", "gpt-5.6-sol", "claude-sonnet-4-6",
    "claude-sonnet-5", "claude-opus-4-6", "claude-opus-4-7",
    "claude-opus-4-8", "claude-opus-5", "claude-fable-5",
    "gemini-3.1-pro", "deepseek-v4-pro", "qwen-3.7-plus", "glm-5.2",
    "minimax-m3", "quantum-lite-1",
)
DEFAULTS = {
    "analysisProvider": "codex",
    "runwayServer": "runway",
    "runwayEndpoint": RUNWAY_ENDPOINT,
    "omegaEndpoint": OMEGA_ENDPOINT,
    "omegaModel": "omega-plus",
}


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise RuntimeError("Windows LOCALAPPDATA is unavailable.")
    return Path(base) / APP_NAME


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def _https_url(value: str, label: str) -> str:
    value = str(value).strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(label + " must be an HTTPS URL without embedded credentials.")
    return value.rstrip("/")


def validate_settings(values: dict) -> dict:
    result = dict(DEFAULTS)
    result.update({key: value for key, value in values.items() if key in DEFAULTS})
    if result["analysisProvider"] not in ("codex", "omega"):
        raise ValueError("Unknown analysis provider.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", str(result["runwayServer"])):
        raise ValueError("Runway MCP name may contain letters, numbers, dot, dash, and underscore.")
    result["runwayEndpoint"] = _https_url(result["runwayEndpoint"], "Runway MCP endpoint")
    result["omegaEndpoint"] = _https_url(result["omegaEndpoint"], "Omega endpoint")
    model = str(result["omegaModel"]).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", model):
        raise ValueError("Invalid Omega model ID.")
    result["omegaModel"] = model
    return result


def load_settings() -> dict:
    path = settings_path()
    if not path.is_file():
        return dict(DEFAULTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("settings root is not an object")
        return validate_settings(data)
    except Exception:
        # Corrupt settings do not weaken URL or provider validation.
        return dict(DEFAULTS)


def save_settings(values: dict) -> dict:
    clean = validate_settings(values)
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    temporary.replace(path)
    return clean


class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
        ("Attributes", wintypes.LPVOID), ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


PCREDENTIALW = ctypes.POINTER(CREDENTIALW)
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2


class CredentialStore:
    """Store the Omega key for the current Windows user; never serialize it."""

    def __init__(self, target: str = CREDENTIAL_TARGET):
        self.target = target
        self._advapi = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        self._advapi.CredWriteW.argtypes = (ctypes.POINTER(CREDENTIALW), wintypes.DWORD)
        self._advapi.CredWriteW.restype = wintypes.BOOL
        self._advapi.CredReadW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD,
                                           wintypes.DWORD, ctypes.POINTER(PCREDENTIALW))
        self._advapi.CredReadW.restype = wintypes.BOOL
        self._advapi.CredFree.argtypes = (wintypes.LPVOID,)
        self._advapi.CredDeleteW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD)
        self._advapi.CredDeleteW.restype = wintypes.BOOL

    def write(self, secret: str) -> None:
        if not secret or not secret.strip():
            raise ValueError("Enter an Omega Plus API key.")
        blob = secret.encode("utf-16-le")
        buffer = ctypes.create_string_buffer(blob)
        credential = CREDENTIALW()
        credential.Type = CRED_TYPE_GENERIC
        credential.TargetName = self.target
        credential.CredentialBlobSize = len(blob)
        credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))
        credential.Persist = CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = APP_NAME
        if not self._advapi.CredWriteW(ctypes.byref(credential), 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def read(self) -> str | None:
        pointer = PCREDENTIALW()
        if not self._advapi.CredReadW(self.target, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            error = ctypes.get_last_error()
            if error == 1168:  # ERROR_NOT_FOUND
                return None
            raise ctypes.WinError(error)
        try:
            credential = pointer.contents
            if not credential.CredentialBlob or not credential.CredentialBlobSize:
                return None
            address = ctypes.addressof(credential.CredentialBlob.contents)
            blob = ctypes.string_at(address, credential.CredentialBlobSize)
            return blob.decode("utf-16-le")
        finally:
            self._advapi.CredFree(pointer)

    def delete(self) -> bool:
        if self._advapi.CredDeleteW(self.target, CRED_TYPE_GENERIC, 0):
            return True
        error = ctypes.get_last_error()
        if error == 1168:
            return False
        raise ctypes.WinError(error)


def codex_path() -> str | None:
    configured = os.environ.get("CODEX_CLI_PATH")
    candidates = [configured, shutil.which("codex"),
                  str(Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin")]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            return str(path)
        if path.is_dir():
            matches = sorted(path.glob("*/codex.exe"), reverse=True)
            if matches:
                return str(matches[0])
    return None


def run_codex(arguments, timeout=20):
    executable = codex_path()
    if not executable:
        raise RuntimeError("Codex CLI was not found. Install or open the Codex desktop app first.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run([executable, *arguments], capture_output=True, text=True,
                            timeout=timeout, creationflags=flags, check=False)
    text = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    # Do not propagate URLs or key-like strings to the Max log.
    text = re.sub(r"https?://\S+", "[link]", text)
    text = re.sub(r"(?i)(bearer|token|api[_ -]?key)\s*[:=]\s*\S+", r"\1=[redacted]", text)
    return result.returncode, text[:1200]


def launch_codex(arguments):
    executable = codex_path()
    if not executable:
        raise RuntimeError("Codex CLI was not found. Install or open the Codex desktop app first.")
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    return subprocess.Popen([executable, *arguments], creationflags=flags, close_fds=True)
