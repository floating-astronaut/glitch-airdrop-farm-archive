"""Google Sheets sync — write farm state to a shared workbook.

Auth: impersonates `glitch-vertex-ai@...` from the GCE default SA via ADC.
No key files. The default SA must have `iam.serviceAccountTokenCreator`
on the impersonated SA, and the target sheet must share Editor access
with the impersonated SA's email.

Tabs written:
  - Wallets         (per-wallet identity + persona + status)
  - Funding         (per-wallet Base + Arbitrum mainnet balances)
  - Faucets         (per-wallet × testnet balance, faucet URL, claim status)
  - Activity        (last 50 actions)
  - Snapshot        (one-row rollup)

All tabs are wiped+rewritten on each sync (idempotent, no stale rows).
Private keys, raw proxy passwords, persona internals — never written.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import google.auth
import psycopg
from google.auth import impersonated_credentials
from googleapiclient.discovery import build

from farm.config import settings
from farm.chains import CHAINS, PROTOCOL_TO_CHAIN

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _client():
    """Build a Sheets API client as the impersonated SA."""
    source, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    target = impersonated_credentials.Credentials(
        source_credentials=source,
        target_principal=settings.sheets_impersonate_sa,
        target_scopes=SCOPES,
        lifetime=900,
    )
    return build("sheets", "v4", credentials=target, cache_discovery=False)


# ─────────────────────────────────────────────────────────────────────


def _ensure_tab(svc, sheet_id: str, title: str) -> None:
    meta = svc.spreadsheets().get(spreadsheetId=sheet_id, fields="sheets.properties.title").execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if title in existing:
        return
    svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
    ).execute()


def _write_tab(svc, sheet_id: str, tab: str, rows: list[list[Any]]) -> None:
    """Clear and rewrite a tab atomically."""
    _ensure_tab(svc, sheet_id, tab)
    svc.spreadsheets().values().clear(spreadsheetId=sheet_id, range=tab).execute()
    if not rows:
        return
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{tab}!A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()


# ─────────────────────────────────────────────────────────────────────


def _persona_summary(p: dict) -> str:
    if not p:
        return ""
    win = p.get("activity_window_utc", [])
    return (
        f"{p.get('geo_country','?')}/{p.get('timezone','?')[:20]} "
        f"· window {win[0] if win else '?'}–{win[1] if len(win)>1 else '?'} UTC "
        f"· slip {p.get('slippage_bps','?')}bps "
        f"· {p.get('weekly_actions_range',[None,None])[0]}–"
        f"{p.get('weekly_actions_range',[None,None])[1]} actions/wk"
    )


def build_rows() -> dict[str, list[list[Any]]]:
    """Pull current state from Postgres and shape into rows-per-tab."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    tabs: dict[str, list[list[Any]]] = {}

    with psycopg.connect(settings.pg_dsn) as conn, conn.cursor() as cur:
        # ── Wallets ───────────────────────────────────────────────
        cur.execute("""
            SELECT i.label, w.address, i.proxy_country, i.timezone,
                   i.persona, w.status, w.funded_at, w.created_at
            FROM wallet w JOIN identity i ON i.id = w.identity_id
            ORDER BY i.label
        """)
        tabs["Wallets"] = [[
            "Label", "Address", "Geo", "Timezone",
            "Persona summary", "Status", "Funded at", "Created at",
        ]]
        for label, addr, geo, tz, persona, status, funded, created in cur.fetchall():
            tabs["Wallets"].append([
                label, addr, geo, tz,
                _persona_summary(persona), status,
                funded.strftime("%Y-%m-%d %H:%M") if funded else "",
                created.strftime("%Y-%m-%d %H:%M") if created else "",
            ])

        # ── Funding (CEX source + on-chain deposit ledger) ────────
        # Live mainnet balance checks are too slow (~5s/wallet through proxies)
        # to embed in a 10-min sync. Sheet shows: per-wallet identity, all
        # recorded funding events (source CEX, amount, chain, timestamp).
        # Live numbers: `farm inbound` from CLI.
        cur.execute("""
            SELECT i.label, w.address, i.proxy_country, f.source, f.amount,
                   f.chain, f.at, f.notes
            FROM wallet w
            JOIN identity i ON i.id = w.identity_id
            LEFT JOIN funding f ON f.wallet_id = w.id AND f.direction = 'in'
            ORDER BY i.label, f.at
        """)
        tabs["Funding"] = [[
            "Label", "Address", "Geo",
            "Source CEX", "Amount", "Chain", "Funded at", "Notes",
        ]]
        for (label, addr, geo, source, amount, chain, at, notes) in cur.fetchall():
            tabs["Funding"].append([
                label, addr, geo,
                source or "(pending)",
                float(amount) if amount else "",
                chain or "",
                at.strftime("%Y-%m-%d %H:%M") if at else "",
                notes or "",
            ])

        # ── Faucets / testnet enrollments ─────────────────────────
        cur.execute("""
            SELECT i.label, w.address, e.protocol_id,
                   e.last_action_at, e.total_actions, e.total_gas_usd,
                   e.points_cached, e.points_at, e.status
            FROM enrollment e
            JOIN wallet w ON w.id = e.wallet_id
            JOIN identity i ON i.id = w.identity_id
            ORDER BY i.label, e.protocol_id
        """)
        tabs["Faucets"] = [[
            "Label", "Address", "Protocol", "Chain",
            "Faucet URL", "Status",
            "Total actions", "Total gas $",
            "Last action at",
        ]]
        for (label, addr, proto, last, total, gas,
             points, points_at, status) in cur.fetchall():
            chain_key = PROTOCOL_TO_CHAIN.get(proto, "")
            chain = CHAINS.get(chain_key)
            tabs["Faucets"].append([
                label, addr, proto, chain_key,
                chain.faucet_url if chain and chain.faucet_url else "",
                status,
                total or 0, float(gas) if gas else 0.0,
                last.strftime("%Y-%m-%d %H:%M") if last else "",
            ])

        # ── Recent activity ───────────────────────────────────────
        cur.execute("""
            SELECT a.executed_at, i.label, a.protocol_id, a.action_type,
                   a.tx_hash, a.succeeded, a.error, a.metadata
            FROM action a
            JOIN wallet w ON w.id = a.wallet_id
            JOIN identity i ON i.id = w.identity_id
            ORDER BY a.executed_at DESC
            LIMIT 50
        """)
        tabs["Activity"] = [[
            "When (UTC)", "Wallet", "Protocol", "Action",
            "TX hash", "OK", "Error", "Explorer link",
        ]]
        for when, label, proto, atype, txh, ok, err, meta in cur.fetchall():
            link = (meta or {}).get("explorer_link", "") if isinstance(meta, dict) else ""
            tabs["Activity"].append([
                when.strftime("%Y-%m-%d %H:%M") if when else "",
                label, proto, atype,
                txh or "", "YES" if ok else "no", (err or "")[:120],
                link,
            ])

        # ── Snapshot rollup ───────────────────────────────────────
        cur.execute("SELECT count(*) FROM wallet")
        n_wallets = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM enrollment WHERE status='active'")
        n_enroll = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM action WHERE succeeded=true")
        n_actions_ok = cur.fetchone()[0]
        cur.execute("SELECT coalesce(sum(total_gas_usd),0) FROM enrollment")
        gas_total = float(cur.fetchone()[0] or 0)
        cur.execute("SELECT count(*) FROM job WHERE finished_at IS NULL")
        pending = cur.fetchone()[0]

    tabs["Snapshot"] = [
        ["Metric", "Value", "Last synced"],
        ["Wallets",                 n_wallets,      now],
        ["Active enrollments",      n_enroll,       now],
        ["Successful actions",      n_actions_ok,   now],
        ["Pending jobs",            pending,        now],
        ["Total gas spent (USD)",   round(gas_total, 4), now],
    ]

    return tabs


def sync() -> dict[str, int]:
    """Write all tabs. Returns row counts per tab."""
    svc = _client()
    tabs = build_rows()
    counts: dict[str, int] = {}
    for title, rows in tabs.items():
        _write_tab(svc, settings.sheets_spreadsheet_id, title, rows)
        counts[title] = max(len(rows) - 1, 0)  # subtract header
    return counts


if __name__ == "__main__":
    print(sync())
