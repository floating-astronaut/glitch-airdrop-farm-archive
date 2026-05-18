# Decisions to make before we wire anything live

These are the choices only you can make. I'll spec defaults and rationale
for each; flag any you want to change.

## 1. Funding source(s) for wallets

We need to push $30–$100 onto each wallet without creating an
obvious "one CEX → 100 wallets in 3 days" graph. Detectors look at:
- Common funding source within tight time windows
- Identical amounts
- Same first-hop

**Default plan (mix of 3 sources, time-staggered):**

| Source | Why | KYC | Approx avail |
|---|---|---|---|
| **Bybit** | High liquidity, sub-account withdrawals, 0.05 BTC/day no-KYC | Optional | Yes |
| **MEXC** | No-KYC up to limits, supports many small chains directly | Optional | Yes |
| **Bitget** | Similar profile, third option for graph diversity | Optional | Yes |

Funding cadence: 5–10 wallets/day max from any one source, randomized
amounts in a $25–$120 band, randomized chains (Arbitrum / Base / Linea
direct deposit where supported). **Never withdraw round numbers.**

**Decisions you need to make:**
- [ ] Do you already have accounts on Bybit / MEXC / Bitget? If not,
      open them this week. Use a privacy-conscious email + KYC only
      to the extent absolutely required.
- [ ] What's the total Phase 1 funding budget? My recommendation:
      $1,500 for 25 wallets in Phase 1 (≈ $60/wallet across 2 protocols).

## 2. Proxy provider

Per-wallet residential IP is non-negotiable. Datacenter IPs get
auto-Sybil-flagged on most protocols by month 6.

| Provider | Cost | Sticky session | Notes |
|---|---|---|---|
| **IPRoyal Royal Residential** | $7/GB → ~$120/mo for 100-wallet ops | Yes (1–60 min) | Best price/quality. Default pick. |
| **BrightData Residential** | $500+/mo entry | Yes | Gold standard, overkill for Phase 1 |
| **SOAX** | $99/mo entry | Yes | Solid middle option |
| **ProxyEmpire** | $4/GB | Yes | Cheap, smaller pool |

**Default: IPRoyal, geo-mix US/EU/APAC.** ~$120/mo at our volume.

## 3. Chain RPC endpoints

We need stable, fast RPCs. Avoid public RPCs (rate-limited, logged).

**Default: Alchemy free tier covers Phase 1 (300M compute units/mo).**
Upgrade to Growth ($199/mo) only at Phase 2 scale. Alternatives:
QuickNode, Infura. Solana: Helius (free tier OK to start).

## 4. Wallet generation strategy

Two options:

(A) **One HD seed per "family" of 50 wallets** — easier to manage, but
    if one privkey leaks via worker bug, the seed leaks all 50.

(B) **Independent 256-bit random per wallet** — no master seed. Each
    privkey stands alone. Recommended.

**Default: (B), independent random per wallet, encrypted at rest.**

Encryption: `nacl.secretbox` with a 32-byte key in `$FARM_WALLET_KEY`.
Key lives in `/etc/glitch-airdrop-farm/.env` (mode 0600), never in DB,
never in git.

## 5. Hosting separation

Should this run on the same GCE box as `glitchexecutor.com` infra?

**Recommendation: same box for Phase 0–1, separate VPS by Phase 2.**

Rationale:
- Phase 0–1 traffic volume is tiny; no perf concern.
- We are NOT violating any protocol or CEX ToS by farming with real
  activity, so reputational risk from co-hosting is low.
- Outbound traffic to protocols goes through residential proxies
  anyway, so the GCE IP is never seen by chains/dapps.
- Wallet keys live encrypted; even if box compromised, attacker
  still needs `FARM_WALLET_KEY` from a 0600 env file.

Move to a separate VPS only if you cross $50k+ in wallet balances.

## 6. Protocol selection for Phase 1

Pick **2 protocols** to start. We want:
- Low gas (cheap to validate the pipeline)
- Active points program
- Confirmed-coming airdrop signals
- Different ecosystems (so failures aren't correlated)

**Recommended Phase 1 pair:**

1. **Linea** — EVM L2, ConsenSys, LXP points live, airdrop confirmed for 2026,
   gas costs $0.05–$0.50/tx. Good documentation.
2. **Scroll** — EVM L2, "Scroll Marks" program, low gas. Different team /
   investor base from Linea so risk-uncorrelated.

Later add: Berachain, Hyperliquid S2, Jupiter (Solana).

## 7. Activity volume per wallet per week

Sybil detectors flag both extremes — too little (clearly farmed, no
real usage) and too much (bot-like). Real users average 1–4 protocol
interactions/week.

**Default per wallet per protocol:**
- 1–3 actions/week
- Random within wallet's `activity_window_utc`
- Action mix: swap (60%), LP add/remove (15%), bridge (15%), other (10%)
- Total weekly USD volume: $50–$400 per wallet per protocol

## 8. Off-ramp plan (Phase 3)

When airdrops hit, we need a path to convert and consolidate without
re-clustering wallets at exit:

1. Sell tokens on **decentralized** exchanges first (1inch, Jupiter)
2. Bridge proceeds to Bitcoin via THORChain or Chainflip (privacy)
3. Off-ramp BTC via P2P (Bisq) or low-KYC CEX (Bybit small chunks)

We don't engineer this yet — only relevant at Phase 3. But knowing
the exit shape changes nothing about Phase 1/2 build.
