#!/usr/bin/env python3
"""Build the GitHub Pages site from README.md.

Run from the repo root: python3 scripts/build_site.py [README.md]
Writes _site/ (index.html + assets). Also runs in .github/workflows/pages.yml
on every push to main, so the site always mirrors the README.

Deal text comes from community PRs, so everything is HTML-escaped here and only
a small whitelist of inline formatting and http(s) links is allowed through.
"""
import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/twf-nikhila/Awesome-Black-Friday-Cyber-Monday-deals"
OUT = ROOT / "_site"

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
SAFE_TAGS = ("s", "strong", "b", "em", "i", "code")


def safe_url(url):
    url = url.strip()
    return url if re.match(r"^https?://", url, re.I) else None


def inline_md(text):
    """Escape a table cell, then allow links, **bold**, `code` and a few tags."""
    s = html.escape(text.strip(), quote=True)
    for tag in SAFE_TAGS:
        s = s.replace(f"&lt;{tag}&gt;", f"<{tag}>").replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    s = re.sub(r"&lt;br\s*/?&gt;", "<br>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)

    def link(m):
        url = safe_url(html.unescape(m.group(2)))
        if not url:
            return m.group(1)
        return f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener nofollow">{m.group(1)}</a>'

    return LINK_RE.sub(link, s)


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def is_big(deal):
    if "💸" in deal:
        return True
    return any(int(n) >= 50 for n in re.findall(r"(\d{2,3})\s*%", deal) if int(n) <= 100)


def is_lifetime(deal):
    return "♾" in deal or bool(re.search(r"lifetime|buy once|one[- ]time|pay once", deal, re.I))


def parse_deal_row(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if cells and re.fullmatch(r"\d+", cells[0]):  # pre-2026 tables had a # column
        cells = cells[1:]
    if len(cells) < 3:
        return None
    m = LINK_RE.search(cells[0])
    name = strip_tags(m.group(1) if m else cells[0])
    url = safe_url(m.group(2)) if m else None
    deal = cells[2] if len(cells) > 2 else ""
    return {
        "name": name,
        "url": url,
        "description": inline_md(cells[1]),
        "deal": inline_md(deal),
        "dates": strip_tags(inline_md(cells[3])) if len(cells) > 3 else "",
        "big": is_big(deal),
        "lifetime": is_lifetime(deal),
    }


def parse_sponsors(text):
    m = re.search(r"^# Sponsors\s*$(.*?)</table>", text, re.M | re.S)
    sponsors = []
    for td in re.findall(r"<td[^>]*>(.*?)</td>", m.group(1) if m else "", re.S):
        img = re.search(r'<img[^>]+src="([^"]+)"', td)
        if not img:  # "Your logo here" placeholder
            continue
        parts = [p.strip() for p in re.split(r"<br\s*/?>", td) if p.strip()]
        href = re.search(r'href="([^"]+)"', td)
        sponsors.append({
            "name": strip_tags(parts[1]) if len(parts) > 1 else "",
            "url": safe_url(href.group(1)) if href else None,
            "logo": img.group(1),
            "description": strip_tags(parts[2]) if len(parts) > 2 else "",
            "deal": strip_tags(parts[3]) if len(parts) > 3 else "",
        })
    return sponsors


def section_links(text, heading_prefix):
    m = re.search(rf"^# {re.escape(heading_prefix)}.*?$(.*?)(?=^# |\Z)", text, re.M | re.S)
    links = []
    for label, url in LINK_RE.findall(m.group(1) if m else ""):
        if not re.match(r"^https?://", url):
            url = f"{REPO}/blob/main/{url}"
        links.append({"label": strip_tags(label), "url": url})
    return links


def parse(readme):
    text = readme.read_text()
    lines = text.split("\n")
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), "Black Friday Deals")
    after_title = lines[lines.index("# " + title) + 1:] if "# " + title in lines else lines
    subtitle = next((l.strip() for l in after_title if l.strip() and not l.lstrip().startswith(("<", "#", "!"))), "")
    subscribe = re.search(r"\((https://app\.vbout\.com/[^)]+)\)", text)

    categories, current = [], None
    for line in lines:
        if line.startswith("## "):
            emoji, _, name = line[3:].strip().partition(" ")
            current = {"emoji": emoji, "name": name.strip(), "deals": []}
            categories.append(current)
        elif line.startswith("# "):
            current = None
        elif current is not None and re.match(r"^\|\s*(\d+\s*\|\s*)?\[", line):
            deal = parse_deal_row(line)
            if deal:
                current["deals"].append(deal)

    now = datetime.now(timezone.utc)
    return {
        "title": title,
        "subtitle": html.unescape(subtitle),
        "subscribe": subscribe.group(1) if subscribe else None,
        "repo": REPO,
        "addDeal": f"{REPO}/edit/main/README.md",
        "form": "https://fill.formnx.com/f/63pk80",
        "sponsorship": f"{REPO}/blob/main/Sponsorship.md",
        "updated": f"{now:%b} {now.day}, {now.year}",
        "categories": categories,
        "sponsors": parse_sponsors(text),
        "archives": section_links(text, "📅 Previous years"),
        "others": section_links(text, "🔖 Other places"),
    }


def main():
    readme = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "README.md"
    data = parse(readme)
    template = (ROOT / "site" / "template.html").read_text()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = (template
            .replace("__TITLE__", html.escape(data["title"]))
            .replace("__SUBTITLE__", html.escape(data["subtitle"]))
            .replace("/*__DATA__*/null", payload))

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    (OUT / "index.html").write_text(page)
    shutil.copytree(ROOT / "assets", OUT / "assets")
    total = sum(len(c["deals"]) for c in data["categories"])
    print(f"Built {OUT / 'index.html'}: {total} deals, {len(data['sponsors'])} sponsors")


if __name__ == "__main__":
    main()
