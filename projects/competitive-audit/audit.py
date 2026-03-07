#!/usr/bin/env python3
"""Competitive Audit — Search & Scrape Pipeline.

Gathers raw data for a competitive audit. Claude does the analysis.

Usage:
    audit.py "Canadian QSR" --brands "Tim Hortons,McDonald's,Wendy's,A&W,Popeyes"
    audit.py "Canadian telecom" --brands "Bell,Rogers,Telus,Beanfield"
"""
import sys
import os
import json
import argparse
import subprocess
from pathlib import Path

WEB_TOOLS = Path.home() / "tools" / "web-tools"
VENV_PYTHON = WEB_TOOLS / ".venv" / "bin" / "python"
OUTPUT_DIR = Path(__file__).parent / "runs"


def _extract_json(text):
    """Extract JSON object from mixed output (botasaurus prints status lines before JSON)."""
    # Find the first '{' and parse from there
    idx = text.find("{")
    if idx == -1:
        return None
    try:
        return json.loads(text[idx:])
    except json.JSONDecodeError:
        # Try to find the last complete JSON object
        for i in range(len(text) - 1, -1, -1):
            if text[i] == "}":
                try:
                    return json.loads(text[idx:i + 1])
                except json.JSONDecodeError:
                    continue
    return None


def run_search(query, limit=10):
    """Run web-search and return results."""
    result = subprocess.run(
        [str(VENV_PYTHON), str(WEB_TOOLS / "search.py"), query, "--limit", str(limit)],
        capture_output=True, text=True, timeout=90
    )
    if result.returncode != 0:
        return {"error": result.stderr[:200], "results": []}
    parsed = _extract_json(result.stdout)
    if parsed:
        return parsed
    return {"error": "Failed to parse search output", "results": []}


def run_scrape(url):
    """Run web-scrape and return content."""
    result = subprocess.run(
        [str(VENV_PYTHON), str(WEB_TOOLS / "scrape.py"), url, "--format", "json"],
        capture_output=True, text=True, timeout=90
    )
    if result.returncode != 0:
        return {"error": result.stderr[:200], "content": ""}
    parsed = _extract_json(result.stdout)
    if parsed:
        return parsed
    return {"error": "Failed to parse scrape output", "content": ""}


def gather_brand_data(brand, category):
    """Gather search results and key page content for a brand."""
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  Gathering: {brand}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    data = {"brand": brand, "searches": {}, "pages": []}

    # Search 1: Brand positioning / strategy
    print(f"  Searching: {brand} brand positioning strategy...", file=sys.stderr)
    data["searches"]["positioning"] = run_search(
        f"{brand} brand positioning strategy marketing {category} 2025 2026", limit=5
    )

    # Search 2: Recent campaigns / creative work
    print(f"  Searching: {brand} recent campaigns...", file=sys.stderr)
    data["searches"]["campaigns"] = run_search(
        f"{brand} advertising campaign Canada 2025 2026", limit=5
    )

    # Search 3: News / market moves
    print(f"  Searching: {brand} market news...", file=sys.stderr)
    data["searches"]["news"] = run_search(
        f"{brand} {category} Canada news expansion 2025 2026", limit=5
    )

    # Scrape the top 2-3 most relevant URLs
    all_results = []
    for search_type, search_data in data["searches"].items():
        for r in search_data.get("results", []):
            # Skip social media, PDFs, and duplicate domains
            url = r.get("url", "")
            if any(skip in url for skip in ["instagram.com", "facebook.com", "linkedin.com", "twitter.com", "youtube.com", ".pdf"]):
                continue
            all_results.append(r)

    # Scrape top 3 unique URLs
    scraped_urls = set()
    for r in all_results[:5]:
        url = r["url"]
        if url in scraped_urls:
            continue
        if len(scraped_urls) >= 3:
            break
        print(f"  Scraping: {url[:70]}...", file=sys.stderr)
        page = run_scrape(url)
        page["source_title"] = r.get("title", "")
        data["pages"].append(page)
        scraped_urls.add(url)

    return data


def main():
    parser = argparse.ArgumentParser(description="Competitive Audit Data Gatherer")
    parser.add_argument("category", help="Market category (e.g. 'Canadian QSR')")
    parser.add_argument("--brands", required=True, help="Comma-separated brand names")
    parser.add_argument("--run-name", help="Name for this run (default: auto-generated)")
    args = parser.parse_args()

    brands = [b.strip() for b in args.brands.split(",")]
    run_name = args.run_name or args.category.lower().replace(" ", "-")

    # Create output directory
    run_dir = OUTPUT_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nCompetitive Audit: {args.category}", file=sys.stderr)
    print(f"Brands: {', '.join(brands)}", file=sys.stderr)
    print(f"Output: {run_dir}\n", file=sys.stderr)

    all_data = {
        "category": args.category,
        "brands": brands,
        "brand_data": [],
    }

    for brand in brands:
        brand_data = gather_brand_data(brand, args.category)
        all_data["brand_data"].append(brand_data)

        # Save per-brand file as we go (in case of interruption)
        brand_file = run_dir / f"{brand.lower().replace(' ', '-').replace('&', 'and')}.json"
        with open(brand_file, "w") as f:
            json.dump(brand_data, f, indent=2)

    # Save combined output
    combined_file = run_dir / "audit-raw.json"
    with open(combined_file, "w") as f:
        json.dump(all_data, f, indent=2)

    print(f"\nData gathered. Raw data saved to: {combined_file}", file=sys.stderr)
    print(f"Per-brand files in: {run_dir}", file=sys.stderr)

    # Also output to stdout for piping
    json.dump(all_data, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
