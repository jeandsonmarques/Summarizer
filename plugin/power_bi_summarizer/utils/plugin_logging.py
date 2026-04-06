from __future__ import annotations

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


LOG_CHANNEL = "PowerBI Summarizer"


def log_info(message: str) -> None:
    QgsMessageLog.logMessage(str(message), LOG_CHANNEL, level=Qgis.Info)


def log_warning(message: str) -> None:
    QgsMessageLog.logMessage(str(message), LOG_CHANNEL, level=Qgis.Warning)


def log_error(message: str) -> None:
    QgsMessageLog.logMessage(str(message), LOG_CHANNEL, level=Qgis.Critical)
