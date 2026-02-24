"""Transcripts tool — import, analyze, and track meeting transcripts.

Uses a two-step import flow:
1. Claude calls import with raw text → server stores, returns text for analysis
2. Claude analyzes (counts words, questions, extracts commitments, generates insights)
3. Claude calls add_analysis with the results → server stores all extracted data

This keeps intelligence with Claude, storage with the server.
"""

import json

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, execute_many, rows_to_dicts


def register(server: FastMCP) -> None:
    @server.tool()
    def transcripts(
        action: str,
        raw_text: str = "",
        title: str = "",
        source: str = "paste",
        occurred_at: str = "",
        transcript_id: int = 0,
        participants: str = "",
        metrics: str = "",
        commitments_data: str = "",
        insights: str = "",
        relationship_scores: str = "",
        call_intelligence: str = "",
        summary: str = "",
        duration_minutes: int = 0,
        commitment_id: int = 0,
    ) -> dict:
        """Import and analyze meeting transcripts.

        Actions:
          import            — Store a transcript for analysis (raw_text required, title optional)
          add_analysis      — Store analysis results (transcript_id required, plus metrics/commitments/insights/relationship_scores)
          list              — List recent transcripts
          get               — Get full transcript details (transcript_id required)
          commitments       — List open commitments (optional transcript_id filter)
          complete_commitment — Mark a commitment done (commitment_id required)

        Two-step import flow:
        1. Call import with the raw_text → returns transcript_id and the text
        2. YOU (Claude) analyze the text: count words per speaker, count questions,
           calculate talk ratios, extract commitments, generate insights
        3. Call add_analysis with transcript_id and all extracted data

        CRITICAL: When analyzing transcripts, derive ALL metrics from actual text.
        Word count = count words. Question count = count '?' marks.
        Duration = parse timestamps (NULL if no timestamps). Never estimate.
        """
        if action == "import":
            return _import(raw_text, title, source, occurred_at)
        elif action == "add_analysis":
            return _add_analysis(transcript_id, participants, metrics, commitments_data,
                                 insights, relationship_scores, call_intelligence, summary, duration_minutes)
        elif action == "list":
            return _list()
        elif action == "get":
            return _get(transcript_id)
        elif action == "commitments":
            return _commitments(transcript_id)
        elif action == "complete_commitment":
            return _complete_commitment(commitment_id)
        else:
            return {"error": f"Unknown action: {action}"}


def _import(raw_text, title, source, occurred_at):
    if not raw_text:
        return {"error": "raw_text is required — paste the transcript content."}

    occ = occurred_at or "datetime('now')"
    if occ == "datetime('now')":
        tid = execute_many([
            (
                "INSERT INTO transcripts (title, source, raw_text) VALUES (?, ?, ?)",
                (title or "Untitled transcript", source, raw_text),
            ),
            (
                """INSERT INTO activity_log (entity_type, entity_id, action, details)
                   VALUES ('transcript', last_insert_rowid(), 'imported', ?)""",
                (f"Transcript: {title or 'Untitled'}",),
            ),
        ])
    else:
        tid = execute_many([
            (
                "INSERT INTO transcripts (title, source, raw_text, occurred_at) VALUES (?, ?, ?, ?)",
                (title or "Untitled transcript", source, raw_text, occurred_at),
            ),
            (
                """INSERT INTO activity_log (entity_type, entity_id, action, details)
                   VALUES ('transcript', last_insert_rowid(), 'imported', ?)""",
                (f"Transcript: {title or 'Untitled'}",),
            ),
        ])

    return {
        "result": {
            "transcript_id": tid,
            "title": title or "Untitled transcript",
            "raw_text": raw_text,
        },
        "_context": {
            "instructions": [
                "Now analyze this transcript. For each speaker:",
                "1. Count their total words (word_count)",
                "2. Count sentences ending in '?' (question_count)",
                "3. Calculate talk_ratio = their words / total words",
                "4. Find longest consecutive block (longest_monologue_seconds — use timestamps if available, estimate from words at ~150wpm if not)",
                "5. Count interruptions (explicit overlap markers only: [overlapping], <crosstalk>, [cross-talk]). Store 0 if none found.",
                "6. Extract commitments (things people said they'd do)",
                "7. Generate a relationship pulse insight and a coach note",
                "7b. Include data_points JSON on every insight (see scoring-methodology.md)",
                "7c. Compute relationship scores using formulas from scoring-methodology.md",
                "8. Extract call intelligence (org intel, pain points, tech stack, concerns)",
                "9. Parse duration from first and last timestamps (NULL if none)",
                "10. Show your work before storing — output the calculation summary",
                "Then call transcripts(action='add_analysis', transcript_id=..., ...)",
            ],
            "presentation": "Tell the user you're analyzing the transcript. Show your work.",
        },
    }


def _add_analysis(transcript_id, participants, metrics, commitments_data,
                   insights, relationship_scores, call_intelligence, summary, duration_minutes):
    if not transcript_id:
        return {"error": "transcript_id is required."}

    statements = []

    # Update transcript with summary and duration
    if summary or duration_minutes or call_intelligence:
        updates = ["processed_at = datetime('now')", "updated_at = datetime('now')"]
        params = []
        if summary:
            updates.append("summary = ?")
            params.append(summary)
        if duration_minutes:
            updates.append("duration_minutes = ?")
            params.append(duration_minutes)
        if call_intelligence:
            updates.append("call_intelligence = ?")
            params.append(call_intelligence)
        params.append(transcript_id)
        statements.append((
            f"UPDATE transcripts SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        ))

    # Save participants: JSON array of {contact_id, speaker_label, is_user}
    if participants:
        try:
            parts = json.loads(participants) if isinstance(participants, str) else participants
            for p in parts:
                statements.append((
                    """INSERT INTO transcript_participants (transcript_id, contact_id, speaker_label, is_user)
                       VALUES (?, ?, ?, ?)""",
                    (transcript_id, p.get("contact_id"), p["speaker_label"], p.get("is_user", 0)),
                ))
        except (json.JSONDecodeError, KeyError):
            pass

    # Save metrics: JSON array of {contact_id, talk_ratio, word_count, question_count, ...}
    if metrics:
        try:
            mets = json.loads(metrics) if isinstance(metrics, str) else metrics
            for m in mets:
                statements.append((
                    """INSERT INTO conversation_metrics
                       (transcript_id, contact_id, talk_ratio, word_count, question_count,
                        interruption_count, longest_monologue_seconds)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (transcript_id, m.get("contact_id"), m.get("talk_ratio"),
                     m.get("word_count"), m.get("question_count"),
                     m.get("interruption_count", 0), m.get("longest_monologue_seconds")),
                ))
        except (json.JSONDecodeError, KeyError):
            pass

    # Save commitments: JSON array of {owner_contact_id, is_user_commitment, description, ...}
    if commitments_data:
        try:
            comms = json.loads(commitments_data) if isinstance(commitments_data, str) else commitments_data
            for c in comms:
                statements.append((
                    """INSERT INTO commitments
                       (transcript_id, owner_contact_id, is_user_commitment, description,
                        deadline_mentioned, deadline_date)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (transcript_id, c.get("owner_contact_id"), c.get("is_user_commitment", 0),
                     c["description"], c.get("deadline_mentioned"), c.get("deadline_date")),
                ))
        except (json.JSONDecodeError, KeyError):
            pass

    # Save insights: JSON array of {contact_id, insight_type, content, sentiment}
    if insights:
        try:
            ins = json.loads(insights) if isinstance(insights, str) else insights
            for i in ins:
                statements.append((
                    """INSERT INTO communication_insights
                       (transcript_id, contact_id, insight_type, content, sentiment, data_points)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (transcript_id, i.get("contact_id"), i["insight_type"],
                     i["content"], i.get("sentiment", "neutral"),
                     json.dumps(i["data_points"]) if i.get("data_points") else None),
                ))
        except (json.JSONDecodeError, KeyError):
            pass

    # Save relationship scores: JSON array of {contact_id, meeting_frequency, talk_ratio_avg, ...}
    if relationship_scores:
        try:
            scores = json.loads(relationship_scores) if isinstance(relationship_scores, str) else relationship_scores
            for s in scores:
                statements.append((
                    """INSERT INTO relationship_scores
                       (contact_id, score_date, meeting_frequency, talk_ratio_avg,
                        commitment_follow_through, topic_diversity, relationship_depth,
                        trajectory, notes)
                       VALUES (?, date('now'), ?, ?, ?, NULL, ?, ?, ?)""",
                    (s["contact_id"], s.get("meeting_frequency"),
                     s.get("talk_ratio_avg"), s.get("commitment_follow_through"),
                     s.get("relationship_depth"), s.get("trajectory"),
                     s.get("notes")),
                ))
        except (json.JSONDecodeError, KeyError):
            pass

    if statements:
        execute_many(statements)

    return {
        "result": {"transcript_id": transcript_id, "analysis_stored": True},
        "_context": {
            "suggestions": [
                "Present the analysis summary to the user",
                "Show commitments as a checklist",
                "Mention the coach's note",
            ],
            "presentation": "Show structured blocks: stats grid, commitments, insights, then narrative.",
        },
    }


def _list():
    rows = execute(
        """SELECT t.id, t.title, t.source, t.duration_minutes, t.occurred_at,
                  t.summary, GROUP_CONCAT(DISTINCT c.name) as participant_names
           FROM transcripts t
           LEFT JOIN transcript_participants tp ON tp.transcript_id = t.id AND tp.is_user = 0
           LEFT JOIN contacts c ON c.id = tp.contact_id
           GROUP BY t.id
           ORDER BY t.occurred_at DESC LIMIT 20"""
    )

    return {
        "result": rows_to_dicts(rows),
        "count": len(rows),
        "_context": {
            "presentation": "Show as a list with title, participants, date, duration.",
        },
    }


def _get(transcript_id):
    if not transcript_id:
        return {"error": "transcript_id is required."}

    t = execute("SELECT * FROM transcripts WHERE id = ?", (transcript_id,))
    if not t:
        return {"error": f"No transcript with id {transcript_id}."}

    participants = execute(
        """SELECT tp.*, c.name as contact_name FROM transcript_participants tp
           LEFT JOIN contacts c ON c.id = tp.contact_id
           WHERE tp.transcript_id = ?""",
        (transcript_id,),
    )
    metrics = execute(
        """SELECT cm.*, c.name as contact_name FROM conversation_metrics cm
           LEFT JOIN contacts c ON c.id = cm.contact_id
           WHERE cm.transcript_id = ?""",
        (transcript_id,),
    )
    comms = execute(
        """SELECT com.*, c.name as owner_name FROM commitments com
           LEFT JOIN contacts c ON c.id = com.owner_contact_id
           WHERE com.transcript_id = ?""",
        (transcript_id,),
    )
    ins = execute(
        "SELECT * FROM communication_insights WHERE transcript_id = ?",
        (transcript_id,),
    )

    return {
        "result": rows_to_dicts(t)[0],
        "participants": rows_to_dicts(participants),
        "metrics": rows_to_dicts(metrics),
        "commitments": rows_to_dicts(comms),
        "insights": rows_to_dicts(ins),
        "_context": {
            "presentation": "Show full transcript analysis: stats, commitments, insights, narrative.",
        },
    }


def _commitments(transcript_id):
    if transcript_id:
        rows = execute(
            """SELECT com.*, c.name as owner_name, t.title as from_call
               FROM commitments com
               LEFT JOIN contacts c ON c.id = com.owner_contact_id
               LEFT JOIN transcripts t ON t.id = com.transcript_id
               WHERE com.transcript_id = ? AND com.status IN ('open', 'overdue')
               ORDER BY com.deadline_date ASC NULLS LAST""",
            (transcript_id,),
        )
    else:
        rows = execute(
            """SELECT com.*, c.name as owner_name, t.title as from_call
               FROM commitments com
               LEFT JOIN contacts c ON c.id = com.owner_contact_id
               LEFT JOIN transcripts t ON t.id = com.transcript_id
               WHERE com.status IN ('open', 'overdue')
               ORDER BY com.deadline_date ASC NULLS LAST"""
        )

    commitments = rows_to_dicts(rows)

    # Flag overdue
    from datetime import date
    today = date.today().isoformat()
    for c in commitments:
        c["overdue"] = c["deadline_date"] and c["deadline_date"] < today

    yours = [c for c in commitments if c["is_user_commitment"]]
    theirs = [c for c in commitments if not c["is_user_commitment"]]

    return {
        "result": commitments,
        "yours": yours,
        "theirs": theirs,
        "count": len(commitments),
        "_context": {
            "suggestions": ["Group by yours vs theirs", "Highlight overdue commitments"],
            "presentation": "Show as two sections: Your commitments and Their commitments. Checklist style.",
        },
    }


def _complete_commitment(commitment_id):
    if not commitment_id:
        return {"error": "commitment_id is required."}

    rows = execute("SELECT * FROM commitments WHERE id = ?", (commitment_id,))
    if not rows:
        return {"error": f"No commitment with id {commitment_id}."}

    execute_many([
        (
            "UPDATE commitments SET status = 'completed', completed_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (commitment_id,),
        ),
        (
            """INSERT INTO activity_log (entity_type, entity_id, action, details)
               VALUES ('commitment', ?, 'completed', ?)""",
            (commitment_id, rows[0]["description"]),
        ),
    ])

    return {
        "result": {"commitment_id": commitment_id, "status": "completed"},
        "_context": {"presentation": "Commitment marked complete."},
    }
