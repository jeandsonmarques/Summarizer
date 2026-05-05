from __future__ import annotations

from Summarizer.utils.logging_utils import sanitize_log_message


def test_sanitize_log_message_redacts_sensitive_values():
    text = "password=abc token:123 api_key=xyz host=db.local"
    redacted = sanitize_log_message(text)

    assert "abc" not in redacted
    assert "123" not in redacted
    assert "xyz" not in redacted
    assert "<redacted>" in redacted


def test_sanitize_log_message_redacts_connection_string():
    text = "Driver={ODBC};Server=host;Database=db;Uid=user;Pwd=secret;"
    redacted = sanitize_log_message(text)

    assert redacted == "[connection string redacted]"
