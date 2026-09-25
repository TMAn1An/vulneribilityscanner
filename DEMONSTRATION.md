# Live Demonstration Runbook — Seat Overbooking (Race Condition)

**Goal:** Show your faculty, live, *how* the 40-seat limit is broken (a section
reaching 41/41), *why* it happens, and *how* the fix prevents it.

> ⚠️ **Do the demo on a throwaway/test section, not a real course students
> want.** The demonstration deliberately overbooks a section; use a test
> section (or one nobody is competing for) so you don't disturb real students.

---

## Part A — Explain the cause (say this to your faculty)

> "My architecture requires every section to have at most 40 seats. The
> enrollment code enforces this in the application: it (1) **reads** the current
> seat count, (2) **checks** if it is less than 40, then (3) **writes** the
> increased count. These are three separate steps. When my bot sends two
> enrollment requests at the *same instant*, both read the same value (e.g. 39),
> both pass the `< 40` check before either has written, and both then increase
> the count — producing **41**. This is a **race condition (Time-Of-Check to
> Time-Of-Use, TOCTOU)**. It also relies on **Broken Access Control**, because
> the target section is taken from the editable course id in the URL rather than
> from the signed token."

Show the **41/41 screenshot** as proof it already happened.

---

## Part B — Reproduce it live

### Step 1 — Bring a test section to 39/40
Using your admin/normal flow, fill a test section until it shows **39 / 40**
(one free seat).

### Step 2 — Capture the real "enroll" request (do this once)
You need the exact HTTP request your site sends when a student enrolls:

1. Log in as a test student in **Chrome/Firefox**.
2. Press **F12** → **Network** tab → tick **Preserve log**.
3. Click the **"+ enroll / add course"** button for a section.
4. In the Network tab, click the request that fired (look for
   `courseinformation` or an enroll/add URL).
5. Right-click it → **Copy → Copy as cURL**.

That cURL command tells us: the **method** (GET or POST), the **URL**, the
**headers/cookies**, and any **body/CSRF token**. Paste it to me and I will
finish the PoC script exactly. (This capture is read-only — you're just watching
one normal click.)

### Step 3 — Fire two enrollments at once
Run `poc_race.py` (below) with **two different test student accounts** targeting
the **same** 39/40 test section. It sends both enroll requests concurrently.

### Step 4 — Show the result
Refresh the section list. It now shows **41 / 41**. The 40-seat invariant is
broken — live, on demand. That is your "live example."

---

## Part C — Show the fix works

Explain (and, if you can edit the code, show) the corrected enrollment logic:

```php
// Atomic: the database itself refuses to exceed capacity.
$updated = DB::table('sections')
    ->where('id', $sectionIdFromToken)   // from the SIGNED token, not the URL
    ->where('enrolled', '<', DB::raw('capacity'))   // capacity = 40
    ->increment('enrolled');

if ($updated === 0) {
    return back()->withErrors('This section is full.');  // second racer fails
}
// record the student's enrollment only when $updated === 1
```

With this in place, re-run Step 3: the **second** concurrent request updates
**zero rows** (because `enrolled < capacity` is now false at the moment of
writing) and is rejected. The section stays at **40 / 40**. Invariant preserved.

**One-line summary for your faculty:** *the fix moves the seat check from
separate application steps into a single atomic database operation, so two
concurrent requests can never both succeed.*

---

## What the faculty asked for — checklist

- [x] How the issue occurs → race condition, demonstrated live (Part B)
- [x] Why it occurs → non-atomic check-then-write + untrusted URL id (Part A)
- [x] The solution → atomic conditional `UPDATE`, trust the token (Part C)
