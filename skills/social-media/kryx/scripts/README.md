# Kryx automation scripts

`kryx_automation.py` — standard-library-only client for the Kryx automation
endpoint. No dependencies, no install step.

    python3 kryx_automation.py {publish|sync|learn|ab|digest} [--limit N] [--json]

Reads `KRYX_BASE_URL` (default `https://getkryxai.com`) and
`KRYX_AUTOMATION_SECRET` from the environment. The secret is never printed,
including in error messages.

Exit codes: `0` success, `1` job or transport failure (reason on stderr).
