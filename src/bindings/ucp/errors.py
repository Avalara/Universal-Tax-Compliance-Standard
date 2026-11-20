# Copyright 2026 Avalara, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Domain failures the UCP binding returns as messages."""

from __future__ import annotations


class BindingError(Exception):
    """A determination failure that must not become a guessed rate."""

    def __init__(
        self,
        code: str,
        content: str,
        *,
        severity: str = "recoverable",
        path: str | None = None,
    ) -> None:
        super().__init__(content)
        self.code = code
        self.content = content
        self.severity = severity
        self.path = path

    def message(self) -> dict[str, str]:
        body = {
            "type": "error",
            "code": self.code,
            "content": self.content,
            "severity": self.severity,
        }
        if self.path:
            body["path"] = self.path
        return body
