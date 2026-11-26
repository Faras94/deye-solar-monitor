"""Unit tests for DeyeCloudClient and credential-safe logging."""

from __future__ import annotations

import hashlib
import json
import logging

import httpx
import pytest

from app.clients.deye_client import (
    DeyeAuthError,
    DeyeCloudClient,
    DeyeConfigError,
    DeyeRateLimitError,
)
from app.logging_utils import CredentialRedactingFilter


def test_password_hashing_lowercase_sha256():
    expected = hashlib.sha256(b"MySecretPass!").hexdigest().lower()
    assert DeyeCloudClient.hash_password("MySecretPass!") == expected
    assert DeyeCloudClient.hash_password("MySecretPass!").islower()


def test_missing_credentials_raises_config_error():
    client = DeyeCloudClient(
        base_url="https://india-developer.deyecloud.com",
        app_id="",
        app_secret="",
        email="",
        password="",
    )
    with pytest.raises(DeyeConfigError):
        client.obtain_token()


def test_token_acquisition_and_auto_refresh_on_expiry():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path, request.headers.get("Authorization")))
        if request.url.path == "/v1.0/account/token":
            body = json.loads(request.content.decode("utf-8"))
            assert body["password"] == hashlib.sha256(b"secret-pw").hexdigest().lower()
            token = "tok_1" if len(calls) == 1 else "tok_2"
            return httpx.Response(200, json={"code": "1000000", "success": True, "accessToken": token, "expiresIn": 3600})

        if request.url.path == "/v1.0/device/latest":
            auth = request.headers.get("Authorization")
            if auth == "Bearer tok_1":
                return httpx.Response(200, json={"code": "2101018", "success": False, "msg": "token expired"})
            return httpx.Response(
                200,
                json={
                    "code": "1000000",
                    "success": True,
                    "deviceDataList": [{"deviceSn": "260605A076", "deviceState": 1, "dataList": []}],
                },
            )
        return httpx.Response(404)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = DeyeCloudClient(
        base_url="https://india-developer.deyecloud.com",
        app_id="12345",
        app_secret="app-sec",
        email="user@example.com",
        password="secret-pw",
        http_client=http_client,
    )

    result = client.get_device_latest(["260605A076"])
    assert len(result) == 1
    assert result[0]["deviceSn"] == "260605A076"
    assert [c[0] for c in calls] == [
        "/v1.0/account/token",
        "/v1.0/device/latest",
        "/v1.0/account/token",
        "/v1.0/device/latest",
    ]


def test_rate_limit_raises_deye_rate_limit_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/account/token":
            return httpx.Response(200, json={"code": "1000000", "success": True, "accessToken": "tok_1"})
        return httpx.Response(429, json={"msg": "Too Many Requests"})

    client = DeyeCloudClient(
        base_url="https://india-developer.deyecloud.com",
        app_id="12345",
        app_secret="app-sec",
        email="user@example.com",
        password="secret-pw",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(DeyeRateLimitError):
        client.get_device_latest(["260605A076"])


def test_auth_failure_raises_deye_auth_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "2101014", "success": False, "msg": "invalid appSecret"})

    client = DeyeCloudClient(
        base_url="https://india-developer.deyecloud.com",
        app_id="12345",
        app_secret="bad-sec",
        email="user@example.com",
        password="secret-pw",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(DeyeAuthError):
        client.obtain_token()


def test_credential_redacting_filter_scrubs_secrets():
    redactor = CredentialRedactingFilter(extra_secrets=["my-super-secret"])
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='Authorization: Bearer abc.def.ghi appSecret="my-super-secret" password=rawpass',
        args=(),
        exc_info=None,
    )
    redactor.filter(record)
    assert "abc.def.ghi" not in record.msg
    assert "my-super-secret" not in record.msg
    assert "rawpass" not in record.msg
    assert "[REDACTED]" in record.msg
