"""Logging configuration with automatic credential and token redaction."""

import logging
import re
from typing import Iterable


class CredentialRedactingFilter(logging.Filter):
    """Redacts secrets, passwords, and bearer tokens from log records."""

    _PATTERNS: Iterable[tuple[re.Pattern[str], str]] = (
        (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE), r"\1[REDACTED]"),
        (
            re.compile(
                r'("(?:appSecret|password|accessToken|access_token|refreshToken)"\s*:\s*")[^"]*(")',
                re.IGNORECASE,
            ),
            r"\1[REDACTED]\2",
        ),
        (
            re.compile(
                r"((?:appSecret|password|accessToken|access_token)=)[^\s&,]+",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]",
        ),
    )

    def __init__(self, extra_secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self._extra_secrets = [s for s in extra_secrets if s and len(s) >= 4]

    def _redact(self, text: str) -> str:
        for pattern, replacement in self._PATTERNS:
            text = pattern.sub(replacement, text)
        for secret in self._extra_secrets:
            if secret in text:
                text = text.replace(secret, "[REDACTED]")
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._redact(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._redact(a) if isinstance(a, str) else a for a in record.args
                )
        return True


def configure_logging(level: str = "INFO", extra_secrets: Iterable[str] = ()) -> None:
    """Configure root logger with credential redaction filter."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(handler)

    redactor = CredentialRedactingFilter(extra_secrets=extra_secrets)
    for handler in root.handlers:
        handler.filters = [f for f in handler.filters if not isinstance(f, CredentialRedactingFilter)]
        handler.addFilter(redactor)
