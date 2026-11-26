"""Pure HTTP client for the DeyeCloud OpenAPI v1.0.

Keeps all DeyeCloud transport, SHA-256 authentication, token caching/refresh,
and rate-limit/error handling separate from business logic and persistence.
"""

from __future__ import annotations

import hashlib
import logging
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


class DeyeAPIError(Exception):
    """Base exception for DeyeCloud API failures."""

    def __init__(self, message: str, code: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class DeyeConfigError(DeyeAPIError):
    """Raised when required DeyeCloud credentials are missing."""


class DeyeAuthError(DeyeAPIError):
    """Raised when DeyeCloud authentication fails."""


class DeyeTokenExpiredError(DeyeAPIError):
    """Raised when DeyeCloud access token is expired or invalid."""


class DeyeRateLimitError(DeyeAPIError):
    """Raised when DeyeCloud rate limit (HTTP 429 or quota code) is hit."""


class DeyeUnavailableError(DeyeAPIError):
    """Raised on network/timeout/5xx errors from DeyeCloud."""


class DeyeCloudClient:
    """Thread-safe DeyeCloud Developer OpenAPI v1.0 client."""

    # Known DeyeCloud error codes for token expiration / auth / rate limit
    _TOKEN_EXPIRED_CODES = {"2101018", "2101019", "1000008", "401"}
    _AUTH_ERROR_CODES = {"2101013", "2101014", "2101015", "2101016", "2101017", "1000003"}
    _RATE_LIMIT_CODES = {"1000010", "2101020", "429"}

    def __init__(
        self,
        base_url: str,
        app_id: str,
        app_secret: str,
        email: str,
        password: str,
        company_id: int = 0,
        timeout_seconds: float = 20.0,
        http_client: Optional[httpx.Client] = None,
        token_loader: Optional[Callable[[], Optional[Tuple[str, float]]]] = None,
        token_saver: Optional[Callable[[str, float], None]] = None,
        call_logger: Optional[
            Callable[[str, str, Optional[int], bool, float, Optional[str]], None]
        ] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.app_id = app_id.strip()
        self.app_secret = app_secret.strip()
        self.email = email.strip()
        self.password = password
        self.company_id = company_id
        self.timeout_seconds = timeout_seconds

        self._http = http_client or httpx.Client(timeout=timeout_seconds)
        self._owns_http = http_client is None
        self._token_lock = threading.Lock()
        self._token_loader = token_loader
        self._token_saver = token_saver
        self._call_logger = call_logger
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        if self._token_loader is not None:
            loaded = self._token_loader()
            if loaded is not None:
                tok, exp_epoch = loaded
                if tok and exp_epoch > (time.time() + 60.0):
                    self._access_token = tok
                    self._token_expires_at = exp_epoch

    def close(self) -> None:
        """Close owned HTTP client."""
        if self._owns_http:
            self._http.close()

    @staticmethod
    def hash_password(password: str) -> str:
        """Return lowercase SHA-256 hex digest as required by DeyeCloud /v1.0/account/token."""
        return hashlib.sha256(password.encode("utf-8")).hexdigest().lower()

    def _ensure_credentials(self) -> None:
        if not (self.app_id and self.app_secret and self.email and self.password):
            raise DeyeConfigError(
                "DeyeCloud credentials are incomplete. Set DEYE_APP_ID, DEYE_APP_SECRET, "
                "DEYE_EMAIL, and DEYE_PASSWORD in the backend .env file."
            )

    def _has_valid_cached_token(self) -> bool:
        return bool(self._access_token) and time.time() < (self._token_expires_at - 60.0)

    def _record_call(
        self,
        method: str,
        endpoint: str,
        status_code: Optional[int],
        success: bool,
        started: float,
        error_message: Optional[str] = None,
    ) -> None:
        if self._call_logger is None:
            return
        duration_ms = round((time.monotonic() - started) * 1000.0, 2)
        try:
            self._call_logger(method, endpoint, status_code, success, duration_ms, error_message)
        except Exception:
            logger.debug("Ignoring call_logger failure for %s", endpoint)

    def obtain_token(self, force_refresh: bool = False) -> str:
        """Authenticate with DeyeCloud and cache the accessToken."""
        self._ensure_credentials()
        with self._token_lock:
            if not force_refresh and self._has_valid_cached_token():
                assert self._access_token is not None
                return self._access_token

            path = "/v1.0/account/token"
            url = f"{self.base_url}{path}"
            payload: Dict[str, Any] = {
                "appSecret": self.app_secret,
                "email": self.email,
                "password": self.hash_password(self.password),
            }
            if self.company_id and self.company_id > 0:
                payload["companyId"] = self.company_id

            started = time.monotonic()
            status_code: Optional[int] = None
            try:
                response = self._http.post(
                    url,
                    params={"appId": self.app_id},
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                status_code = response.status_code
                data = self._parse_response(response, is_auth=True)
            except httpx.TimeoutException as exc:
                self._record_call("POST", path, status_code, False, started, str(exc))
                raise DeyeUnavailableError(f"DeyeCloud token request timed out: {exc}") from exc
            except httpx.HTTPError as exc:
                self._record_call("POST", path, status_code, False, started, str(exc))
                raise DeyeUnavailableError(f"DeyeCloud token network error: {exc}") from exc
            except DeyeAPIError as exc:
                self._record_call("POST", path, status_code, False, started, str(exc))
                raise

            token = data.get("accessToken") or data.get("access_token")
            if not token:
                self._record_call("POST", path, status_code, False, started, "Missing accessToken in response")
                raise DeyeAuthError("DeyeCloud token response did not include accessToken.")

            self._record_call("POST", path, status_code, True, started, None)

            expires_in = float(data.get("expiresIn") or 5184000)
            self._access_token = str(token)
            self._token_expires_at = time.time() + expires_in
            if self._token_saver is not None:
                self._token_saver(self._access_token, self._token_expires_at)
            logger.info("Obtained DeyeCloud access token (expires in %.0fs).", expires_in)
            return self._access_token

    def _parse_response(self, response: httpx.Response, is_auth: bool = False) -> Dict[str, Any]:
        if response.status_code == 429:
            raise DeyeRateLimitError(
                "DeyeCloud API rate limit exceeded (HTTP 429).",
                code="429",
                status_code=429,
            )
        if response.status_code == 401:
            if is_auth:
                raise DeyeAuthError("DeyeCloud authentication failed (HTTP 401).", status_code=401)
            raise DeyeTokenExpiredError("DeyeCloud access token expired or unauthorized.", status_code=401)
        if response.status_code >= 500:
            raise DeyeUnavailableError(
                f"DeyeCloud server error (HTTP {response.status_code}).",
                status_code=response.status_code,
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise DeyeAPIError(
                f"Invalid JSON from DeyeCloud (HTTP {response.status_code}).",
                status_code=response.status_code,
            ) from exc

        if not isinstance(body, dict):
            raise DeyeAPIError("Unexpected non-object JSON response from DeyeCloud.")

        code = str(body.get("code")) if body.get("code") is not None else None
        success = body.get("success")
        msg = str(body.get("msg") or body.get("message") or "")

        # DeyeCloud OpenAPI v1.0 uses code == "1000000" or "0" or success == True for success
        is_ok = success is True or code in {"1000000", "0"} or (success is None and code is None and response.is_success)
        if not is_ok:
            lower_msg = msg.lower()
            if code in self._RATE_LIMIT_CODES or "rate limit" in lower_msg or "too many" in lower_msg:
                raise DeyeRateLimitError(msg or "DeyeCloud API rate limit exceeded.", code=code, status_code=response.status_code)
            if not is_auth and (code in self._TOKEN_EXPIRED_CODES or "token" in lower_msg and "expir" in lower_msg):
                raise DeyeTokenExpiredError(msg or "DeyeCloud token expired.", code=code, status_code=response.status_code)
            if is_auth or code in self._AUTH_ERROR_CODES or "password" in lower_msg or "appsecret" in lower_msg:
                raise DeyeAuthError(msg or f"DeyeCloud authentication failed (code={code}).", code=code, status_code=response.status_code)
            raise DeyeAPIError(msg or f"DeyeCloud API error (code={code}).", code=code, status_code=response.status_code)

        return body

    def _post_authenticated(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an authenticated POST request with token refresh and backoff on 429/5xx."""
        token = self.obtain_token(force_refresh=False)
        token_refreshed = False
        max_attempts = 3

        for attempt in range(max_attempts):
            url = f"{self.base_url}{path}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            started = time.monotonic()
            status_code: Optional[int] = None
            try:
                response = self._http.post(url, json=payload, headers=headers)
                status_code = response.status_code
                parsed = self._parse_response(response, is_auth=False)
                self._record_call("POST", path, status_code, True, started, None)
                return parsed
            except DeyeTokenExpiredError as exc:
                self._record_call("POST", path, status_code, False, started, str(exc))
                if not token_refreshed:
                    logger.warning("DeyeCloud token expired; refreshing and retrying %s.", path)
                    token = self.obtain_token(force_refresh=True)
                    token_refreshed = True
                    continue
                raise
            except (DeyeRateLimitError, DeyeUnavailableError) as exc:
                self._record_call("POST", path, status_code, False, started, str(exc))
                if attempt < max_attempts - 1:
                    delay = (0.5 * (2**attempt)) + random.uniform(0.05, 0.25)
                    logger.warning("Transient DeyeCloud error on %s (%s); retrying in %.2fs.", path, exc, delay)
                    time.sleep(delay)
                    continue
                raise
            except DeyeAPIError as exc:
                self._record_call("POST", path, status_code, False, started, str(exc))
                raise
            except httpx.TimeoutException as exc:
                self._record_call("POST", path, status_code, False, started, str(exc))
                if attempt < max_attempts - 1:
                    delay = (0.5 * (2**attempt)) + random.uniform(0.05, 0.25)
                    time.sleep(delay)
                    continue
                raise DeyeUnavailableError(f"DeyeCloud request to {path} timed out: {exc}") from exc
            except httpx.HTTPError as exc:
                self._record_call("POST", path, status_code, False, started, str(exc))
                raise DeyeUnavailableError(f"DeyeCloud network error on {path}: {exc}") from exc

        raise DeyeUnavailableError(f"DeyeCloud request to {path} failed after retries.")

    def get_station_list(self, page: int = 1, size: int = 50) -> List[Dict[str, Any]]:
        """POST /v1.0/station/list - List solar stations on the account."""
        data = self._post_authenticated("/v1.0/station/list", {"page": page, "size": size})
        return list(data.get("stationList") or data.get("list") or [])

    def get_station_devices(
        self, station_ids: List[int], page: int = 1, size: int = 50
    ) -> List[Dict[str, Any]]:
        """POST /v1.0/station/device - List devices bound to given station IDs."""
        if not station_ids:
            return []
        data = self._post_authenticated(
            "/v1.0/station/device",
            {"stationIds": station_ids, "page": page, "size": size},
        )
        return list(data.get("deviceListItems") or data.get("deviceList") or [])

    def get_device_latest(self, device_sns: List[str]) -> List[Dict[str, Any]]:
        """POST /v1.0/device/latest - Fetch latest telemetry for up to 10 devices per batch."""
        results: List[Dict[str, Any]] = []
        for idx in range(0, len(device_sns), 10):
            batch = device_sns[idx : idx + 10]
            if not batch:
                continue
            data = self._post_authenticated("/v1.0/device/latest", {"deviceList": batch})
            items = data.get("deviceDataList") or data.get("list") or []
            results.extend(items)
        return results

    def get_device_measure_points(
        self, device_sn: str, device_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """POST /v1.0/device/measurePoints - Retrieve supported measurement points for a device."""
        payload: Dict[str, Any] = {"deviceSn": device_sn}
        if device_type:
            payload["deviceType"] = device_type
        data = self._post_authenticated("/v1.0/device/measurePoints", payload)
        raw_points = data.get("measurePoints") or data.get("list") or []
        normalized: List[Dict[str, Any]] = []
        for item in raw_points:
            if isinstance(item, str):
                normalized.append({"key": item, "name": item, "unit": None})
            elif isinstance(item, dict):
                key = item.get("key") or item.get("measurePoint") or item.get("code") or ""
                if key:
                    normalized.append(
                        {
                            "key": str(key),
                            "name": item.get("name") or item.get("desc") or str(key),
                            "unit": item.get("unit"),
                        }
                    )
        return normalized

    def get_device_history(
        self,
        device_sn: str,
        start_at: str,
        end_at: str,
        granularity: int = 2,
        measure_points: Optional[List[str]] = None,
        device_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """POST /v1.0/device/history - Query historical telemetry for a device."""
        payload: Dict[str, Any] = {
            "deviceSn": device_sn,
            "granularity": granularity,
            "startAt": start_at,
            "endAt": end_at,
        }
        if device_type:
            payload["deviceType"] = device_type
        if measure_points:
            payload["measurePoints"] = measure_points
        data = self._post_authenticated("/v1.0/device/history", payload)
        return list(data.get("dataList") or data.get("list") or [])
