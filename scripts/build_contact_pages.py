#!/usr/bin/env python3
"""
build_contact_pages.py — deterministic renderer for the "Your People" contact sheets.

Rebuilds, from the SQLite DB, one HTML intelligence page per contact plus an index:
    output/contact-cards.html        # index ("Your People")
    output/people/<slug>.html        # one page per contact

Each page surfaces everything the system holds about a person — the relationship
brief, how we're valuing them (relationship_scores / v_contact_health), how the
conversations read (conversation_metrics + coaching insights), the touchpoint
timeline, and commitments. Gaps render as "—"; nothing is invented.

Pure stdlib (sqlite3). Safe to run any time — idempotent, reads only.
Run:  python3 scripts/build_contact_pages.py
Resolves the repo root from CLAUDE_PLUGIN_ROOT, else from this file's location.
"""
import sqlite3, html, re, os, datetime, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(HERE)
DB = os.path.join(ROOT, "data", "soy.db")
OUT = os.path.join(ROOT, "output")
PEOPLE = os.path.join(OUT, "people")

def esc(x): return html.escape(str(x)) if x is not None else ""
def slug(name): return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

DEPTH_COLOR = {'professional':'indigo','transactional':'zinc','personal':'emerald',
               'collaborative':'emerald','trusted':'violet','strategic':'violet'}
def chip(text, color):
    c = {'indigo':'bg-indigo-50 text-indigo-700 ring-indigo-200','zinc':'bg-zinc-100 text-zinc-600 ring-zinc-200',
         'emerald':'bg-emerald-50 text-emerald-700 ring-emerald-200','amber':'bg-amber-50 text-amber-700 ring-amber-200',
         'sky':'bg-sky-50 text-sky-700 ring-sky-200','violet':'bg-violet-50 text-violet-700 ring-violet-200'}[color]
    return f'<span class="text-[11px] font-medium px-2.5 py-1 rounded-full ring-1 {c}">{text}</span>'

def talkbar(r):
    if r is None: return ''
    you = round(r*100); them = 100-you
    return (f'<div class="mt-2"><div class="flex h-2 rounded-full overflow-hidden ring-1 ring-zinc-200">'
            f'<div style="width:{you}%" class="bg-indigo-400"></div><div style="width:{them}%" class="bg-zinc-200"></div></div>'
            f'<div class="flex justify-between text-[11px] text-zinc-500 mt-1"><span>You {you}%</span><span>Them {them}%</span></div></div>')

def build_rel(noteraw):
    if not noteraw:
        return ('<section><h2 class="display text-2xl text-zinc-900 mb-2">The relationship</h2>'
                '<p class="text-[13px] text-zinc-400 italic">No relationship context yet — it fills in from interactions.</p></section>')
    note = noteraw.strip(); source = None
    m = re.search(r'(Basis:\s*.+)$', note)
    if m: source = m.group(1).strip(); note = note[:m.start()].strip()
    else:
        m = re.search(r'\((From [^)]*)\)\s*$', note)
        if m: source = m.group(1).strip(); note = note[:m.start()].strip()
    pat = re.compile(r'([A-Z]{2}[A-Z \-/]*?(?:\s*\([^)]*\))?:)(?:\s)')
    ms = list(pat.finditer(note)); segs = []
    if ms:
        if ms[0].start() > 0:
            intro = note[:ms[0].start()].strip().rstrip('.')
            if intro: segs.append((None, intro))
        for i, mm in enumerate(ms):
            lab = mm.group(1).rstrip(':').strip()
            s = mm.end(); e = ms[i+1].start() if i+1 < len(ms) else len(note)
            segs.append((lab, note[s:e].strip()))
    else:
        segs.append((None, note))
    CALL = {'STATE','OPEN THREAD','WHERE IT STANDS','NEXT'}
    callout = [t for l,t in segs if l and l.upper() in CALL]
    intro = [t for l,t in segs if l is None]
    spec = [(l,t) for l,t in segs if l and l.upper() not in CALL]
    h = '<section><h2 class="display text-2xl text-zinc-900 mb-3">The relationship</h2>'
    if callout:
        h += (f'<div class="rounded-2xl bg-amber-50 ring-1 ring-amber-200 p-5 mb-4">'
              f'<div class="text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-700 mb-1">&#9679; Where it stands</div>'
              f'<p class="text-[14px] leading-relaxed text-amber-900/90">{esc(" ".join(callout))}</p></div>')
    body = ''
    for t in intro:
        body += f'<p class="px-5 py-4 text-[15px] leading-relaxed text-zinc-700">{esc(t)}.</p>'
    for l, t in spec:
        disp = l.title() if l.isupper() else l
        body += (f'<div class="grid sm:grid-cols-4 gap-x-4 gap-y-1 px-5 py-4">'
                 f'<div class="text-[11px] uppercase tracking-[0.1em] text-zinc-400 sm:col-span-1 pt-0.5">{esc(disp)}</div>'
                 f'<div class="sm:col-span-3 text-[14px] leading-relaxed text-zinc-700">{esc(t)}</div></div>')
    if body:
        h += f'<div class="bg-white rounded-2xl ring-1 ring-zinc-200 divide-y divide-zinc-100">{body}</div>'
    if source:
        h += f'<p class="text-[11px] text-zinc-400 mt-2 flex items-center gap-1"><span class="text-zinc-300">&#9636;</span> {esc(source)}</p>'
    return h + '</section>'

def page(cur, c):
    cid = c['id']; name = c['name']
    rs = cur.execute("SELECT * FROM relationship_scores WHERE contact_id=? ORDER BY score_date DESC LIMIT 1", (cid,)).fetchone()
    h = cur.execute("SELECT * FROM v_contact_health WHERE id=?", (cid,)).fetchone()
    metrics = cur.execute("""SELECT cm.*, t.title, t.occurred_at FROM conversation_metrics cm JOIN transcripts t ON t.id=cm.transcript_id
                             WHERE cm.contact_id=? ORDER BY t.occurred_at DESC""", (cid,)).fetchall()
    insights = cur.execute("SELECT * FROM communication_insights WHERE contact_id=? ORDER BY created_at", (cid,)).fetchall()
    inter = cur.execute("SELECT * FROM contact_interactions WHERE contact_id=? ORDER BY occurred_at DESC", (cid,)).fetchall()
    emails = cur.execute("SELECT subject,direction,received_at FROM emails WHERE contact_id=? ORDER BY received_at DESC LIMIT 12", (cid,)).fetchall()
    comms = cur.execute("SELECT * FROM commitments WHERE owner_contact_id=? ORDER BY status, deadline_date", (cid,)).fetchall()

    depth = (rs['relationship_depth'] if rs else None) or (h['relationship_depth'] if h else None)
    traj = (rs['trajectory'] if rs else None) or (h['trajectory'] if h else None)
    dsil = h['days_silent'] if h else None
    badges = []
    if depth: badges.append(chip(depth.title(), DEPTH_COLOR.get(depth.lower(), 'zinc')))
    if traj: badges.append(chip('Trajectory: ' + traj, 'sky'))
    if dsil is not None: badges.append(chip(f'Last contact {dsil}d ago', 'amber' if dsil > 21 else 'zinc'))

    def stat(label, val, sub=''):
        v = val if (val not in (None, '')) else '&mdash;'
        subhtml = f'<div class="text-[11px] text-zinc-400">{sub}</div>' if sub else ''
        return (f'<div class="py-3 border-b border-zinc-100 last:border-0">'
                f'<div class="text-[11px] uppercase tracking-wide text-zinc-400">{label}</div>'
                f'<div class="text-[15px] text-zinc-800 mt-0.5">{v}</div>{subhtml}</div>')
    talk_avg = round(rs['talk_ratio_avg']*100) if rs and rs['talk_ratio_avg'] is not None else None
    ft = 'Not enough data' if (not rs or rs['commitment_follow_through'] is None) else f"{round(rs['commitment_follow_through']*100)}%"
    yours = h['your_open_commitments'] if h else None
    theirs = h['their_open_commitments'] if h else None
    stats = stat('Relationship depth', depth.title() if depth else None)
    stats += stat('Trajectory', traj)
    stats += stat('Meetings on file', h['transcripts_total'] if h else None)
    stats += stat('Avg talk share', f'You {talk_avg}%' if talk_avg is not None else None, 'across recorded calls')
    stats += stat('Follow-through', ft, 'tracked once commitments resolve')
    stats += stat('Open commitments', f'{yours} yours · {theirs} theirs' if (yours is not None) else None)
    stats += stat('Next meeting', h['next_meeting'] if h else None)

    if metrics:
        cards = ''
        for m in metrics:
            cards += (f'<div class="rounded-xl ring-1 ring-zinc-200 p-4 bg-white">'
                      f'<div class="flex items-center justify-between"><div class="text-[13px] font-medium text-zinc-800">{esc(m["title"])}</div>'
                      f'<div class="text-[11px] text-zinc-400">{esc(str(m["occurred_at"])[:10])}</div></div>{talkbar(m["talk_ratio"])}'
                      f'<div class="grid grid-cols-4 gap-2 mt-3 text-center">'
                      f'<div><div class="text-[15px] text-zinc-800">{m["word_count"]}</div><div class="text-[10px] uppercase text-zinc-400">words</div></div>'
                      f'<div><div class="text-[15px] text-zinc-800">{m["question_count"]}</div><div class="text-[10px] uppercase text-zinc-400">questions</div></div>'
                      f'<div><div class="text-[15px] text-zinc-800">{m["interruption_count"]}</div><div class="text-[10px] uppercase text-zinc-400">interrupts</div></div>'
                      f'<div><div class="text-[15px] text-zinc-800">~{m["longest_monologue_seconds"]}s</div><div class="text-[10px] uppercase text-zinc-400">longest mono</div></div>'
                      f'</div></div>')
        analysis = f'<div class="grid sm:grid-cols-2 gap-3">{cards}</div>'
    else:
        analysis = '<p class="text-[13px] text-zinc-400 italic">No recorded calls analyzed yet — metrics populate from transcripts.</p>'

    coach = ''
    for i in insights:
        if i['insight_type'] == 'coach_note':
            attn = i['sentiment'] == 'needs_attention'
            ring = 'ring-amber-200 bg-amber-50/50' if attn else 'ring-sky-200 bg-sky-50/40'
            coach += (f'<div class="rounded-xl p-4 ring-1 {ring}">'
                      f'<div class="flex items-center gap-2 mb-1">{chip("Coaching", "amber" if attn else "sky")}'
                      f'<span class="text-[11px] text-zinc-400">{esc(i["sentiment"])}</span></div>'
                      f'<p class="text-[13px] leading-relaxed text-zinc-700">{esc(i["content"])}</p></div>')
    coach_block = f'<div class="space-y-3 mt-4">{coach}</div>' if coach else ''

    tl = []
    for it in inter:
        tl.append((str(it['occurred_at'])[:10], 'Meeting', esc(it['subject']), esc(it['summary'] or '')))
    for e in emails:
        tl.append((str(e['received_at'])[:10], 'Email · ' + esc(e['direction'] or ''), esc(e['subject']), ''))
    tl.sort(key=lambda x: x[0], reverse=True)
    if tl:
        items = ''
        for d, typ, subj, summ in tl:
            sm = f'<div class="text-[12px] text-zinc-500 mt-0.5">{summ}</div>' if summ else ''
            items += (f'<li class="relative pl-6 pb-5 last:pb-0">'
                      f'<span class="absolute left-0 top-1.5 w-2.5 h-2.5 rounded-full bg-indigo-300 ring-4 ring-indigo-50"></span>'
                      f'<div class="text-[11px] text-zinc-400">{d} · {typ}</div>'
                      f'<div class="text-[14px] text-zinc-800">{subj}</div>{sm}</li>')
        timeline = f'<ul class="relative border-l border-zinc-200 ml-1 mt-2">{items}</ul>'
    else:
        timeline = '<p class="text-[13px] text-zinc-400 italic">No touchpoints logged yet.</p>'

    if comms:
        rows = ''
        for cm in comms:
            done = cm['status'] == 'completed'
            due = f' · due {esc(cm["deadline_date"])}' if cm['deadline_date'] else ''
            rows += (f'<li class="flex items-start gap-3 py-2 border-b border-zinc-100 last:border-0">'
                     f'<span class="mt-1 text-{("emerald" if done else "amber")}-500">{"&#10003;" if done else "&#9675;"}</span>'
                     f'<div><div class="text-[13px] text-zinc-700">{esc(cm["description"])}</div>'
                     f'<div class="text-[11px] text-zinc-400">{esc(cm["status"])}{due}</div></div></li>')
        commit = f'<ul>{rows}</ul>'
    else:
        commit = '<p class="text-[13px] text-zinc-400 italic">No commitments owned by this contact.</p>'

    rel_html = build_rel(c['notes'])
    contact_chips = ' · '.join([x for x in [esc(c['email']), esc(c['phone'])] if x]) or '&mdash;'
    meta = ' · '.join([x for x in [esc(c['role']), esc(c['company'])] if x]) or '&mdash;'

    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(name)} — Software of You</title><script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Instrument+Serif&display=swap" rel="stylesheet">
<style>body{{font-family:'Inter',sans-serif;background:#faf9f7}}.display{{font-family:'Instrument Serif',serif}}</style></head>
<body class="text-zinc-800"><div class="max-w-5xl mx-auto px-6 py-10">
  <a href="../contact-cards.html" class="text-[12px] text-zinc-400 hover:text-zinc-700">&larr; Your People</a>
  <header class="mt-3 mb-8 flex items-start justify-between gap-4 flex-wrap">
    <div><h1 class="display text-5xl text-zinc-900 leading-none">{esc(name)}</h1>
      <p class="text-[14px] text-zinc-500 mt-2">{meta}</p>
      <p class="text-[12px] text-zinc-400 mt-1">{contact_chips}</p></div>
    <div class="flex flex-wrap gap-2 justify-end max-w-sm">{''.join(badges)}</div>
  </header>
  <div class="grid lg:grid-cols-3 gap-6">
    <aside class="lg:col-span-1 space-y-6">
      <div class="bg-white rounded-2xl ring-1 ring-zinc-200 p-5">
        <h2 class="text-[12px] font-semibold tracking-wide text-zinc-500 uppercase mb-1">How we're valuing them</h2>{stats}</div>
    </aside>
    <main class="lg:col-span-2 space-y-8">
      {rel_html}
      <section><h2 class="display text-2xl text-zinc-900 mb-1">How we're reading our conversations</h2>
        <p class="text-[12px] text-zinc-400 mb-3">Talk share, questions and monologue length per recorded call — with coaching where a pattern needs attention.</p>
        {analysis}{coach_block}</section>
      <section><h2 class="display text-2xl text-zinc-900 mb-2">Touchpoints</h2>{timeline}</section>
      <section><h2 class="display text-2xl text-zinc-900 mb-2">Commitments</h2>
        <div class="bg-white rounded-2xl ring-1 ring-zinc-200 p-5">{commit}</div></section>
    </main>
  </div>
  <footer class="mt-12 pt-5 border-t border-zinc-200 text-[11px] text-zinc-400">Software of You · every field grounded in your transcripts, emails and calendar — gaps shown as &mdash;, never invented.</footer>
</div></body></html>'''

def idx_card(cur, c):
    h = cur.execute("SELECT relationship_depth,days_silent FROM v_contact_health WHERE id=?", (c['id'],)).fetchone()
    d = h['relationship_depth'] if h else None
    badge = chip(d.title(), DEPTH_COLOR.get(d.lower(), 'zinc')) if d else ''
    dsil = f"{h['days_silent']}d ago" if h and h['days_silent'] is not None else 'no contact yet'
    meta = ' · '.join([x for x in [esc(c['role']), esc(c['company'])] if x]) or '&mdash;'
    return (f'<a href="people/{slug(c["name"])}.html" class="block bg-white rounded-2xl ring-1 ring-zinc-200 hover:ring-indigo-300 hover:shadow-md transition p-5">'
            f'<div class="flex items-start justify-between gap-2"><h3 class="display text-2xl text-zinc-900 leading-tight">{esc(c["name"])}</h3>{badge}</div>'
            f'<p class="text-[12px] text-zinc-500 mt-1">{meta}</p>'
            f'<p class="text-[11px] text-zinc-400 mt-3">Last contact: {dsil}</p></a>')

def main():
    if not os.path.exists(DB):
        sys.stderr.write(f"build_contact_pages: DB not found at {DB}\n"); return 1
    os.makedirs(PEOPLE, exist_ok=True)
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row; cur = con.cursor()
    contacts = cur.execute("SELECT * FROM contacts ORDER BY id").fetchall()
    for c in contacts:
        with open(os.path.join(PEOPLE, slug(c['name']) + ".html"), "w") as f:
            f.write(page(cur, c))
    net = [c for c in contacts if (c['company'] or '') != "Benji's Interior Plants"]
    team = [c for c in contacts if (c['company'] or '') == "Benji's Interior Plants"]
    index = f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Your People — Software of You</title><script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Instrument+Serif&display=swap" rel="stylesheet">
<style>body{{font-family:'Inter',sans-serif;background:#faf9f7}}.display{{font-family:'Instrument Serif',serif}}</style></head>
<body class="text-zinc-800"><div class="max-w-6xl mx-auto px-6 py-12">
<p class="text-[12px] font-medium tracking-[0.18em] text-zinc-400 uppercase">Software of You · Contact Intelligence</p>
<h1 class="display text-5xl text-zinc-900 mt-2">Your People</h1>
<p class="text-zinc-500 mt-3 max-w-2xl">{len(contacts)} contacts. Click anyone to open their full page — the relationship, how we're valuing it, how your conversations read, every touchpoint and commitment.</p>
<h2 class="text-[13px] font-semibold tracking-[0.14em] text-zinc-500 uppercase mt-10 mb-4">Your Network · {len(net)}</h2>
<div class="grid md:grid-cols-3 gap-4">{''.join(idx_card(cur, c) for c in net)}</div>
<h2 class="text-[13px] font-semibold tracking-[0.14em] text-zinc-500 uppercase mt-10 mb-4">Benji's Interior Plants · client team · {len(team)}</h2>
<div class="grid md:grid-cols-4 gap-4">{''.join(idx_card(cur, c) for c in team)}</div>
</div></body></html>'''
    with open(os.path.join(OUT, "contact-cards.html"), "w") as f:
        f.write(index)
    con.close()
    print(f"build_contact_pages: wrote {len(contacts)} pages + index to {OUT}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
