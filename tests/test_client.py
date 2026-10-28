import unittest
from unittest.mock import Mock

import requests

from etl_pipeline.client import RestApiClient, _retry_after_seconds
from etl_pipeline.config import Config


def make_config(**overrides: object) -> Config:
    values: dict[str, object] = {
        "api_url": "https://api.example.test/items",
        "api_token": "test-token",
        "mysql_url": "mysql+pymysql://user:pass@localhost/db",
    }
    values.update(overrides)
    return Config(**values)  # type: ignore[arg-type]


class RestApiClientTests(unittest.TestCase):
    def test_paginates_until_empty_page_and_sets_auth_header(self) -> None:
        session = Mock()
        first = Mock(status_code=200, headers={})
        first.json.return_value = {"data": [{"id": 1}]}
        second = Mock(status_code=200, headers={})
        second.json.return_value = {"data": []}
        session.get.side_effect = [first, second]

        client = RestApiClient(make_config(), session=session, sleep=Mock())
        records = client.fetch_records()

        self.assertEqual(records, [{"id": 1}])
        self.assertEqual(session.headers.update.call_args.args[0]["Authorization"], "Bearer test-token")
        self.assertEqual(session.get.call_args_list[0].kwargs["params"], {"page": 1, "per_page": 100})
        self.assertEqual(session.get.call_args_list[1].kwargs["params"], {"page": 2, "per_page": 100})

    def test_follows_configured_next_link(self) -> None:
        session = Mock()
        first = Mock(status_code=200, headers={})
        first.json.return_value = {
            "results": [{"id": 1}],
            "paging": {"next": "https://api.example.test/items?cursor=next"},
        }
        second = Mock(status_code=200, headers={})
        second.json.return_value = {"results": [{"id": 2}], "paging": {"next": None}}
        session.get.side_effect = [first, second]

        client = RestApiClient(
            make_config(records_key="results", next_url_key="paging.next"),
            session=session,
            sleep=Mock(),
        )

        self.assertEqual(client.fetch_records(), [{"id": 1}, {"id": 2}])
        self.assertEqual(session.get.call_args_list[1].args[0], "https://api.example.test/items?cursor=next")
        self.assertIsNone(session.get.call_args_list[1].kwargs["params"])

    def test_retries_rate_limit_using_retry_after(self) -> None:
        session = Mock()
        rate_limited = Mock(status_code=429, headers={"Retry-After": "3"})
        success = Mock(status_code=200, headers={})
        success.json.return_value = []
        session.get.side_effect = [rate_limited, success]
        sleep = Mock()

        client = RestApiClient(make_config(max_retries=1), session=session, sleep=sleep)
        self.assertEqual(client.fetch_records(), [])
        sleep.assert_called_once_with(3.0)

    def test_invalid_record_shape_is_reported(self) -> None:
        session = Mock()
        response = Mock(status_code=200, headers={})
        response.json.return_value = {"data": "not-an-array"}
        session.get.return_value = response
        client = RestApiClient(make_config(), session=session, sleep=Mock())

        with self.assertRaisesRegex(ValueError, "must be a JSON array"):
            client.fetch_records()

    def test_request_exception_is_retried_then_propagated(self) -> None:
        session = Mock()
        session.get.side_effect = requests.ConnectionError("offline")
        sleep = Mock()
        client = RestApiClient(make_config(max_retries=1), session=session, sleep=sleep)

        with self.assertRaises(requests.ConnectionError):
            client.fetch_records()
        sleep.assert_called_once_with(1)


class RetryAfterTests(unittest.TestCase):
    def test_parses_seconds_and_rejects_invalid_values(self) -> None:
        self.assertEqual(_retry_after_seconds("2.5"), 2.5)
        self.assertIsNone(_retry_after_seconds("not-a-date"))


if __name__ == "__main__":
    unittest.main()
