"""Lunar phases after Meeus, Astronomical Algorithms (2nd ed.), chapter 49.

Gives the instants of new moon, first quarter, full moon and last quarter to
within a few minutes (the planetary correction terms, worth under a minute,
are left out). Times are converted from TT to UTC with a fixed Delta T.
"""
import datetime as dt
import math

DELTA_T = 70.0  # seconds, TT - UTC, adequate for 2020-2030
J2000_UNIX = 946728000.0  # 2000-01-01 12:00 UTC as a POSIX time


def _phase_jde(k: float) -> float:
    T = k / 1236.85
    jde = (2451550.09766 + 29.530588861 * k + 0.00015437 * T**2
           - 0.000000150 * T**3 + 0.00000000073 * T**4)
    E = 1 - 0.002516 * T - 0.0000074 * T**2
    r = math.radians
    M = r(2.5534 + 29.10535670 * k - 0.0000014 * T**2 - 0.00000011 * T**3)
    Mp = r(201.5643 + 385.81693528 * k + 0.0107582 * T**2 + 0.00001238 * T**3 - 0.000000058 * T**4)
    F = r(160.7108 + 390.67050284 * k - 0.0016118 * T**2 - 0.00000227 * T**3 + 0.000000011 * T**4)
    Om = r(124.7746 - 1.56375588 * k + 0.0020672 * T**2 + 0.00000215 * T**3)
    s = math.sin
    frac = round((k % 1) * 4) % 4
    if frac == 0:  # new
        c = (-0.40720 * s(Mp) + 0.17241 * E * s(M) + 0.01608 * s(2 * Mp) + 0.01039 * s(2 * F)
             + 0.00739 * E * s(Mp - M) - 0.00514 * E * s(Mp + M) + 0.00208 * E * E * s(2 * M)
             - 0.00111 * s(Mp - 2 * F) - 0.00057 * s(Mp + 2 * F) + 0.00056 * E * s(2 * Mp + M)
             - 0.00042 * s(3 * Mp) + 0.00042 * E * s(M + 2 * F) + 0.00038 * E * s(M - 2 * F)
             - 0.00024 * E * s(2 * Mp - M) - 0.00017 * s(Om))
    elif frac == 2:  # full
        c = (-0.40614 * s(Mp) + 0.17302 * E * s(M) + 0.01614 * s(2 * Mp) + 0.01043 * s(2 * F)
             + 0.00734 * E * s(Mp - M) - 0.00515 * E * s(Mp + M) + 0.00209 * E * E * s(2 * M)
             - 0.00111 * s(Mp - 2 * F) - 0.00057 * s(Mp + 2 * F) + 0.00056 * E * s(2 * Mp + M)
             - 0.00042 * s(3 * Mp) + 0.00042 * E * s(M + 2 * F) + 0.00038 * E * s(M - 2 * F)
             - 0.00024 * E * s(2 * Mp - M) - 0.00017 * s(Om))
    else:  # quarters
        c = (-0.62801 * s(Mp) + 0.17172 * E * s(M) - 0.01183 * E * s(Mp + M) + 0.00862 * s(2 * Mp)
             + 0.00804 * s(2 * F) + 0.00454 * E * s(Mp - M) + 0.00204 * E * E * s(2 * M)
             - 0.00180 * s(Mp - 2 * F) - 0.00070 * s(Mp + 2 * F) - 0.00040 * s(3 * Mp)
             - 0.00034 * E * s(2 * Mp - M) + 0.00032 * E * s(M + 2 * F) + 0.00032 * E * s(M - 2 * F)
             - 0.00028 * E * E * s(Mp + 2 * M) + 0.00027 * E * s(2 * Mp + M) - 0.00017 * s(Om))
        w = (0.00306 - 0.00038 * E * math.cos(M) + 0.00026 * math.cos(Mp) - 0.00002 * math.cos(Mp - M)
             + 0.00002 * math.cos(Mp + M) + 0.00002 * math.cos(2 * F))
        c += w if frac == 1 else -w
    return jde + c


def _jde_to_utc(jde: float) -> dt.datetime:
    secs = (jde - 2451545.0) * 86400.0 - DELTA_T + J2000_UNIX
    return dt.datetime.fromtimestamp(secs, tz=dt.timezone.utc)


PHASE_NAMES = ["new moon", "first quarter", "full moon", "last quarter"]


def phases_between(start: dt.datetime, end: dt.datetime):
    """[(utc datetime, 0..3 phase index)] for every principal phase in [start, end]."""
    year = start.year + (start.timetuple().tm_yday / 365.25)
    k = math.floor((year - 2000) * 12.3685) - 2
    out = []
    while True:
        for q in range(4):
            t = _jde_to_utc(_phase_jde(k + q / 4))
            if t > end:
                return out
            if t >= start:
                out.append((t, q))
        k += 1


def new_moons_between(start, end):
    return [t for t, q in phases_between(start, end) if q == 0]
