from __future__ import annotations

import pytest

from open_ikc_sdk.errors import (
    OpenIKCBusinessError,
    OpenIKCConflictError,
    OpenIKCError,
    OpenIKCForbiddenError,
    OpenIKCMethodNotAllowedError,
    OpenIKCNotImplementedError,
    OpenIKCNotFoundError,
    OpenIKCSystemError,
    OpenIKCUnauthorizedError,
    OpenIKCValidationError,
    exception_from_code,
)


@pytest.mark.parametrize(
    ("err_code", "expected"),
    [
        ("100001", OpenIKCValidationError),
        ("100401", OpenIKCUnauthorizedError),
        ("100403", OpenIKCForbiddenError),
        ("100404", OpenIKCNotFoundError),
        ("100405", OpenIKCMethodNotAllowedError),
        ("100409", OpenIKCConflictError),
        ("501001", OpenIKCNotImplementedError),
        ("999999", OpenIKCSystemError),
    ],
)
def test_error_code_mapping(err_code, expected):
    exc = exception_from_code(err_code, "msg", trace_id="123")
    assert isinstance(exc, expected)
    assert exc.err_code == err_code
    assert exc.err_msg == "msg"
    assert exc.trace_id == "123"


def test_unknown_code_maps_to_business_error():
    exc = exception_from_code("200010", "接入失败")
    assert isinstance(exc, OpenIKCBusinessError)
    assert exc.err_code == "200010"


def test_all_api_errors_share_base():
    exc = exception_from_code("100403", "无权限")
    assert isinstance(exc, OpenIKCError)
