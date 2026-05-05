from __future__ import annotations

from typing import Any, Mapping

try:  # pragma: no cover - available inside QGIS
    from qgis.core import QgsApplication, QgsAuthMethodConfig
except Exception:  # pragma: no cover - allows smoke tests outside QGIS
    QgsApplication = None  # type: ignore
    QgsAuthMethodConfig = None  # type: ignore


SENSITIVE_KEYS = {
    "api_key",
    "authcfg",
    "connection string",
    "connection_string",
    "password",
    "pwd",
    "secret",
    "token",
}


def mask_sensitive_value(key: str | None, value: Any) -> str:
    text = "" if value is None else str(value)
    normalized_key = str(key or "").strip().lower()
    if not normalized_key:
        return text
    if any(token in normalized_key for token in SENSITIVE_KEYS):
        return "*******"
    return text


def mask_sensitive_mapping(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in dict(payload or {}).items():
        if isinstance(value, Mapping):
            masked[key] = mask_sensitive_mapping(value)
        elif isinstance(value, (list, tuple)):
            masked[key] = [mask_sensitive_value(key, item) for item in value]
        else:
            masked[key] = mask_sensitive_value(key, value)
    return masked


def create_basic_authcfg(username: str = "", password: str = "", name: str = "Summarizer") -> str:
    if QgsApplication is None or QgsAuthMethodConfig is None:
        return ""
    username = str(username or "").strip()
    password = str(password or "")
    if not username or not password:
        return ""
    auth_manager = QgsApplication.authManager()
    if auth_manager is None:
        return ""
    config = QgsAuthMethodConfig("Basic")
    config.setName(str(name or "Summarizer"))
    config.setConfig("username", username)
    config.setConfig("password", password)
    if not config.isValid():
        return ""
    try:
        if not auth_manager.storeAuthenticationConfig(config):
            return ""
    except Exception:
        return ""
    return config.id() or ""


def secure_connection_payload(
    payload: Mapping[str, Any] | None,
    *,
    name: str = "Summarizer",
) -> dict[str, Any]:
    data = dict(payload or {})
    password = str(data.get("password") or "")
    authcfg = str(data.get("authcfg") or "")
    if password and not authcfg:
        authcfg = create_basic_authcfg(data.get("user", ""), password, name=name)
        if authcfg:
            data["authcfg"] = authcfg
            data["password"] = ""
            data["savePassword"] = False
    return data


__all__ = [
    "create_basic_authcfg",
    "mask_sensitive_mapping",
    "mask_sensitive_value",
    "secure_connection_payload",
]
