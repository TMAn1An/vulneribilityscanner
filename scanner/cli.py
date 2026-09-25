"""Command-line entry point.

Example (route everything through Burp):

    python -m scanner --proxy http://127.0.0.1:8080 --proxy-ca burp-ca.pem https://example.com

Or trust Burp's cert implicitly for a quick test:

    python -m scanner --burp --insecure https://example.com
"""

from __future__ import annotations

import argparse
import sys
from typing import List

import httpx

from . import __version__
from .checks import Finding, run_all
from .http_client import DEFAULT_BURP_PROXY, ProxyConfig, build_client


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="scanner",
        description="Proxy-aware web vulnerability scanner (Burp-friendly).",
    )
    p.add_argument("targets", nargs="+", help="One or more target URLs.")
    p.add_argument(
        "--proxy",
        help="Upstream proxy URL, e.g. http://127.0.0.1:8080 (Burp).",
    )
    p.add_argument(
        "--burp",
        action="store_true",
        help=f"Shortcut for --proxy {DEFAULT_BURP_PROXY}.",
    )
    p.add_argument(
        "--proxy-ca",
        help="Path to the proxy CA cert (PEM) so HTTPS through Burp verifies.",
    )
    p.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS verification (accept Burp's cert without importing it).",
    )
    p.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout (s).")
    p.add_argument("--version", action="version", version=f"scanner {__version__}")
    return p.parse_args(argv)


def _severity_rank(sev: str) -> int:
    return {"high": 3, "medium": 2, "low": 1, "info": 0}.get(sev, 0)


def scan_target(client: httpx.Client, url: str) -> List[Finding]:
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        return [Finding("info", f"Request failed for {url}", str(exc))]
    return run_all(response)


def main(argv: List[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    proxy = args.proxy or (DEFAULT_BURP_PROXY if args.burp else None)
    config = ProxyConfig.from_env(
        proxy=proxy,
        proxy_ca=args.proxy_ca,
        verify=False if args.insecure else None,
        timeout=args.timeout,
    )

    if config.proxy:
        print(f"[*] Routing traffic through proxy: {config.proxy}")
    else:
        print("[*] No proxy set (traffic goes direct). Use --burp to route via Burp.")

    exit_code = 0
    with build_client(config) as client:
        for url in args.targets:
            print(f"\n=== {url} ===")
            findings = scan_target(client, url)
            if not findings:
                print("  No findings.")
                continue
            findings.sort(key=lambda f: _severity_rank(f.severity), reverse=True)
            for f in findings:
                print(f"  [{f.severity.upper():6}] {f.title}")
                print(f"           {f.detail}")
                if _severity_rank(f.severity) >= 2:
                    exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
