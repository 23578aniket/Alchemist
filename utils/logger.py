# utils/logger.py
import logging
import sys


def setup_logger(name, level=logging.INFO):
    """
    Sets up a standardized logger for agents and services.
    Logs to stdout, which Docker captures.
    """
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Prevent duplicate handlers if called multiple times for the same logger name
    if not logger.handlers:
        logger.addHandler(handler)
    return logger


