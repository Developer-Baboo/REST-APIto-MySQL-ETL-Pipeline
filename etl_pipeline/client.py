import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

import requests

from .config import Config


logger = logging.getLogger(__name__)


def _get_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"Response does not contain configured key path: {path}")
        current = current[part]
    return current


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


class RestApiClient:
    def __init__(
        self,
        config: Config,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        token_value = (
            f"{config.auth_scheme} {config.api_token}".strip()
            if config.auth_scheme
            else config.api_token
        )
        self.session.headers.update({config.auth_header: token_value})
        self._sleep = sleep

    def _request_json(self, url: str, params: dict[str, int] | None) -> Any:
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.config.timeout_seconds,
                )
            except requests.RequestException:
                if attempt >= self.config.max_retries:
                    raise
                delay = min(2**attempt, 60)
                logger.warning("API request failed; retrying in %s seconds", delay)
                self._sleep(delay)
                continue

            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt >= self.config.max_retries:
                    response.raise_for_status()
                delay = _retry_after_seconds(response.headers.get("Retry-After"))
                if delay is None:
                    delay = min(2**attempt, 60)
                logger.warning(
                    "API returned HTTP %s; retrying in %s seconds",
                    response.status_code,
                    delay,
                )
                self._sleep(delay)
                continue

            response.raise_for_status()
            return response.json()

        raise RuntimeError("API request exhausted retries without a response")

    def _records_from(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            records = payload
        elif self.config.records_key:
            records = _get_path(payload, self.config.records_key)
        else:
            raise ValueError(
                "Configure API_RECORDS_KEY for object responses, "
                "or return a JSON array"
            )

        if not isinstance(records, list):
            raise ValueError("The configured API records value must be a JSON array")
        if any(not isinstance(record, dict) for record in records):
            raise ValueError("Every API record must be a JSON object")
        return records

    def fetch_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        url = self.config.api_url

        for page_index in range(self.config.max_pages):
            params = None
            if not self.config.next_url_key:
                params = {
                    self.config.page_param: self.config.start_page + page_index,
                    self.config.page_size_param: self.config.page_size,
                }

            payload = self._request_json(url, params)
            page_records = self._records_from(payload)
            records.extend(page_records)
            logger.info("Fetched page %s: %s records", page_index + 1, len(page_records))

            if self.config.next_url_key:
                next_url = _get_path(payload, self.config.next_url_key)
                if not next_url:
                    return records
                if not isinstance(next_url, str):
                    raise ValueError("The configured next-page value must be a URL string")
                url = next_url
            elif not page_records:
                return records

        raise RuntimeError(
            f"API_MAX_PAGES ({self.config.max_pages}) reached; "
            "increase the limit if more pages are expected"
        )
