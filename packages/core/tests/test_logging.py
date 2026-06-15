"""Logging contract: emits valid JSON to the configured stream."""

from __future__ import annotations

import io
import json

from tp_core.logging import configure_logging, get_logger


def test_emits_parseable_json_with_expected_fields() -> None:
    stream = io.StringIO()
    configure_logging(level="INFO", json_logs=True, stream=stream)

    get_logger("test").info("itinerary_generated", city="Kyoto", days=2)

    line = stream.getvalue().strip()
    record = json.loads(line)  # must be a single valid JSON object
    assert record["event"] == "itinerary_generated"
    assert record["city"] == "Kyoto"
    assert record["days"] == 2
    assert record["level"] == "info"
    assert "timestamp" in record


def test_redacts_pii_from_log_values() -> None:
    stream = io.StringIO()
    configure_logging(level="INFO", json_logs=True, stream=stream)

    get_logger("test").info(
        "user_input", note="reach me at jane.doe@example.com or 555-123-4567"
    )

    record = json.loads(stream.getvalue().strip())
    assert "jane.doe@example.com" not in record["note"]
    assert "555-123-4567" not in record["note"]
    assert "[redacted]" in record["note"]


def test_respects_level_filter() -> None:
    stream = io.StringIO()
    configure_logging(level="WARNING", json_logs=True, stream=stream)

    get_logger("test").info("should_be_filtered")
    get_logger("test").warning("should_appear")

    output = stream.getvalue()
    assert "should_be_filtered" not in output
    assert "should_appear" in output
