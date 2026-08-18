#!/usr/bin/env python3
"""corpus-quality.py — Classify raw sources/publications_npc.json into a
"solid" (citation-grounding-worthy) subset vs. a "thin" remainder.

The raw corpus (2,460 records, PubMed + Web of Science + Google Scholar,
merged with light deduplication via `overlap_category`) is immutable per
wiki/NPC.wiki/SCHEMA_NPC.md's Source of Truth rule — this script never
writes back into raw sources/. It only classifies and reports, so wiki
pages can cite from a documented, reproducible subset instead of the raw
2,460 records including near-empty stubs.

A record is "solid" when all three hold:
  - abstract is present and >= 200 chars (enough to ground a real claim)
  - journal_source is non-empty (citable venue)
  - has a citation/recency signal: times_cited >= 1, OR published 2022+
    (young papers legitimately haven't accumulated citations yet)

This is a pragmatic bar for "safe to cite in a wiki claim," not a claim
that excluded records are false, low-quality science, or unimportant —
a 1985 case report with 0 recorded citations may still be a completely
valid clinical description; it just isn't citable on its own steam by
this heuristic without a human double-checking it first.

Usage:
    python3 scripts/corpus-quality.py
    python3 scripts/corpus-quality.py --stats
    python3 scripts/corpus-quality.py --output scripts/kg/build/publications_npc.solid.json
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "raw sources" / "publications_npc.json"
DEFAULT_OUTPUT = REPO_ROOT / "scripts" / "kg" / "build" / "publications_npc.solid.json"

MIN_ABSTRACT_CHARS = 200
MIN_CITES_IF_OLD = 1
RECENT_YEAR_CUTOFF = 2022


def is_solid(record):
    has_abstract = len((record.get("abstract") or "").strip()) >= MIN_ABSTRACT_CHARS
    has_journal = bool((record.get("journal_source") or "").strip())
    cites = record.get("times_cited")
    year = record.get("publication_year") or 0
    has_signal = (cites is not None and cites >= MIN_CITES_IF_OLD) or year >= RECENT_YEAR_CUTOFF
    return has_abstract and has_journal and has_signal


def why_thin(record):
    reasons = []
    if len((record.get("abstract") or "").strip()) < MIN_ABSTRACT_CHARS:
        reasons.append("short_or_missing_abstract")
    if not (record.get("journal_source") or "").strip():
        reasons.append("no_journal")
    cites = record.get("times_cited")
    year = record.get("publication_year") or 0
    if not ((cites is not None and cites >= MIN_CITES_IF_OLD) or year >= RECENT_YEAR_CUTOFF):
        reasons.append("no_citation_or_recency_signal")
    return reasons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=None,
                         help="Write the solid subset (title/year/journal/doi/times_cited) as JSON here.")
    parser.add_argument("--stats", action="store_true", help="Print a breakdown to stderr.")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    solid = [d for d in data if is_solid(d)]
    thin = [d for d in data if not is_solid(d)]

    print(f"Total records:  {len(data)}", file=sys.stderr)
    print(f"Solid records:  {len(solid)} ({len(solid) / len(data) * 100:.1f}%)", file=sys.stderr)
    print(f"Thin records:   {len(thin)}", file=sys.stderr)

    if args.stats:
        reasons = Counter()
        for d in thin:
            for r in why_thin(d):
                reasons[r] += 1
        print("\nThin-record reasons (a record can have more than one):", file=sys.stderr)
        for reason, count in reasons.most_common():
            print(f"  {reason}: {count}", file=sys.stderr)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        slim = [
            {
                "title": d.get("title"),
                "publication_year": d.get("publication_year"),
                "journal_source": d.get("journal_source"),
                "doi": d.get("doi"),
                "times_cited": d.get("times_cited"),
            }
            for d in solid
        ]
        args.output.write_text(json.dumps(slim, indent=2))
        print(f"\nWrote {len(slim)} solid records to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
