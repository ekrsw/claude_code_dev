import logging
import sys
from typing import Any, Dict

import structlog
from structlog.stdlib import LoggerFactory

from app.core.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application"""
    
    # Set up standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )
    
    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if settings.LOG_FORMAT == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance"""
    return structlog.get_logger(name)


class LoggerAdapter:
    """Adapter for logging with context"""
    
    def __init__(self, logger: structlog.BoundLogger):
        self.logger = logger
    
    def bind(self, **kwargs: Any) -> "LoggerAdapter":
        """Bind context to logger"""
        return LoggerAdapter(self.logger.bind(**kwargs))
    
    def info(self, msg: str, **kwargs: Any) -> None:
        """Log info message"""
        self.logger.info(msg, **kwargs)
    
    def error(self, msg: str, **kwargs: Any) -> None:
        """Log error message"""
        self.logger.error(msg, **kwargs)
    
    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log warning message"""
        self.logger.warning(msg, **kwargs)
    
    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log debug message"""
        self.logger.debug(msg, **kwargs)