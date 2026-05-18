-- Seed protocols. Refresh weights quarterly.

INSERT INTO protocol (id, display_name, chain, status, weight, notes) VALUES
-- TESTNETS (Phase 0 focus — $50 validation plan)
('monad-tn',      'Monad Testnet',           'monad-testnet',     'active', 45, 'Testnet → mainnet TGE 2026. Highest-EV testnet farm.'),
('megaeth-tn',    'MegaETH Testnet',         'megaeth-testnet',   'active', 40, 'Active campaign. Real-time L2 thesis, TGE 2026.'),
('berachain-tn',  'Berachain Bartio',        'berachain-bartio',  'active', 35, 'Bartio testnet feeds mainnet drop.'),
('linea-tn',      'Linea Sepolia',           'linea-sepolia',     'active', 10, 'EVM practice surface; mirror of mainnet flow.'),
('scroll-tn',     'Scroll Sepolia',          'scroll-sepolia',    'active', 10, 'EVM practice surface.'),

-- MAINNETS (Phase 1+; not enrolled until Day 30 kill/scale decision)
('linea',         'Linea LXP',               'linea-mainnet',     'paused', 35, 'L2 from ConsenSys. LXP → TGE 2026.'),
('scroll',        'Scroll Sessions',         'scroll-mainnet',    'paused', 25, 'Scroll Marks program.'),
('berachain',     'Berachain BGT',           'berachain-mainnet', 'paused', 30, 'Post-mainnet BGT/HONEY ecosystem.'),
('hyperliquid',   'Hyperliquid Season 2',    'hyperliquid-l1',    'paused', 40, 'S1 paid $50k–$500k/wallet.'),
('jupiter',       'Jupiter LFG',             'solana-mainnet',    'paused', 25, 'Solana DEX, recurring rewards.'),
('kamino',        'Kamino kPoints',          'solana-mainnet',    'paused', 20, 'SOL lending.'),
('eigenlayer',    'EigenLayer LRT',          'ethereum-mainnet',  'paused', 15, 'High-capital. Phase 2 only.'),
('layerzero',     'LayerZero / Stargate',    'multi',             'paused', 10, 'Multi-chain bridge points.')
ON CONFLICT (id) DO UPDATE SET
  status = EXCLUDED.status,
  weight = EXCLUDED.weight,
  notes  = EXCLUDED.notes;
