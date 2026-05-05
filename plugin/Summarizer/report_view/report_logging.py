try:
    from ..utils.runtime_paths import runtime_state_file
except ImportError:  # pragma: no cover - supports running report_view as a top-level package
    from utils.runtime_paths import runtime_state_file
from ..utils.logging_utils import LOG_CHANNEL, log_error as _log_error, log_exception as _log_exception, log_info as _log_info, log_warning as _log_warning


LOG_FILE = runtime_state_file("relatorios_debug.log")


def log_info(message: object):
    return _log_info(message, file_path=LOG_FILE)


def log_warning(message: object):
    return _log_warning(message, file_path=LOG_FILE)


def log_error(message: object):
    return _log_error(message, file_path=LOG_FILE)


def log_exception(context: object, exc=None):
    return _log_exception(context, exc=exc, file_path=LOG_FILE)


__all__ = ["LOG_CHANNEL", "LOG_FILE", "log_error", "log_exception", "log_info", "log_warning"]
