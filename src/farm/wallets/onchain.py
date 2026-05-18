"""Proxied JSON-RPC client + signing.

Every chain call from a wallet goes through the wallet's residential
proxy. web3.py's stock HTTPProvider doesn't take a proxy directly, so
we use httpx with a minimal JSON-RPC wrapper.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
from eth_account import Account
from eth_account.signers.local import LocalAccount

from farm.chains import Chain


class RPCError(RuntimeError):
    pass


@dataclass
class ProxiedRPC:
    chain: Chain
    proxy_url: str
    timeout_s: float = 30.0

    def _client(self) -> httpx.Client:
        return httpx.Client(proxy=self.proxy_url, timeout=self.timeout_s)

    def call(self, method: str, params: list[Any] | None = None) -> Any:
        body = {"jsonrpc": "2.0", "id": int(time.time() * 1000) & 0xFFFFFFFF,
                "method": method, "params": params or []}
        with self._client() as c:
            r = c.post(self.chain.rpc_url, json=body)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RPCError(f"{method}: {data['error']}")
        return data["result"]

    # ─── convenience wrappers ───────────────────────────────────
    def block_number(self) -> int:
        return int(self.call("eth_blockNumber"), 16)

    def balance_wei(self, address: str) -> int:
        return int(self.call("eth_getBalance", [address, "latest"]), 16)

    def chain_id(self) -> int:
        return int(self.call("eth_chainId"), 16)

    def tx_count(self, address: str) -> int:
        return int(self.call("eth_getTransactionCount", [address, "pending"]), 16)

    def gas_price(self) -> int:
        return int(self.call("eth_gasPrice"), 16)

    def estimate_gas(self, tx: dict) -> int:
        return int(self.call("eth_estimateGas", [tx]), 16)

    def send_raw_tx(self, signed_hex: str) -> str:
        if not signed_hex.startswith("0x"):
            signed_hex = "0x" + signed_hex
        return self.call("eth_sendRawTransaction", [signed_hex])


def account_from_privkey(privkey_hex: str) -> LocalAccount:
    if not privkey_hex.startswith("0x"):
        privkey_hex = "0x" + privkey_hex
    return Account.from_key(privkey_hex)


def assert_chain_matches(rpc: ProxiedRPC) -> None:
    """Defensive: refuse to operate if RPC chain ID disagrees with registry."""
    seen = rpc.chain_id()
    if seen != rpc.chain.chain_id:
        raise RPCError(
            f"chain id mismatch for {rpc.chain.key}: "
            f"registry={rpc.chain.chain_id}, rpc={seen}. "
            "Refusing to sign on the wrong chain."
        )
