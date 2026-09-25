# Seat Overbooking — Safe Race-Condition Reproduction

A self-contained demo that reproduces the **41/40 seat overbooking** bug and its
fix **without touching the live site**. Use it to show your faculty *how* the bug
happens and *why* the fix works.

## Run it

```bash
python seat_race_demo.py
```

Only Python's standard library is needed (no install). It creates a local
`seatdemo.db` (a tiny SQLite database) with one section at **39/40**, then:

1. **VULNERABLE run** — two students enroll at the same instant using the same
   *read → check `< 40` → write `+1`* logic as the live site. Both pass the
   check before either writes, so the section ends at **41/40 (OVERBOOKED)**.
2. **FIXED run** — the same two students, but enrollment uses a single atomic
   `UPDATE ... WHERE enrolled < capacity`. The second student is correctly
   **rejected**, and the section stays at **40/40**.

## What to say to your faculty

> "The live site enforces the 40-seat limit in two separate steps — it reads the
> count, checks it is below 40, then writes the increased count. When two
> requests arrive at the same moment (which my bot does), both read 39, both
> pass the check, and both increment — so the section reaches 41. This demo
> reproduces that exact mechanism locally. The fix moves the check and the write
> into one atomic database statement, so the second request is rejected and the
> limit always holds."

This is the standard, safe way to demonstrate a server-side race condition:
reproduce the *mechanism* in a controlled environment rather than attacking the
live system (which would corrupt real students' enrollments).
