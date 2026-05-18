"""Per-wallet scheduler.

Reads enrollments, computes when each wallet's next action *should*
happen using its persona, inserts jobs into the queue. Workers consume.

Run as a cron every 10 minutes; idempotent.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import psycopg

from farm.config import settings
from farm.protocols import linea


def schedule_next_for_wallet(cur, wallet_id, protocol_id, persona):
    """Insert a job for this wallet+protocol if it's due."""
    cur.execute(
        """
        SELECT last_action_at FROM enrollment
        WHERE wallet_id=%s AND protocol_id=%s
        """,
        (wallet_id, protocol_id),
    )
    row = cur.fetchone()
    if not row:
        return False
    last = row[0] or (datetime.now(timezone.utc) - timedelta(days=7))

    # Persona dictates cadence: weekly_actions_range → mean gap
    lo, hi = persona["weekly_actions_range"]
    actions_per_week = random.uniform(lo, hi)
    mean_gap_hours = (7 * 24) / actions_per_week
    # Add ±40% jitter so two wallets don't fire on the same cadence.
    gap_hours = random.uniform(mean_gap_hours * 0.6, mean_gap_hours * 1.4)

    next_action_at = last + timedelta(hours=gap_hours)
    now = datetime.now(timezone.utc)
    if next_action_at > now + timedelta(hours=2):
        # Not due yet, and already queued in future — skip.
        return False

    # Constrain to activity_window_utc.
    win_start, win_end = persona["activity_window_utc"]
    scheduled = max(next_action_at, now)
    scheduled = _shift_into_window(scheduled, win_start, win_end)

    # Pick playbook (per protocol, eventually a registry).
    playbook = f"{protocol_id}.next"

    # Idempotency: skip if there's already an unfinished job.
    cur.execute(
        """
        SELECT 1 FROM job
        WHERE wallet_id=%s AND protocol_id=%s
          AND finished_at IS NULL
        LIMIT 1
        """,
        (wallet_id, protocol_id),
    )
    if cur.fetchone():
        return False

    cur.execute(
        """
        INSERT INTO job (wallet_id, protocol_id, playbook, scheduled_for)
        VALUES (%s,%s,%s,%s)
        """,
        (wallet_id, protocol_id, playbook, scheduled),
    )
    return True


def _shift_into_window(when: datetime, win_start_h: int, win_end_h: int) -> datetime:
    """Move `when` into the wallet's UTC activity window. Adds small jitter."""
    hour = when.hour
    in_window = (
        (win_start_h <= win_end_h and win_start_h <= hour < win_end_h)
        or (win_start_h > win_end_h and (hour >= win_start_h or hour < win_end_h))
    )
    if in_window:
        return when + timedelta(minutes=random.randint(0, 30))

    # Advance to next window start.
    target = when.replace(hour=win_start_h, minute=random.randint(2, 55), second=0, microsecond=0)
    if target <= when:
        target += timedelta(days=1)
    return target


def run_once():
    with psycopg.connect(settings.pg_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT w.id, e.protocol_id, i.persona
                FROM wallet w
                JOIN identity i ON i.id = w.identity_id
                JOIN enrollment e ON e.wallet_id = w.id
                WHERE w.status = 'active'
                  AND e.status = 'active'
                  AND i.retired_at IS NULL
                """
            )
            scheduled = 0
            for wallet_id, protocol_id, persona in cur.fetchall():
                if schedule_next_for_wallet(cur, wallet_id, protocol_id, persona):
                    scheduled += 1
            conn.commit()
            return scheduled


if __name__ == "__main__":
    n = run_once()
    print(f"scheduled {n} jobs")
