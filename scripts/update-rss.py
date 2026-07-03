#!/usr/bin/env python3
"""Update feed.xml and regenerate the landing-page archive.

Usage:
  python3 update-rss.py --date 2026-04-14 --title "..." --description "..." \
    --duration "05:23" --size-bytes 8000000 --audio-url "https://..."
  python3 update-rss.py --refresh-index
"""

import argparse
import email.utils
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET
from xml.sax.saxutils import quoteattr

REPO_ROOT = Path(__file__).resolve().parent.parent
FEED = REPO_ROOT / "feed.xml"
INDEX = REPO_ROOT / "index.html"
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ARCHIVE_LIMIT = 14


def rfc822(date_str: str) -> str:
    """Convert YYYY-MM-DD (MYT assumed 06:00) to RFC 822."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(
        hour=6, minute=0, tzinfo=timezone(timedelta(hours=8))
    )
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def attr(s: str) -> str:
    return quoteattr(s)


def format_date(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d, %Y")


def slug_from_guid(guid: str) -> str:
    return guid.replace("ai-english-daily-", "", 1)


def parse_guid_date(guid: str) -> Optional[str]:
    match = re.match(r"ai-english-daily-(\d{4}-\d{2}-\d{2})", guid)
    if match:
        return match.group(1)
    return None


def parse_pubdate(pub_date: str) -> Optional[str]:
    """Best-effort YYYY-MM-DD from an RFC 822 pubDate; None if unparseable."""
    if not pub_date:
        return None
    try:
        return email.utils.parsedate_to_datetime(pub_date).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def description_lines(description: str) -> list[str]:
    return [line.strip() for line in description.splitlines() if line.strip()]


def first_matching_line(lines: list[str], prefix: str) -> Optional[str]:
    for line in lines:
        if line.startswith(prefix):
            return line
    return None


def summary_from_description(description: str) -> str:
    lines = description_lines(description)
    if not lines:
        return ""
    framework = first_matching_line(lines, "Today's framework:")
    if framework:
        return framework
    return lines[0]


def trim_summary(text: str, limit: int = 220) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def strip_prefix(text: str, prefix: str) -> str:
    if text.startswith(prefix):
        return text[len(prefix) :].strip()
    return text.strip()


def parse_feed_items(limit: int = ARCHIVE_LIMIT) -> list[dict[str, str]]:
    tree = ET.parse(FEED)
    channel = tree.getroot().find("channel")
    if channel is None:
        raise ValueError("RSS channel element not found")

    items: list[dict[str, str]] = []
    for item in channel.findall("item"):
        if len(items) >= limit:
            break
        guid = item.findtext("guid", default="")
        date_str = parse_guid_date(guid) or parse_pubdate(
            item.findtext("pubDate", default="")
        )
        if not date_str:
            # No usable date from guid or pubDate — skip rather than crash the
            # daily update flow on an unexpected item.
            continue

        description = item.findtext("description", default="")
        lines = description_lines(description)
        enclosure = item.find("enclosure")
        duration = item.findtext(f"{{{ITUNES_NS}}}duration", default="")
        items.append(
            {
                "title": item.findtext("title", default="Untitled episode"),
                "date": date_str,
                "formatted_date": format_date(date_str),
                "guid_slug": slug_from_guid(guid) or date_str,
                "description": description,
                "summary": trim_summary(summary_from_description(description)),
                "framework": first_matching_line(lines, "Today's framework:") or "",
                "key_terms": first_matching_line(lines, "🔑 Key terms:") or "",
                "practice_tip": first_matching_line(lines, "🎓 Practice tip:") or "",
                "audio_url": ""
                if enclosure is None
                else enclosure.attrib.get("url", ""),
                "duration": duration,
            }
        )
    return items


def render_episode_card(item: dict[str, str]) -> str:
    framework = (
        strip_prefix(item["framework"], "Today's framework:")
        if item["framework"]
        else ""
    )
    key_terms = (
        strip_prefix(item["key_terms"], "🔑 Key terms:") if item["key_terms"] else ""
    )
    practice_tip = (
        strip_prefix(item["practice_tip"], "🎓 Practice tip:")
        if item["practice_tip"]
        else ""
    )
    parts = [
        '      <article class="episode-card">',
        "        <header>",
        f'          <p class="episode-date">{escape(item["formatted_date"])}</p>',
        f'          <h3 id="{escape(item["guid_slug"])}">{escape(item["title"])}</h3>',
        "        </header>",
    ]
    # Skip the summary when it just repeats the framework line, which is already
    # rendered as its own labeled chip below.
    if item["summary"] and item["summary"] != item["framework"]:
        parts.append(
            f'        <p class="episode-summary">{escape(item["summary"])}</p>'
        )
    if item["framework"]:
        parts.append(
            f'        <p class="study-chip"><strong>Framework</strong> {escape(framework)}</p>'
        )
    if item["key_terms"]:
        parts.append(
            f'        <p class="study-chip"><strong>Key terms</strong> {escape(key_terms)}</p>'
        )
    if item["practice_tip"]:
        parts.append(
            f'        <p class="study-chip"><strong>Practice tip</strong> {escape(practice_tip)}</p>'
        )
    parts.extend(
        [
            '        <p class="episode-meta">',
            f"          <span>{escape(item['duration'] or 'Duration n/a')}</span>",
            f'          <a href={attr(item["audio_url"])} target="_blank" rel="noreferrer">Listen to audio</a>',
            "        </p>",
            "      </article>",
        ]
    )
    return "\n".join(parts)


def build_index_html(items: list[dict[str, str]]) -> str:
    cards = "\n".join(render_episode_card(item) for item in items)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AI English Daily</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f7f4ed;
        --ink: #1f2933;
        --muted: #52606d;
        --card: #fffdf8;
        --line: #d7d0c3;
        --accent: #154b4a;
        --accent-soft: #deefe9;
      }}
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        background:
          radial-gradient(circle at top right, #efe7d6 0, transparent 28%),
          linear-gradient(180deg, #f7f4ed 0%, #f4efe4 100%);
        color: var(--ink);
      }}
      main {{
        max-width: 880px;
        margin: 0 auto;
        padding: 32px 20px 56px;
      }}
      .hero {{
        background: rgba(255, 253, 248, 0.92);
        border: 1px solid var(--line);
        border-radius: 24px;
        padding: 28px;
        box-shadow: 0 18px 50px rgba(31, 41, 51, 0.08);
      }}
      .eyebrow {{
        margin: 0 0 10px;
        color: var(--accent);
        font: 600 0.8rem/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        letter-spacing: 0.16em;
        text-transform: uppercase;
      }}
      h1, h2, h3 {{
        margin: 0;
      }}
      h1 {{
        font-size: clamp(2.2rem, 5vw, 3.6rem);
        line-height: 1.05;
      }}
      .lead {{
        margin: 16px 0 0;
        font-size: 1.08rem;
        line-height: 1.75;
        color: var(--muted);
      }}
      .subscribe-box {{
        margin-top: 24px;
        padding: 18px;
        border-radius: 18px;
        background: var(--accent-soft);
      }}
      .feed-url {{
        display: inline-block;
        margin-top: 10px;
        padding: 10px 12px;
        border-radius: 12px;
        background: #fff;
        color: var(--accent);
        font: 600 0.92rem/1.4 "SFMono-Regular", Menlo, monospace;
        overflow-wrap: anywhere;
      }}
      .archive-header {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: end;
        margin: 34px 0 18px;
      }}
      .archive-copy {{
        max-width: 50ch;
        color: var(--muted);
        line-height: 1.65;
      }}
      .episode-grid {{
        display: grid;
        gap: 16px;
      }}
      .episode-card {{
        padding: 20px;
        border-radius: 20px;
        background: var(--card);
        border: 1px solid var(--line);
        box-shadow: 0 10px 28px rgba(31, 41, 51, 0.05);
      }}
      .episode-date {{
        margin: 0 0 8px;
        color: var(--accent);
        font: 600 0.78rem/1.3 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}
      .episode-card h3 {{
        font-size: 1.35rem;
        line-height: 1.25;
      }}
      .episode-summary {{
        margin: 14px 0 0;
        color: var(--muted);
        line-height: 1.72;
      }}
      .study-chip {{
        margin: 12px 0 0;
        padding: 10px 12px;
        border-radius: 14px;
        background: #f3efe6;
        line-height: 1.6;
      }}
      .study-chip strong {{
        color: var(--accent);
        margin-right: 8px;
      }}
      .episode-meta {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
        align-items: center;
        margin: 16px 0 0;
        color: var(--muted);
        font: 600 0.94rem/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      a {{
        color: var(--accent);
      }}
      @media (max-width: 640px) {{
        main {{
          padding: 20px 14px 40px;
        }}
        .hero {{
          padding: 22px 18px;
        }}
        .archive-header {{
          display: block;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <p class="eyebrow">Daily Business English</p>
        <h1>AI English Daily</h1>
        <p class="lead">
          Daily AI news as short business-English listening practice. Use the latest
          episodes for shadowing, vocabulary review, and presentation-pattern repetition.
        </p>
        <div class="subscribe-box">
          <h2>Subscribe</h2>
          <p class="archive-copy">
            Apple Podcasts → Library → “…” → Add a Show by URL, then paste this feed:
          </p>
          <span class="feed-url">https://knishioka.github.io/ai-english-daily-podcast/feed.xml</span>
        </div>
      </section>

      <section aria-labelledby="recent-episodes">
        <div class="archive-header">
          <div>
            <h2 id="recent-episodes">Recent Episodes</h2>
            <p class="archive-copy">
              The latest {len(items)} episodes are shown here so you can quickly pick one
              by framework, key terms, or practice tip before listening.
            </p>
          </div>
        </div>
        <div class="episode-grid">
{cards}
        </div>
      </section>
    </main>
  </body>
</html>
"""


def write_index_html() -> None:
    INDEX.write_text(build_index_html(parse_feed_items()), encoding="utf-8")


def build_item(
    date: str,
    title: str,
    description: str,
    duration: str,
    size_bytes: int,
    audio_url: str,
    variant: str = "",
) -> str:
    suffix = f"-{variant}" if variant else ""
    guid = f"ai-english-daily-{date}{suffix}"
    pub = rfc822(date)
    return f"""    <item>
      <title>{escape(title)}</title>
      <description>{escape(description)}</description>
      <pubDate>{pub}</pubDate>
      <guid isPermaLink="false">{guid}</guid>
      <enclosure url={attr(audio_url)} length="{size_bytes}" type="audio/mpeg"/>
      <itunes:duration>{duration}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD")
    ap.add_argument("--title")
    ap.add_argument("--description")
    ap.add_argument("--duration", help="HH:MM:SS or MM:SS")
    ap.add_argument("--size-bytes", type=int)
    ap.add_argument("--audio-url")
    ap.add_argument(
        "--variant",
        default="",
        help="Optional variant suffix (e.g. 'shadowing') for a second item on the same date",
    )
    ap.add_argument(
        "--refresh-index",
        action="store_true",
        help="Regenerate index.html from the current feed without adding an episode",
    )
    args = ap.parse_args()

    if args.refresh_index:
        write_index_html()
        print("Refreshed index.html from feed.xml")
        return 0

    required = {
        "date": args.date,
        "title": args.title,
        "description": args.description,
        "duration": args.duration,
        "size_bytes": args.size_bytes,
        "audio_url": args.audio_url,
    }
    missing = [name for name, value in required.items() if value in (None, "")]
    if missing:
        ap.error(f"missing required arguments for episode update: {', '.join(missing)}")

    xml = FEED.read_text(encoding="utf-8")
    item_xml = build_item(
        args.date,
        args.title,
        args.description,
        args.duration,
        args.size_bytes,
        args.audio_url,
        args.variant,
    )

    # Remove existing item with the exact same guid if present
    suffix = f"-{args.variant}" if args.variant else ""
    guid_value = f"ai-english-daily-{args.date}{suffix}"
    guid_pattern = re.compile(
        r"\s*<item>.*?<guid[^>]*>" + re.escape(guid_value) + r"</guid>.*?</item>",
        re.DOTALL,
    )
    xml = guid_pattern.sub("", xml)

    # Insert new item at the top of the episode list
    marker = "<!-- EPISODES_START -->"
    xml = xml.replace(marker, f"{marker}\n{item_xml}")

    FEED.write_text(xml, encoding="utf-8")
    write_index_html()
    print(f"Updated feed.xml with episode {args.date}")


if __name__ == "__main__":
    sys.exit(main() or 0)
