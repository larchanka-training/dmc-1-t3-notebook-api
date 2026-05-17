import logging
import sys


def setup_logging(log_level: str) -> None:
    """
    Configures standard Python logging infrastructure.
    Prepares the application layout for potential JSON log-routing structures.
    """
    root_logger = logging.getLogger()

    # Reset existing handlers to prevent duplicate formatting pipelines
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    console_handler.setFormatter(formatter)

    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(console_handler)

    # Suppress verbose third-party log noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
