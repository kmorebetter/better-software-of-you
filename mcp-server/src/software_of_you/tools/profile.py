"""Profile tool — rich cross-referenced entity profile for a contact."""

from mcp.server.fastmcp import FastMCP

from software_of_you.db import execute, rows_to_dicts, get_installed_modules


def register(server: FastMCP) -> None:
    @server.tool()
    def get_profile(contact_id: int = 0, contact_name: str = "") -> dict:
        """Get a complete cross-referenced profile for a contact.

        Returns all data needed to build an entity page: contact details,
        interactions, emails, calendar events, projects, transcripts,
        commitments, notes, tags, and relationship scores.

        Also includes synthesis prompts for Claude to write narrative
        sections (relationship context, company intel, discovery questions).

        This is a data-gathering tool — use it before generate_view to
        create a rich entity page, or to answer detailed questions about a contact.

        Args:
            contact_id: The contact ID (preferred)
            contact_name: Search by name if ID not known
        """
        # Resolve contact
        if contact_id:
            rows = execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        elif contact_name:
            rows = execute("SELECT * FROM contacts WHERE name LIKE ?", (f"%{contact_name}%",))
        else:
            return {"error": "Provide contact_id or contact_name."}

        if not rows:
            return {"error": "Contact not found."}
        if len(rows) > 1:
            return {
                "error": "Multiple contacts match.",
                "matches": rows_to_dicts(rows),
            }

        contact = rows_to_dicts(rows)[0]
        cid = contact["id"]
        modules = get_installed_modules()
        profile = {"contact": contact, "modules": modules}

        # Determine scope (company contacts)
        scope_ids = [cid]
        if contact["type"] == "company":
            members = execute(
                "SELECT id FROM contacts WHERE company = ? AND type = 'individual' AND status = 'active'",
                (contact["company"],),
            )
            scope_ids.extend([m["id"] for m in members])
            profile["company_members"] = rows_to_dicts(members)

        scope_placeholder = ",".join("?" * len(scope_ids))

        # Tags
        profile["tags"] = rows_to_dicts(execute(
            f"""SELECT t.name, t.color FROM tags t
                JOIN entity_tags et ON et.tag_id = t.id
                WHERE et.entity_type = 'contact' AND et.entity_id IN ({scope_placeholder})""",
            tuple(scope_ids),
        ))

        # Entity notes
        profile["notes"] = rows_to_dicts(execute(
            f"SELECT content, created_at FROM notes WHERE entity_type = 'contact' AND entity_id IN ({scope_placeholder}) ORDER BY created_at DESC LIMIT 10",
            tuple(scope_ids),
        ))

        # CRM data
        if "crm" in modules:
            profile["interactions"] = rows_to_dicts(execute(
                f"""SELECT ci.*, c.name as contact_name FROM contact_interactions ci
                    JOIN contacts c ON c.id = ci.contact_id
                    WHERE ci.contact_id IN ({scope_placeholder})
                    ORDER BY ci.occurred_at DESC LIMIT 30""",
                tuple(scope_ids),
            ))

            profile["relationships"] = rows_to_dicts(execute(
                """SELECT cr.relationship_type, cr.notes,
                          CASE WHEN cr.contact_id_a = ? THEN cb.name ELSE ca.name END as related_name,
                          CASE WHEN cr.contact_id_a = ? THEN cb.company ELSE ca.company END as related_company
                   FROM contact_relationships cr
                   LEFT JOIN contacts ca ON ca.id = cr.contact_id_a
                   LEFT JOIN contacts cb ON cb.id = cr.contact_id_b
                   WHERE cr.contact_id_a = ? OR cr.contact_id_b = ?""",
                (cid, cid, cid, cid),
            ))

            profile["follow_ups"] = rows_to_dicts(execute(
                f"SELECT * FROM follow_ups WHERE contact_id IN ({scope_placeholder}) AND status = 'pending' ORDER BY due_date ASC",
                tuple(scope_ids),
            ))

        # Emails
        if "gmail" in modules:
            profile["emails"] = rows_to_dicts(execute(
                f"""SELECT id, thread_id, subject, snippet, from_name, from_address,
                           to_addresses, direction, received_at, contact_id
                    FROM emails WHERE contact_id IN ({scope_placeholder})
                    ORDER BY received_at ASC""",
                tuple(scope_ids),
            ))

        # Calendar events
        if "calendar" in modules:
            profile["events"] = rows_to_dicts(execute(
                "SELECT * FROM calendar_events WHERE contact_ids LIKE ? ORDER BY start_time DESC LIMIT 30",
                (f"%{cid}%",),
            ))

        # Projects
        if "project-tracker" in modules:
            profile["projects"] = rows_to_dicts(execute(
                f"""SELECT p.*,
                           (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status != 'done') as open_tasks,
                           (SELECT COUNT(*) FROM tasks WHERE project_id = p.id AND status = 'done') as done_tasks
                    FROM projects p WHERE p.client_id IN ({scope_placeholder})
                    ORDER BY p.updated_at DESC""",
                tuple(scope_ids),
            ))

            if profile["projects"]:
                project_ids = [p["id"] for p in profile["projects"]]
                ph = ",".join("?" * len(project_ids))
                profile["tasks"] = rows_to_dicts(execute(
                    f"SELECT t.*, p.name as project_name FROM tasks t JOIN projects p ON p.id = t.project_id WHERE p.client_id IN ({scope_placeholder}) ORDER BY t.due_date ASC NULLS LAST",
                    tuple(scope_ids),
                ))

        # Transcripts
        if "conversation-intelligence" in modules:
            profile["transcripts"] = rows_to_dicts(execute(
                f"""SELECT t.id, t.title, t.summary, t.duration_minutes, t.occurred_at, t.call_intelligence,
                           GROUP_CONCAT(DISTINCT c.name) as participant_names
                    FROM transcripts t
                    JOIN transcript_participants tp ON tp.transcript_id = t.id
                    LEFT JOIN contacts c ON c.id = tp.contact_id AND tp.is_user = 0
                    WHERE tp.contact_id IN ({scope_placeholder})
                    GROUP BY t.id ORDER BY t.occurred_at DESC LIMIT 20""",
                tuple(scope_ids),
            ))

            profile["open_commitments"] = rows_to_dicts(execute(
                f"""SELECT com.*, c.name as owner_name, t.title as from_call
                    FROM commitments com
                    LEFT JOIN contacts c ON c.id = com.owner_contact_id
                    LEFT JOIN transcripts t ON t.id = com.transcript_id
                    WHERE com.status IN ('open', 'overdue')
                      AND (com.owner_contact_id IN ({scope_placeholder})
                           OR com.transcript_id IN (
                             SELECT transcript_id FROM transcript_participants WHERE contact_id IN ({scope_placeholder})))""",
                tuple(scope_ids * 2),
            ))

            profile["relationship_score"] = rows_to_dicts(execute(
                "SELECT * FROM relationship_scores WHERE contact_id = ? ORDER BY score_date DESC LIMIT 1",
                (cid,),
            ))

            profile["communication_insights"] = rows_to_dicts(execute(
                "SELECT insight_type, content, sentiment FROM communication_insights WHERE contact_id = ? ORDER BY created_at DESC LIMIT 5",
                (cid,),
            ))

        # Standalone notes
        if "notes" in modules:
            profile["standalone_notes"] = rows_to_dicts(execute(
                "SELECT id, title, substr(content, 1, 150) as preview, tags, pinned, created_at FROM standalone_notes WHERE linked_contacts LIKE ? ORDER BY pinned DESC, created_at DESC LIMIT 10",
                (f"%{cid}%",),
            ))

        return {
            "result": profile,
            "_context": {
                "synthesis_prompts": {
                    "relationship_context": "Using the interactions, emails, notes, and commitments above, write a 3-5 sentence narrative about this relationship: how it started, key moments, current state, and what's next.",
                    "company_intel": "If company info exists, summarize: what they do, key people, notable projects or work together.",
                    "discovery_questions": "Based on their role, company, and what you know so far, generate 3-5 tailored discovery questions for the next meeting.",
                },
                "suggestions": [
                    "Offer to generate an entity page HTML view",
                    "Highlight upcoming meetings or overdue commitments",
                ],
                "presentation": "Present as a comprehensive profile. Lead with what's most actionable.",
            },
        }
