"""Linea farming playbook.

Linea LXP points accrue from interactions with whitelisted dapps.
Confirmed-coming token (TGE expected in 2026). Gas costs are cheap
($0.05–$0.50 per tx), so it's the cheapest protocol to validate the
end-to-end pipeline.

Activity menu (rotate, don't repeat):
  - Swap on Lynex / SyncSwap / EchoDEX
  - Bridge ETH in/out via official Linea bridge or Across
  - Provide LP on Lynex stable pools (low IL)
  - Mint NFT on a featured Linea Voyage dapp
  - Vote on snapshot.org governance (where allowed)

This module returns a planned action; the worker executes via
ethers/web3 + the wallet's identity (proxy + camofox session).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

ActionType = Literal["swap", "lp_add", "lp_remove", "bridge_in", "bridge_out", "nft_mint"]


@dataclass
class PlannedAction:
    action_type: ActionType
    dapp: str
    chain_in: str
    chain_out: str | None
    asset_in: str
    asset_out: str | None
    amount_usd: float
    slippage_bps: int
    notes: str


# Whitelisted Linea dapps that historically earn LXP. Refresh quarterly.
LINEA_DAPPS = {
    "swap": ["lynex", "syncswap", "echodex", "openocean"],
    "lp_add": ["lynex", "syncswap"],
    "bridge_in": ["linea-bridge", "across", "stargate"],
    "nft_mint": ["zonic", "element"],
}

# Action weights per session — rough mix observed in real Linea users.
ACTION_MIX = [
    ("swap",       55),
    ("lp_add",     12),
    ("lp_remove",   6),
    ("bridge_in",  15),
    ("bridge_out",  7),
    ("nft_mint",    5),
]


def plan_action(persona: dict, wallet_state: dict) -> PlannedAction:
    """Generate next action for a wallet on Linea, using its persona.

    `wallet_state` should include at minimum:
      - eth_balance_linea_usd: float
      - has_lp_position: bool
      - last_action_type: str | None
    """
    rng = random.Random()

    # Avoid repeating last action immediately — real users vary.
    last = wallet_state.get("last_action_type")
    mix = [(a, w) for a, w in ACTION_MIX if a != last] or ACTION_MIX

    # Force bridge_in if balance too low; LP-remove only if has LP.
    bal = wallet_state.get("eth_balance_linea_usd", 0)
    if bal < 5:
        chosen: ActionType = "bridge_in"
    elif not wallet_state.get("has_lp_position", False):
        mix = [(a, w) for a, w in mix if a != "lp_remove"]
        chosen = _weighted(mix, rng)
    else:
        chosen = _weighted(mix, rng)

    lo, hi = persona["swap_size_usd_range"]
    amt = rng.uniform(lo, hi)

    if chosen == "swap":
        pair = rng.choice([("USDC", "WETH"), ("WETH", "USDC"),
                           ("USDC", "USDT"), ("WETH", "wstETH")])
        return PlannedAction(
            action_type="swap",
            dapp=rng.choice(LINEA_DAPPS["swap"]),
            chain_in="linea",
            chain_out=None,
            asset_in=pair[0],
            asset_out=pair[1],
            amount_usd=round(amt, 2),
            slippage_bps=persona["slippage_bps"],
            notes=f"linea swap {pair[0]}->{pair[1]}",
        )
    if chosen == "lp_add":
        return PlannedAction(
            action_type="lp_add",
            dapp=rng.choice(LINEA_DAPPS["lp_add"]),
            chain_in="linea",
            chain_out=None,
            asset_in="USDC/USDT",
            asset_out=None,
            amount_usd=round(min(amt, 60), 2),
            slippage_bps=persona["slippage_bps"],
            notes="stable LP add",
        )
    if chosen == "lp_remove":
        return PlannedAction(
            action_type="lp_remove", dapp="lynex", chain_in="linea",
            chain_out=None, asset_in="LP", asset_out=None,
            amount_usd=0, slippage_bps=persona["slippage_bps"],
            notes="LP remove",
        )
    if chosen == "bridge_in":
        return PlannedAction(
            action_type="bridge_in",
            dapp=rng.choice(LINEA_DAPPS["bridge_in"]),
            chain_in=rng.choice(["arbitrum", "base", "ethereum"]),
            chain_out="linea",
            asset_in="ETH",
            asset_out="ETH",
            amount_usd=round(rng.uniform(20, 60), 2),
            slippage_bps=0,
            notes="bridge in for activity",
        )
    if chosen == "bridge_out":
        return PlannedAction(
            action_type="bridge_out",
            dapp="across",
            chain_in="linea",
            chain_out=rng.choice(["arbitrum", "base"]),
            asset_in="ETH", asset_out="ETH",
            amount_usd=round(rng.uniform(10, 30), 2),
            slippage_bps=0,
            notes="bridge out",
        )
    return PlannedAction(
        action_type="nft_mint",
        dapp=rng.choice(LINEA_DAPPS["nft_mint"]),
        chain_in="linea", chain_out=None,
        asset_in="ETH", asset_out=None,
        amount_usd=round(rng.uniform(0.5, 3), 2),
        slippage_bps=0,
        notes="voyage nft mint",
    )


def _weighted(pairs, rng):
    total = sum(w for _, w in pairs)
    r = rng.uniform(0, total)
    upto = 0
    for v, w in pairs:
        upto += w
        if upto >= r:
            return v
    return pairs[-1][0]
