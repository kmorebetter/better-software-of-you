# This Is Software of You

A comprehensive brief on what it is, why it exists, and what we've built.

---

## What It Is

Software of You is a personal data platform that runs as a Claude Code plugin. It turns your AI assistant into a unified operating system for your professional life — your contacts, conversations, decisions, email, calendar, journal, and notes, all cross-referenced by AI and stored locally on your machine.

You interact entirely through natural language. There's no separate app to learn, no forms to fill out, no dashboard to navigate manually. Claude is the interface. SQLite is the database. The data lives on your machine.

**One-time purchase. $149. All modules included, forever.**

---

## The Problem It Solves

### The stateless AI problem

Every AI conversation starts from zero. The model knows nothing about you — your clients, your history, your relationships, your work. So you compensate: you paste in background, re-explain your situation, remind it what happened last time. You're doing the work of context manually, repeatedly, incompletely.

This is prompt engineering's ceiling. You can craft a perfect question, but the machine still knows nothing about you before you ask.

### The fragmentation problem

Your context is shattered across a dozen SaaS tools. Contacts in HubSpot. Conversations trapped in Zoom recordings. Decisions scattered across Slack threads. Email in Gmail, calendar in Google Calendar, notes in Notion, tasks in Asana. And your relationships — the actual texture of who you know and what you've built together — live nowhere at all.

Each tool holds a fragment. None of them talk to each other. And critically, none of them talk to your AI.

So when you ask Claude "should I follow up with Sarah?" — it has nothing. No relationship history. No conversation context. No knowledge of your shared projects. Generic context produces generic answers.

You're paying $100+/month for tools that don't talk to each other, and still doing the context work yourself.

---

## The Idea: Context Engineering

The prompt engineering era taught us to talk to AI. The context engineering era is teaching us to think with it.

Context engineering is not about optimizing what you *say*. It's about building what your AI *knows* — a structured, cross-referenced representation of your professional world that makes every interaction smarter.

**It compounds.** Every contact you add, every conversation you log, every email that syncs — each one makes every future interaction more useful. Not because the model improved. Because the context did.

Software of You is a context engineering platform for your life. You bring the data. It builds the structure. Every question you ask, every dashboard you generate, every decision you revisit draws on everything you've put in.

You are not talking to AI. You are thinking with it.

---

## Positioning

**Category:** Personal data platform / context engineering tool
**For:** Individual professionals — freelancers, consultants, founders, technical operators
**Against:** Fragmented SaaS stacks (HubSpot, Notion, Otter.ai, Linear, etc.) + stateless AI
**Price:** $149 one-time vs. $100+/month for equivalent coverage
**Moat:** Local data ownership + compounding cross-references + no lock-in

### Who it's for

- **Freelancers and consultants** juggling 10+ client relationships, each with their own email threads, meeting cadences, and project timelines
- **Founders and agency owners** managing partnerships, investors, team dynamics, and strategic decisions across time
- **Technical professionals** already working in Claude Code who want their relationship and project data where they work

### What it's not

- Not a team tool — it's a personal operating system, one installation per person
- Not a cloud SaaS — everything is local, nothing is sent to external servers (except direct Google OAuth sync)
- Not another CRM — it's a cross-referenced system where everything connects to everything else

---

## What We've Built

### The architecture

- **Claude Code plugin** — runs natively inside the Claude Code environment
- **SQLite database** — lives at `~/.local/share/software-of-you/soy.db`, survives repo updates
- **Natural language interface** — Claude handles all SQL translation; users never see a query
- **Auto-backup system** — snapshots before every migration, auto-restores if data loss detected
- **Auto-sync** — Gmail and Calendar sync automatically before any view is generated (15-min freshness window)
- **Slash commands** — 45+ commands covering every workflow

### 8 modules

| Module | What it does |
|---|---|
| **CRM** | Contacts, interactions, relationships, follow-ups |
| **Project Tracker** | Projects, tasks, milestones linked to contacts |
| **Gmail** | Email sync, compose, threads with contact context |
| **Calendar** | Event sync, scheduling, meeting context |
| **Conversation Intelligence** | Transcript analysis, commitment extraction, relationship scoring |
| **Decision Log** | Structured decisions with options, rationale, and outcome tracking |
| **Journal** | Daily entries with mood/energy tracking, cross-referenced to contacts and projects |
| **Notes** | Standalone notes with #hashtag tags, pinning, and auto cross-referencing |

### The views

Generated HTML pages that provide a rich visual interface alongside the conversational layer:

- **Dashboard** — command center with activity feed, email, calendar, follow-ups, nudges
- **Entity pages** — full contact intelligence briefs with relationship history, emails, transcripts, projects
- **Project pages** — project briefs with client context, task status, milestones, meeting history
- **Module views** — Conversations, Decisions, Journal, Notes, Email Hub, Network Map, Weekly Review, Timeline, Search Hub, Nudges
- **Build-all** — generates every view at once, all with full spec

### Intelligence features

- **Cross-referencing** — contacts know about their projects; projects know their client history; decisions know who shaped them
- **Conversation intelligence** — import any meeting transcript, extract commitments, measure talk ratios, track relationship health over time
- **Relationship scoring** — derived from interaction frequency, email tone, commitment follow-through
- **Nudges** — surfaces contacts going cold, overdue commitments, stale projects, upcoming anniversaries
- **Decision outcomes** — grounded in Annie Duke's process/outcome framework; tracks what actually happened vs. what you expected

### Google integration

- Gmail sync — last 50 emails, auto-linked to contacts by address
- Calendar sync — next 14 days + last 7 days, linked to contacts as attendees
- Gemini transcript sync — scans emails from Gemini Notes, fetches linked Google Docs, stores raw transcripts for analysis
- OAuth embedded — no credential file required; users authenticate once

### Privacy and ownership

- All data lives locally — no cloud, no analytics, no telemetry
- Standard SQLite format — open with any SQLite client, no vendor lock-in
- Google OAuth runs directly between your machine and Google's API — we never see the data
- Backup and export built in

---

## Why

> The prompt engineering era taught us to talk to AI. But every conversation starts from zero — the AI knows nothing about your work, your relationships, your history. You are a stranger every time.
>
> Context engineering is different. Instead of optimizing what you say, you build what your AI knows — a structured, cross-referenced representation of your professional world that makes every interaction smarter.
>
> The problem is that your context is scattered across a dozen SaaS tools that don't talk to each other and don't talk to your AI. Your contacts are in one place, your emails in another, your conversations in a third, and your relationships — the actual texture of who you know and what you've built together — live nowhere at all.
>
> Software of You brings it together. One place. On your machine. Compounding over time.
>
> Every contact you add, every conversation you log, every email that syncs — each one makes every future question smarter. Not because the model improved. Because the context did.
>
> You are not talking to AI. You are thinking with it.

---

## The Thesis in One Sentence

**Software of You is a context engineering platform — a local, AI-powered, cross-referenced model of your professional life that makes every Claude interaction smarter the longer you use it.**

---

*Last updated: February 2026*
