-- Glitch Airdrop Farm — schema v1
-- Database: glitch_airdrop_farm (on local PG17)

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ─────────────────────────────────────────────────────────────
-- IDENTITIES: one per wallet. The "person" the wallet is.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE identity (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  label           text NOT NULL,                  -- 'eth-072'
  camofox_user_id text UNIQUE NOT NULL,           -- camofox session userId
  proxy_url       text NOT NULL,                  -- 'http://user:pass@host:port'
  proxy_country   text NOT NULL,                  -- 'US','DE','SG' etc
  locale          text NOT NULL,                  -- 'en-US','de-DE'
  timezone        text NOT NULL,                  -- 'America/New_York'
  user_agent      text NOT NULL,
  -- Persona traits drawn at creation, used to randomize every action.
  persona         jsonb NOT NULL DEFAULT '{}'::jsonb,
  /* persona example:
     { "slippage_bps":  47,                 -- ranges 30–80
       "activity_window_utc": [13, 21],     -- hours UTC active
       "gas_patience":        "medium",     -- low/medium/high
       "preferred_swaps":    ["USDC/ETH","ETH/wstETH"],
       "weekly_action_count":[4, 9],
       "session_minutes":    [6, 22] } */
  created_at      timestamptz NOT NULL DEFAULT now(),
  retired_at      timestamptz
);

CREATE INDEX identity_active ON identity(retired_at) WHERE retired_at IS NULL;

-- ─────────────────────────────────────────────────────────────
-- WALLETS: 1:1 to identity. EVM + Solana.
-- We store ENCRYPTED private keys. Decryption key lives in env
-- (FARM_WALLET_KEY) and never touches the DB.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE wallet (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  identity_id   uuid NOT NULL REFERENCES identity(id) ON DELETE RESTRICT,
  chain_family  text NOT NULL CHECK (chain_family IN ('evm','svm')),
  address       text NOT NULL,
  privkey_enc   bytea NOT NULL,                  -- libsodium secretbox
  derivation    text,                            -- 'm/44'/60'/0'/0/N' if HD
  funded_at     timestamptz,                     -- first inbound tx confirmed
  status        text NOT NULL DEFAULT 'fresh',   -- fresh/warming/active/paused/burned
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE(chain_family, address)
);

CREATE INDEX wallet_status ON wallet(status);
CREATE INDEX wallet_identity ON wallet(identity_id);

-- ─────────────────────────────────────────────────────────────
-- PROTOCOLS: things we farm.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE protocol (
  id              text PRIMARY KEY,               -- 'linea','scroll','jupiter'...
  display_name    text NOT NULL,
  chain           text NOT NULL,                  -- 'linea-mainnet','solana-mainnet'
  status          text NOT NULL DEFAULT 'active', -- active/paused/snapshotted/dead
  weight          int  NOT NULL DEFAULT 10,       -- airdrop expectation weight, 1-100
  notes           text,
  metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────
-- WALLET ↔ PROTOCOL ENROLLMENT: which wallets farm which protocols
-- ─────────────────────────────────────────────────────────────
CREATE TABLE enrollment (
  wallet_id     uuid REFERENCES wallet(id) ON DELETE CASCADE,
  protocol_id   text REFERENCES protocol(id) ON DELETE CASCADE,
  started_at    timestamptz NOT NULL DEFAULT now(),
  last_action_at timestamptz,
  total_actions int NOT NULL DEFAULT 0,
  total_gas_usd numeric(10,4) NOT NULL DEFAULT 0,
  points_cached jsonb,                            -- last scraped points
  points_at     timestamptz,
  status        text NOT NULL DEFAULT 'active',   -- active/done/abandoned
  PRIMARY KEY (wallet_id, protocol_id)
);

-- ─────────────────────────────────────────────────────────────
-- ACTIONS: every onchain or off-chain step, logged.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE action (
  id            bigserial PRIMARY KEY,
  wallet_id     uuid NOT NULL REFERENCES wallet(id),
  protocol_id   text NOT NULL REFERENCES protocol(id),
  action_type   text NOT NULL,                    -- 'swap','bridge','stake','lp','vote'
  tx_hash       text,
  amount_usd    numeric(12,4),
  gas_usd       numeric(10,4),
  metadata      jsonb NOT NULL DEFAULT '{}'::jsonb,
  succeeded     boolean,
  error         text,
  executed_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX action_wallet_time ON action(wallet_id, executed_at DESC);
CREATE INDEX action_protocol_time ON action(protocol_id, executed_at DESC);

-- ─────────────────────────────────────────────────────────────
-- JOB QUEUE: orchestrator inserts, workers claim.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE job (
  id           bigserial PRIMARY KEY,
  wallet_id    uuid NOT NULL REFERENCES wallet(id),
  protocol_id  text NOT NULL REFERENCES protocol(id),
  playbook     text NOT NULL,                     -- 'linea.daily_swap'
  params       jsonb NOT NULL DEFAULT '{}'::jsonb,
  scheduled_for timestamptz NOT NULL,             -- earliest run time
  claimed_by   text,                              -- worker id
  claimed_at   timestamptz,
  finished_at  timestamptz,
  succeeded    boolean,
  result       jsonb,
  attempts     int NOT NULL DEFAULT 0,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX job_ready ON job(scheduled_for)
  WHERE finished_at IS NULL AND claimed_by IS NULL;

-- ─────────────────────────────────────────────────────────────
-- POINTS SNAPSHOTS: regular scrape per protocol
-- ─────────────────────────────────────────────────────────────
CREATE TABLE points_snapshot (
  id           bigserial PRIMARY KEY,
  wallet_id    uuid NOT NULL REFERENCES wallet(id),
  protocol_id  text NOT NULL REFERENCES protocol(id),
  points       numeric(20,6) NOT NULL,
  rank         int,
  raw          jsonb,
  taken_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ps_lookup ON points_snapshot(wallet_id, protocol_id, taken_at DESC);

-- ─────────────────────────────────────────────────────────────
-- FUNDING LEDGER: every inbound (CEX→wallet) and outbound
-- ─────────────────────────────────────────────────────────────
CREATE TABLE funding (
  id           bigserial PRIMARY KEY,
  wallet_id    uuid REFERENCES wallet(id),
  direction    text NOT NULL CHECK (direction IN ('in','out','internal')),
  source       text,                              -- 'bybit','mexc','wallet:0xabc..'
  asset        text NOT NULL,
  amount       numeric(28,12) NOT NULL,
  amount_usd   numeric(12,4),
  tx_hash      text,
  chain        text,
  at           timestamptz NOT NULL DEFAULT now(),
  notes        text
);
