"""Input sanitizer — detect prompt injection attempts in input documents."""

from __future__ import annotations

_DEFAULT_INJECTION_PATTERNS: list[str] = [
    "ignore previous instructions",
    "ignore all instructions",
    "disregard your instructions",
    "you are now",
    "act as if",
    "pretend you are",
    "forget everything",
    "system prompt",
    "jailbreak",
    "reveal your prompt",
    "output your instructions",
]


class InputSanitizer:
    """Detect prompt injection and validate input documents.

    Checks:
    1. Document length does not exceed max_length.
    2. Document does not contain known injection patterns (case-insensitive).
    """

    def __init__(
        self,
        max_length: int = 10000,
        injection_patterns: list[str] | None = None,
    ) -> None:
        self.max_length = max_length
        self._patterns: list[str] = (
            injection_patterns
            if injection_patterns is not None
            else _DEFAULT_INJECTION_PATTERNS
        )

    def check(self, text: str) -> tuple[bool, list[str]]:
        """Check document for safety issues.

        Returns (is_safe, list_of_flags).
        """
        flags: list[str] = []

        if len(text) > self.max_length:
            flags.append(
                f"Document exceeds maximum length of {self.max_length} "
                f"characters (got {len(text)})"
            )

        if not text.strip():
            flags.append("Document is empty")

        text_lower = text.lower()
        for pattern in self._patterns:
            if pattern.lower() in text_lower:
                flags.append(f"Potential injection detected: '{pattern}'")

        return (len(flags) == 0, flags)
