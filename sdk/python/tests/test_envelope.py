from __future__ import annotations

import pytest

from open_ikc_sdk.envelope import Envelope, parse_envelope
from open_ikc_sdk.errors import OpenIKCProtocolError


def test_parse_envelope_success():
    envelope = parse_envelope('{"errCode": "000000", "errMsg": "success", "data": {"kbId": "kb_1"}, "traceId": "123"}')
    assert envelope.ok
    assert envelope.err_code == "000000"
    assert envelope.data == {"kbId": "kb_1"}
    assert envelope.trace_id == "123"


def test_parse_envelope_business_error():
    envelope = parse_envelope('{"errCode": "100403", "errMsg": "无权限", "data": {}, "traceId": "123"}')
    assert not envelope.ok
    assert envelope.err_msg == "无权限"


def test_parse_envelope_missing_data_defaults_to_empty():
    envelope = parse_envelope('{"errCode": "000000", "errMsg": "success"}')
    assert envelope.ok
    assert envelope.data == {}


def test_parse_envelope_invalid_json_raises_protocol_error():
    with pytest.raises(OpenIKCProtocolError):
        parse_envelope("not-json")


def test_parse_envelope_missing_err_code_raises_protocol_error():
    with pytest.raises(OpenIKCProtocolError):
        parse_envelope('{"errMsg": "success"}')


def test_parse_envelope_non_dict_payload_raises_protocol_error():
    with pytest.raises(OpenIKCProtocolError):
        parse_envelope("[1, 2, 3]")


def test_envelope_is_dataclass():
    envelope = Envelope(err_code="000000", err_msg="success")
    assert envelope.data == {}
