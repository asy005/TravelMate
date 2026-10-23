import unittest

from app.services.plan_orchestrator import _filter_foreign_destination_highlights


class TestDestinationHighlightFiltering(unittest.TestCase):
    def test_removes_highlight_for_another_known_destination(self):
        highlights = [
            "Ganpatipule beaches are a relaxing place to spend the afternoon.",
            "Tiruchirappalli has Rock Fort and a Railway Museum worth visiting.",
            "Gokarna is a peaceful beach destination for a coastal holiday.",
        ]
        result = _filter_foreign_destination_highlights(
            "Ganpatipule",
            highlights,
            ["Tiruchirappalli", "Gokarna", "Ganpatipule"],
        )
        self.assertEqual(
            result,
            ["Ganpatipule beaches are a relaxing place to spend the afternoon."],
        )

    def test_does_not_match_destination_name_inside_another_word(self):
        highlights = ["A great goal is to enjoy the coast and relax by the sea."]
        result = _filter_foreign_destination_highlights("Ganpatipule", highlights, ["Goa"])
        self.assertEqual(result, highlights)

    def test_empty_or_short_highlights_are_discarded(self):
        result = _filter_foreign_destination_highlights(
            "Ganpatipule", ["Too short", None], ["Gokarna"]
        )
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
