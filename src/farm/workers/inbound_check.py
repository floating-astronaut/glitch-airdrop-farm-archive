"""Check inbound mainnet balances on Base + Arbitrum.

Read-only. Confirms 0.001 ETH proof-of-personhood deposits landed.
We do NOT farm on these chains — they exist only so testnet faucets
believe the wallet has skin in the game.
"""

from __future__ import annotations

import psycopg

from farm.config import settings
from farm.chains import CHAINS
from farm.wallets.onchain import ProxiedRPC, assert_chain_matches


CHECK_CHAINS = ["base-mainnet", "arbitrum-mainnet"]


def run() -> None:
    with psycopg.connect(settings.pg_dsn) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.label, w.address, i.proxy_url
            FROM wallet w JOIN identity i ON i.id = w.identity_id
            ORDER BY i.label
        """)
        rows = cur.fetchall()

    print(f"{'wallet':18s} {'chain':18s} {'balance':>18s}  {'qualifies':>10s}")
    print("-" * 70)
    for label, address, proxy_url in rows:
        for chain_key in CHECK_CHAINS:
            chain = CHAINS[chain_key]
            rpc = ProxiedRPC(chain=chain, proxy_url=proxy_url)
            try:
                assert_chain_matches(rpc)
                wei = rpc.balance_wei(address)
                eth = wei / 1e18
                qual = "YES" if eth >= 0.001 else "no"
                status = f"{eth:.6f} ETH"
            except Exception as e:
                status = f"ERR {type(e).__name__}"
                qual = "?"
            print(f"{label:18s} {chain_key:18s} {status:>18s}  {qual:>10s}")


if __name__ == "__main__":
    run()
