"""Runtime configuration. Reads from env, never from DB."""

from __future__ import annotations

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            "/etc/glitch-airdrop-farm/.env",
            "/home/support/glitch-airdrop-farm/.env",
            ".env",
        ),
        env_prefix="FARM_",
        extra="ignore",
    )

    # Postgres
    pg_dsn: str = "postgresql:///glitch_airdrop_farm"

    # Wallet encryption — 32 bytes, base64.
    # Generated once: `python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"`
    wallet_key: str = Field(..., min_length=44)

    # Camofox
    camofox_url: str = "http://127.0.0.1:8765"
    camofox_token: str | None = None

    # RPC
    rpc_linea: str = "https://rpc.linea.build"
    rpc_scroll: str = "https://rpc.scroll.io"
    rpc_arbitrum: str = "https://arb1.arbitrum.io/rpc"
    rpc_base: str = "https://mainnet.base.org"
    rpc_solana: str = "https://api.mainnet-beta.solana.com"

    # Proxies — DataImpulse residential gateway
    # Username format supports geo + sticky-session:
    #   <login>__cr.<cc>;sid-<sid>
    # Example: 715fffa...__cr.us;sid-eth-001
    proxy_host: str = "gw.dataimpulse.com"
    proxy_port: int = 823
    proxy_login: str | None = None
    proxy_pass: str | None = None
    proxy_provider: str = "dataimpulse"

    # Brain MCP (optional, for persona state sharing)
    brain_mcp_url: str | None = None
    brain_mcp_token: str | None = None

    # Operational
    worker_concurrency: int = 4
    log_dir: Path = Path("/home/support/glitch-airdrop-farm/logs")

    # Google Sheets sync — impersonated SA on this GCE box
    sheets_spreadsheet_id: str = "1hb-o39wYE9LlrFMCEN-RRhYKFSy-juEBMuuyWDDvk8M"
    sheets_impersonate_sa: str = "glitch-vertex-ai@capable-boulder-487806-j0.iam.gserviceaccount.com"


settings = Settings()  # type: ignore[call-arg]
