import unittest

from reference_app import summarize_scores


class CalculatorTests(unittest.TestCase):
    def test_summarize_scores_is_stable(self) -> None:
        self.assertEqual(
            summarize_scores([90, 100, 95]),
            {
                "count": 3,
                "minimum": 90,
                "maximum": 100,
                "average": 95.0,
            },
        )

    def test_summarize_scores_handles_empty_input(self) -> None:
        self.assertEqual(
            summarize_scores([]),
            {
                "count": 0,
                "minimum": 0,
                "maximum": 0,
                "average": 0.0,
            },
        )


if __name__ == "__main__":
    unittest.main()
