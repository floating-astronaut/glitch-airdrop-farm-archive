"""Operator CLI for the airdrop farm."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import click
import psycopg

from farm.config import settings
from farm.identity.persona import generate_persona, to_jsonb
from farm.identity.proxy_pool import for_identity as proxy_for_identity
from farm.wallets.keystore import new_evm_wallet, seal


@click.group()
def main():
    """Glitch Airdrop Farm — operator CLI."""


@main.command("init-db")
def init_db():
    """Apply schema and seed data."""
    schema = open("/home/support/glitch-airdrop-farm/sql/001_init.sql").read()
    seeds = open("/home/support/glitch-airdrop-farm/seeds/protocols.sql").read()
    with psycopg.connect(settings.pg_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
            cur.execute(seeds)
            conn.commit()
    click.echo("schema + seeds applied")


@main.command("provision")
@click.option("--count", default=5, help="How many identities+wallets to create.")
@click.option("--protocols", default="linea,scroll", help="Comma-separated protocol ids to enroll.")
def provision(count, protocols):
    """Create N identities + EVM wallets and enroll them in given protocols."""
    enroll = [p.strip() for p in protocols.split(",") if p.strip()]
    with psycopg.connect(settings.pg_dsn) as conn:
        for i in range(count):
            with conn.cursor() as cur:
                persona = generate_persona()
                label = f"eth-{int(datetime.now(timezone.utc).timestamp()) % 100000:05d}-{i:03d}"
                proxy = proxy_for_identity(label, persona.geo_country)
                cur.execute(
                    """
                    INSERT INTO identity (label, camofox_user_id, proxy_url,
                      proxy_country, locale, timezone, user_agent, persona)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (label,
                     f"camofox_{label}",
                     proxy.url,
                     persona.geo_country,
                     persona.locale,
                     persona.timezone,
                     persona.user_agent,
                     json.dumps(to_jsonb(persona))),
                )
                identity_id = cur.fetchone()[0]

                addr, pk = new_evm_wallet()
                cur.execute(
                    """
                    INSERT INTO wallet (identity_id, chain_family, address, privkey_enc)
                    VALUES (%s, 'evm', %s, %s)
                    RETURNING id
                    """,
                    (identity_id, addr, seal(pk)),
                )
                wallet_id = cur.fetchone()[0]

                for p in enroll:
                    cur.execute(
                        """
                        INSERT INTO enrollment (wallet_id, protocol_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (wallet_id, p),
                    )
                conn.commit()
                click.echo(f"  {label}  {addr}")
    click.echo(f"provisioned {count} wallets")


@main.command("faucet-list")
def faucet_list():
    """Print the manual-claim checklist for every (wallet × testnet)."""
    from farm.workers.faucet import print_checklist
    print_checklist()


@main.command("balances")
def balances():
    """Check native-token balance for every (wallet × protocol)."""
    from farm.workers.balances import run
    run()


@main.command("inbound")
def inbound():
    """Check Base + Arbitrum mainnet balances (0.001 ETH faucet gate)."""
    from farm.workers.inbound_check import run
    run()


@main.command("schedule")
def schedule():
    """Run the orchestrator once: enqueue jobs for any wallet that's due."""
    from farm.orchestrator.scheduler import run_once
    n = run_once()
    click.echo(f"scheduled {n} jobs")


@main.command("enqueue-smoke")
def enqueue_smoke():
    """Insert one self_send smoke-test job per active enrollment."""
    with psycopg.connect(settings.pg_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO job (wallet_id, protocol_id, playbook, scheduled_for)
                SELECT e.wallet_id, e.protocol_id,
                       e.protocol_id || '.self_send', now()
                FROM enrollment e
                WHERE e.status='active'
                  AND NOT EXISTS (
                    SELECT 1 FROM job j
                    WHERE j.wallet_id=e.wallet_id AND j.protocol_id=e.protocol_id
                      AND j.finished_at IS NULL
                  )
                RETURNING id
            """)
            n = cur.rowcount
            conn.commit()
    click.echo(f"enqueued {n} smoke jobs")


@main.command("execute")
@click.option("--once", is_flag=True, help="Run one job and exit.")
@click.option("--max", "max_iter", default=None, type=int)
def execute(once, max_iter):
    """Drain the job queue."""
    from farm.workers.executor import run_once, run_loop
    if once:
        ran = run_once()
        click.echo("ran 1 job" if ran else "queue empty")
        return
    run_loop(max_iterations=max_iter)


@main.command("sync-sheet")
def sync_sheet():
    """Push current farm state to the shared Google Sheet."""
    from farm.integrations.sheets import sync
    counts = sync()
    for tab, n in counts.items():
        click.echo(f"  {tab:14s} {n} rows")


@main.command("status")
def status():
    """One-line summary of the farm."""
    with psycopg.connect(settings.pg_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, count(*) FROM wallet GROUP BY status")
            wallets = dict(cur.fetchall())
            cur.execute("SELECT count(*) FROM job WHERE finished_at IS NULL")
            pending = cur.fetchone()[0]
            cur.execute("""
                SELECT protocol_id, count(*)
                FROM enrollment WHERE status='active'
                GROUP BY protocol_id
            """)
            enrolled = dict(cur.fetchall())
    click.echo(f"wallets: {wallets}")
    click.echo(f"enrolled: {enrolled}")
    click.echo(f"pending jobs: {pending}")


if __name__ == "__main__":
    main()
