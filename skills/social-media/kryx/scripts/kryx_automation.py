#!/usr/bin/env python3
"""Kryx automation client.

Drives the Kryx background jobs over its authenticated automation endpoint.
Standard library only, so it runs wherever Hermes runs with no install step.

Environment:
    KRYX_BASE_URL           e.g. https://getkryxai.com   (default)
    KRYX_AUTOMATION_SECRET  shared secret, sent as a bearer token

The secret is read from the environment and never printed, logged, or echoed
back — not even on error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

JOBS = {
    "publish": "publish_due",
    "sync": "sync_metrics",
    "learn": "learn_edits",
    "ab": "decide_ab",
    "digest": "digest",
}

DEFAULT_BASE_URL = "https://getkryxai.com"
TIMEOUT_SECONDS = 300


class KryxError(RuntimeError):
    """A job failed. The message never contains the secret."""


def _run_job(job: str, limit: int) -> dict:
    base_url = os.environ.get("KRYX_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    secret = os.environ.get("KRYX_AUTOMATION_SECRET")
    if not secret:
        raise KryxError(
            "KRYX_AUTOMATION_SECRET is not set. Add it to the Hermes environment "
            "(it must match the value deployed with the Kryx app)."
        )

    payload = json.dumps({"job": job, "limit": limit}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/api/public/automation/run",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "User-Agent": "kryx-hermes-automation/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        if exc.code == 401:
            raise KryxError(
                "Kryx rejected the automation secret (401). Check that "
                "KRYX_AUTOMATION_SECRET matches the deployed value."
            ) from None
        if exc.code == 503:
            raise KryxError(
                "Kryx has no automation secret configured (503). Set "
                "KRYX_AUTOMATION_SECRET in the app's environment and redeploy."
            ) from None
        raise KryxError(f"Kryx returned HTTP {exc.code}: {body}") from None
    except urllib.error.URLError as exc:
        raise KryxError(f"Could not reach Kryx at {base_url}: {exc.reason}") from None


def _summarise(job: str, result) -> str:
    """One human line per job, for delivery to Telegram/Slack/CLI."""
    if job == "publish_due":
        line = f"Publish queue: {result['published']} published, {result['failed']} failed, {result['due']} due."
        for err in result.get("errors", [])[:3]:
            line += f"\n  - {err['postId']}: {err['error']}"
        return line
    if job == "sync_metrics":
        line = f"Metrics sync: {result['synced']}/{result['users']} accounts synced."
        for err in result.get("errors", [])[:3]:
            line += f"\n  - {err}"
        return line
    if job == "learn_edits":
        return (
            f"Persona learning: {result['updated']} personas updated "
            f"from {result['edits']} edits across {result['users']} users."
        )
    if job == "decide_ab":
        line = f"A/B tests: {result['decided']} decided."
        for r in result.get("results", [])[:5]:
            line += f"\n  - Variant {r['winner'].upper()} won by {r['lift']}%."
        return line
    if job == "digest":
        if not result:
            return "Weekly digest: no connected accounts yet."
        lines = [f"Weekly digest for {len(result)} account(s):"]
        for user in result:
            handle = f"@{user['handle']}" if user.get("handle") else user["userId"][:8]
            change = user.get("impressionsChange")
            change_str = f" ({change:+}%)" if change is not None else ""
            lines.append(
                f"  {handle}: {user['impressions']:,} impressions{change_str}, "
                f"{user['followersGained']:+} followers, {user['postsPublished']} posts."
            )
            for insight in user.get("insights", [])[:2]:
                lines.append(f"      - {insight}")
        return "\n".join(lines)
    return json.dumps(result, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Kryx automation job.")
    parser.add_argument("job", choices=sorted(JOBS), help="Which job to run.")
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Max items to process this run (1-200, default 25).",
    )
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of a summary.")
    args = parser.parse_args(argv)

    job = JOBS[args.job]
    try:
        response = _run_job(job, max(1, min(args.limit, 200)))
    except KryxError as exc:
        print(f"Kryx automation failed: {exc}", file=sys.stderr)
        return 1

    if "error" in response:
        print(f"Kryx job '{job}' failed: {response['error']}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(response, indent=2))
    else:
        print(_summarise(job, response.get("result")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
