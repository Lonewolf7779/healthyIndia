import logging
import re
from typing import Any

# Sensitive headers and keywords that must never appear in logs
SENSITIVE_HEADER_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "proxy-authorization",
}

SENSITIVE_KEYWORD_PATTERN = re.compile(
    r"(secret|password|token|api_key|access_token|refresh_token)\s*[=:]\s*['\"]?([^'\"&\s]+)['\"]?",
    re.IGNORECASE,
)


class SensitiveDataFilter(logging.Filter):
    """
    Sanitizes log messages by masking sensitive tokens, passwords, and keys.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = SENSITIVE_KEYWORD_PATTERN.sub(r"\1=***", record.msg)
        return True


def setup_logging(debug: bool = False) -> None:
    """
    Configure application logging with safe filters.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if reconfigured
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        root_logger.addHandler(handler)


def sanitize_headers(headers: dict[str, Any]) -> dict[str, str]:
    """
    Returns a copy of request headers with sensitive values masked.
    """
    sanitized = {}
    for k, v in headers.items():
        if k.lower() in SENSITIVE_HEADER_KEYS:
            sanitized[k] = "***REDACTED***"
        else:
            sanitized[k] = str(v)
    return sanitized
