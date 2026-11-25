#!/usr/bin/env python3
"""Update deal counts in the README's Table of Contents and the stats line,
tag outbound deal links with UTM params, and mark each deal's status in its
date cell (🟢 live, ⏳ not started yet, struck through once ended).

Run from the repo root: python3 scripts/update_stats.py
Also runs in .github/workflows/update-stats.yml on every push to main and
once a day, so statuses change even when nothing is merged.
"""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utm import add_utm

README = Path(__file__).resolve().parent.parent / "README.md"
STATS_RE = re.compile(r"<!-- stats:start -->.*?<!-- stats:end -->", re.S)
TOC_RE = re.compile(r"^(\* \S+ \[([^\]]+)\]\([^)]+\))(?: \(\d+\))?(.*)$")
DEAL_ROW_RE = re.compile(r"^\|\s*\[")
LINK_RE = re.compile(r"\]\((https?://[^)\s]+)\)")
DATE = r"[A-Z][a-z]{2} \d{1,2}, \d{4}"
# The date cell, with or without a status we added on an earlier run
DATES_RE = re.compile(rf"\| *(?:🟢|⏳)? *(?:~~)?({DATE}) - ({DATE})(?:~~)? *\|\s*$")
LIVE, SOON = "🟢", "⏳"


def count_deals(lines):
    counts, section = {}, None
    for line in lines:
        if line.startswith("## "):
            # "## 🧑‍💻 Developer Tools" -> "Developer Tools"
            section = line[3:].split(" ", 1)[-1].strip()
            counts[section] = 0
        elif line.startswith("# "):
            section = None
        elif section and DEAL_ROW_RE.match(line):
            counts[section] += 1
    return counts


def tag_links(lines):
    """Add our UTM params to deal-row and "Other places" links."""
    in_deals = in_places = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            in_deals = True  # the deal tables; skips the example row in "Add Your Deal"
        elif line.startswith("# "):
            in_deals, in_places = False, line.startswith("# 🔖 Other places")
        if (in_deals and DEAL_ROW_RE.match(line)) or (in_places and line.startswith("[")):
            lines[i] = LINK_RE.sub(lambda m: "](" + add_utm(m.group(1), "github") + ")", line)


def deal_status(start, end, now):
    """A deal starts with the UTC day and only ends once its last day is over
    everywhere on Earth (UTC-12), so nothing live is ever shown as ended."""
    if now.date() < start:
        return "soon"
    if (now - timedelta(hours=12)).date() > end:
        return "ended"
    return "live"


def mark_status(lines, now):
    """Prefix each deal's dates with its status; makers never type it."""
    in_deals = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            in_deals = True
        elif line.startswith("# "):
            in_deals = False
        m = DATES_RE.search(line) if in_deals and DEAL_ROW_RE.match(line) else None
        if not m:
            continue
        try:
            start, end = (datetime.strptime(d, "%b %d, %Y").date() for d in m.groups())
        except ValueError:
            continue
        dates = f"{m.group(1)} - {m.group(2)}"
        cell = {"live": f"{LIVE} {dates}", "soon": f"{SOON} {dates}", "ended": f"~~{dates}~~"}[
            deal_status(start, end, now)
        ]
        lines[i] = f"{line[:m.start()]}| {cell} |"


def main():
    lines = README.read_text().split("\n")
    now = datetime.now(timezone.utc)
    tag_links(lines)
    mark_status(lines, now)
    counts = count_deals(lines)

    in_toc = False
    for i, line in enumerate(lines):
        if line.startswith("# "):
            in_toc = line.strip() == "# Table of Contents"
            continue
        m = TOC_RE.match(line) if in_toc else None
        if m and m.group(2) in counts:
            n = counts[m.group(2)]
            lines[i] = m.group(1) + (f" ({n})" if n else "") + m.group(3)

    total = sum(counts.values())
    updated = f"{now:%b} {now.day}, {now.year}"
    # Stay blank until the first deal is added
    stats = f"🔥 <b>{total} deals listed</b> · Updated {updated}" if total else ""

    text = STATS_RE.sub(
        f"<!-- stats:start -->{stats}<!-- stats:end -->", "\n".join(lines)
    )
    README.write_text(text)
    print(f"{total} deals: " + ", ".join(f"{k} {v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
