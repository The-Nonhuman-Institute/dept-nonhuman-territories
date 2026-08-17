---
description: Rebuild the local dashboard from the terrain's state files and open it. Free.
allowed-tools: Bash(cd:*), Bash(python3:*), Bash(open:*)
---

Regenerate the dashboard and open it:

```bash
cd basin-01 && python3 dashboard.py --open
```

It reads the terrain's own state files and writes a single self-contained HTML
page — no server, no network, nothing sent anywhere. The research record stays
on the steward's machine.

It is a view: it never writes to `state/` or `shifts/`, and it makes no model
call, so it costs nothing and cannot alter the record it displays. Re-run it
after any shift to refresh.

Then tell the steward in one line what changed since the last time — new
categories, new anomalies, spend — rather than describing the page to him. He
can see the page.
