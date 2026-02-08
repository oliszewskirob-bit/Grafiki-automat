"""Polish calendar helpers."""

from __future__ import annotations

from datetime import date, timedelta


def _easter_sunday(year: int) -> date:
    """Return Easter Sunday for the given year (Gregorian calendar)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def polish_holidays(year: int) -> set[date]:
    fixed = {
        date(year, 1, 1),
        date(year, 1, 6),
        date(year, 5, 1),
        date(year, 5, 3),
        date(year, 8, 15),
        date(year, 11, 1),
        date(year, 11, 11),
        date(year, 12, 25),
        date(year, 12, 26),
    }
    easter = _easter_sunday(year)
    movable = {
        easter,
        easter + timedelta(days=1),  # Easter Monday
        easter + timedelta(days=49),  # Pentecost (Zielone Swiatki)
        easter + timedelta(days=60),  # Corpus Christi (Boze Cialo)
    }
    return fixed | movable


def is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def is_holiday(day: date) -> bool:
    return day in polish_holidays(day.year)


def month_days(ym: str) -> list[date]:
    year_str, month_str = ym.split("-", 1)
    year = int(year_str)
    month = int(month_str)
    first = date(year, month, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    days: list[date] = []
    current = first
    while current < next_month:
        days.append(current)
        current += timedelta(days=1)
    return days
