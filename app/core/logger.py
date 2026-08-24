import logging
from logging.handlers import RotatingFileHandler

from .paths import APP_NAME, logs_dir

MAX_LOG_BYTES = 100 * 1024 * 1024
BACKUP_COUNT = 3


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)
    fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = RotatingFileHandler(
        logs_dir() / "maitranslator.log",
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.captureWarnings(True)
