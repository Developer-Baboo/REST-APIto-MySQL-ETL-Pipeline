import logging

from .config import Config
from .pipeline import run_pipeline


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.from_env()
    row_count = run_pipeline(config)
    logging.getLogger(__name__).info("ETL complete: loaded %s rows", row_count)


if __name__ == "__main__":
    main()
