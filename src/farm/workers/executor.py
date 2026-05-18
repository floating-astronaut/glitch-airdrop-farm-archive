"""Job executor — single-worker loop.

Claims one ready job from the queue with row-level locking, dispatches
to the appropriate playbook, logs result.

Phase 0 scope: native-token "self-send" or balance-check tx only. This
proves the signing + proxy + chain-id-check + tx-broadcast path
end-to-end on testnet without depending on a specific dapp.

Real protocol playbooks plug in here later (one dispatch entry per
`playbook` string).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from decimal import Decimal

import psycopg

from farm.config import settings
from farm.chains import for_protocol
from farm.wallets.keystore import unseal
from farm.wallets.onchain import (
    ProxiedRPC,
    account_from_privkey,
    assert_chain_matches,
)

WORKER_ID_PREFIX = "exec"


def claim_job(cur, worker_id: str) -> dict | None:
    """Atomically claim one ready job. Returns None if nothing to do."""
    cur.execute("""
        SELECT j.id, j.wallet_id, j.protocol_id, j.playbook, j.params,
               i.proxy_url, i.label, w.address, w.privkey_enc
        FROM job j
        JOIN wallet w ON w.id = j.wallet_id
        JOIN identity i ON i.id = w.identity_id
        WHERE j.finished_at IS NULL
          AND j.claimed_by IS NULL
          AND j.scheduled_for <= now()
        ORDER BY j.scheduled_for
        FOR UPDATE OF j SKIP LOCKED
        LIMIT 1
    """)
    row = cur.fetchone()
    if not row:
        return None
    job_id = row[0]
    cur.execute("""
        UPDATE job SET claimed_by=%s, claimed_at=now(), attempts=attempts+1
        WHERE id=%s
    """, (worker_id, job_id))
    return {
        "id": job_id,
        "wallet_id": row[1], "protocol_id": row[2],
        "playbook": row[3], "params": row[4] or {},
        "proxy_url": row[5], "label": row[6],
        "address": row[7], "privkey_enc": row[8],
    }


def finish_job(cur, job_id: int, ok: bool, result: dict) -> None:
    cur.execute("""
        UPDATE job SET finished_at=now(), succeeded=%s, result=%s
        WHERE id=%s
    """, (ok, json.dumps(result, default=str), job_id))


def log_action(cur, wallet_id, protocol_id, action_type, tx_hash,
               amount_usd, gas_usd, metadata, succeeded, error) -> None:
    cur.execute("""
        INSERT INTO action (wallet_id, protocol_id, action_type, tx_hash,
                            amount_usd, gas_usd, metadata, succeeded, error)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (wallet_id, protocol_id, action_type, tx_hash,
          amount_usd, gas_usd, json.dumps(metadata), succeeded, error))


def bump_enrollment(cur, wallet_id, protocol_id, gas_usd) -> None:
    cur.execute("""
        UPDATE enrollment SET
          last_action_at = now(),
          total_actions  = total_actions + 1,
          total_gas_usd  = total_gas_usd + %s
        WHERE wallet_id=%s AND protocol_id=%s
    """, (gas_usd, wallet_id, protocol_id))


# ─── playbooks ────────────────────────────────────────────────────


def playbook_self_send(job: dict) -> dict:
    """Phase 0 smoke test: send 0 native tokens to self.

    Validates signing + nonce + gas + proxy + chain id + broadcast.
    Costs ~21000 gas. Safe to run on any wallet that has any gas
    balance. If the wallet has zero balance, we report 'no_funds'
    without throwing — that's expected pre-faucet.
    """
    chain = for_protocol(job["protocol_id"])
    rpc = ProxiedRPC(chain=chain, proxy_url=job["proxy_url"])

    assert_chain_matches(rpc)

    address = job["address"]
    bal = rpc.balance_wei(address)
    if bal == 0:
        return {"skipped": "no_funds", "balance_wei": 0}

    acct = account_from_privkey(unseal(bytes(job["privkey_enc"])))
    if acct.address.lower() != address.lower():
        raise RuntimeError("address mismatch — refusing to sign")

    nonce = rpc.tx_count(address)
    gas_price = rpc.gas_price()

    tx = {
        "from": address,
        "to": address,
        "value": 0,
        "nonce": nonce,
        "gas": 21000,
        "gasPrice": gas_price,
        "chainId": chain.chain_id,
    }

    signed = acct.sign_transaction(tx)
    tx_hash = rpc.send_raw_tx(signed.raw_transaction.hex())
    gas_cost_wei = 21000 * gas_price
    return {
        "tx_hash": tx_hash,
        "gas_wei": gas_cost_wei,
        "gas_eth": gas_cost_wei / 1e18,
        "balance_before_wei": bal,
        "chain_id": chain.chain_id,
        "explorer_link": f"{chain.explorer}/tx/{tx_hash}",
    }


PLAYBOOKS = {
    "monad-tn.self_send":          playbook_self_send,
    "megaeth-tn.self_send":        playbook_self_send,
    "berachain-tn.self_send":      playbook_self_send,
    "linea-tn.self_send":          playbook_self_send,
    "scroll-tn.self_send":         playbook_self_send,
    "sepolia-validate.self_send":  playbook_self_send,
}


def run_once(worker_id: str | None = None) -> bool:
    """Claim and run ONE job. Returns True if a job ran, False if idle."""
    worker_id = worker_id or f"{WORKER_ID_PREFIX}-{int(time.time())}"
    with psycopg.connect(settings.pg_dsn) as conn:
        with conn.cursor() as cur:
            job = claim_job(cur, worker_id)
            conn.commit()
        if not job:
            return False

        ok = False
        result: dict = {}
        err: str | None = None
        try:
            pb = PLAYBOOKS.get(job["playbook"])
            if not pb:
                raise RuntimeError(f"unknown playbook: {job['playbook']}")
            result = pb(job)
            ok = True
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            result = {"error": err}

        with conn.cursor() as cur:
            log_action(
                cur,
                wallet_id=job["wallet_id"],
                protocol_id=job["protocol_id"],
                action_type=job["playbook"].split(".")[-1],
                tx_hash=result.get("tx_hash"),
                amount_usd=Decimal(0),
                gas_usd=Decimal(0),  # testnet — zero USD
                metadata=result,
                succeeded=ok,
                error=err,
            )
            if ok and result.get("tx_hash"):
                bump_enrollment(cur, job["wallet_id"], job["protocol_id"],
                                Decimal(0))
            finish_job(cur, job["id"], ok, result)
            conn.commit()

        tag = "OK" if ok else "FAIL"
        print(f"  [{tag}] {job['label']} {job['protocol_id']}"
              f" {job['playbook']} → {result.get('tx_hash') or result.get('skipped') or err}")
        return True


def run_loop(max_iterations: int | None = None, sleep_s: float = 3.0) -> None:
    """Drain queue then sleep, repeat. max_iterations=None → forever."""
    n = 0
    idle_streak = 0
    while max_iterations is None or n < max_iterations:
        worked = run_once()
        if worked:
            idle_streak = 0
            n += 1
        else:
            idle_streak += 1
            time.sleep(min(sleep_s * (1 + idle_streak * 0.5), 30.0))


if __name__ == "__main__":
    run_once()
