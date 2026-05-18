"""Chain registry. Single source of truth for chain IDs, RPCs, faucets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chain:
    key: str            # 'monad-testnet'
    chain_id: int
    rpc_url: str
    explorer: str
    native_symbol: str
    faucet_url: str | None = None
    faucet_kind: str = "manual"   # 'manual' / 'cli' / 'social'
    notes: str = ""


CHAINS: dict[str, Chain] = {
    # ─── Pipeline-validation testnet ─────────────────────────────
    # Used only to prove signing + proxy + broadcast end-to-end.
    # Sepolia has no airdrop value; do not enroll wallets in production.
    "ethereum-sepolia": Chain(
        key="ethereum-sepolia",
        chain_id=11155111,
        rpc_url="https://ethereum-sepolia.publicnode.com",
        explorer="https://sepolia.etherscan.io",
        native_symbol="ETH",
        faucet_url="https://sepolia-faucet.pk910.de/",
        faucet_kind="pow",
        notes="Validation-only chain. Not for farming.",
    ),

    # ─── Mainnet proof-of-personhood chains ──────────────────────
    # Used only to receive the 0.001 ETH "I'm not a bot" deposit
    # that faucets check against. NOT for farming activity. Read-only.
    "base-mainnet": Chain(
        key="base-mainnet",
        chain_id=8453,
        rpc_url="https://base.publicnode.com",
        explorer="https://basescan.org",
        native_symbol="ETH",
        notes="Mainnet ETH proof-of-personhood receiver.",
    ),
    "arbitrum-mainnet": Chain(
        key="arbitrum-mainnet",
        chain_id=42161,
        rpc_url="https://arbitrum-one.publicnode.com",
        explorer="https://arbiscan.io",
        native_symbol="ETH",
        notes="Mainnet ETH proof-of-personhood receiver.",
    ),

    # ─── Testnets we farm ────────────────────────────────────────
    "monad-testnet": Chain(
        key="monad-testnet",
        chain_id=10143,
        rpc_url="https://testnet-rpc.monad.xyz",
        explorer="https://testnet.monadexplorer.com",
        native_symbol="MON",
        faucet_url="https://faucet.monad.xyz",
        faucet_kind="social",
        notes="Discord-gated faucet; manual claim per wallet.",
    ),
    "megaeth-testnet": Chain(
        key="megaeth-testnet",
        chain_id=6343,
        rpc_url="https://carrot.megaeth.com/rpc",
        explorer="https://www.megaexplorer.xyz",
        native_symbol="ETH",
        faucet_url="https://testnet.megaeth.com/",
        faucet_kind="social",
    ),
    # Bartio was sunset after Berachain mainnet launch.
    # Current testnet is Bepolia.
    "berachain-bepolia": Chain(
        key="berachain-bepolia",
        chain_id=80069,
        rpc_url="https://bepolia.rpc.berachain.com",
        explorer="https://bepolia.beratrail.io",
        native_symbol="BERA",
        faucet_url="https://bepolia.faucet.berachain.com",
        faucet_kind="social",
    ),
    "linea-sepolia": Chain(
        key="linea-sepolia",
        chain_id=59141,
        rpc_url="https://rpc.sepolia.linea.build",
        explorer="https://sepolia.lineascan.build",
        native_symbol="ETH",
        faucet_url="https://www.infura.io/faucet/linea",
        faucet_kind="social",
    ),
    "scroll-sepolia": Chain(
        key="scroll-sepolia",
        chain_id=534351,
        rpc_url="https://sepolia-rpc.scroll.io",
        explorer="https://sepolia.scrollscan.com",
        native_symbol="ETH",
        faucet_url="https://docs.scroll.io/en/user-guide/faucet/",
        faucet_kind="social",
    ),
}


# Map our protocol.id → chain.key
PROTOCOL_TO_CHAIN: dict[str, str] = {
    "monad-tn":     "monad-testnet",
    "megaeth-tn":   "megaeth-testnet",
    "berachain-tn": "berachain-bepolia",
    "sepolia-validate": "ethereum-sepolia",
    "linea-tn":     "linea-sepolia",
    "scroll-tn":    "scroll-sepolia",
}


def for_protocol(protocol_id: str) -> Chain:
    chain_key = PROTOCOL_TO_CHAIN.get(protocol_id)
    if not chain_key:
        raise KeyError(f"no chain mapping for protocol {protocol_id}")
    return CHAINS[chain_key]
