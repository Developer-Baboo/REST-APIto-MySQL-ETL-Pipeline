import unittest

import pandas as pd

from etl_pipeline.pipeline import transform_records


class TransformRecordsTests(unittest.TestCase):
    def test_flattens_objects_and_serializes_nested_values(self) -> None:
        result = transform_records(
            [
                {
                    "id": 1,
                    "profile": {"name": "Ada"},
                    "events": [{"type": "created", "source": "api"}],
                }
            ]
        )

        self.assertEqual(result.loc[0, "profile_name"], "Ada")
        self.assertEqual(
            result.loc[0, "events"],
            '[{"type": "created", "source": "api"}]',
        )

    def test_empty_input_returns_empty_dataframe(self) -> None:
        self.assertIsInstance(transform_records([]), pd.DataFrame)
        self.assertTrue(transform_records([]).empty)


if __name__ == "__main__":
    unittest.main()
