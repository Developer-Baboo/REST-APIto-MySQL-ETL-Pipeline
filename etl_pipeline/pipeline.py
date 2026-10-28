import json
import logging
from typing import Any

import pandas as pd
from sqlalchemy import create_engine

from .client import RestApiClient
from .config import Config


logger = logging.getLogger(__name__)


def transform_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Flatten JSON objects into rows and serialize nested values as JSON."""
    frame = pd.json_normalize(records, sep="_")
    for column in frame.columns:
        frame[column] = frame[column].map(
            lambda value: json.dumps(value, ensure_ascii=False)
            if isinstance(value, (dict, list))
            else value
        )
    return frame


def run_pipeline(config: Config) -> int:
    client = RestApiClient(config)
    records = client.fetch_records()
    if not records:
        logger.info("The API returned no records; MySQL was not changed")
        return 0

    frame = transform_records(records)
    engine = create_engine(config.mysql_url)
    try:
        frame.to_sql(
            name=config.mysql_table,
            con=engine,
            if_exists=config.mysql_if_exists,
            index=False,
            chunksize=1000,
            method="multi",
        )
    finally:
        engine.dispose()

    logger.info("Loaded %s rows into MySQL table %s", len(frame), config.mysql_table)
    return len(frame)
