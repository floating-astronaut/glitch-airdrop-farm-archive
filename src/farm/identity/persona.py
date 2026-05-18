"""Per-wallet persona generation.

The single most important Sybil-defense mechanism. Every behavioral
parameter that a Sybil detector might look at should vary by wallet,
drawn at identity creation and stored in `identity.persona` JSONB.
"""

from __future__ import annotations

import random
import zoneinfo
from dataclasses import asdict, dataclass


# Realistic distributions — wide enough that two wallets rarely
# share a fingerprint, narrow enough that none look bot-extreme.

GEO_PROFILES = [
    # (country, locale, timezone, weight)
    ("US", "en-US", "America/New_York", 30),
    ("US", "en-US", "America/Los_Angeles", 15),
    ("US", "en-US", "America/Chicago", 10),
    ("GB", "en-GB", "Europe/London", 8),
    ("DE", "de-DE", "Europe/Berlin", 6),
    ("FR", "fr-FR", "Europe/Paris", 5),
    ("NL", "nl-NL", "Europe/Amsterdam", 4),
    ("PL", "pl-PL", "Europe/Warsaw", 3),
    ("BR", "pt-BR", "America/Sao_Paulo", 5),
    ("SG", "en-SG", "Asia/Singapore", 4),
    ("JP", "ja-JP", "Asia/Tokyo", 4),
    ("VN", "vi-VN", "Asia/Ho_Chi_Minh", 3),
    ("ID", "id-ID", "Asia/Jakarta", 3),
]

USER_AGENTS = [
    # Chrome on macOS/Windows/Linux + Firefox on Win, real recent versions.
    # Camofox will spoof matching navigator props.
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]


@dataclass
class Persona:
    geo_country: str
    locale: str
    timezone: str
    user_agent: str
    slippage_bps: int            # 30–90 (0.30–0.90%)
    activity_window_utc: tuple[int, int]
    weekday_active_prob: float   # 0.4–0.95 chance of activity on any given day
    gas_patience: str            # 'low' / 'medium' / 'high'
    session_minutes_range: tuple[int, int]
    weekly_actions_range: tuple[int, int]
    swap_size_usd_range: tuple[int, int]


def _weighted_choice(choices):
    total = sum(w for *_, w in choices)
    r = random.uniform(0, total)
    upto = 0
    for *vals, w in choices:
        upto += w
        if upto >= r:
            return vals
    return list(choices[-1][:-1])


def generate_persona(seed: int | None = None) -> Persona:
    rng = random.Random(seed) if seed is not None else random

    country, locale, tz = _weighted_choice(GEO_PROFILES)
    tz_obj = zoneinfo.ZoneInfo(tz)  # validates
    del tz_obj

    # Activity window in UTC, derived loosely from waking hours in geo:
    # we just pick a 6–10h window starting somewhere 9–22 UTC, biased
    # so wallets aren't all active during the same global hours.
    win_start = rng.randint(7, 22)
    win_len = rng.randint(5, 11)
    win_end = (win_start + win_len) % 24

    return Persona(
        geo_country=country,
        locale=locale,
        timezone=tz,
        user_agent=rng.choice(USER_AGENTS),
        slippage_bps=rng.randint(30, 90),
        activity_window_utc=(win_start, win_end),
        weekday_active_prob=round(rng.uniform(0.45, 0.92), 2),
        gas_patience=rng.choice(["low", "medium", "medium", "high"]),
        session_minutes_range=(rng.randint(3, 8), rng.randint(12, 30)),
        weekly_actions_range=(rng.randint(2, 4), rng.randint(5, 11)),
        swap_size_usd_range=(rng.randint(15, 40), rng.randint(80, 350)),
    )


def to_jsonb(p: Persona) -> dict:
    return asdict(p)
