import logging
import os
import time

# Marker for handlers created here. Only marked handlers are ever closed or
# removed, so foreign handlers on root (pytest's caplog, an embedding host)
# survive a config()/_disable_file_logging() round trip.
_OWNED = "_valvet_owned"

# Root now carries the app handlers, so it also carries these chatty
# third-party loggers unless they are pinned back to WARNING.
_QUIET_LOGGERS = (
    "PIL",
    "PySide6",
    "asyncio",
    "matplotlib",
    "numba",
    "trimesh",
    "urllib3",
    "vtkmodules",
)

_FILE_FORMAT = "%(asctime)s %(levelname)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def __get_logs_directory() -> str:
    logs_path = os.path.dirname(__file__)
    logs_path = os.path.join(logs_path, "..")
    logs_path = os.path.abspath(logs_path)
    logs_path = os.path.join(logs_path, "logs")
    return logs_path


def _fallback_logger():
    """Console-only logger for the window between import and config().

    Never raises: a broken logging setup must not stop the app from starting.
    """
    try:
        log = logging.getLogger(__name__)
        log.setLevel(logging.DEBUG)
        if not log.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
            setattr(handler, _OWNED, True)
            log.addHandler(handler)
        return log
    except Exception:  # pragma: no cover - logging must never break import
        return None


# -----------------------------------------------------------------------------

_facade = _fallback_logger()


def _detach_owned_handlers(log: logging.Logger) -> None:
    """Close then remove the handlers we added; leave foreign ones alone.

    ``close()`` matters on Windows: without it the dated log file stays locked
    and a later run cannot recreate it.
    """
    for handler in list(log.handlers):
        if not getattr(handler, _OWNED, False):
            continue
        log.removeHandler(handler)
        try:
            handler.close()
        except Exception:  # pragma: no cover - close() is best effort
            pass


def _own(handler: logging.Handler) -> logging.Handler:
    setattr(handler, _OWNED, True)
    return handler


def _adopt_root_facade() -> None:
    """Point the facade at root, so getLogger(__name__) records are captured too."""
    global _facade
    log = logging.getLogger(__name__)
    _detach_owned_handlers(log)
    log.setLevel(logging.NOTSET)
    log.propagate = True
    _facade = log


def _quiet_third_party() -> None:
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def _apply_level_names(use_color_logs: bool) -> None:
    if use_color_logs:
        # logger config with dimmed time
        # https://docs.python.org/3/howto/logging.html
        # https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
        ANSI_FG_WHITE = "\033[1;37m"
        ANSI_FG_YELLOW = "\033[1;33m"
        ANSI_FG_RED = "\033[1;31m"
        ANSI_FG_DEFAULT = "\033[1;0m"

        logging.addLevelName(logging.DEBUG, "DEBUG")
        logging.addLevelName(logging.INFO, f"{ANSI_FG_WHITE}INFO {ANSI_FG_DEFAULT}")
        logging.addLevelName(logging.WARNING, f"{ANSI_FG_YELLOW}WARN {ANSI_FG_DEFAULT}")
        logging.addLevelName(logging.ERROR, f"{ANSI_FG_RED}ERROR{ANSI_FG_DEFAULT}")
        logging.addLevelName(logging.FATAL, f"{ANSI_FG_RED}FATAL{ANSI_FG_DEFAULT}")
    else:
        logging.addLevelName(logging.DEBUG, "DEBUG")
        logging.addLevelName(logging.INFO, "INFO ")
        logging.addLevelName(logging.WARNING, "WARN ")
        logging.addLevelName(logging.ERROR, "ERROR")
        logging.addLevelName(logging.FATAL, "FATAL")


def _open_log_file():
    """Dated log file handler, or None when the directory/file is unusable.

    ``delay=True`` keeps the file uncreated until something is really logged,
    and every OS error (read-only install, full disk, no permission) degrades
    to console-only logging instead of raising during startup.
    """
    try:
        os.makedirs(__get_logs_directory(), exist_ok=True)
        path = os.path.join(__get_logs_directory(), time.strftime("%Y-%m-%d.log"))
        handler = logging.FileHandler(path, encoding="utf-8", delay=True)
    except OSError as exc:
        _log(logging.WARNING, "file logging disabled (%s): %s", type(exc).__name__, exc)
        return None
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(fmt=_FILE_FORMAT, datefmt=_DATE_FORMAT))
    return _own(handler)


def config(use_color_logs: bool):
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    _detach_owned_handlers(root)
    # Before any handler is attached, so a warning raised while opening the log
    # file is not printed twice (own handler + root's).
    _adopt_root_facade()

    # https://betterstack.com/community/questions/how-to-log-to-file-and-console-in-python/
    console_formatter = (
        logging.Formatter(
            fmt="\033[30m%(asctime)s\033[39m %(levelname)s: %(message)s",
            datefmt=_DATE_FORMAT,
        )
        if use_color_logs
        else logging.Formatter(fmt=_FILE_FORMAT, datefmt=_DATE_FORMAT)
    )
    console_handler = _own(logging.StreamHandler())
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(console_formatter)
    root.addHandler(console_handler)

    file_handler = _open_log_file()
    if file_handler is not None:
        root.addHandler(file_handler)

    _quiet_third_party()
    _apply_level_names(use_color_logs)

    root.debug("----------------- STARTING -----------------")
    global _debug_mode
    _debug_mode = True


_debug_mode = False


def env_debug_enabled() -> bool:
    return os.environ.get("VALVET_DEBUG", "").strip().lower() in ("1", "true", "yes")


def debug_mode_enabled() -> bool:
    return bool(_debug_mode)


def _disable_file_logging() -> None:
    """Keep a quiet stderr handler; no dated log file."""
    global _debug_mode
    root = logging.getLogger()
    _detach_owned_handlers(root)
    _adopt_root_facade()
    handler = logging.StreamHandler()
    handler.setLevel(logging.WARNING)
    root.addHandler(_own(handler))
    root.setLevel(logging.WARNING)
    _debug_mode = False


def set_debug_mode(enabled: bool, *, use_color_logs: bool = True) -> None:
    """Same as ``--debug``: file + verbose stderr when enabled."""
    global _debug_mode
    if enabled:
        if _debug_mode:
            return
        config(use_color_logs)
        return
    _disable_file_logging()


def configure_if_debug(
    *, argv_debug: bool = False, use_color_logs: bool = True
) -> bool:
    """Enable file + stderr logging when ``--debug`` or ``VALVET_DEBUG`` is set."""
    if not (argv_debug or env_debug_enabled()):
        return False
    set_debug_mode(True, use_color_logs=use_color_logs)
    return True


# -----------------------------------------------------------------------------


def _log(level: int, msg, *args, **kwargs) -> None:
    """Shared emit path.

    ``stacklevel=3`` makes ``pathname``/``lineno`` point at the module that
    called ``logger.debug(...)`` instead of this file, which is the only reason
    a log file is worth having. Loggers that only had a private handler used to
    report ``src/logger.py`` for every single record.
    """
    log = _facade
    if log is None or not log.isEnabledFor(level):
        return
    kwargs.setdefault("stacklevel", 3)
    log.log(level, msg, *args, **kwargs)


def debug(msg, *args, **kwargs):
    """Log 'msg % args' with severity 'DEBUG'."""
    _log(logging.DEBUG, msg, *args, **kwargs)


def info(msg, *args, **kwargs):
    """Log 'msg % args' with severity 'INFO'."""
    _log(logging.INFO, msg, *args, **kwargs)


def warning(msg, *args, **kwargs):
    """Log 'msg % args' with severity 'WARNING'."""
    _log(logging.WARNING, msg, *args, **kwargs)


def error(msg, *args, **kwargs):
    """Log 'msg % args' with severity 'ERROR'."""
    _log(logging.ERROR, msg, *args, **kwargs)


def exception(msg, *args, **kwargs):
    """Log 'msg % args' with severity 'ERROR' plus the active traceback.

    Prefer this over ``error(str(e))`` inside ``except``: it keeps the stack,
    which is the only thing that says where the failure came from.
    """
    kwargs.setdefault("exc_info", True)
    _log(logging.ERROR, msg, *args, **kwargs)


def fatal(msg, *args, **kwargs):
    """Don't use this method, use critical() instead."""
    _log(logging.FATAL, msg, *args, **kwargs)
