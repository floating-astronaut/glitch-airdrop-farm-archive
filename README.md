# Glitch Airdrop Farm

AI-orchestrated crypto airdrop farming across EVM and Solana ecosystems.
100–500 wallets, each with isolated identity, executing protocol-native
activity patterns designed to survive Sybil detection.

## Why this stack

| Risk vector | Median farmer | This stack |
|---|---|---|
| Browser fingerprint reuse | Multilogin (manual) | `camofox-browser` — per-wallet `userId`, automated |
| Behavior correlation across wallets | Same script everywhere | Brain MCP enforces uncorrelated action graphs |
| Funding-source clustering | One CEX → many wallets in days | Time-staggered, multi-hop, multi-CEX funding |
| State tracking | Notion / Google Sheets | Postgres + LISTEN/NOTIFY, queryable |
| Activity scheduling | Cron-spammed at top of hour | Per-wallet circadian + variance |

## Phases

**Phase 0 — Setup** (Week 1, ~$500)
- Provision wallets, proxies, exchange accounts
- Schema + identity pool seeded
- 5 wallets fully wired end-to-end on one protocol (Linea)

**Phase 1 — Validation** (Weeks 2–4, ~$1,500)
- Scale to 25 wallets across 2 protocols (Linea + Scroll)
- Confirm no Sybil correlation (different IPs/fingerprints visible
  in protocol explorers)
- Confirm points accrue per wallet

**Phase 2 — Production** (Months 2–4, ~$5–8k)
- Scale to 100–300 wallets across 5–7 protocols
- Add Solana ecosystem (Jupiter, Kamino, Drift, MarginFi)
- Daily snapshot of points per wallet

**Phase 3 — Harvest** (rolling)
- Watch for snapshot announcements via LISTEN/NOTIFY
- Claim, consolidate, off-ramp through clean exit paths

## Target protocols (refresh quarterly; see `protocols/active.md`)

EVM:
- Linea (LXP points, LayerZero-era)
- Scroll (Sessions / Scroll Marks)
- Berachain (BGT, post-mainnet)
- Monad (mainnet activity)
- MegaETH (testnet → mainnet)
- Hyperliquid Season 2
- EigenLayer LRT stack (Renzo, Puffer, Kelp)
- LayerZero / Stargate / Plume

Solana:
- Jupiter (perpetuals + LFG)
- Kamino (kPoints)
- Drift (Drift Foundation drops)
- MarginFi (mrgnLEND points)
- Sanctum
- Eclipse (separate L2, EVM+SVM-compatible)

## Sub-systems

```
                    ┌─────────────────┐
                    │  Orchestrator   │  scheduler + per-wallet circadian
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
 ┌────────────┐     ┌─────────────────┐    ┌──────────────┐
 │  Worker N  │     │  Worker N+1     │    │  Worker N+M  │
 │ (1 wallet) │     │  (1 wallet)     │    │ (1 wallet)   │
 └─────┬──────┘     └────────┬────────┘    └──────┬───────┘
       │                     │                    │
       ▼                     ▼                    ▼
 ┌─────────────┐    ┌────────────────┐    ┌──────────────┐
 │ camofox     │    │  RPC calls     │    │  Brain MCP   │
 │ (DEX UI)    │    │  (ethers.py)   │    │  state log   │
 └─────────────┘    └────────────────┘    └──────────────┘
```

Each worker = one wallet's autonomous loop, driven by Postgres job queue.

## Key principle: do not script identically

Sybil detection looks for behavioral correlation, not just IP overlap.
Two wallets that always swap USDC→ETH at 14:32:01 with the same
slippage tolerance are Sybils even on different IPs.

Brain MCP holds **per-wallet persona traits** (preferred slippage, time
of day window, swap pair preferences, gas-price patience, protocol
sequence). Every action draws from the wallet's persona, not a global
default. Two wallets should look like two different humans — not two
runs of the same script.

## Non-goals

- We do not exploit, drain, or attack any protocol.
- We do not impersonate any specific real human.
- We do not violate any sanctions / OFAC list.
- Sybil-farming is grey — protocols may disqualify wallets they
  detect as farmed. That is priced into the EV model. We will not
  attempt to subvert post-snapshot disqualification reviews.
