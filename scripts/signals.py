#!/usr/bin/env python3
"""Signals Engine — proactive-attention layer for Software of You.

An *attention inbox* the system writes to. The hard problems in proactive
surfacing are relevance/restraint (a partner that pings 20x/day gets muted) and
memory (knowing what it already told you and what you did about it). This engine:

    detect (deterministic) -> score -> state-ledger/dedup -> restraint -> deliver -> feedback

- DETECT: candidate signals derive ONLY from the computed views already in the DB
  (v_nudge_items, v_email_response_queue, v_discovery_candidates, v_meeting_prep).
  Every signal carries a source_ref trail, so nothing is invented.
- SCORE: score = 0.5*urgency + 0.3*importance + 0.2*novelty  (deterministic, tunable).
- STATE: upsert into `signals` keyed by a stable signal_key so a recurring condition
  updates one row. A signal auto-RESOLVES when its detector stops emitting (you acted).
- RESTRAINT: `top` returns only the few highest-scoring unacted signals for the push
  brief; everything else stays pull-based on the dashboard.

Pure stdlib. Safe to run repeatedly.

CLI:
    python3 scripts/signals.py detect              # refresh the ledger
    python3 scripts/signals.py top --n 5 [--surface]   # top unacted as JSON (--surface marks them)
    python3 scripts/signals.py summary             # one-line text for SessionStart
    python3 scripts/signals.py dismiss <id>
    python3 scripts/signals.py snooze <id> <days>
    python3 scripts/signals.py act <id>
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

DATA_HOME = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
DB_PATH = Path(DATA_HOME) / "software-of-you" / "soy.db"

# Score weights (tunable). Sum to 1.0.
W_URGENCY, W_IMPORTANCE, W_NOVELTY = 0.5, 0.3, 0.2

TIER_URGENCY = {"urgent": 0.85, "soon": 0.55, "awareness": 0.30}


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _rows(conn, sql, params=()):
    """Run a query, returning [] if the view/table is absent (module not installed)."""
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    except sqlite3.OperationalError:
        return []


# ── Importance: how much this contact matters (client / relationship depth) ──

def _contact_importance(conn):
    """Map contact_id -> base importance in [0,1] from v_contact_health.

    A client (active projects) or a deep relationship weighs more. Deterministic.
    """
    imp = {}
    for r in _rows(conn, "SELECT id, active_projects, relationship_depth FROM v_contact_health"):
        base = 0.5
        if (r.get("active_projects") or 0) > 0:
            base += 0.3  # client relationship
        depth = r.get("relationship_depth")
        try:
            # relationship_depth may be numeric (0..1) or NULL; add a small weighted bump
            if depth is not None:
                base += 0.2 * _clamp(float(depth))
        except (TypeError, ValueError):
            pass
        imp[r["id"]] = _clamp(base)
    return imp


# ── Detectors: each returns a list of candidate signal dicts ──

def _detect_nudges(conn, imp):
    out = []
    for r in _rows(conn, """
        SELECT nudge_type, tier, entity_id, entity_name, contact_id, project_id,
               description, relevant_date, days_value, extra_context
        FROM v_nudge_items
    """):
        ntype = r["nudge_type"]
        if ntype == "untracked_contact":
            continue  # covered (richer) by the discovery detector below
        tier = r.get("tier") or "awareness"
        days = r.get("days_value") or 0

        urgency = TIER_URGENCY.get(tier, 0.3)
        if tier == "urgent":
            urgency = _clamp(urgency + min(0.15, days / 100.0))

        importance = imp.get(r.get("contact_id"), 0.5)
        if ntype == "commitment" and (r.get("entity_name") or "") == "You":
            importance = _clamp(importance + 0.2)  # your reputation is on the line

        signal_class = {
            "follow_up": "commitment_followthrough",
            "commitment": "commitment_followthrough",
            "task": "time_sensitive",
            "cold_contact": "relationship_decay",
        }.get(ntype, "time_sensitive")

        if ntype == "cold_contact":
            title = f"{r['entity_name']} has gone quiet ({days}d)"
            detail = r.get("description") or ""
        elif ntype == "commitment":
            who = r.get("entity_name") or "Someone"
            title = f"Commitment {days}d overdue — {r.get('description') or ''}".strip()
            detail = f"Owner: {who}" + (f" · {r['extra_context']}" if r.get("extra_context") else "")
        elif ntype == "follow_up":
            title = f"Follow-up {days}d overdue — {r.get('entity_name') or ''}"
            detail = r.get("description") or ""
        else:  # task
            title = f"Task {days}d overdue — {r.get('description') or ''}".strip()
            detail = r.get("extra_context") or ""

        out.append({
            "signal_key": f"{ntype}:{r.get('entity_id')}",
            "signal_type": ntype,
            "signal_class": signal_class,
            "entity_type": "contact" if r.get("contact_id") else ("project" if r.get("project_id") else ntype),
            "entity_id": r.get("contact_id") or r.get("project_id") or r.get("entity_id"),
            "entity_name": r.get("entity_name"),
            "title": title,
            "detail": detail,
            "source_ref": json.dumps({"view": "v_nudge_items", "nudge_type": ntype,
                                      "id": r.get("entity_id"), "days": days}),
            "urgency": round(urgency, 3),
            "importance": round(importance, 3),
        })
    return out


# Automation senders that never need a personal reply. Restraint over recall:
# one burst of bot/notification mail must not drown out real people.
_AUTOMATION_LOCALPARTS = (
    "notifications", "noreply", "no-reply", "donotreply", "do-not-reply",
    "mailer-daemon", "bounce", "calendar-noreply", "postmaster", "mailer",
)


def _is_automated(from_name, from_address):
    name = (from_name or "").lower()
    addr = (from_address or "").lower()
    if "[bot]" in name or "noreply" in addr or "no-reply" in addr:
        return True
    local = addr.split("@", 1)[0]
    return local in _AUTOMATION_LOCALPARTS


def _detect_email_queue(conn, imp):
    out = []
    for r in _rows(conn, """
        SELECT id, thread_id, subject, from_name, from_address, contact_id,
               contact_name, days_old, urgency
        FROM v_email_response_queue
    """):
        if _is_automated(r.get("from_name"), r.get("from_address")):
            continue
        u = {"overdue": 0.8, "aging": 0.55}.get(r.get("urgency"), 0.4)
        u = _clamp(u + min(0.15, (r.get("days_old") or 0) / 30.0))
        # Known contact -> use their importance; unknown role-sender -> penalized
        # so a real person always outranks an unlinked address.
        importance = imp.get(r.get("contact_id"), 0.45)
        if not r.get("contact_id"):
            importance = min(importance, 0.3)
        who = r.get("contact_name") or r.get("from_name") or r.get("from_address") or "someone"
        out.append({
            "signal_key": f"email_response:{r.get('thread_id') or r.get('id')}",
            "signal_type": "email_response",
            "signal_class": "time_sensitive",
            "entity_type": "email",
            "entity_id": r.get("contact_id"),
            "entity_name": who,
            "title": f"Unanswered {r.get('days_old')}d — {who}: {r.get('subject') or '(no subject)'}",
            "detail": f"From {r.get('from_address') or ''}",
            "source_ref": json.dumps({"view": "v_email_response_queue",
                                      "thread_id": r.get("thread_id"), "days_old": r.get("days_old")}),
            "urgency": round(u, 3),
            "importance": round(importance, 3),
        })
    return out


def _detect_discovery(conn):
    out = []
    for r in _rows(conn, """
        SELECT from_address, from_name, email_count, thread_count,
               days_since_last, relevance_score
        FROM v_discovery_candidates
        ORDER BY relevance_score DESC LIMIT 10
    """):
        rel = r.get("relevance_score") or 0
        # relevance_score scale is unknown across installs; normalize defensively.
        importance = _clamp(0.35 + (rel / 100.0 if rel > 1 else rel))
        name = r.get("from_name") or r.get("from_address")
        out.append({
            "signal_key": f"discovery:{r.get('from_address')}",
            "signal_type": "discovery",
            "signal_class": "discovery",
            "entity_type": "email",
            "entity_id": None,
            "entity_name": name,
            "title": f"Not in your CRM: {name} ({r.get('email_count')} emails)",
            "detail": f"{r.get('thread_count')} threads · last {r.get('days_since_last')}d ago",
            "source_ref": json.dumps({"view": "v_discovery_candidates",
                                      "from_address": r.get("from_address"),
                                      "email_count": r.get("email_count")}),
            "urgency": 0.35,
            "importance": round(importance, 3),
        })
    return out


def _detect_meetings(conn, imp):
    out = []
    for r in _rows(conn, """
        SELECT event_id, title, start_time, minutes_until, contact_ids, project_name
        FROM v_meeting_prep
        WHERE minutes_until IS NOT NULL AND minutes_until >= 0 AND minutes_until <= 1440
    """):
        mins = r.get("minutes_until") or 0
        urgency = 0.9 if mins <= 120 else 0.7
        out.append({
            "signal_key": f"meeting_prep:{r.get('event_id')}",
            "signal_type": "meeting_prep",
            "signal_class": "time_sensitive",
            "entity_type": "event",
            "entity_id": r.get("event_id"),
            "entity_name": r.get("title"),
            "title": f"Meeting soon: {r.get('title')}"
                     + (f" ({r['project_name']})" if r.get("project_name") else ""),
            "detail": f"in {mins} min",
            "source_ref": json.dumps({"view": "v_meeting_prep", "event_id": r.get("event_id"),
                                      "minutes_until": mins}),
            "urgency": urgency,
            "importance": 0.6,
        })
    return out


def _novelty(surfaced_count):
    return _clamp(1.0 - 0.15 * (surfaced_count or 0), lo=0.3)


def _score(urgency, importance, novelty):
    return round(W_URGENCY * urgency + W_IMPORTANCE * importance + W_NOVELTY * novelty, 4)


def detect(conn):
    """Run all detectors, upsert the ledger, auto-resolve cleared signals."""
    imp = _contact_importance(conn)
    candidates = (
        _detect_nudges(conn, imp)
        + _detect_email_queue(conn, imp)
        + _detect_discovery(conn)
        + _detect_meetings(conn, imp)
    )

    detected_keys = set()
    inserted = updated = 0
    for c in candidates:
        key = c["signal_key"]
        detected_keys.add(key)
        existing = conn.execute(
            "SELECT id, status, surfaced_count FROM signals WHERE signal_key = ?", (key,)
        ).fetchone()

        if existing:
            nov = _novelty(existing["surfaced_count"])
            sc = _score(c["urgency"], c["importance"], nov)
            # A re-emitting resolved/expired-snooze signal reopens.
            status = existing["status"]
            reopen = ""
            if status == "resolved" or status == "snoozed":
                reopen = ", status = 'new', resolved_at = NULL"
            conn.execute(
                f"""UPDATE signals SET urgency=?, importance=?, novelty=?, score=?,
                    title=?, detail=?, source_ref=?, entity_name=?, entity_id=?,
                    last_detected=datetime('now'), updated_at=datetime('now'){reopen}
                    WHERE id=?""",
                (c["urgency"], c["importance"], nov, sc, c["title"], c["detail"],
                 c["source_ref"], c["entity_name"], c["entity_id"], existing["id"]),
            )
            updated += 1
        else:
            nov = 1.0
            sc = _score(c["urgency"], c["importance"], nov)
            conn.execute(
                """INSERT INTO signals
                   (signal_key, signal_type, signal_class, entity_type, entity_id,
                    entity_name, title, detail, source_ref, urgency, importance, novelty, score)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (key, c["signal_type"], c["signal_class"], c["entity_type"], c["entity_id"],
                 c["entity_name"], c["title"], c["detail"], c["source_ref"],
                 c["urgency"], c["importance"], nov, sc),
            )
            inserted += 1

    # Auto-resolve: anything active but no longer detected means the condition cleared
    # (you replied, logged the interaction, closed the commitment). dismissed/acted stay.
    resolved = 0
    active = conn.execute(
        "SELECT id, signal_key FROM signals WHERE status IN ('new','surfaced','snoozed')"
    ).fetchall()
    for row in active:
        if row["signal_key"] not in detected_keys:
            conn.execute(
                "UPDATE signals SET status='resolved', resolved_at=datetime('now'), "
                "updated_at=datetime('now') WHERE id=?", (row["id"],))
            resolved += 1

    conn.commit()
    return {"inserted": inserted, "updated": updated, "resolved": resolved,
            "detected": len(detected_keys)}


def _active_query():
    return """SELECT * FROM signals
              WHERE status IN ('new','surfaced')
                AND (snooze_until IS NULL OR snooze_until < datetime('now'))
              ORDER BY score DESC, urgency DESC"""


def top(conn, n=5, surface=False):
    rows = [dict(r) for r in conn.execute(_active_query() + f" LIMIT {int(n)}").fetchall()]
    if surface and rows:
        ids = [r["id"] for r in rows]
        conn.executemany(
            "UPDATE signals SET status='surfaced', last_surfaced=datetime('now'), "
            "surfaced_count=surfaced_count+1, updated_at=datetime('now') WHERE id=?",
            [(i,) for i in ids])
        conn.commit()
    return rows


def summary(conn, n=3):
    rows = [dict(r) for r in conn.execute(_active_query()).fetchall()]
    if not rows:
        return "Signals: nothing needs attention right now."
    urgent = sum(1 for r in rows if r["urgency"] >= TIER_URGENCY["urgent"])
    tops = "; ".join(r["title"] for r in rows[:n])
    lead = f"{len(rows)} signal(s) need attention"
    if urgent:
        lead += f" ({urgent} urgent)"
    return f"{lead}. Top: {tops}."


def _set_status(conn, sid, status, snooze_days=None, feedback=None):
    if snooze_days is not None:
        conn.execute(
            "UPDATE signals SET status='snoozed', snooze_until=datetime('now', ?), "
            "updated_at=datetime('now') WHERE id=?", (f"+{int(snooze_days)} days", sid))
    else:
        conn.execute(
            "UPDATE signals SET status=?, feedback=COALESCE(?, feedback), "
            "updated_at=datetime('now') WHERE id=?", (status, feedback, sid))
    conn.commit()
    return conn.total_changes


def main():
    p = argparse.ArgumentParser(description="Software of You — Signals Engine")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("detect")
    t = sub.add_parser("top")
    t.add_argument("--n", type=int, default=5)
    t.add_argument("--surface", action="store_true")
    sub.add_parser("summary")
    d = sub.add_parser("dismiss"); d.add_argument("id", type=int)
    s = sub.add_parser("snooze"); s.add_argument("id", type=int); s.add_argument("days", type=int)
    a = sub.add_parser("act"); a.add_argument("id", type=int)
    args = p.parse_args()

    if not DB_PATH.exists():
        print(json.dumps({"error": f"DB not found at {DB_PATH}"}))
        sys.exit(0)

    conn = get_db()
    try:
        if args.cmd == "detect":
            print(json.dumps(detect(conn)))
        elif args.cmd == "top":
            print(json.dumps(top(conn, args.n, args.surface), default=str))
        elif args.cmd == "summary":
            print(summary(conn))
        elif args.cmd == "dismiss":
            _set_status(conn, args.id, "dismissed"); print(json.dumps({"dismissed": args.id}))
        elif args.cmd == "snooze":
            _set_status(conn, args.id, "snoozed", snooze_days=args.days)
            print(json.dumps({"snoozed": args.id, "days": args.days}))
        elif args.cmd == "act":
            _set_status(conn, args.id, "acted", feedback="user acted")
            print(json.dumps({"acted": args.id}))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
