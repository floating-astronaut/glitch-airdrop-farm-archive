# $50 / 30-day validation plan

Goal: prove the pipeline works end-to-end on **testnets** with 5
isolated wallets, so that by Day 30 you have a kill/scale decision
based on real data — not on $thousands of risked capital.

## Budget (hard cap: $50)

| Item | Cost | When |
|---|---|---|
| IPRoyal residential proxy starter — 1GB sticky | $7 | Day 1 |
| Bybit deposit (refundable; only to test withdrawal mechanics) | $20 | Day 3 |
| Contingency / extra proxy GB if needed | $13 | Day 14 |
| LLM inference (Claude Haiku, your existing key) | ~$5 | rolling |
| Testnet gas | $0 | rolling |
| **Total** | **$45** | |

Mainnet money: **$0.** Not a single mainnet transaction in 30 days.

## Targets — 5 wallets × 3 testnets

| Wallet # | Geo persona | Protocols enrolled |
|---|---|---|
| 1 | US-East | Monad testnet, MegaETH testnet, Berachain Bartio |
| 2 | DE | Monad testnet, MegaETH testnet, Linea Sepolia |
| 3 | SG | Monad testnet, Berachain Bartio, Scroll Sepolia |
| 4 | BR | MegaETH testnet, Berachain Bartio, Linea Sepolia |
| 5 | JP | Monad testnet, Scroll Sepolia, Linea Sepolia |

Geo spread is deliberate: when proxy IPs land in different countries,
the wallet's locale + timezone + UA all match the proxy geo via
persona. A Sybil detector grouping by `country code` will see five
unrelated users.

## Why these 3 testnets

- **Monad** — testnet activity is the only path to the mainnet drop.
  Confirmed-coming. Most farmers underrate the value-per-tx because
  it's free.
- **MegaETH** — high-FDV expected mainnet TGE 2026. Active testnet
  campaign now.
- **Berachain Bartio** — already-known generous drop mechanics; we
  build behavioral history early.

Linea Sepolia and Scroll Sepolia are bonus — they let us practice
EVM flows that mirror their mainnet counterparts, with zero gas.

## What "1 action" means per wallet per protocol

- 1 swap on the protocol's main DEX (testnet token <-> testnet stable)
- 1 LP add (sometimes)
- 1 bridge (sometimes)
- 1 small NFT mint on a featured dapp

Each wallet does ~3–6 actions per week per protocol, drawn from its
persona's `weekly_actions_range`.

## Weekly cadence

| Day | What happens |
|---|---|
| **W1 D1** | Apply schema, generate wallet key, provision 5 wallets |
| **W1 D2** | Wire IPRoyal proxy pool, assign 1 sticky IP per identity |
| **W1 D3** | Faucet 5 wallets on Monad, MegaETH, Berachain Bartio |
| **W1 D4–7** | First 2 actions per wallet per protocol; verify each tx via explorer + log to DB |
| **W2** | Daily 1–2 actions per wallet (orchestrator-driven). Add Scroll/Linea Sepolia. |
| **W3** | Add points-scraping where dashboards exist. Compare points-earned per wallet. |
| **W4** | Stress test: stop scripting, let orchestrator run unattended for 5 days. Verify nothing breaks. |

## Day-30 kill/scale decision matrix

After 30 days, look at the wallets in your DB:

| Signal | Kill | Scale |
|---|---|---|
| 5 wallets still alive (no captcha walls, no shadow-bans) | <3 alive | ≥4 alive |
| Each wallet ran ≥15 successful txs | <10 | ≥15 |
| Wallets touched all enrolled protocols | <70% coverage | ≥90% |
| Monad/MegaETH points dashboards show accrual | flat | growing |
| Activity timing across wallets is genuinely uncorrelated (manual eyeball) | clustered | dispersed |
| One wallet's behavior is *visibly distinguishable* from another's | feels scripted | feels human |

**If you hit ≥4 of the "scale" column → put $300 toward Tier 1
(Linea mainnet, 5 wallets).** Don't go to $1000+ until Tier 1 also
proves out at day 60.

## What to NOT do during 30 days

- ❌ No mainnet transactions on any wallet.
- ❌ No funding wallets from your real-name CEX accounts.
- ❌ No reusing browser sessions across wallets (camofox enforces, but operator
  habit is the leak).
- ❌ No "let me speed this up" mass-action bursts. Patience is the moat.
- ❌ No telling friends specific addresses you're farming with — addr clusters
  leak through chat platforms.

## What "done" looks like at Day 30

- 5 wallets, 5 identities, 3+ protocols, 75+ logged actions in `action` table.
- A `points_snapshot` for each (wallet, protocol) showing growth over time.
- An honest gut-check: "would a Sybil-hunter looking at these 5 wallets
  side-by-side think they were the same operator?" If yes, the moat
  isn't there yet — fix before scaling. If no, you have something.

## What we build this week (code)

1. `workers/executor.py` — claim job → load wallet → camofox session → execute via RPC or UI. Testnet-only initially.
2. `identity/proxy_pool.py` — IPRoyal client with sticky sessions per identity.
3. `workers/faucet.py` — auto-claim testnet faucets where possible (Monad, MegaETH, Berachain).
4. `protocols/monad.py`, `protocols/megaeth.py`, `protocols/berachain.py` — playbooks like `linea.py`.
5. systemd units for orchestrator + 2 workers.

I'll wire these once you've signed up for IPRoyal and have the proxy
gateway credentials.
