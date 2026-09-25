"""A small set of passive security checks.

These are deliberately non-intrusive: a single GET per target. When the client
is proxied through Burp, the request and response are captured in Burp's HTTP
history, so you can pivot to Repeater/Intruder for deeper manual testing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import httpx


@dataclass
class Finding:
    severity: str  # "info" | "low" | "medium" | "high"
    title: str
    detail: str


# Security response headers we expect to see, and why they matter.
_SECURITY_HEADERS = {
    "strict-transport-security": "HSTS not set; connection may be downgraded to HTTP.",
    "content-security-policy": "No CSP; increased XSS/data-injection exposure.",
    "x-content-type-options": "Missing 'nosniff'; MIME-sniffing possible.",
    "x-frame-options": "Missing; page may be clickjacked (unless CSP frame-ancestors set).",
    "referrer-policy": "No Referrer-Policy; referrer data may leak.",
}


def check_security_headers(response: httpx.Response) -> List[Finding]:
    findings: List[Finding] = []
    present = {k.lower() for k in response.headers.keys()}
    for header, why in _SECURITY_HEADERS.items():
        if header not in present:
            findings.append(
                Finding("low", f"Missing security header: {header}", why)
            )
    return findings


def check_server_disclosure(response: httpx.Response) -> List[Finding]:
    findings: List[Finding] = []
    for header in ("server", "x-powered-by"):
        value = response.headers.get(header)
        if value:
            findings.append(
                Finding(
                    "info",
                    f"Technology disclosure via '{header}'",
                    f"{header}: {value}",
                )
            )
    return findings


def check_cookies(response: httpx.Response) -> List[Finding]:
    findings: List[Finding] = []
    for raw in response.headers.get_list("set-cookie"):
        low = raw.lower()
        name = raw.split("=", 1)[0].strip()
        missing = [flag for flag in ("secure", "httponly") if flag not in low]
        if missing:
            findings.append(
                Finding(
                    "low",
                    f"Cookie '{name}' missing flags: {', '.join(missing)}",
                    raw.split(";", 1)[0],
                )
            )
    return findings


ALL_CHECKS = (check_security_headers, check_server_disclosure, check_cookies)


def run_all(response: httpx.Response) -> List[Finding]:
    findings: List[Finding] = []
    for check in ALL_CHECKS:
        findings.extend(check(response))
    return findings
