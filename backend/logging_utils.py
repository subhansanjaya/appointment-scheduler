import logging


def log_debug(logger: logging.Logger, *values: object) -> None:
    logger.debug(" ".join(str(value) for value in values))
