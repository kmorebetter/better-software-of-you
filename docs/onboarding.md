# First-Run Onboarding

> Extracted from CLAUDE.md to reduce always-on context weight.
> Load this file when bootstrap returns contacts = 0.

After bootstrap, check the contact count from the status line. If contacts = 0, check if the user profile exists:
```sql
SELECT COUNT(*) FROM user_profile WHERE category = 'identity';
```

## Case 1: Brand new user (contacts = 0, no identity rows)

**Show the welcome art and pitch:**

```
        ╭──────────╮
        │  ◠    ◠  │
        │    ◡◡    │
        ╰────┬┬────╯
            ╱╲╱╲

  S O F T W A R E  of  Y O U
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Your personal data platform.
  Nice to meet you! ♡
```

Everything lives on your machine, and I'm your only interface.

I can track your relationships, log conversations, connect your email and calendar, make decisions, keep a journal — and I'll cross-reference all of it automatically.

**Then collect the user's profile:**

1. Ask their name conversationally: "First — what should I call you?"
2. Store the name:
   ```sql
   INSERT OR REPLACE INTO user_profile (category, key, value, source, updated_at) VALUES ('identity', 'name', '<name>', 'explicit', datetime('now'));
   ```
3. Use the `AskUserQuestion` tool with 3 questions in a single call:
   - **Q1** (header: "Role"): "What best describes your work?" — options: Freelancer/Consultant, Agency/Studio Owner, Solopreneur, Corporate/In-house (multiSelect: false)
   - **Q2** (header: "Focus", multiSelect: true): "What are you primarily tracking?" — options: Client relationships, Projects & deliverables, Business communications, Personal network
   - **Q3** (header: "Style"): "How should I communicate with you?" — options: Brief and direct, Detailed with context, Casual and conversational (multiSelect: false)
4. Store all answers in `user_profile`:
   ```sql
   INSERT OR REPLACE INTO user_profile (category, key, value, source, updated_at) VALUES ('identity', 'role', '<answer>', 'explicit', datetime('now'));
   INSERT OR REPLACE INTO user_profile (category, key, value, source, updated_at) VALUES ('preferences', 'focus', '<answer(s) comma-separated>', 'explicit', datetime('now'));
   INSERT OR REPLACE INTO user_profile (category, key, value, source, updated_at) VALUES ('preferences', 'communication_style', '<answer>', 'explicit', datetime('now'));
   ```
5. Log to `activity_log` and set profile as complete:
   ```sql
   INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) VALUES ('user_profile', 0, 'profile_created', 'Initial profile setup completed', datetime('now'));
   INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('profile_setup_completed', '1', datetime('now'));
   ```
6. Transition: "Got it, [name]. Now let's get some data in here." Then continue to the data prompts below.

## Case 2: Profile exists but no contacts (contacts = 0, identity rows exist)

Skip profile collection. Go straight to data prompts:

**The best way to start is to give me data.** Here are a few ways in:

- **Add people** — "Add a contact named Sarah Chen, VP of Engineering at Acme"
- **Import in bulk** — drop a CSV of your clients or contacts right here
- **Upload a transcript** — paste a call transcript and I'll extract insights and commitments
- **Connect Gmail** — "Connect my Google account" to sync emails and calendar

Who's someone you work with that you'd like to start tracking?

## Case 3: Has contacts (contacts > 0)

Normal session — no onboarding needed.

## Post-First-Contact Guidance

**After the first contact is added, suggest ONE next step** — not a list. Match what feels natural:
- If they added a client → "When did you last talk to them?"
- If they imported a CSV → "Want to connect Google to pull in email history for these contacts?"
- If they uploaded a transcript → "I extracted 3 commitments from that call. Want to see them?"

**Stop onboarding guidance** once they have 3+ contacts or have used 2+ different features. They've got it.
