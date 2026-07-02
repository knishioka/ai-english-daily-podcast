import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "update-rss.py"


def load_update_rss():
    spec = importlib.util.spec_from_file_location("update_rss", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_feed_xml(items: list[str]) -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>AI English Daily</title>
    <!-- EPISODES_START -->
{items}
  </channel>
</rss>
""".format(items="\n".join(items))


class UpdateRssTests(unittest.TestCase):
    def setUp(self):
        self.update_rss = load_update_rss()

    def test_build_item_escapes_text_and_audio_url(self):
        item = self.update_rss.build_item(
            date="2026-04-14",
            title='AI & "English" <Daily>',
            description='Use A&B < C "today"',
            duration="05:23",
            size_bytes=8000000,
            audio_url="https://example.com/podcast.mp3?token=a&name=Ken",
        )

        self.assertIn("AI &amp; &quot;English&quot; &lt;Daily&gt;", item)
        self.assertIn("Use A&amp;B &lt; C &quot;today&quot;", item)
        self.assertIn(
            'url="https://example.com/podcast.mp3?token=a&amp;name=Ken"', item
        )

    def test_build_item_uses_variant_in_guid(self):
        item = self.update_rss.build_item(
            date="2026-04-14",
            title="Shadowing",
            description="Practice",
            duration="05:23",
            size_bytes=8000000,
            audio_url="https://example.com/podcast-shadowing.mp3",
            variant="shadowing",
        )

        self.assertIn("ai-english-daily-2026-04-14-shadowing", item)

    def test_write_index_html_renders_recent_episode_archive(self):
        items = []
        for day in range(14, 30):
            items.append(
                self.update_rss.build_item(
                    date=f"2026-04-{day:02d}",
                    title=f"AI English Daily — 04/{day:02d}",
                    description=(
                        "Today's framework: Before → After → Bridge\n\n"
                        "A short learner-focused summary.\n\n"
                        "🔑 Key terms: runway, retention\n\n"
                        "🎓 Practice tip: shadow the second paragraph."
                    ),
                    duration="05:23",
                    size_bytes=8000000,
                    audio_url=f"https://example.com/{day}.mp3",
                )
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            feed = root / "feed.xml"
            index = root / "index.html"
            feed.write_text(build_feed_xml(items), encoding="utf-8")

            original_feed = self.update_rss.FEED
            original_index = self.update_rss.INDEX
            try:
                self.update_rss.FEED = feed
                self.update_rss.INDEX = index
                self.update_rss.write_index_html()
            finally:
                self.update_rss.FEED = original_feed
                self.update_rss.INDEX = original_index

            html = index.read_text(encoding="utf-8")
            self.assertIn("Recent Episodes", html)
            self.assertIn("Framework", html)
            self.assertIn("Key terms", html)
            self.assertIn("Practice tip", html)
            self.assertIn("AI English Daily — 04/14", html)
            self.assertIn("AI English Daily — 04/27", html)
            self.assertNotIn("AI English Daily — 04/28", html)


if __name__ == "__main__":
    unittest.main()
