# What to Say and Do in Front of Your Faculty

Simple words to read out, and simple steps to do. You do not need to attack the
live website. You have three kinds of proof already.

---

## PART 1 — Say this first (the summary)

> "Sir, I found three security problems in my enrollment system. I will explain
>  what each one is, why it happens, and how to fix it. I will also show one of
>  them running live in a small safe demo."

---

## PART 2 — Problem 1: The seat limit can be broken (41 seats)

**Say:**
> "Every section has a limit of 40 seats. But sometimes a section shows 41.
>  This happens because my code checks the seats in three separate steps:
>  first it READS the count, then it CHECKS if it is less than 40, then it
>  WRITES the new count. When two students enroll at the exact same moment,
>  both read 39, both pass the check, and both add one. So it becomes 41.
>  This is called a race condition."

**Show the live safe demo** (on your laptop, no risk):
1. Open a terminal in the `race_demo` folder.
2. Type: `python seat_race_demo.py`
3. Point at the screen:
   - First part shows **41/40 → OVERBOOKED** (the bug).
   - Second part shows **40/40 → limit held** (the fix).

**Say:**
> "The fix is to check and update the seats in ONE database command, so two
>  students can never both pass. You can see in the demo the fixed version
>  rejects the second student."

---

## PART 3 — Problem 2: I can enroll in the wrong section by editing the link

**Say:**
> "When I click a section, the website opens a link like this:
>  courseinformation / ID / course_code / section.
>  The course_code and section are encrypted, but the ID is plain text.
>  Because the ID is not protected, I can change it in the URL and the system
>  enrolls me in a different section. This is called an IDOR — Insecure Direct
>  Object Reference."

**Show:** open your `StuPreOffering` source, point to the `openPopup(id, ...)`
function and one button's `onclick`. Show that the first value is plain text.

**Say:**
> "The fix is to use the encrypted, signed value to decide the section, and
>  never trust the plain-text ID from the URL."

---

## PART 4 — Problem 3: Taking a course again in another section replaces it

**Say:**
> "If I already have a course and I take the same course in a different section,
>  the system does not stop me. It silently replaces my old section with the new
>  one. It only blocks me if I choose the exact same section again. This is
>  because the 'already taken' check looks at course AND section together,
>  instead of just the course."

**Show:** your screen recording where CSC 466 moves from section L to section O.

**Say:**
> "The fix is to check by course only, and add a database rule that a student can
>  take each course one time."

---

## PART 5 — Close

> "So in summary: a race condition breaks the seat limit, a plain-text ID lets me
>  change sections, and a wrong duplicate-check lets me replace a course. I have
>  written the cause and the fix for each one in my report. Thank you, sir."

---

## If the faculty asks: "Show me the seat bug on the real site"

**Say (this is a correct, professional answer):**
> "The seat bug is in the server code, which the browser cannot show. Security
>  testers prove server bugs by demonstrating the behavior, which I did on my
>  test data — the section reached 41. I also reproduced the exact mechanism in
>  this safe local demo so you can see how it happens step by step."

If he still wants to see it on the site, and you have dummy sections + a Remove
button to undo, you can do this yourself:
1. Bring a **dummy** section to 39/40.
2. Open its enroll popup in **two browser windows** (two dummy accounts), both on Submit.
3. Click Submit in both windows at the same time.
4. Refresh → it may show 41.
5. Use **Remove/decrement** to undo the test enrollments.
