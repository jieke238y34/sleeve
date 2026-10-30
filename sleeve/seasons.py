"""The calendar behind the optional seasonal and holiday looks: which one a date falls into.

The Look settings choose what follows the calendar ('seasons', 'holidays' or 'both'; 'off' turns it off) and
whether the season and the holiday follow the calendar ('auto') or are pinned by the user for that part. A
holiday wins over a season when the date is in both. Pure date maths, so it can be tested.
"""

import datetime as dt

# Holiday windows as (start, end) month-day strings; a window repeats every year, and an end before the start
# wraps a new year. These are the days people get into the mood: Halloween a full week, Christmas the lead-up and
# the day itself, New Year across the end of December and the start of January.
HOLIDAY_WINDOWS = {
    "halloween": ("10-26", "11-01"),
    "christmas": ("12-01", "12-27"),
    "newyear": ("12-27", "01-03"),
}

# The meteorological seasons (northern hemisphere: Sleeve's maintainer is in one). A user can pin a season in
# Settings, which overrides this for them.
SEASON_MONTHS = (("winter", (12, 1, 2)), ("spring", (3, 4, 5)), ("summer", (6, 7, 8)), ("autumn", (9, 10, 11)))
SEASONS = frozenset(s for s, _ in SEASON_MONTHS)


def season_at(day):
    "The season running on `day` (a date): 'winter', 'spring', 'summer' or 'autumn'."
    for season, months in SEASON_MONTHS:
        if day.month in months:
            return season
    return None


def holiday_at(day):
    "The holiday running on `day` (a date), or None. The 'newyear' window wraps the turn of the year."
    md = (day.month, day.day)
    for name, (start, end) in HOLIDAY_WINDOWS.items():
        s, e = ((int(m), int(d)) for m, d in (part.split("-") for part in (start, end)))
        smd, emd = s, e
        if smd <= emd:                                      # inside one year: a plain range
            if smd <= md < emd:
                return name
        elif md >= smd or md < emd:                         # the window wraps: December into January
            return name
    return None


def resolve(what, season="auto", holiday="auto", today=None):
    "The name of the look the settings ask for on `today`, or None when the plain look stays."
    if what == "off":
        return None
    day = today or dt.date.today()
    if what in ("holidays", "both"):
        if holiday in HOLIDAY_WINDOWS:
            return holiday                              # a holiday pinned by hand
        if holiday != "auto":                           # an unknown name: nothing (validation blocks it anyway)
            return None if what == "holidays" else None
        found = holiday_at(day)
        if found:
            return found
        if what == "holidays":
            return None                                 # waiting for the next window
    if season in SEASONS:
        return season                                   # a season pinned by hand
    return season_at(day) if season == "auto" and what in ("seasons", "both") else None
