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
- `references/coaching-guidelines.md` — how to generate specific, non-generic coaching insights

## Core Principles

1. **Every insight must cite evidence.** Never generate generic advice. Reference specific moments, quotes, or patterns.
2. **Relationship context matters.** A 60% talk ratio is fine for a presentation but concerning for a collaborative discussion. Context determines whether a metric is positive or negative.
3. **Commitments are sacred.** Track them rigorously. Missed commitments erode trust — this is the most actionable data in the system.
4. **Preserve raw text.** Always store the original transcript. Models will improve, and re-analysis should be possible.
