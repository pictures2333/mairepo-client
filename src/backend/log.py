import logging
import os
import sys

# Format

_BASE_LOGGER_NAME = "mairepo.client"
_RESET = "\033[0m"
_NAME_COLOR = "\033[36m"
_LEVEL_COLORS = {
    logging.DEBUG: "\033[90m",
    logging.INFO: "\033[32m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[91m",
}


def _set_display_fields(record: logging.LogRecord, use_colors: bool) -> None:
    levelprefix = f"{record.levelname}:".ljust(9)
    nameprefix = f"[{record.name}]"

    if use_colors:
        level_color = _LEVEL_COLORS.get(record.levelno, _RESET)
        levelprefix = f"{level_color}{levelprefix}{_RESET}"
        nameprefix = f"{_NAME_COLOR}{nameprefix}{_RESET}"

    record.levelprefix = levelprefix
    record.nameprefix = nameprefix


def _prepare_record(record: logging.LogRecord) -> bool:
    isatty = getattr(sys.stderr, "isatty", None)
    use_colors = bool(isatty and isatty()) and "NO_COLOR" not in os.environ
    _set_display_fields(record, use_colors)
    return True


# Handler

_formatter = logging.Formatter("%(levelprefix)s %(nameprefix)s %(message)s")
_handler = logging.StreamHandler()
_handler.addFilter(_prepare_record)
_handler.setFormatter(_formatter)


# Logger


def _configure_base_logger() -> logging.Logger:
    logger = logging.getLogger(_BASE_LOGGER_NAME)

    if _handler not in logger.handlers:
        logger.handlers.clear()
        logger.addHandler(_handler)

    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.disabled = False
    return logger


def get_logger(name: str) -> logging.Logger:
    base_logger = _configure_base_logger()
    if not name or name == _BASE_LOGGER_NAME:
        return base_logger

    logger_name = (
        name
        if name.startswith(f"{_BASE_LOGGER_NAME}.")
        else f"{_BASE_LOGGER_NAME}.{name}"
    )
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    logger.disabled = False
    return logger
