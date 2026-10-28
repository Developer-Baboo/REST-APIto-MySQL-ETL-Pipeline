import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class Config:
    api_url: str
    api_token: str
    mysql_url: str
    mysql_table: str = "api_records"
    records_key: str = "data"
    next_url_key: str = ""
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    page_param: str = "page"
    page_size_param: str = "per_page"
    page_size: int = 100
    start_page: int = 1
    max_pages: int = 1000
    timeout_seconds: int = 30
    max_retries: int = 5
    mysql_if_exists: str = "append"

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()

        api_url = os.getenv("API_URL", "").strip()
        api_token = os.getenv("API_TOKEN", "").strip()
        mysql_url = os.getenv("MYSQL_URL", "").strip()
        if not api_url:
            raise ValueError("API_URL is required")
        if not api_token:
            raise ValueError("API_TOKEN is required")
        if not mysql_url:
            raise ValueError("MYSQL_URL is required")

        table = os.getenv("MYSQL_TABLE", "api_records").strip()
        if not _IDENTIFIER_PATTERN.fullmatch(table):
            raise ValueError(
                "MYSQL_TABLE must be a simple SQL identifier "
                "(letters, numbers, and underscores)"
            )

        if_exists = os.getenv("MYSQL_IF_EXISTS", "append").strip().lower()
        if if_exists not in {"append", "replace", "fail"}:
            raise ValueError("MYSQL_IF_EXISTS must be append, replace, or fail")

        return cls(
            api_url=api_url,
            api_token=api_token,
            mysql_url=mysql_url,
            mysql_table=table,
            records_key=os.getenv("API_RECORDS_KEY", "data").strip(),
            next_url_key=os.getenv("API_NEXT_URL_KEY", "").strip(),
            auth_header=os.getenv("API_AUTH_HEADER", "Authorization").strip(),
            auth_scheme=os.getenv("API_AUTH_SCHEME", "Bearer").strip(),
            page_param=os.getenv("API_PAGE_PARAM", "page").strip(),
            page_size_param=os.getenv("API_PAGE_SIZE_PARAM", "per_page").strip(),
            page_size=_positive_int("API_PAGE_SIZE", 100),
            start_page=_positive_int("API_START_PAGE", 1),
            max_pages=_positive_int("API_MAX_PAGES", 1000),
            timeout_seconds=_positive_int("API_TIMEOUT_SECONDS", 30),
            max_retries=int(os.getenv("API_MAX_RETRIES", "5")),
            mysql_if_exists=if_exists,
        )

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("API_MAX_RETRIES cannot be negative")
        if self.mysql_if_exists not in {"append", "replace", "fail"}:
            raise ValueError("mysql_if_exists must be append, replace, or fail")
