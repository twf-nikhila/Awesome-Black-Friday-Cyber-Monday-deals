#!/usr/bin/env python3
"""Update deal counts in the README's Table of Contents and the stats line.

Run from the repo root: python3 scripts/update_stats.py
Also runs in .github/workflows/update-stats.yml on every push to main.
"""
import re
from datetime import datetime, timezone
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"
STATS_RE = re.compile(r"<!-- stats:start -->.*?<!-- stats:end -->", re.S)
TOC_RE = re.compile(r"^(\* \S+ \[([^\]]+)\]\([^)]+\))(?: \(\d+\))?(.*)$")
DEAL_ROW_RE = re.compile(r"^\|\s*\[")


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


def main():
    lines = README.read_text().split("\n")
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
    now = datetime.now(timezone.utc)
    updated = f"{now:%b} {now.day}, {now.year}"
    # Stay blank until the first deal is added
    stats = f"🔥 **{total} deals** listed · Updated {updated}" if total else ""

    text = STATS_RE.sub(
        f"<!-- stats:start -->{stats}<!-- stats:end -->", "\n".join(lines)
    )
    README.write_text(text)
    print(f"{total} deals: " + ", ".join(f"{k} {v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
