import logging
from pythonjsonlogger import jsonlogger
from app.middleware.request_id import request_id_var


class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get() or ""
        return True


def setup_logging():
    root_logger = logging.getLogger()
    root_logger.handlers = []

    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    root_logger.addFilter(RequestIDFilter())
