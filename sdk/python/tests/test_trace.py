from __future__ import annotations

from open_ikc_sdk.trace import ensure_trace_id, generate_trace_id


def test_generate_trace_id_is_23_numeric_digits():
    trace_id = generate_trace_id()
    assert len(trace_id) == 23
    assert trace_id.isdigit()


def test_generate_trace_id_unique_enough():
    ids = {generate_trace_id() for _ in range(1000)}
    assert len(ids) == 1000


def test_ensure_trace_id_reuses_caller_value():
    assert ensure_trace_id("12345678901234567890123") == "12345678901234567890123"


def test_ensure_trace_id_generates_when_empty():
    trace_id = ensure_trace_id(None)
    assert len(trace_id) == 23
    assert trace_id.isdigit()
