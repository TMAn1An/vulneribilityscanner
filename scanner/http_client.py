"""Proxy-aware HTTP client.

The whole point of this module is Burp integration: build a client that sends
every request through an upstream proxy (Burp's proxy listener, default
http://127.0.0.1:8080) so the traffic is visible and interceptable in Burp.

Burp presents its own CA for HTTPS interception, so when proxying HTTPS you
must either trust Burp's CA (``proxy_ca``) or disable verification
(``verify=False``) for testing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import httpx

# Burp Suite's default proxy listener.
DEFAULT_BURP_PROXY = "http://127.0.0.1:8080"


@dataclass
class ProxyConfig:
    """How the scanner should route traffic through a proxy such as Burp."""

    proxy: Optional[str] = None
    """Upstream proxy URL, e.g. ``http://127.0.0.1:8080``. If None, no proxy
    is used unless HTTP(S)_PROXY environment variables are set."""

    proxy_ca: Optional[str] = None
    """Path to the proxy's CA certificate (Burp: Proxy > Options > Import /
    export CA certificate > 'Certificate in DER format', then convert to PEM).
    Used to verify HTTPS through Burp without disabling verification."""

    verify: bool = True
    """TLS verification. Set False to accept Burp's cert without importing its
    CA (testing only)."""

    timeout: float = 20.0

    @classmethod
    def from_env(cls, **overrides) -> "ProxyConfig":
        """Build config, letting explicit kwargs override HTTP(S)_PROXY env."""
        env_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        cfg = cls(proxy=env_proxy)
        for key, value in overrides.items():
            if value is not None:
                setattr(cfg, key, value)
        return cfg

    def use_burp_default(self) -> "ProxyConfig":
        """Convenience: point at Burp's default listener."""
        self.proxy = DEFAULT_BURP_PROXY
        return self


def build_client(config: ProxyConfig, headers: Optional[dict] = None) -> httpx.Client:
    """Create an ``httpx.Client`` wired to route through the configured proxy.

    Passing the resulting client to the scanner ensures every request it makes
    flows through Burp when ``config.proxy`` is set.
    """
    # httpx uses `verify` for both the CA bundle path and the on/off toggle.
    verify: object = config.verify
    if config.proxy_ca:
        verify = config.proxy_ca

    default_headers = {
        "User-Agent": "vulneribilityscanner/0.1 (+burp-proxy-aware)",
    }
    if headers:
        default_headers.update(headers)

    return httpx.Client(
        proxy=config.proxy,
        verify=verify,
        timeout=config.timeout,
        follow_redirects=True,
        headers=default_headers,
    )
