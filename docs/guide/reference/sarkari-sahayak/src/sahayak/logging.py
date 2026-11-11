"""Structured logging. JSON in hosted/CI, pretty console locally."""

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", *, json: bool = False) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,  # request_id, trace_id bound per request
        structlog.processors.add_log_level,
        timestamper,
    ]
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer(ensure_ascii=False)  # keep Devanagari readable
        if json
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[*shared, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )
