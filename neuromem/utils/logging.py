"""
Structured logging utilities for NeuroMem SDK.

Provides consistent, structured logging across the entire SDK with
PII redaction and JSON formatting support.
"""

import logging
import re
from typing import Any, Dict, Optional
import json
from datetime import datetime


# PII patterns to redact
PII_PATTERNS = [
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL_REDACTED]'),  # Email
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN_REDACTED]'),  # SSN
    (re.compile(r'\b\d{3}-\d{3}-\d{4}\b'), '[PHONE_REDACTED]'),  # Phone
    (re.compile(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'), '[CARD_REDACTED]'),  # Credit card
]


class PIIRedactingFormatter(logging.Formatter):
    """Formatter that redacts PII from log messages."""

    def format(self, record: logging.LogRecord) -> str:
        # Redact PII from message
        msg = super().format(record)
        for pattern, replacement in PII_PATTERNS:
            msg = pattern.sub(replacement, msg)
        return msg


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add extra fields
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'trace_id'):
            log_data['trace_id'] = record.trace_id
        if hasattr(record, 'task_type'):
            log_data['task_type'] = record.task_type

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Redact PII
        msg_str = json.dumps(log_data)
        for pattern, replacement in PII_PATTERNS:
            msg_str = pattern.sub(replacement, msg_str)

        return msg_str


def get_logger(name: str, json_format: bool = False, level: int = logging.INFO) -> logging.Logger:
    """
    Get a configured logger for NeuroMem.

    Args:
        name: Logger name (usually __name__)
        json_format: Use JSON formatter (default: False)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Memory retrieved", extra={'user_id': 'user_123', 'count': 5})
    """
    logger = logging.getLogger(f"neuromem.{name}")

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Console handler
    handler = logging.StreamHandler()
    handler.setLevel(level)

    # Choose formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = PIIRedactingFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def sanitize_for_logging(data: Any) -> Any:
    """
    Sanitize data for logging by redacting PII.

    Args:
        data: Data to sanitize (str, dict, list, etc.)

    Returns:
        Sanitized data
    """
    if isinstance(data, str):
        for pattern, replacement in PII_PATTERNS:
            data = pattern.sub(replacement, data)
        return data

    elif isinstance(data, dict):
        return {k: sanitize_for_logging(v) for k, v in data.items()}

    elif isinstance(data, list):
        return [sanitize_for_logging(item) for item in data]

    else:
        return data


# Default logger for the SDK
default_logger = get_logger('core')
