"""Manual-faucet workflow.

Testnet faucets (Monad, MegaETH, Berachain, Linea Sepolia, Scroll Sepolia)
are deliberately social/captcha-gated to prevent farming. We do NOT
automate the claim — that's a different kind of grey we said no to.

Instead, this prints a per-wallet checklist the operator runs once.
Then `farm balances` confirms which wallets received funds.
"""

from __future__ import annotations

import psycopg

from farm.config import settings
from farm.chains import for_protocol


def print_checklist() -> None:
    with psycopg.connect(settings.pg_dsn) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.label, w.address, e.protocol_id
            FROM wallet w
            JOIN identity i ON i.id = w.identity_id
            JOIN enrollment e ON e.wallet_id = w.id
            ORDER BY i.label, e.protocol_id
        """)
        rows = cur.fetchall()

    by_chain: dict[str, list[tuple[str, str]]] = {}
    for label, addr, proto in rows:
        try:
            chain = for_protocol(proto)
        except KeyError:
            continue
        by_chain.setdefault(chain.key, []).append((label, addr))

    print("\n=== TESTNET FAUCET CHECKLIST ===")
    print("Each wallet is on the same residential IP it'll farm from,")
    print("so claim each manually using your own browser proxied to")
    print("the wallet's sticky session — OR just claim from your")
    print("normal browser; the chain explorer doesn't care.\n")

    for chain_key, wallets in by_chain.items():
        from farm.chains import CHAINS
        chain = CHAINS[chain_key]
        print(f"--- {chain.key}  ({chain.native_symbol})  faucet: {chain.faucet_url}")
        for label, addr in wallets:
            print(f"  [ ]  {label}  {addr}")
        print()


if __name__ == "__main__":
    print_checklist()
