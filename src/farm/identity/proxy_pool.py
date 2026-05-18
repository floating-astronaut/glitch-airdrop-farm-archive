"""DataImpulse residential proxy pool.

Each identity gets a deterministic sticky session ID derived from
its label, so the *same* identity always lands on (or near) the
*same* exit IP for the duration of a session window. Different
identities get visibly different IPs.

DataImpulse username format:
    <login>__cr.<cc>;sid-<sid>

  - cc:  ISO 3166-1 alpha-2, lower-case (us, gb, de, ...)
  - sid: arbitrary string; same sid → same exit IP, ~10 min sticky
         (DataImpulse default; refreshes if upstream IP rotates)
"""

from __future__ import annotations

from dataclasses import dataclass

from farm.config import settings


@dataclass
class ProxyHandle:
    """Everything needed to wire a proxied HTTP/HTTPS connection."""
    scheme: str       # 'http'
    host: str
    port: int
    username: str     # composed login with geo + sid
    password: str
    country: str      # 'us', 'de', etc

    @property
    def url(self) -> str:
        return f"{self.scheme}://{self.username}:{self.password}@{self.host}:{self.port}"

    def as_requests_dict(self) -> dict:
        return {"http": self.url, "https": self.url}

    def as_camofox_options(self) -> dict:
        """Shape camofox /start expects: server + username + password."""
        return {
            "server": f"{self.scheme}://{self.host}:{self.port}",
            "username": self.username,
            "password": self.password,
        }


def for_identity(label: str, country: str) -> ProxyHandle:
    """Return a sticky-session proxy handle for an identity.

    `label`   → used as the stable sticky-session id
    `country` → 2-letter country code (lower-cased)
    """
    if not settings.proxy_login or not settings.proxy_pass:
        raise RuntimeError(
            "FARM_PROXY_LOGIN / FARM_PROXY_PASS not set in env"
        )

    cc = country.lower()
    sid = _safe_sid(label)
    username = f"{settings.proxy_login}__cr.{cc};sid-{sid}"

    return ProxyHandle(
        scheme="http",
        host=settings.proxy_host,
        port=settings.proxy_port,
        username=username,
        password=settings.proxy_pass,
        country=cc,
    )


def _safe_sid(label: str) -> str:
    """DataImpulse sids should be alphanum; sanitize the identity label."""
    return "".join(c for c in label if c.isalnum() or c in "-_")[:32] or "default"
