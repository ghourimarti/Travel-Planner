"""Application exceptions.

Ports the demo's ``CustomException`` (which captures the originating file/line)
and hardens it to behave sanely when constructed outside an ``except`` block.
"""

from __future__ import annotations

import sys


class CustomException(Exception):
    """Wraps an error with the source file/line where it occurred."""

    def __init__(self, message: str, error_detail: Exception | None = None) -> None:
        self.error_message = self._format(message, error_detail)
        super().__init__(self.error_message)

    @staticmethod
    def _format(message: str, error_detail: Exception | None) -> str:
        exc_tb = sys.exc_info()[2]
        if exc_tb is not None:
            file_name = exc_tb.tb_frame.f_code.co_filename
            line_number: int | str = exc_tb.tb_lineno
        else:
            file_name, line_number = "unknown", "unknown"
        return f"{message} | error={error_detail} | file={file_name} | line={line_number}"

    def __str__(self) -> str:
        return self.error_message
