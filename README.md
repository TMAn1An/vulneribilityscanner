# vulneribilityscanner

A small, **proxy-aware** web vulnerability scanner. Its defining feature is
first-class integration with an upstream proxy such as **Burp Suite**: every
request the scanner makes can be routed through Burp so you can observe,
intercept, and manually test the traffic in Burp's *Proxy > HTTP history*.

Currently it runs a set of lightweight **passive** checks (security headers,
technology disclosure, insecure cookie flags) — one GET per target. The value
of the Burp integration is that once traffic is flowing through Burp you can
pivot any captured request into Repeater / Intruder for deeper manual testing.

## Install

```bash
pip install -r requirements.txt
```

## Usage

Direct (no proxy):

```bash
python -m scanner https://example.com
```

Through Burp (the reason this project exists):

```bash
# 1. Start Burp. Its Proxy listener defaults to 127.0.0.1:8080.
# 2. Run the scanner pointed at Burp:
python -m scanner --burp --insecure https://example.com
```

`--burp` is shorthand for `--proxy http://127.0.0.1:8080`.

### HTTPS through Burp without --insecure

Burp intercepts HTTPS by presenting its own CA, so a normal client rejects the
certificate. Two options:

- **Quick/testing:** add `--insecure` to skip TLS verification.
- **Proper:** export Burp's CA and trust it:
  1. In Burp: *Proxy > Proxy settings > Import / export CA certificate >
     Certificate in DER format* → save as `burp-ca.der`.
  2. Convert to PEM: `openssl x509 -inform der -in burp-ca.der -out burp-ca.pem`
  3. Run: `python -m scanner --proxy http://127.0.0.1:8080 --proxy-ca burp-ca.pem https://example.com`

## Important: running against Burp on your machine

This scanner talks to Burp over a normal HTTP proxy connection, so **run the
scanner on the same machine (or network) as Burp**. If you launch it from an
isolated environment (a CI runner, a cloud sandbox), `127.0.0.1:8080` refers to
*that* environment, not your laptop — point `--proxy` at a Burp instance the
scanner can actually reach.

## Options

| Flag | Description |
|------|-------------|
| `--proxy URL` | Upstream proxy, e.g. `http://127.0.0.1:8080`. |
| `--burp` | Shortcut for Burp's default listener. |
| `--proxy-ca PATH` | Burp CA cert (PEM) to verify HTTPS interception. |
| `--insecure` | Disable TLS verification (testing only). |
| `--timeout SECONDS` | Per-request timeout (default 20). |

`HTTP_PROXY` / `HTTPS_PROXY` environment variables are also honored when no
`--proxy`/`--burp` flag is given.

## Only test what you're authorized to test

Point this at systems you own or have explicit written permission to assess.
