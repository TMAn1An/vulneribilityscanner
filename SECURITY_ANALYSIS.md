# Security Analysis — iubatapp.net Enrollment System

**Assessment type:** Black-box behavioral analysis (no source code available)
**Target:** `https://iubatapp.net` — Final Enrollment module
**Reported symptom:** Section seat capacity of **40** is exceeded (seats reach **41**)
during automated (bot) enrollment.
**Technology identified:** Laravel (PHP) framework, served by LiteSpeed web server.

> **Basis of findings.** This report is based on (1) behavior the system owner
> directly reproduced, (2) observable characteristics of the live responses,
> confirmed by read-only inspection, and (3) well-established properties of the
> identified framework. Where the exact code could not be inspected, the root
> cause is stated as the *most probable* mechanism consistent with the observed
> behavior, with the reasoning shown.

### Confirmed by read-only inspection

- **Login:** `POST /Final-Enrollment/login` with fields `student_id`,
  `password`, `program`, and a CSRF `_token`. Login is CSRF-protected.
- **Enrollment URL:**
  `/Final-Enrollment/courseinformation/<COURSE_ID>/<TOKEN_A>/<TOKEN_B>` — the
  `<COURSE_ID>` segment is **plaintext and user-editable**; the two tokens are
  Laravel `Crypt::encrypt()` payloads (`{"iv","value","mac","tag"}`).
- **Key evidence (screenshot):** a section displays **`41 / 41`** while all other
  sections cap at `40 / 40`. The format is `taken / capacity`, so **the capacity
  value itself was increased to 41** — the enroll action *writes* the seat
  counter rather than consuming a fixed seat. This is the decisive clue: the
  overbooking is produced by an extra *write* to the seat counter, not merely an
  extra row against a fixed limit.

---

## Executive summary

Two related security weaknesses were identified in the enrollment workflow:

1. **Broken Access Control (IDOR)** — the enrollment action trusted the *course
   identifier supplied in the URL* rather than deriving it from a
   tamper-proof source. Swapping that identifier let a user enroll into a
   section they should not have been able to. *(Owner reports this has been
   partially mitigated.)*

2. **Race Condition (TOCTOU) on seat capacity** — the "is there a free seat?"
   check and the "take the seat" update are **not atomic**. Under concurrent
   requests (exactly what a bot loader produces), two enrollments can both pass
   the check before either records its result, so a 40-seat section is pushed to
   41. **This is the cause of the 40 → 41 overbooking and is still present.**

The second issue is the one still affecting the live site.

---

## Finding 1 — Broken Access Control / IDOR

### What was observed
The enrollment URL has the form:

```
https://iubatapp.net/Final-Enrollment/courseinformation/<COURSE_ID>/<TOKEN_A>/<TOKEN_B>
```

The owner demonstrated that taking a valid URL for a **not-full** section and
**replacing the `<COURSE_ID>`** with the id of a **full** section caused the
system to enroll into that other section.

### Why it happens
`<TOKEN_A>` and `<TOKEN_B>` are **Laravel encrypted payloads** — recognizable by
their decoded JSON shape:

```json
{ "iv": "…", "value": "…", "mac": "…", "tag": "" }
```

This is the output of Laravel's `Crypt::encrypt()` / `encryptString()`. These
tokens are integrity-protected (the `mac` prevents tampering).

The vulnerability is that the application used the **plaintext `<COURSE_ID>` from
the URL path** to decide *which section to enroll in*, instead of using the value
**inside** the signed token. Because the plaintext id is not integrity-checked,
an attacker can freely change it. This is a classic **Insecure Direct Object
Reference (IDOR)**: the object identifier is user-controlled and not validated
against the user's actual authorization or against the trusted token.

### Why the "fix" is incomplete
The owner reports the enroll pop-up still appears but the final action now fails —
i.e. a *symptom* was blocked, but the underlying trust of the URL-supplied id may
remain. A correct fix must **derive the section identity solely from the
decrypted token** (or reject any request where the path id does not match the
decrypted token).

---

## Finding 2 — Race Condition on seat capacity (root cause of 40 → 41)

### What was observed
- Seat limit is configured to **40** (sections show `taken / 40`).
- Under normal manual use, the limit holds.
- Under a **bot loader** issuing rapid/parallel enrollment requests, an affected
  section shows **`41 / 41`** — both the taken count **and the capacity** moved to
  41. The seat counter was *written* past its intended maximum.

### Why it happens — Time-Of-Check to Time-Of-Use (TOCTOU)
The enrollment logic almost certainly follows this shape:

```
1. READ  current enrolled count for the section        (e.g. 39)
2. CHECK if count < 40                                   (39 < 40 → true)
3. WRITE enrollment + set count = count + 1              (→ 40)
```

Steps 1–3 are **not performed as a single atomic operation**. When two requests
arrive almost simultaneously:

```
Request A: READ 39 ─┐
Request B: READ 39 ─┤ both read the SAME value before either writes
Request A: 39 < 40 → enroll → write 40
Request B: 39 < 40 → enroll → write 41   ← limit exceeded
```

Both requests read `39`, **both** pass the `< 40` check, and **both** proceed to
enroll. The result is **41**. This is a canonical **race condition (TOCTOU)**.

### Why only *some* sections and only under a bot
The window between "check" and "update" is tiny — a few milliseconds. A human
clicking cannot hit it. A **bot firing many concurrent requests** deliberately
(or accidentally) lands two requests inside that window, which is why it appears
intermittently and only on sections that fill up while the bot is active.

### Why this is a real vulnerability, not just a display glitch
The seat count is the security/business control that enforces fairness and room
capacity. Bypassing it means unauthorized over-enrollment — students can take
seats that should not exist.

---

## Finding 3 — Improper duplicate-enrollment check (section overwrite)

### What was observed (screen recording)
- The application **does** correctly reject some cases server-side: a full section
  shows *"Sorry! The section seat has been filled up. Please try another
  section."* and a timetable clash shows *"Class conflict of this section(A).
  Please try to take another section."*
- However, for a course the student is **already enrolled in**, requesting the
  **same course in a different section** does **not** show the "already taken"
  message. Instead the existing enrollment is **silently replaced** with the new
  section. Confirmed live: a single `CSC 466` row in the taken-courses list moved
  from section **L** to section **O**, with **Total Credit Hours unchanged (11)**
  — i.e. an overwrite, not a duplicate.
- Same course + **same** section is still rejected as already taken.

### Why it happens
The "already enrolled" guard is almost certainly keyed on **course *and*
section** rather than **course** alone:

```
-- current (flawed) duplicate check
WHERE student_id = ? AND course_code = ? AND section = ?
```

Because `section` is part of the match, the same course in a *different* section
is not recognised as a duplicate, so the code proceeds — and (via an update or an
upsert keyed on course+section) **reassigns** the student's enrollment to the new
section.

### Why it is a problem
- A student can **move themselves between sections at will**, bypassing section
  assignment/locking rules and fairness.
- If the replacement does **not** free the old section's seat and reserve the new
  one atomically, **seat counts drift** — which directly feeds the overbooking in
  Finding 2.
- Combined with the IDOR (Finding 1), the target section is chosen from an
  editable URL id, widening the abuse.

### The fix
Key the uniqueness rule on **course only**, and enforce it in the database:

```php
$exists = Enrollment::where('student_id', $sid)
                    ->where('course_code', $course)   // NOT section
                    ->exists();
if ($exists) {
    return back()->withErrors('You have already taken this course.');
}
```

Add a database constraint `UNIQUE (student_id, course_code)` so a duplicate is
impossible even under concurrency. If switching section is intended to be
allowed, route it through an explicit "change section" action that, in one
transaction, **releases the old section's seat and reserves the new one**.

> **Note on evidence capture.** During recording, the browser's Network panel
> appeared empty because enrollment happens in a **separate popup window**; a
> DevTools instance attached to the main tab cannot see another window's
> requests. Open DevTools **inside the popup** to capture the enroll request
> (observed initiator/endpoint hint: `AddOfferedCourse` / `taken_course_info`).
> This is normal browser behaviour, not a security control.

---

## How the findings combine

A bot that (a) exploits the IDOR to target arbitrary/full sections and (b) fires
concurrent requests to defeat the seat check can enroll into sections it should
not, and beyond their capacity. Both stem from the same underlying principle
being violated: **security decisions were made on client-supplied, non-atomic,
untrusted state instead of on trusted, atomically-enforced server state.**

---

## Root-cause principle (the "why" for your faculty)

> The system checks a condition and then acts on it in **two separate steps**,
> using values that are either **user-controllable** (the course id in the URL)
> or **read non-atomically** (the seat count). Any control enforced this way can
> be bypassed by (1) tampering with the untrusted input, or (2) racing between
> the check and the act. Correct enforcement requires the **database itself** to
> guarantee the invariant in a single atomic operation, and requires **authority
> to come from the signed token, never from the raw URL.**

---

## Recommended remediation (for completeness)

### Fix the race condition — make the seat limit atomic
Let the database enforce the rule in one statement, so the check and the update
cannot be separated:

```php
// Only increments when a seat is actually free. Atomic on a single row.
$updated = DB::table('sections')
    ->where('id', $sectionIdFromToken)
    ->where('enrolled', '<', DB::raw('capacity'))   // capacity = 40
    ->increment('enrolled');

if ($updated === 0) {
    // Nothing updated => section already full. Reject.
    return back()->withErrors('This section is full.');
}
// proceed to record the student's enrollment only after $updated === 1
```

Additional hardening:
- Wrap enroll + increment in a **DB transaction** and use
  `->lockForUpdate()` when reading the section row.
- Add a **UNIQUE constraint** on `(student_id, section_id)` to stop double
  enrollment, and a **CHECK / trigger** so `enrolled <= capacity` can never be
  violated at the storage layer.

### Fix the IDOR — trust the token, not the URL
- Decrypt the Laravel token and use **only** the section id contained in it.
- If a plaintext id is also present in the path, **verify it equals** the
  decrypted id and reject on mismatch.
- Re-check on the server that the authenticated student is actually **allowed**
  to enroll in that section (authorization, not just authentication).

### Defense in depth
- Require enrollment via a **POST** request with a valid **CSRF token**, so a
  bare shareable URL cannot trigger a state change.
- Add **rate limiting** on the enrollment endpoint to blunt bot loaders.

---

## Summary table

| # | Vulnerability | Class | Cause | Status |
|---|---------------|-------|-------|--------|
| 1 | Enroll via swapped course id in URL | Broken Access Control (IDOR) | Section chosen from untrusted URL id, not the signed token | Partially mitigated |
| 2 | Seats exceed 40 (→41) under bot | Race Condition (TOCTOU) | Non-atomic check-then-update of seat count | **Active** |
| 3 | Re-taking a course in another section overwrites it | Improper duplicate check / business-logic flaw | "Already enrolled" guard keyed on course+section instead of course | **Active** |

---

*Prepared as a black-box security assessment. Findings 1 and 2 are supported by
reproduced behavior; exact code-level confirmation requires access to the
enrollment controller and section model.*
