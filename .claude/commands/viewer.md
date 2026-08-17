---
description: Open the observation deck — walk through the terrain in 3D. Free.
allowed-tools: Bash(cd:*), Bash(python3:*), Bash(nohup:*), Bash(curl:*)
---

Refresh the world export and serve the observation deck:

```bash
cd basin-01 && python3 world_export.py --serve
```

This runs until stopped, so start it in the background and then tell the
steward the URL it printed. Do not leave him waiting on a blocked command.

**A browser will not load the viewer straight off the filesystem.** JavaScript
modules are refused as cross-origin over `file://`, which leaves the page stuck
on "loading terrain". It has to be served, which is what this does. The server
binds to 127.0.0.1 — reachable from this machine and nowhere else. The terrain's
record is not published by running it.

Before handing over the URL, check it actually works:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8731/three.module.js
```

Then give him the URL and one line on what changed in the terrain since last
time — new arrivals, anything that ended, how the cover has moved. Don't
describe the scene to him; he can see it.
