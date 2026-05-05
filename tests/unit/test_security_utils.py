from __future__ import annotations

from types import SimpleNamespace

import Summarizer.utils.security_utils as security_utils


def test_mask_sensitive_value_and_mapping_redact_credentials():
    payload = {
        "password": "secret",
        "token": "abc",
        "nested": {"api_key": "xyz"},
        "safe": "ok",
    }

    masked = security_utils.mask_sensitive_mapping(payload)

    assert masked["password"] == "*******"
    assert masked["token"] == "*******"
    assert masked["nested"]["api_key"] == "*******"
    assert masked["safe"] == "ok"


def test_secure_connection_payload_migrates_to_authcfg(monkeypatch):
    class FakeConfig:
        def __init__(self, method):
            self.method = method
            self._config = {}
            self._name = ""

        def setName(self, name):
            self._name = name

        def setConfig(self, key, value):
            self._config[key] = value

        def isValid(self):
            return bool(self._config.get("username") and self._config.get("password"))

        def id(self):
            return "auth1234"

    class FakeAuthManager:
        def storeAuthenticationConfig(self, config):
            return True

    fake_app = SimpleNamespace(authManager=lambda: FakeAuthManager())
    monkeypatch.setattr(security_utils, "QgsApplication", fake_app)
    monkeypatch.setattr(security_utils, "QgsAuthMethodConfig", FakeConfig)

    payload = security_utils.secure_connection_payload(
        {"user": "alice", "password": "secret", "authcfg": "", "name": "Conn"},
        name="Conn",
    )

    assert payload["authcfg"] == "auth1234"
    assert payload["password"] == ""
    assert payload["savePassword"] is False
