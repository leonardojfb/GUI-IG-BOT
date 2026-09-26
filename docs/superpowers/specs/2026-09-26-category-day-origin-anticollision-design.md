# Category-Day Origin Anti-Collision

## Goal

Avoid a logical video origin repeat in the same account category and calendar day whenever unique origins remain, while completing the requested schedule when they do not.

## Rule

The primary reservation key is `(normalized account category, day number, logical origin)`. Copy suffixes such as `__c01` are not part of the origin. A source may be reused by a different category on the same day and by the same category on a different day.

## Capacity and failure

When a category has fewer distinct logical origins than its required assignments for a day, distribution must use a fill-up copy of the least-used origin in that category/day. It records each unavoidable repeat in the result summary. It still stops only when no physical copy remains.

## Scope

Apply the rule in `MainApp._acct_dist_run` before candidate scoring. Keep existing per-account/day and lifetime preferences. Preserve manifest and Telegram ordering; they consume the distribution plan and do not select videos.

## Verification

Add a focused Por Cuentas regression with 40 same-category accounts and 35 origins with 40 copies each. A 1 video/day plan must complete with exactly five least-used fill-up repeats per day. A separate-category account may still use an already reserved origin.
