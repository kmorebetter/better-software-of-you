"""Tests for generated-HTML escaping (stored-XSS hardening, finding C2).

The view layer renders Jinja2 templates that interpolate DB- and
external-derived values (contact names, email ``from_name``, calendar event
titles, transcript text). Before the fix the Jinja ``Environment`` ran with
``autoescape=False``, so a value like ``<script>alert(1)</script>`` stored in
the DB was emitted verbatim into the generated page and executed when the file
was opened in a browser — a stored-XSS hole.

The fix flips the env to ``jinja2.select_autoescape(["html"])``. These tests
prove:

1. Hostile DB values render ESCAPED/inert in a generated page (no live
   ``<script>`` / ``onerror=`` reaches the output; the escaped form does).
2. The one intentional raw-HTML channel — ``module_view.html``'s
   ``{{ section.html | safe }}`` — still renders legitimate trusted markup
   without double-escaping.
3. A source guard: ``autoescape=False`` no longer appears in ``views.py``.
"""

import inspect
from pathlib import Path

from software_of_you.tools import contacts, views


def test_contact_name_script_is_escaped_in_entity_page(soy_db, tmp_path, monkeypatch):
    """A hostile contact name renders inert through the full builder.

    Invokes the real ``_render_entity_page`` builder end-to-end (the simplest
    full view entry point that takes DB-derived data) with a stored contact name
    carrying an attribute-breakout XSS payload, and asserts the raw injected tag
    never reaches the rendered HTML while its escaped form does.

    A ``</script>``-style payload would derive a slug containing ``/`` and break
    the filesystem write (a separate slug-sanitisation gap, out of scope for the
    escaping fix), so this uses an equivalent script-injection-class payload that
    yields a writable slug. The pure ``<script>...`` case is covered at the
    template level in ``test_hostile_email_and_event_values_escaped_via_template``.
    """
    # views.py imported VIEWS_DIR by value at module load; redirect the name it
    # actually writes to so the test never touches the user's real views dir.
    out_dir = tmp_path / "views_out"
    out_dir.mkdir()
    monkeypatch.setattr(views, "VIEWS_DIR", out_dir)

    hostile = '"><img src=x onerror=alert(1)>'
    contacts._add(hostile, "evil@example.com", "", "Acme", "", "individual", "active", None)
    rows = soy_db.execute("SELECT id FROM contacts WHERE name = ?", (hostile,))
    assert len(rows) == 1
    contact_id = rows[0]["id"]

    result = views._render_entity_page(contact_id, "", open_after=False)
    assert "error" not in result, result

    html = Path(result["result"]["path"]).read_text()

    # The live injected tag (and attribute breakout) must NOT appear unescaped.
    assert "<img src=x onerror=" not in html
    assert '"><img' not in html
    # The escaped form proves the DB value was rendered as inert text.
    assert "&lt;img src=x onerror=alert(1)&gt;" in html


def test_hostile_email_and_event_values_escaped_via_template(soy_db):
    """Email ``from_name`` / event title with an img/onerror payload render inert.

    Renders ``entity_page.html`` directly through the (now autoescaping) Jinja
    env with hostile context values, which proves the escaping fix independently
    of how much DB seeding a full builder invocation would need.
    """
    env = views._get_env()
    template = env.get_template("pages/entity_page.html")

    payload = '"><img src=x onerror=alert(1)>'
    ctx = {
        "contact": {"id": 1, "name": payload, "company": payload, "status": "active"},
        "modules": ["gmail", "calendar"],
        "active_page": "contacts",
        "active_section": "people",
        "active_entity_id": 1,
        "nav_counts": type("Counts", (), {})(),
        "contact_pages": [],
        "project_pages": [],
        "tip_text": "tip",
        "generated_at": "now",
        "tags": [],
        "notes": [],
        "emails": [
            {
                "from_name": payload,
                "subject": payload,
                "snippet": payload,
                "direction": "inbound",
                "received_at_formatted": "today",
            }
        ],
        "upcoming_events": [{"title": payload, "start_formatted": "soon"}],
        "narrative_sections": {},
        "next_action": None,
    }

    html = template.render(**ctx)

    # No live injected tag survives: the dangerous form is an actual ``<img ...>``
    # element. With escaping on, the angle brackets become entities, so the raw
    # tag (and the attribute-breakout ``"><``) must NOT appear unescaped. (The
    # bare text ``onerror=alert(1)`` between escaped brackets is inert and may
    # legitimately remain as escaped text — only the live tag matters.)
    assert "<img src=x onerror=" not in html
    assert '"><img' not in html
    # Escaped markers prove the payload was neutralised into inert text.
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "&#34;&gt;" in html or "&quot;&gt;" in html


def test_safe_channel_renders_trusted_html_without_double_escaping(soy_db):
    """The intentional ``{{ section.html | safe }}`` channel still renders raw HTML.

    Autoescaping must not double-escape trusted markup that legitimately passes
    through the ``|safe`` channel (e.g. chart markup, a ``<strong>`` callout).
    """
    env = views._get_env()
    template = env.get_template("pages/module_view.html")

    trusted = '<strong class="font-bold">Revenue up <svg><rect></rect></svg></strong>'
    ctx = {
        "modules": [],
        "active_page": "dashboard",
        "active_section": "",
        "active_entity_id": None,
        "nav_counts": type("Counts", (), {})(),
        "contact_pages": [],
        "project_pages": [],
        "tip_text": "tip",
        "generated_at": "now",
        "page_title": "Report",
        "page_subtitle": "",
        "header_stats": [],
        "sections": [{"type": "html", "html": trusted}],
    }

    html = template.render(**ctx)

    # Trusted markup passes through intact — not double-escaped.
    assert trusted in html
    assert "&lt;strong" not in html


def test_views_source_has_no_autoescape_false():
    """Guard: the autoescape=False foot-gun must not return to views.py."""
    source = inspect.getsource(views)
    assert "autoescape=False" not in source
    # And the env is built with select_autoescape (positive assertion).
    assert "select_autoescape" in source


def test_env_autoescape_is_active_for_html():
    """The constructed env autoescapes .html templates."""
    env = views._get_env()
    # select_autoescape(["html"]) enables escaping for html-suffixed templates.
    assert env.autoescape  # truthy callable/flag
    rendered = env.from_string("{{ x }}").render(x="<b>")  # no name → default off
    # from_string has no filename, so this just confirms the env is usable;
    # the template-level assertions above cover .html escaping behaviour.
    assert rendered in ("<b>", "&lt;b&gt;")
