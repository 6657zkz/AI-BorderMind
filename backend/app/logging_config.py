import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_VERSION = "0.2.0"
LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / f"{APP_VERSION}_logs.txt"


def configure_logging() -> None:
    logger = logging.getLogger("chuhai")
    if logger.handlers:
        return
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.propagate = False


configure_logging()
logger = logging.getLogger("chuhai")
