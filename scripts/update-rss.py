#!/usr/bin/env python3
"""Add or update an episode entry in feed.xml.

Usage:
  python3 update-rss.py --date 2026-04-14 --title "..." --description "..." \
    --duration "05:23" --size-bytes 8000000 --audio-url "https://..."
"""

import argparse
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FEED = REPO_ROOT / "feed.xml"


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
      <enclosure url="{audio_url}" length="{size_bytes}" type="audio/mpeg"/>
      <itunes:duration>{duration}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--title", required=True)
    ap.add_argument("--description", required=True)
    ap.add_argument("--duration", required=True, help="HH:MM:SS or MM:SS")
    ap.add_argument("--size-bytes", required=True, type=int)
    ap.add_argument("--audio-url", required=True)
    ap.add_argument(
        "--variant",
        default="",
        help="Optional variant suffix (e.g. 'shadowing') for a second item on the same date",
    )
    args = ap.parse_args()

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
    print(f"Updated feed.xml with episode {args.date}")


if __name__ == "__main__":
    sys.exit(main() or 0)
