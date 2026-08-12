---
name: saasgrave-launches
description: Watch traffic on the Saasgrave Launches launchpad. Poll the diagnosis endpoint, explain where visitors dropped and which referrers worked, and report to the admin.
version: 1.0.0
author: community
license: MIT
platforms: [linux, macos, windows]
prerequisites:
  env_vars: [SAASGRAVE_LAUNCHES_URL, SAASGRAVE_INSIGHTS_TOKEN]
  commands: [curl]
metadata:
  hermes:
    tags: [Analytics, Traffic, SaaS, Growth, API]
    homepage: https://launches.saasgrave.org
---

# Saasgrave Launches — traffic watcher

Saasgrave Launches is a weekly product launchpad. It exposes one read-only
endpoint that already contains the whole diagnosis: traffic totals, referrer
attribution, funnel drop-off, friction counters, and a list of **findings** —
each a problem plus the action it implies.

Your job is to fetch that report, decide whether anything in it is worth waking
the admin for, and say it in a few sentences. **Do not invent findings.** The
site's rule engine decides what counts as a problem; you decide what is worth
reporting and how to phrase it.

## Prerequisites

Store both values in `${HERMES_HOME:-~/.hermes}/.env`:

```
SAASGRAVE_LAUNCHES_URL=https://launches.saasgrave.org
SAASGRAVE_INSIGHTS_TOKEN=<the ADMIN_INSIGHTS_TOKEN from the site's env>
```

The token is the site's `ADMIN_INSIGHTS_TOKEN`. If the site has no token set,
machine access is off and every request returns `401` — that is a
configuration problem to report, not a bug to work around. Never try to reach
the data another way (the admin page, the database, scraping); if the token
fails, say so and stop.

## Fetch the report

Use the `terminal` tool:

```bash
curl -sS -H "Authorization: Bearer $SAASGRAVE_INSIGHTS_TOKEN" \
  "$SAASGRAVE_LAUNCHES_URL/api/admin/insights?days=7&narrate=1"
```

Query parameters:

| Param | Meaning |
| --- | --- |
| `days` | Window, 1–90. Default 7. Use `1` for a daily check, `7` for a weekly review. |
| `narrate=1` | Adds `narrative`: a three-sentence AI summary of the findings. Omit it if you'd rather write the summary yourself. |

Pipe through `jq` when you only need part of it:

```bash
curl -sS -H "Authorization: Bearer $SAASGRAVE_INSIGHTS_TOKEN" \
  "$SAASGRAVE_LAUNCHES_URL/api/admin/insights?days=1" \
  | jq '{sessions: .totals.sessions, findings: [.findings[] | select(.severity=="critical")]}'
```

## What comes back

```jsonc
{
  "windowDays": 7,
  "generatedAt": "2026-08-12T09:00:00.000Z",
  "totals":   { "sessions": 412, "pageViews": 980, "publishes": 9, "outboundClicks": 61, … },
  "daily":    [ { "day": "2026-08-06", "sessions": 44, "pageViews": 96 }, … ],
  "sources":  [ { "host": "x", "label": "X (Twitter)", "sessions": 180, "share": 0.44 }, … ],
  "funnel":   [ { "event": "page_view", "label": "Landed on the site",
                  "sessions": 412, "stepRate": 1, "totalRate": 1, "dropped": 0 }, … ],
  "friction": { "bounceRate": 0.58, "autofillErrorRate": 0.07, "publishBlocked": 4,
                "publishErrors": 0, "abandonedDrafts": 12 },
  "content":  { "liveThisWeek": 7, "liveTotal": 96, "zeroUpvoteLive": 3 },
  "findings": [ { "severity": "critical", "title": "…", "detail": "…", "action": "…" } ],
  "narrative": "…"
}
```

Two things worth understanding before you interpret any of it:

- **`sources` counts each session once**, attributed to the referrer on its
  first event. The shares sum to 1. `direct` means no referrer, not "typed the
  URL"; `internal` navigation is excluded entirely.
- **`funnel` is measured in sessions, not hits**, and `stepRate` is the share of
  the *previous* step that got here. That's the number that localises a drop —
  `totalRate` only tells you how far it is from the top.

## Reporting rules

Report when a `critical` finding is present, or when a `warn` finding is new
since your last check. Otherwise stay quiet — a watcher that reports "nothing
changed" every hour gets muted, and then it isn't a watcher.

When you do report:

1. Lead with the single most severe finding and its `action`. One sentence.
2. Add the number that makes it real (the `detail` field already has it).
3. Mention the best referrer only if it changed rank since last time.
4. Stop. Do not paste the whole JSON, and do not list every finding.

Keep a short note of what you last reported (memory, or a file in
`${HERMES_HOME:-~/.hermes}/`) so you can tell "new" from "still true". Include
`generatedAt` in that note.

Deliver it through whatever channel the admin normally uses — `send_message` for
Telegram/Discord/Slack, or just the reply if you're being asked directly.

## Severity, and what each one usually means

| Severity | Treat as | Typical cause |
| --- | --- | --- |
| `critical` | Wake the admin | Empty weekly board, publishes erroring, autofill failing, form completion under 35% |
| `warn` | Mention once, then only if it worsens | Thin board, high bounce, live launches with no upvotes, publishes blocked by the support rule |
| `info` | Context only | Low traffic overall, unattributed traffic, which channel is winning |

A `critical` about the **board being empty** is the one that compounds: an empty
board makes every visitor bounce, which suppresses the next week too. Say so.

## Scheduling it

Ask the scheduler for a daily check with `days=1` and a Monday review with
`days=7` — Monday is when the ISO week rolls over and the previous board
closes, so that's when a weekly summary is actually about a finished week.

Nothing in this skill writes to the site. It is read-only by design; if you are
asked to change something on the launchpad, say that this skill can't and point
at the admin dashboard at `$SAASGRAVE_LAUNCHES_URL/admin`.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `401 Not authorised` | Token wrong, or `ADMIN_INSIGHTS_TOKEN` unset on the site (machine access is off by default). |
| `narrative` is `null` | The site has no `OPENROUTER_API_KEY`, or every model on its ladder failed. `findings` are still complete — they're rule-based, not model-based. |
| All rates look extreme | Check `totals.sessions`. Under ~20 sessions every ratio is noise, and the report says so in an `info` finding. |
| `findings` is empty | Nothing tripped a threshold. That's a valid, quiet result. |
