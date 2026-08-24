# Hermes as the basis for an AI head of content

Written against this checkout of `NousResearch/hermes-agent` at `main`, for the
question: can Hermes be deployed to Vercel as the agent behind an AI head of
content product, and if not, what should be taken from it?

## Summary

**Hermes cannot be deployed to Vercel, and it is not the right shape for this
product.** But its architecture is the right answer to the hardest problem in
the category, and that architecture has been ported natively into the product
app instead. The port lives in `social-sparky` under `src/agent/`, documented in
`docs/agent-architecture.md` there.

One thing found here does apply directly: Hermes' default LLM provider is the
**Vercel AI Gateway**, and that is now the product's primary provider path.

## Why it cannot run on Vercel

This is a shape mismatch, not a configuration problem.

| Fact | Where | Consequence |
|---|---|---|
| 3,710 Python files, 152 MB checkout | `find . -name '*.py' \| wc -l` | Far past Vercel's function bundle limit |
| State is local SQLite at `~/.hermes/state.db` | `hermes_state.py:236` | Vercel's filesystem is ephemeral; state would vanish between invocations |
| Long-running gateway process serving Telegram/Discord/Slack/WhatsApp/Signal | `gateway/` | Vercel functions are request-scoped and time-bounded |
| Full terminal UI | `ui-tui/`, `tui_gateway/` | No terminal on a serverless host |
| Python 3.11–3.13, exact-pinned heavy deps | `pyproject.toml:15` | Sized for a VPS, not a function |

Hermes is explicit about its intended targets: a $5 VPS, a GPU cluster, or
serverless *sandbox* backends (Modal, Daytona, Vercel Sandbox). That last one is
worth naming precisely, because it is easy to misread:

**Vercel appears in Hermes in two roles, and neither is "deploy Hermes to
Vercel".**

1. **Vercel Sandbox as a terminal backend** (`hermes_cli/vercel_auth.py`) —
   Hermes runs *somewhere else* and uses a Vercel sandbox to execute code.
   `VERCEL_TOKEN` / `VERCEL_PROJECT_ID` / `VERCEL_TEAM_ID`.
2. **Vercel AI Gateway as an LLM provider** (`hermes_constants.py:1250`,
   `hermes_cli/auth.py:368`) — `https://ai-gateway.vercel.sh/v1`, keyed by
   `AI_GATEWAY_API_KEY`.

Role 2 is the useful one, and it is now in production use in the product.

## What was taken

The gap this product has to close is that a stateless model call produces
generic output. Hermes' answer is a closed learning loop, and four of its ideas
port cleanly to a serverless TypeScript app:

**1. Persistent, layered context.** Hermes assembles each turn from curated
memory, user modelling, and past-session search rather than a fixed prompt.
Ported as `src/agent/context.server.ts`, which assembles brain documents, a
learned voice profile, ranked memories, and measured post performance.

**2. Agent-curated memory that compounds.** Hermes nudges itself to persist
knowledge. Ported as `src/agent/memory.server.ts` — atomic facts, one per row,
with near-duplicate merging so re-observing a fact raises its confidence rather
than appending a duplicate. Atomic rather than one blob so a user can delete the
single thing the agent got wrong.

**3. Skills as scoped capability modules.** Hermes loads skills per task
(`skills/`, `optional-skills/`). Ported as the tool set in
`src/agent/tools.server.ts` plus task-specific closing instructions in
`buildContext` — one grounded context serving drafting, critique and analysis
without three prompts drifting apart.

**4. Cron routines with delivery.** Hermes ships a cron scheduler
(`hermes cron create`, `hermes-already-has-routines.md`). Ported as
`src/agent/rituals.server.ts` and a Vercel Cron sweep — morning brief, evening
report, weekly plan, voice rebuild, metrics sync.

**5. Model-agnosticism, which is Hermes' strongest architectural stance.**
It supports any provider and switches without code changes. Ported as
`src/agent/llm.server.ts`: AI Gateway → Anthropic → OpenAI → legacy gateway,
with `smart` and `fast` tiers both overridable by env var. The product is never
pinned to one vendor's pricing or availability.

## What was deliberately not taken

- **Self-modifying skills.** Hermes writes and rewrites its own skills during
  use. In a product where the output goes out under a customer's name, an agent
  editing its own instructions unsupervised is a liability, not a feature. The
  learning loop here is narrow and auditable: it learns voice from published
  posts and user edits, and every memory is visible and deletable in the Brain
  screen.
- **The multi-platform gateway.** Telegram/Discord/Slack delivery is a large
  surface for an audience that lives in a web app.
- **Batch trajectory generation and trajectory compression.** Research
  tooling for training tool-calling models; no product use here.

## One thing worth revisiting

`skills/social-media/xurl/SKILL.md` wraps `xurl`, X's official CLI, covering
post search, posting, DMs and media. The product currently calls the X API
directly (`src/lib/publish.server.ts`, `src/agent/metrics.server.ts`), which is
correct for a serverless runtime — a CLI dependency does not belong in a
function. But the skill file is a useful reference for endpoint shapes when
extending coverage, particularly for media upload, which the product does not
support yet.

## Practical note

If Hermes itself is ever wanted — as an internal operator tool rather than the
product backend — it needs a persistent host: a small VPS, Modal, or Daytona.
It would run *alongside* the product, talking to it over its API, not inside it.
That is a separate decision from anything the product needs today.
