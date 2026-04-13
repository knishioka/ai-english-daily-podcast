# AI English Daily Podcast

Private podcast feed for Ken's daily AI news + business English learning.

## Subscribe

Apple Podcasts → Library → "..." → Add a Show by URL:

```
https://knishioka.github.io/ai-english-daily-podcast/feed.xml
```

## How it works

- OpenClaw cron generates audio daily at 6:00 AM MYT
- Audio uploaded as GitHub Release asset (not committed to repo)
- `scripts/update-rss.py` regenerates `feed.xml` with the new episode
- GitHub Pages serves `feed.xml` for podcast apps to fetch

## Retention

Episodes older than 90 days are deleted automatically by the cron job.
