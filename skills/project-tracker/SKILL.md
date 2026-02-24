---
name: project-tracker
description: Use when generating project pages, project briefs, or assessing project health. This skill provides the scoring methodology for momentum, risk, action prioritization, and client relationship temperature.
version: 1.0.0
---

# Project Tracker

This skill provides reference material for the project tracker module — project health scoring, risk assessment, and action prioritization.

## When to Use

- Generating project pages (`/project-page`)
- Generating project briefs (`/project-brief`)
- Assessing project health, momentum, or risk
- Prioritizing next actions for a project
- Cross-module queries involving project + client relationship data

## Key References

- `references/project-methodology.md` — exact formulas, thresholds, and display formats for every computed project value

## Core Principles

1. **Every project assessment follows project-methodology.md.** Momentum, risk, prioritization — all have defined formulas and thresholds.
2. **Show your work.** Every health label must display the numbers that drove the classification.
3. **NULL over fiction.** If velocity can't be computed (no task completions), show "—" not a guess.
4. **Actions must be specific.** Not "follow up with client" but "Send Sarah the revised timeline — she asked for it in the Feb 12 email."
5. **Client relationship data comes from relationship_scores.** Never invent satisfaction signals, email tone assessments, or relationship dynamics.
