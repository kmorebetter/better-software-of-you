---
title: "Installed ≠ fires: prove scheduled jobs run, and bound any headless model step"
date: 2026-07-17
category: best-practices
module: scheduling
problem_type: best_practice
component: background_job
severity: high
applies_when:
  - Setting up a scheduled/background job (launchd, cron, systemd timer)
  - A scheduled job shells out to a headless model/CLI (e.g. `claude -p`) or any long-running child
  - Delivery of the job's output must not depend on an optional or flaky step succeeding
tags: [launchd, cron, scheduled-jobs, verification, headless, timeout, reliability, delivery-guarantee]
---

# Installed ≠ fires: prove scheduled jobs run, and bound any headless model step

## Context

The whole point of a scheduled job is that it runs unattended — which is exactly why "I set it up" is
not evidence it works. Two failure modes are easy to ship and hard to notice: a job that is *loaded*
but never actually *fires* correctly (wrong PATH/env/working-dir under the scheduler), and a job whose
optional model/enrichment step hangs and silently blocks the real deliverable. Both were live risks in
a launchd-based sync + morning-brief setup; both are cheap to close once named.

## Guidance

**1. Prove it fires — don't infer from "loaded."** `launchctl list | grep job` showing status 0 means
*loaded*, not *ran correctly*. The scheduler's environment (PATH, HOME, cwd, no interactive shell
aliases) differs from your terminal, so a job that works when you run it by hand can still fail under
the scheduler. Force one real run and inspect the effects:

```bash
launchctl kickstart -k "gui/$(id -u)/com.example.job"   # fire it now, under launchd
# then confirm: fresh entry in the job's own log, and no errors in the scheduler's stdout/stderr log
```

Check that binaries actually resolve under the *plist's* declared PATH (interactive aliases like
`claude → claude --dangerously-skip-permissions` do **not** apply under launchd), and that any headless
tool is authenticated in a non-interactive context.

**2. Bound any headless model/CLI step so it can never block delivery.** A headless `claude -p` (or any
child that can hang or wait for auth) with no timeout will stall the whole job. macOS has no `timeout`
builtin, so use a portable guard:

```bash
run_bounded() {                       # cap wall-clock; portable across coreutils / no-coreutils
  local secs="$1"; shift
  if command -v timeout  >/dev/null 2>&1; then timeout  "$secs" "$@"; return $?; fi
  if command -v gtimeout >/dev/null 2>&1; then gtimeout "$secs" "$@"; return $?; fi
  "$@" & local pid=$!
  ( sleep "$secs"; kill -0 "$pid" 2>/dev/null && kill "$pid" 2>/dev/null ) & local w=$!
  wait "$pid" 2>/dev/null; local rc=$?; kill "$w" 2>/dev/null; return "$rc"
}
```

**3. Guarantee a deterministic floor; make the model step strictly additive.** Produce the real
deliverable deterministically *first*, then let the model enrich a *copy*. Swap the enriched version in
only if it succeeded, so a killed/hung model run can neither block nor corrupt the floor:

```bash
build_floor_output              # deterministic; this is what actually ships
run_bounded 180 claude -p "...write to $ENRICHED..." || true
[ -s "$ENRICHED" ] && mv "$ENRICHED" "$OUTPUT" || rm -f "$ENRICHED"   # additive, never destructive
deliver "$OUTPUT"               # always has content
```

## Why This Matters

- **Silent non-delivery is the worst outcome.** A scheduler that quietly never fires, or a brief that
  never sends because enrichment hung, looks identical to "nothing needed to happen" — you find out by
  its absence, days later. The kickstart check and the bounded floor turn both into non-events.
- **The failure being fixed is literally "built but never ran."** For any reliability work in this
  space, treating "installed" as "working" reproduces the exact bug.
- **Environments diverge silently.** Scheduler PATH/env/cwd and missing interactive aliases cause
  works-by-hand / fails-on-schedule bugs that only a real scheduled run surfaces.

## When to Apply

- Any launchd/cron/systemd job, at install time — always do one kickstart-and-verify.
- Any scheduled job that calls a model/CLI or another process that could hang or await auth.
- Any "deterministic core + optional enrichment" delivery where the enrichment must not gate the output.

## Examples

**Verification that actually discriminates** (from the real setup): a manual run with a restricted PATH
had *skipped* the model branch, so it proved nothing about the scheduled path. The `launchctl kickstart`
run produced a fresh sync-log entry with no scheduler-log errors — that is the evidence that the plumbing
(venv python, working dir, env) resolves under launchd.

**PATH gotcha:** `command -v claude` succeeded in the terminal via an alias, but under launchd only the
on-disk binary (in the plist's declared PATH) runs — without the alias's flags. Verify the *binary*
resolves and behaves headless, not the alias.

## Related

- `docs/solutions/architecture-patterns/signals-engine-proactive-surfacing.md` and
  `docs/solutions/architecture-patterns/deterministic-render-cached-judgment.md` — both rely on a
  deterministic floor with the model as an additive layer; this doc is how that floor stays guaranteed
  when the work runs on a schedule.
