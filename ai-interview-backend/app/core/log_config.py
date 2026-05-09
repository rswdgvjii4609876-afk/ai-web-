import logging
import logging.handlers
import os
from datetime import datetime
from logging.config import dictConfig

from app.core.config import settings

script_path = os.path.abspath(__file__)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(script_path), "../.."))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, f"app_{datetime.now().strftime('%Y%m%d')}.log")
SQLALCHEMY_LOG_FILE = os.path.join(
    LOG_DIR, f"sqlalchemy_{datetime.now().strftime('%Y%m%d')}.log"
)

ENV = settings.ENV.lower()
LOG_LEVELS = {
    "development": "DEBUG",
    "testing": "INFO",
    "production": "WARNING",
}
LOG_LEVEL = LOG_LEVELS.get(ENV, "INFO")
SQLALCHEMY_LEVEL = "INFO" if ENV == "production" else "DEBUG"


def is_master_process():
    # Keep compatibility with existing imports; logging no longer depends on
    # multi-process lock files or background consumer threads.
    return True


class SafeTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """Multiprocess-friendly file handler."""

    def __init__(
        self,
        filename,
        when="h",
        interval=1,
        backupCount=0,
        encoding=None,
        delay=False,
        utc=False,
        atTime=None,
    ):
        super().__init__(
            filename, when, interval, backupCount, encoding, delay, utc, atTime
        )
        self.delay = True
        self.mode = "a"

    def _open(self):
        return open(self.baseFilename, self.mode, encoding=self.encoding)


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console_formatter": {
            "format": "%(asctime)s [%(levelname)s] [PID:%(process)d] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "file_formatter": {
            "format": "%(asctime)s [%(levelname)s] [PID:%(process)d] %(name)s [%(pathname)s:%(lineno)d]: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": LOG_LEVEL,
            "formatter": "console_formatter",
        },
        "file": {
            "class": "app.core.log_config.SafeTimedRotatingFileHandler",
            "level": LOG_LEVEL,
            "formatter": "file_formatter",
            "filename": LOG_FILE,
            "when": "midnight",
            "interval": 1,
            "backupCount": 7,
            "encoding": "utf-8",
        },
        "sqlalchemy_file": {
            "class": "app.core.log_config.SafeTimedRotatingFileHandler",
            "level": SQLALCHEMY_LEVEL,
            "formatter": "file_formatter",
            "filename": SQLALCHEMY_LOG_FILE,
            "when": "midnight",
            "interval": 1,
            "backupCount": 7,
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": True,
        },
        "pdfminer": {
            "handlers": ["file"],
            "level": "WARNING",
            "propagate": False,
        },
        "python_multipart": {
            "handlers": ["file"],
            "level": "WARNING",
            "propagate": False,
        },
        "sqlalchemy.engine": {
            "handlers": ["console", "sqlalchemy_file"],
            "level": SQLALCHEMY_LEVEL,
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}


def setup_logging():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    dictConfig(LOGGING_CONFIG)
    logging.getLogger("app.core.log_config").info("Logging initialized")


def shutdown_logging():
    logging.getLogger("app.core.log_config").info("Shutting down logging")
    logging.shutdown()
