from __future__ import annotations

import inspect
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

try:
    from qgis.core import Qgis, QgsMessageLog
except Exception:  # pragma: no cover - allows pure-python smoke tests
    class Qgis:
        Info = "INFO"
        Warning = "WARNING"
        Critical = "CRITICAL"

    class QgsMessageLog:
        @staticmethod
        def logMessage(message, tag, level=None):
            return None


LOG_CHANNEL = "Summarizer"

_SENSITIVE_KEY_PATTERNS = (
    re.compile(r"(?i)\b(password|pwd|token|api[_-]?key|access[_-]?token|secret)\s*=\s*([^;&\s]+)"),
    re.compile(r"(?i)\b(password|pwd|token|api[_-]?key|access[_-]?token|secret)\s*:\s*([^;&\s]+)"),
)
_SENSITIVE_URL_PATTERNS = (
    re.compile(r"(?i)([?&](?:password|pwd|token|api_key|api-key|access_token|secret)=)([^&#\s]+)"),
    re.compile(r"(?i)([?&](?:password|pwd|token|api_key|api-key|access_token|secret)%3[dD])([^&#\s]+)"),
)
_CONNECTION_STRING_PATTERNS = (
    re.compile(r"(?i)\bDriver=\{[^}]+\};.*"),
    re.compile(r"(?i)\bServer=[^;]+;.*\bDatabase=[^;]+;.*"),
    re.compile(r"(?i)\bHost=[^;]+;.*\bDatabase=[^;]+;.*"),
    re.compile(r"(?i)\bPwd=[^;]+;.*"),
    re.compile(r"(?i)\bPassword=[^;]+;.*"),
)
_URL_CREDENTIALS_PATTERN = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)([^:/\s@]+):([^@\s]+)@")
_SEEN_KEYS = set()


def _normalize_message(value: object) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n")


def sanitize_log_message(value: object) -> str:
    redacted = _normalize_message(value)
    for pattern in _SENSITIVE_KEY_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)}=<redacted>", redacted)
    for pattern in _SENSITIVE_URL_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)}<redacted>", redacted)
    redacted = _URL_CREDENTIALS_PATTERN.sub(r"\1<redacted>:<redacted>@", redacted)
    for pattern in _CONNECTION_STRING_PATTERNS:
        if pattern.search(redacted):
            return "[connection string redacted]"
    return redacted


def _caller_origin() -> Tuple[str, str]:
    frame = inspect.currentframe()
    if frame is None or frame.f_back is None or frame.f_back.f_back is None:
        return "__main__", "<unknown>"
    caller = frame.f_back.f_back
    module = caller.f_globals.get("__name__", "__main__")
    function = caller.f_code.co_name or "<module>"
    return module, function


def _emit(level, message: object, *, file_path: Optional[Path] = None) -> str:
    clean = sanitize_log_message(message)
    key = (level, clean, str(file_path) if file_path is not None else "")
    if key in _SEEN_KEYS:
        return clean
    _SEEN_KEYS.add(key)
    try:
        QgsMessageLog.logMessage(clean, LOG_CHANNEL, level=level)
    except Exception:
        return clean  # intentional fallback: logger must not recurse
    if file_path is not None:
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().isoformat(timespec="seconds")
            with file_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{timestamp} [{level}] {clean}\n")
        except Exception:
            return clean  # intentional fallback: file logging is best effort
    return clean


def log_info(message: object, *, file_path: Optional[Path] = None) -> str:
    return _emit(Qgis.Info, message, file_path=file_path)


def log_warning(message: object, *, file_path: Optional[Path] = None) -> str:
    return _emit(Qgis.Warning, message, file_path=file_path)


def log_error(message: object, *, file_path: Optional[Path] = None) -> str:
    return _emit(Qgis.Critical, message, file_path=file_path)


def log_exception(
    context: object,
    exc: BaseException | None = None,
    *,
    file_path: Optional[Path] = None,
    level=Qgis.Warning,
) -> str:
    module, function = _caller_origin()
    current_exc = exc if exc is not None else sys.exc_info()[1]
    pieces = [
        f"[{module}.{function}]",
        _normalize_message(context).strip() or "falha ao registrar exceção",
    ]
    if current_exc is not None:
        pieces.append(f"{type(current_exc).__name__}: {current_exc}")
    return _emit(level, " | ".join(piece for piece in pieces if piece), file_path=file_path)


__all__ = [
    "LOG_CHANNEL",
    "log_error",
    "log_exception",
    "log_info",
    "log_warning",
    "sanitize_log_message",
]
