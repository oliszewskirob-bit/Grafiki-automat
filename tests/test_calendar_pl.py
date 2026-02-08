import unittest
from datetime import date

from scheduler import calendar_pl


class CalendarPLTests(unittest.TestCase):
    def test_month_days_length(self) -> None:
        days = calendar_pl.month_days("2026-02")
        self.assertEqual(len(days), 28)
        self.assertEqual(days[0], date(2026, 2, 1))
        self.assertEqual(days[-1], date(2026, 2, 28))

    def test_weekend(self) -> None:
        self.assertTrue(calendar_pl.is_weekend(date(2026, 1, 3)))  # Saturday
        self.assertFalse(calendar_pl.is_weekend(date(2026, 1, 5)))  # Monday

    def test_fixed_holiday(self) -> None:
        self.assertTrue(calendar_pl.is_holiday(date(2026, 1, 1)))
        self.assertFalse(calendar_pl.is_holiday(date(2026, 1, 2)))

    def test_easter_related_holidays(self) -> None:
        self.assertTrue(calendar_pl.is_holiday(date(2026, 4, 5)))  # Easter Sunday
        self.assertTrue(calendar_pl.is_holiday(date(2026, 4, 6)))  # Easter Monday
        self.assertTrue(calendar_pl.is_holiday(date(2026, 5, 24)))  # Pentecost
        self.assertTrue(calendar_pl.is_holiday(date(2026, 6, 4)))  # Corpus Christi


if __name__ == "__main__":
    unittest.main()
