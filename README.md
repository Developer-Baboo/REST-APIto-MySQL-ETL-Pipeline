# REST API to MySQL ETL Pipeline

A configurable Python ETL pipeline that extracts JSON records from a token-authenticated REST API, handles pagination and rate limits, flattens the response with pandas, and loads the rows into a MySQL table.

## Features

- Token authentication through a configurable HTTP header (Bearer by default).
- Page-number pagination or a configured next-page URL in the response.
- Retry handling for network errors, HTTP 429 responses, and transient HTTP 5xx responses. Honors the `Retry-After` header when available.
- JSON parsing and flattening with `pandas.json_normalize`; nested objects become columns and nested arrays are stored as JSON strings.
- MySQL loading through SQLAlchemy and PyMySQL.
- Environment-based configuration; credentials are not stored in source code.

## Requirements

- Python 3.10 or newer
- MySQL 8.0 or a compatible MySQL server
- Access to a REST API and a valid API token

## Setup

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `API_URL`, `API_TOKEN`, and `MYSQL_URL`. Create the target MySQL database and grant the configured MySQL user permission to create and write tables. The pipeline creates the target table automatically on its first successful load.

For passwords containing reserved URL characters, percent-encode the password in `MYSQL_URL`.

## Run

Run the pipeline from the project root:

```powershell
python -m etl_pipeline
```

The process logs page counts and load results. Request, configuration, API, and database errors are surfaced and cause a non-zero process exit.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `API_URL` | Required | API endpoint URL |
| `API_TOKEN` | Required | Token sent to the API |
| `API_AUTH_HEADER` | `Authorization` | Name of the authentication header |
| `API_AUTH_SCHEME` | `Bearer` | Prefix before the token; set empty to send the token as-is |
| `API_RECORDS_KEY` | `data` | Dot-separated path to the records array in object responses; a top-level JSON array needs no key |
| `API_NEXT_URL_KEY` | Empty | Dot-separated path to the next-page URL; when set, URL-based pagination is used instead of page numbers |
| `API_PAGE_PARAM` | `page` | Page-number query parameter |
| `API_PAGE_SIZE_PARAM` | `per_page` | Page-size query parameter |
| `API_PAGE_SIZE` | `100` | Requested number of records per page |
| `API_START_PAGE` | `1` | First page number |
| `API_MAX_PAGES` | `1000` | Safety limit; exceeding it raises an error rather than silently truncating results |
| `API_TIMEOUT_SECONDS` | `30` | Per-request timeout |
| `API_MAX_RETRIES` | `5` | Retries after network errors, HTTP 429, or HTTP 5xx |
| `MYSQL_URL` | Required | SQLAlchemy MySQL connection URL |
| `MYSQL_TABLE` | `api_records` | Destination table; must be a simple SQL identifier |
| `MYSQL_IF_EXISTS` | `append` | pandas table behavior: `append`, `replace`, or `fail` |

Page-number mode ends when the API returns an empty records array. Next-URL mode ends when the configured next URL is missing or null. Adapt these settings to the API's actual response shape and pagination contract.

`append` preserves existing rows but does not deduplicate them; arrange deduplication or idempotency according to the source API's record identifiers and your data-retention requirements. `replace` recreates the destination table on each run.

## Example response shapes

Page-number mode with the default records key:

```json
{
  "data": [
    {"id": 1, "name": "Example"}
  ]
}
```

Next-URL mode, configured with `API_RECORDS_KEY=results` and `API_NEXT_URL_KEY=paging.next`:

```json
{
  "results": [{"id": 1, "name": "Example"}],
  "paging": {"next": "https://api.example.com/v1/items?cursor=next"}
}
```

## Tests

Run the unit tests from the project root:

```powershell
python -m unittest discover -s tests -v
```

The tests cover pagination, auth-header setup, rate-limit retries, request failures, response validation, and JSON transformation. They do not require a live API or MySQL server.
