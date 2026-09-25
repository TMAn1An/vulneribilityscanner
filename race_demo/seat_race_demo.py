#!/usr/bin/env python3
"""
Self-contained, SAFE reproduction of the seat-overbooking race condition.

It does NOT touch the live site. It builds a tiny local database with one
section (capacity 40, already 39 enrolled) and shows:

  1) THE BUG  - the "read -> check < 40 -> write +1" logic used non-atomically.
                Two students enrolling at the same instant BOTH succeed,
                pushing the section to 41/40.  (This is exactly the pattern
                behind the live 41/41 you observed.)

  2) THE FIX  - a single atomic "UPDATE ... WHERE enrolled < capacity".
                The second concurrent student is correctly rejected, and the
                section stays at 40/40.

Run:  python seat_race_demo.py
Needs only Python's standard library.
"""

import sqlite3
import threading
import time

CAPACITY = 40


def make_db():
    """Fresh in-memory-style DB (file so multiple connections can share it)."""
    con = sqlite3.connect("seatdemo.db")
    con.execute("DROP TABLE IF EXISTS sections")
    con.execute("CREATE TABLE sections (id INTEGER PRIMARY KEY, "
                "capacity INTEGER, enrolled INTEGER)")
    con.execute("INSERT INTO sections (id, capacity, enrolled) VALUES (1, ?, ?)",
                (CAPACITY, 39))          # start at 39/40 -> one seat left
    con.commit()
    con.close()


def seats():
    con = sqlite3.connect("seatdemo.db")
    row = con.execute("SELECT enrolled, capacity FROM sections WHERE id=1").fetchone()
    con.close()
    return row


# ----------------------------------------------------------------------
# 1) VULNERABLE enrollment: check and write are SEPARATE steps (TOCTOU).
# ----------------------------------------------------------------------
def enroll_vulnerable(student, barrier, results):
    con = sqlite3.connect("seatdemo.db")
    barrier.wait()                                   # line everyone up...
    enrolled, capacity = con.execute(
        "SELECT enrolled, capacity FROM sections WHERE id=1").fetchone()  # READ (39)
    if enrolled < capacity:                          # CHECK (39 < 40 -> true for BOTH)
        time.sleep(0.05)                             # the tiny real-world gap
        # WRITE is a relative increment. Both threads already passed the check
        # above, so the two increments stack: 39 -> 40 -> 41 (over capacity).
        con.execute("UPDATE sections SET enrolled = enrolled + 1 WHERE id=1")
        con.commit()
        results[student] = "ENROLLED"
    else:
        results[student] = "REJECTED (full)"
    con.close()


# ----------------------------------------------------------------------
# 2) FIXED enrollment: ONE atomic statement enforces the limit.
# ----------------------------------------------------------------------
def enroll_fixed(student, barrier, results):
    con = sqlite3.connect("seatdemo.db")
    barrier.wait()
    cur = con.execute(
        "UPDATE sections SET enrolled = enrolled + 1 "
        "WHERE id=1 AND enrolled < capacity")        # check + write in ONE step
    con.commit()
    results[student] = "ENROLLED" if cur.rowcount == 1 else "REJECTED (full)"
    con.close()


def run(title, target):
    make_db()
    print(f"\n=== {title} ===")
    print(f"Before: {seats()[0]}/{seats()[1]}  (one seat left)")
    barrier = threading.Barrier(2)
    results = {}
    t1 = threading.Thread(target=target, args=("Student A", barrier, results))
    t2 = threading.Thread(target=target, args=("Student B", barrier, results))
    t1.start(); t2.start(); t1.join(); t2.join()
    for s, r in sorted(results.items()):
        print(f"  {s}: {r}")
    enrolled, capacity = seats()
    verdict = "OVERBOOKED!  <-- the bug" if enrolled > capacity else "limit held"
    print(f"After:  {enrolled}/{capacity}   ->  {verdict}")


if __name__ == "__main__":
    print("Two students try to take the SAME 39/40 section at the SAME instant.")
    run("1) VULNERABLE  (check-then-write, like the live site)", enroll_vulnerable)
    run("2) FIXED       (atomic UPDATE ... WHERE enrolled < capacity)", enroll_fixed)
    print("\nConclusion: the non-atomic check lets two enrollments exceed the "
          "limit (40 -> 41).\nThe atomic update rejects the second one, so the "
          "40-seat rule always holds.")
