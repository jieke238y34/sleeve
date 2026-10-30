"""The calendar maths behind the seasons and holidays looks: dates resolve to the right look, or to none."""

import datetime as dt

from sleeve import seasons


def day(y, m, d):
    return dt.date(y, m, d)


def test_seasons_follow_the_calendar():
    assert seasons.season_at(day(2026, 1, 15)) == "winter"      # new year winter
    assert seasons.season_at(day(2026, 2, 28)) == "winter"
    assert seasons.season_at(day(2026, 3, 1)) == "spring"
    assert seasons.season_at(day(2026, 6, 1)) == "summer"
    assert seasons.season_at(day(2026, 9, 1)) == "autumn"
    assert seasons.season_at(day(2026, 12, 15)) == "winter"


def test_holidays_run_in_their_windows():
    assert seasons.holiday_at(day(2026, 10, 28)) == "halloween"
    assert seasons.holiday_at(day(2026, 11, 2)) is None         # the week is over
    assert seasons.holiday_at(day(2026, 12, 1)) == "christmas"
    assert seasons.holiday_at(day(2026, 12, 26)) == "christmas"  # the window runs to the 26th inclusive
    assert seasons.holiday_at(day(2026, 12, 27)) == "newyear"    # wrapping the year
    assert seasons.holiday_at(day(2027, 1, 2)) == "newyear"
    assert seasons.holiday_at(day(2027, 1, 3)) is None
    assert seasons.holiday_at(day(2026, 11, 20)) is None         # no window covers late November


def test_resolve_off_is_none_even_on_a_holiday():
    assert seasons.resolve("off", today=day(2026, 12, 25)) is None


def test_resolve_holidays_only():
    assert seasons.resolve("holidays", today=day(2026, 10, 30)) == "halloween"
    assert seasons.resolve("holidays", today=day(2026, 7, 4)) is None      # out of every window
    assert seasons.resolve("holidays", holiday="christmas", today=day(2026, 7, 4)) == "christmas"  # pinned by hand
    assert seasons.resolve("holidays", holiday="gone", today=day(2026, 7, 4)) is None              # unknown: none


def test_resolve_seasons_only_and_pins():
    assert seasons.resolve("seasons", today=day(2026, 6, 30)) == "summer"
    assert seasons.resolve("seasons", season="winter", today=day(2026, 6, 30)) == "winter"  # pinned wins
    assert seasons.resolve("seasons", season="nonsense", today=day(2026, 6, 30)) is None


def test_resolve_both_prefers_a_holiday():
    assert seasons.resolve("both", today=day(2026, 12, 20)) == "christmas"
    assert seasons.resolve("both", today=day(2026, 11, 20)) == "autumn"    # no holiday in the window
    assert seasons.resolve("both", season="spring", holiday="halloween", today=day(2026, 11, 20)) == "halloween"
    assert seasons.resolve("both", season="spring", today=day(2026, 11, 20)) == "spring"
