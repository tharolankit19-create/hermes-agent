---
name: kryx
description: "Kryx AI writing studio: run the publish queue, sync X analytics, compound the voice persona, decide A/B tests, and deliver a weekly growth digest."
version: 1.0.0
author: Kryx + Hermes Agent
license: MIT
platforms: [linux, macos]
prerequisites:
  commands: [python3]
  env: [KRYX_AUTOMATION_SECRET]
metadata:
  hermes:
    tags: [kryx, x, twitter, linkedin, social-media, scheduling, analytics, automation]
    homepage: https://getkryxai.com
---

# Kryx — unattended growth automation

[Kryx](https://getkryxai.com) is an AI writing studio that writes X/LinkedIn posts
in the user's own voice. This skill runs the parts of Kryx that should happen
without anyone watching: publishing what is scheduled, pulling in analytics,
teaching the voice persona from the user's edits, deciding A/B tests, and
reporting weekly.

Use this skill when the user asks to:

- publish, schedule, or "post what's queued" on Kryx
- refresh, sync, or check their Kryx analytics
- update, retrain, or "teach" their Kryx voice profile
- pick an A/B winner
- get their weekly growth report
- set up any of the above to run on a schedule

---

## Secret safety (MANDATORY)

- `KRYX_AUTOMATION_SECRET` is a shared secret with full cross-user job access.
- **Never** print, echo, log, paste into chat, or read it into LLM context.
- **Never** ask the user to paste it into a conversation. It belongs in the
  Hermes environment (`.env` / `direnv` / the host's secret store).
- The script reads it from the environment and keeps it out of every message it
  emits, including errors. Keep it that way.

---

## Setup

Two environment variables, set once in the Hermes environment:

```bash
export KRYX_BASE_URL="https://getkryxai.com"   # optional, this is the default
export KRYX_AUTOMATION_SECRET="…"              # must match the value deployed with the app
```

The same secret must be set as `KRYX_AUTOMATION_SECRET` in the Kryx app's own
environment. If it is missing there, every job returns HTTP 503 and the script
says so plainly.

---

## Running a job

```bash
python3 skills/social-media/kryx/scripts/kryx_automation.py <job> [--limit N] [--json]
```

| Job | What it does | Suggested cadence |
|---|---|---|
| `publish` | Publishes scheduled posts whose time has come | every 5 minutes |
| `sync` | Pulls impressions, engagement and followers from the X API | hourly |
| `learn` | Folds the user's recent edits into their voice persona | nightly |
| `ab` | Decides A/B tests older than 24h on engagement rate | every 6 hours |
| `digest` | Returns each account's weekly growth summary | Mondays |

`--limit` bounds how much one run processes (1–200, default 25), so a backlog
drains over several ticks instead of in one stampede. `--json` prints the raw
response when you need the numbers rather than the prose.

Each job is **idempotent**: a missed run catches up on the next tick, and a
re-run never double-publishes. `publish` claims each row before sending it, so
two overlapping workers cannot post the same draft twice.

---

## Scheduling it (the point of this skill)

The four maintenance jobs need no reasoning, so run them with `no_agent=True`
and spend zero tokens. Only the weekly digest is worth an agent turn, because
it should arrive written like a person wrote it.

```python
from cron.jobs import create_job

# Publish what is due — the job that makes Kryx an executor, not an adviser.
create_job(
    prompt="Kryx publish queue",
    schedule="every 5m",
    name="kryx-publish",
    script="python3 skills/social-media/kryx/scripts/kryx_automation.py publish --limit 50",
    no_agent=True,
    deliver="local",
)

# Keep analytics warm so the dashboard is never stale.
create_job(
    prompt="Kryx metrics sync",
    schedule="0 * * * *",
    name="kryx-sync",
    script="python3 skills/social-media/kryx/scripts/kryx_automation.py sync --limit 100",
    no_agent=True,
    deliver="local",
)

# Compound the voice persona overnight, from the day's edits.
create_job(
    prompt="Kryx persona learning",
    schedule="0 3 * * *",
    name="kryx-learn",
    script="python3 skills/social-media/kryx/scripts/kryx_automation.py learn --limit 50",
    no_agent=True,
    deliver="local",
)

# Call A/B winners once both variants have had a day to breathe.
create_job(
    prompt="Kryx A/B decisions",
    schedule="0 */6 * * *",
    name="kryx-ab",
    script="python3 skills/social-media/kryx/scripts/kryx_automation.py ab",
    no_agent=True,
    deliver="local",
)

# Monday 09:00 — the one job worth an agent turn.
create_job(
    prompt=(
        "Run: python3 skills/social-media/kryx/scripts/kryx_automation.py digest --json\n"
        "Then write the user a short weekly growth note in plain language. Lead with the "
        "single number that moved most, say what caused it, and end with ONE specific thing "
        "to do this week. No preamble, no bullet-point soup, no congratulating them on "
        "'crushing it'. If the numbers are down, say so directly and say what to change."
    ),
    schedule="0 9 * * 1",
    name="kryx-weekly-digest",
    skills=["kryx"],
    deliver="origin",
)
```

Adjust cadence to the user's account size: a creator posting twice a week does
not need an hourly sync, and `every 5m` on the publish queue is only worth it
if they actually schedule posts.

---

## Reading the output

Each job prints one human-readable summary line (plus detail lines where it
matters):

```
Publish queue: 3 published, 1 failed, 4 due.
  - 8f2c…: X rate limit reached. Try again shortly.
Metrics sync: 7/8 accounts synced.
A/B tests: 1 decided.
  - Variant A won by 43%.
```

**Failures are normal and mostly self-healing.** A failed publish is retried on
the next tick, up to three attempts, then parked as `failed` for the user to
look at. A single account with an expired X token never stops the batch — it is
reported and the rest continue. Only escalate to the user when:

- the secret is rejected (401) or missing (503) — that is a config problem
- the same post fails all three attempts
- more than half of accounts fail a sync, which usually means the X app's
  credentials or access tier changed

---

## Things this skill will not do

- It does not write posts. Generation is a paid, per-user action that runs in
  the app, against the user's own credits and persona.
- It does not post on a user's behalf outside their own schedule. Everything it
  publishes was explicitly scheduled by the user in the Kryx Studio.
- It has no per-user login. It runs cross-user maintenance under a service
  credential, which is exactly why the secret must never leak.
