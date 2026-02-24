---
name: conversation-intelligence
description: Use when processing meeting transcripts, analyzing conversations, extracting commitments, or generating communication coaching insights. This skill provides parsing patterns, coaching guidelines, and the relationship scoring algorithm.
version: 1.0.0
---

# Conversation Intelligence

This skill provides reference material for the conversation intelligence module — transcript parsing, commitment extraction, coaching, and relationship scoring.

## When to Use

- Processing an imported transcript (`/import-call`)
- Generating communication reviews or relationship pulses
- Answering questions about conversation patterns or commitments
- Cross-module queries involving conversation data

## Key References

- `references/transcript-formats.md` — speaker label patterns, timestamp formats, VTT/SRT handling
- `references/coaching-guidelines.md` — SBI+T coaching framework, threshold checklist, direct tone
- `references/scoring-methodology.md` — exact formulas, thresholds, and NULL conditions for every computed value

## Core Principles

1. **Every insight must cite evidence.** Never generate generic advice. Reference specific moments, quotes, or patterns.
2. **Relationship context matters.** A 60% talk ratio is fine for a presentation but concerning for a collaborative discussion. Context determines whether a metric is positive or negative.
3. **Commitments are sacred.** Track them rigorously. Missed commitments erode trust — this is the most actionable data in the system.
4. **Preserve raw text.** Always store the original transcript. Models will improve, and re-analysis should be possible.
5. **Every computed value follows scoring-methodology.md.** Depth, trajectory, sentiment, follow-through — all have defined formulas and thresholds. Insufficient data = NULL, not a guess.
6. **data_points populated for every insight.** Every row in `communication_insights` must have a `data_points` JSON value showing the evidence that triggered the insight. No evidence = no insight row.
