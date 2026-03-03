#!/usr/bin/env python3
"""Export a generated SoY page as a client-safe HTML file.

Strips internal elements (sidebar, dark mode, AI analysis cards,
internal links, interactive buttons) and produces a clean, self-contained
HTML file suitable for sharing with clients.

Usage:
    python3 shared/export_page.py <input_file> [--output <path>] [--title "Custom Title"]
"""

import argparse
import json
import os
import re
import sys
from datetime import date


def strip_sidebar(html: str) -> str:
    """Remove sidebar HTML, mobile toggle, and backdrop."""
    # Remove <aside id="sidebar"> ... </aside> blocks
    html = re.sub(
        r'<aside\s+id=["\']sidebar["\'][^>]*>.*?</aside>',
        '', html, flags=re.DOTALL
    )
    # Remove sidebar mobile toggle button
    html = re.sub(
        r'<button\s+[^>]*sidebar-mobile-toggle[^>]*>.*?</button>',
        '', html, flags=re.DOTALL
    )
    # Remove sidebar backdrop div
    html = re.sub(
        r'<div\s+[^>]*sidebar-backdrop[^>]*>.*?</div>',
        '', html, flags=re.DOTALL
    )
    # Remove PM report fixed aside nav (section nav)
    html = re.sub(
        r'<aside\s+class="fixed[^"]*"[^>]*>.*?</aside>',
        '', html, flags=re.DOTALL
    )
    return html


def strip_sidebar_css(html: str) -> str:
    """Remove sidebar CSS rules from <style> blocks."""
    # Remove the sidebar CSS block (/* ── SIDEBAR ── */ ... to next major section or closing)
    html = re.sub(
        r'/\*\s*──\s*SIDEBAR\s*──[^*]*\*/.*?(?=/\*\s*──|\s*</style>)',
        '', html, flags=re.DOTALL
    )
    # Remove .sidebar { ... } and related rules
    selectors = [
        r'\.sidebar\s*\{[^}]*\}',
        r'\.sidebar[\.\s][^{]*\{[^}]*\}',
        r'\.sidebar-[a-z-]*\s*\{[^}]*\}',
        r'\.section-subnav[^{]*\{[^}]*\}',
    ]
    for sel in selectors:
        html = re.sub(sel, '', html, flags=re.DOTALL)
    # Remove @media rules containing .sidebar
    html = re.sub(
        r'@media\s*\([^)]*\)\s*\{\s*\.sidebar[^}]*\{[^}]*\}\s*\}',
        '', html, flags=re.DOTALL
    )
    return html


def strip_dark_mode(html: str) -> str:
    """Remove dark mode init script, CSS, toggle button, and JS."""
    # Remove dark mode init script in <head>
    html = re.sub(
        r'<script>\s*\(function\(\)\s*\{var\s+s=localStorage\.getItem\([\'"]soy-dark-mode[\'"]\).*?\}\)\(\);?\s*</script>',
        '', html, flags=re.DOTALL
    )
    # Also handle the {{ escaped version from server
    html = re.sub(
        r'<script>\s*\(function\(\)\s*\{\{var\s+s=localStorage\.getItem\([\'"]soy-dark-mode[\'"]\).*?\}\}\)\(\);?\s*</script>',
        '', html, flags=re.DOTALL
    )
    # Remove /* DARK MODE OVERRIDES */ block
    html = re.sub(
        r'/\*\s*DARK\s+MODE\s+OVERRIDES?\s*\*/.*?(?=/\*|</style>)',
        '', html, flags=re.DOTALL
    )
    # Remove html.dark rules
    html = re.sub(r'html\.dark\s+[^{]*\{[^}]*\}', '', html)
    # Remove .dark-toggle CSS
    html = re.sub(r'\.dark-toggle[^{]*\{[^}]*\}', '', html)
    # Remove dark mode toggle button
    html = re.sub(
        r'<button\s+[^>]*dark-toggle[^>]*>.*?</button>',
        '', html, flags=re.DOTALL
    )
    # Remove toggleDarkMode JS function
    html = re.sub(
        r'function\s+toggleDarkMode\s*\(\)\s*\{.*?\}\s*\n',
        '', html, flags=re.DOTALL
    )
    # Remove dark class from html element
    html = re.sub(r'(<html[^>]*)\s+class="dark"', r'\1', html)
    return html


def strip_ai_analysis_cards(html: str) -> str:
    """Remove AI Analysis cards using balanced-div counting.

    Anchors on the <!-- AI Analysis Card --> comment, then counts nested
    div open/close tags to remove exactly the card container.  Falls back to
    matching any card that contains the /project-analysis clipboard text.
    """
    # Strategy 1: find the comment marker, then remove the next balanced <div>
    comment_pat = re.compile(r'<!--\s*AI Analysis Card\s*-->\s*')
    m = comment_pat.search(html)
    if m:
        # Find the opening <div after the comment
        div_open = re.compile(r'<div\b[^>]*>', re.DOTALL)
        dm = div_open.search(html, m.end())
        if dm:
            depth = 1
            pos = dm.end()
            while pos < len(html) and depth > 0:
                next_open = re.search(r'<div\b', html[pos:])
                next_close = re.search(r'</div>', html[pos:])
                if next_close is None:
                    break
                if next_open and next_open.start() < next_close.start():
                    depth += 1
                    pos += next_open.start() + 4
                else:
                    depth -= 1
                    pos += next_close.end()
            # Remove from comment start through balanced close + trailing whitespace
            end = pos
            while end < len(html) and html[end] in ' \t\n\r':
                end += 1
            html = html[:m.start()] + html[end:]
            return html

    # Strategy 2 (fallback): find the card by its clipboard content and use
    # balanced-div counting from that card's opening tag.
    clip_pat = re.compile(r'navigator\.clipboard\.writeText\([\'\"]/project-analysis')
    cm = clip_pat.search(html)
    if cm:
        # Walk backward to find the enclosing bg-white rounded-xl div
        search_region = html[:cm.start()]
        card_start = None
        for card_m in re.finditer(r'<div\s+class="bg-white\s+rounded-xl[^"]*"[^>]*>', search_region):
            card_start = card_m.start()  # keep the last one before the clipboard text
        if card_start is not None:
            dm = re.search(r'<div\b[^>]*>', html[card_start:])
            if dm:
                depth = 1
                pos = card_start + dm.end()
                while pos < len(html) and depth > 0:
                    next_open = re.search(r'<div\b', html[pos:])
                    next_close = re.search(r'</div>', html[pos:])
                    if next_close is None:
                        break
                    if next_open and next_open.start() < next_close.start():
                        depth += 1
                        pos += next_open.start() + 4
                    else:
                        depth -= 1
                        pos += next_close.end()
                end = pos
                while end < len(html) and html[end] in ' \t\n\r':
                    end += 1
                html = html[:card_start] + html[end:]

    return html


def _remove_js_function(html: str, name: str) -> str:
    """Remove a JS function definition by matching balanced braces."""
    # Find the function start
    pattern = re.compile(
        r'(?:async\s+)?function\s+' + re.escape(name) + r'\s*\([^)]*\)\s*\{',
        re.DOTALL
    )
    match = pattern.search(html)
    if not match:
        return html
    start = match.start()
    # Find matching closing brace by counting
    brace_count = 1
    pos = match.end()
    while pos < len(html) and brace_count > 0:
        if html[pos] == '{':
            brace_count += 1
        elif html[pos] == '}':
            brace_count -= 1
        pos += 1
    # Remove function + trailing whitespace
    end = pos
    while end < len(html) and html[end] in ' \t\n\r':
        end += 1
    return html[:start] + html[end:]


def strip_owner_comments(html: str) -> str:
    """Remove injected owner comment thread (CSS, HTML, and JS blocks)."""
    html = re.sub(
        r'<!-- SOY-OWNER-COMMENTS-CSS -->.*?<!-- /SOY-OWNER-COMMENTS-CSS -->',
        '', html, flags=re.DOTALL
    )
    html = re.sub(
        r'<!-- SOY-OWNER-COMMENTS -->.*?<!-- /SOY-OWNER-COMMENTS -->',
        '', html, flags=re.DOTALL
    )
    html = re.sub(
        r'<!-- SOY-OWNER-COMMENTS-JS -->.*?<!-- /SOY-OWNER-COMMENTS-JS -->',
        '', html, flags=re.DOTALL
    )
    return html


def strip_interactive_buttons(html: str) -> str:
    """Remove Convert to Task / Dismiss buttons and their JS."""
    # Remove JS functions (handles nested braces properly)
    for fn_name in ('convertToTask', 'dismissItem', 'showToast'):
        html = _remove_js_function(html, fn_name)
    # Remove API_BASE const
    html = re.sub(r'const\s+API_BASE\s*=\s*[^;]+;\s*\n?', '', html)
    # Remove Convert to Task buttons
    html = re.sub(
        r'<button\s+onclick="convertToTask\([^"]*\)"[^>]*>.*?</button>',
        '', html, flags=re.DOTALL
    )
    # Remove Dismiss buttons
    html = re.sub(
        r'<button\s+onclick="dismissItem\([^"]*\)"[^>]*>.*?</button>',
        '', html, flags=re.DOTALL
    )
    return html


def strip_internal_links(html: str) -> str:
    """Convert internal SoY links to plain text spans."""
    # Remove "Back to Hub" links
    html = re.sub(
        r'<a\s+[^>]*href=["\']/["\'][^>]*>.*?</a>',
        '', html, flags=re.DOTALL
    )
    # Convert /pages/... links to plain spans
    html = re.sub(
        r'<a\s+[^>]*href=["\']\/pages\/[^"\']*["\'][^>]*>(.*?)</a>',
        r'<span>\1</span>', html, flags=re.DOTALL
    )
    return html


def fix_main_layout(html: str) -> str:
    """Remove lg:ml-60 from main tag (no sidebar offset needed)."""
    html = re.sub(
        r'(<main\s+class="[^"]*?)lg:ml-60\s*',
        r'\1', html
    )
    # Also handle lg:ml-56 variant (PM reports)
    html = re.sub(
        r'(<main\s+class="[^"]*?)lg:ml-56\s*',
        r'\1', html
    )
    return html


def update_title(html: str, title: str) -> str:
    """Replace <title> content."""
    return re.sub(r'<title>[^<]*</title>', f'<title>{title}</title>', html)


def add_meta_noindex(html: str) -> str:
    """Add noindex meta tag if not present."""
    if 'noindex' not in html:
        html = html.replace(
            '<meta charset="UTF-8">',
            '<meta charset="UTF-8">\n    <meta name="robots" content="noindex">',
            1
        )
    return html


def replace_footer(html: str, user_name: str, date_str: str) -> str:
    """Replace the footer with a client-safe attribution."""
    new_footer = (
        f'<footer class="mt-8 pb-8">\n'
        f'  <div class="pt-4 border-t border-zinc-100 text-center">\n'
        f'    <p class="text-xs text-zinc-400">Prepared by {user_name} &middot; {date_str}</p>\n'
        f'  </div>\n'
        f'</footer>'
    )
    # Replace existing footer
    html = re.sub(
        r'<footer[^>]*>.*?</footer>',
        new_footer, html, flags=re.DOTALL
    )
    return html


def clean_empty_style_blocks(html: str) -> str:
    """Clean up empty or near-empty style/script blocks left after stripping."""
    # Remove excessive blank lines
    html = re.sub(r'\n{4,}', '\n\n', html)
    return html


def export_page(input_path: str, output_path: str = None,
                title: str = None, user_name: str = None) -> dict:
    """Main export function. Returns metadata dict."""
    with open(input_path, 'r') as f:
        html = f.read()

    # Derive defaults
    basename = os.path.basename(input_path)
    if output_path is None:
        share_dir = os.path.join(os.path.dirname(os.path.dirname(input_path)), 'output', 'share')
        # Handle case where input is already in output/
        if '/output/' in input_path:
            share_dir = os.path.join(os.path.dirname(input_path), 'share')
        output_path = os.path.join(share_dir, basename)

    # Extract current title for defaults
    title_match = re.search(r'<title>([^<]*)</title>', html)
    current_title = title_match.group(1) if title_match else basename
    if title is None:
        # Clean up: remove " — Project Page" etc. and make client-facing
        title = re.sub(r'\s*[—–-]\s*(Project Page|Entity Page|PM Report|Analysis).*', '', current_title)
        title = f"{title} — Project Brief"

    if user_name is None:
        user_name = "Software of You"

    date_str = date.today().strftime("%B %-d, %Y")

    # Apply all stripping transforms
    html = strip_sidebar(html)
    html = strip_sidebar_css(html)
    html = strip_dark_mode(html)
    html = strip_ai_analysis_cards(html)
    html = strip_interactive_buttons(html)
    html = strip_owner_comments(html)
    html = strip_internal_links(html)
    html = fix_main_layout(html)
    html = update_title(html, title)
    html = add_meta_noindex(html)
    html = replace_footer(html, user_name, date_str)
    html = clean_empty_style_blocks(html)

    # Write output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)

    size_kb = round(os.path.getsize(output_path) / 1024, 1)

    return {
        "input": input_path,
        "output": output_path,
        "title": title,
        "size_kb": size_kb,
    }


def main():
    parser = argparse.ArgumentParser(description='Export a SoY page as client-safe HTML')
    parser.add_argument('input_file', help='Path to the generated HTML file')
    parser.add_argument('--output', '-o', help='Output file path (default: output/share/<filename>)')
    parser.add_argument('--title', '-t', help='Custom page title')
    parser.add_argument('--user-name', '-u', help='Name for the footer attribution')

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(json.dumps({"error": f"File not found: {args.input_file}"}))
        sys.exit(1)

    result = export_page(
        input_path=args.input_file,
        output_path=args.output,
        title=args.title,
        user_name=args.user_name,
    )
    print(json.dumps(result))


if __name__ == '__main__':
    main()
