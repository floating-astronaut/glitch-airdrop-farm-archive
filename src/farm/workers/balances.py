"""Read-only balance check across every (wallet × chain) we farm.

Uses each wallet's own residential proxy, validates the RPC reports
the expected chain id, and prints a tidy report. Pure read — safe to
run any time.
"""

from __future__ import annotations

import psycopg

from farm.config import settings
from farm.chains import for_protocol
from farm.wallets.onchain import ProxiedRPC, assert_chain_matches


def run() -> list[dict]:
    out = []
    with psycopg.connect(settings.pg_dsn) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.label, w.address, i.proxy_url, e.protocol_id
            FROM wallet w
            JOIN identity i ON i.id = w.identity_id
            JOIN enrollment e ON e.wallet_id = w.id
            ORDER BY i.label, e.protocol_id
        """)
        rows = cur.fetchall()

    for label, address, proxy_url, protocol_id in rows:
        try:
            chain = for_protocol(protocol_id)
        except KeyError:
            continue
        rpc = ProxiedRPC(chain=chain, proxy_url=proxy_url)
        try:
            assert_chain_matches(rpc)
            wei = rpc.balance_wei(address)
            eth = wei / 1e18
            blk = rpc.block_number()
            status = f"{eth:.6f} {chain.native_symbol}  (block {blk})"
            ok = True
        except Exception as e:
            status = f"ERR {type(e).__name__}: {e}"
            ok = False
        out.append({"label": label, "protocol": protocol_id,
                    "address": address, "status": status, "ok": ok})
        print(f"  {label:18s} {protocol_id:13s} {status}")
    return out


if __name__ == "__main__":
    run()
