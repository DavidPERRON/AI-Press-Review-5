# SEO workspace — `podcast.aequitus.net`

Isolated SEO tooling + proposed site enhancements for mainstream search engine
indexing (Google, Bing, DuckDuckGo, Yandex). **Nothing in this directory touches
the live publish pipeline.** All assets here are either standalone scripts or
staged files you copy into `docs/` when you're ready to ship.

## What's in here

```
seo/
├── README.md                     (this file)
├── SETUP.md                      step-by-step Google Search Console + Bing WMT
├── tools/
│   ├── generate_sitemap.py       Build a complete sitemap.xml from docs/
│   └── submit_indexnow.py        Push fresh URLs to Bing/Yandex via IndexNow
├── templates/
│   └── episode-schema-enhanced.html   Proposed richer JSON-LD + BreadcrumbList
├── static/
│   ├── robots.txt                Proposed robots.txt (cosmetic upgrade)
│   └── ecc8dffbb048713bbab441ddaee8958e.txt   IndexNow ownership key
└── output/
    └── sitemap.xml               Generated sample (safe to inspect/diff)
```

## Why the site needs these

The live site already has strong baseline SEO (meta, OG, Twitter cards, RSS,
hreflang EN/FR, basic PodcastSeries schema, a robots.txt, a sitemap). What was
missing for consistent indexing:

| Issue                                           | Impact                                  | Fix in this dir                 |
|-------------------------------------------------|-----------------------------------------|---------------------------------|
| `sitemap.xml` lists only 6 URLs, no episodes    | Google won't discover episode pages     | `tools/generate_sitemap.py`     |
| Sitemap is hand-maintained, goes stale          | Freshness signals miss new episodes     | Same (runs on every publish)    |
| Episode JSON-LD uses invalid `PT17:45` duration | Rich-result eligibility fails           | `templates/episode-schema-enhanced.html` |
| Episode schema missing `url`/`image`/`language` | Reduced rich-result eligibility         | Same                            |
| No `BreadcrumbList` schema                      | No SERP breadcrumb trail                | Same                            |
| No push-indexing to Bing/Yandex                 | Indexing lag (days vs. minutes)         | `tools/submit_indexnow.py`      |
| No GSC / Bing WMT verification                  | No indexing diagnostics                 | `SETUP.md`                      |

## Quick start

```bash
# 1. Generate a fresh sitemap and inspect it (writes to seo/output/)
python seo/tools/generate_sitemap.py -v

# 2. Once validated, write it straight to docs/ (replaces the stale hand-written one)
python seo/tools/generate_sitemap.py --write-to-docs

# 3. Copy the IndexNow key into docs/ so IndexNow can verify ownership
cp seo/static/ecc8dffbb048713bbab441ddaee8958e.txt docs/

# 4. Ping Bing/Yandex about every URL on the site
python seo/tools/submit_indexnow.py --all --dry-run   # preview
python seo/tools/submit_indexnow.py --all             # actually submit

# 5. Follow seo/SETUP.md to register with Google Search Console + Bing WMT.
```

## Integration paths (pick one, later)

The tooling is deliberately standalone so you can decide how to wire it in:

**Option A — Run as a separate CI step (safest).**
Add a step at the end of `.github/workflows/approve-release.yml` (and the
daily/weekly workflows) that runs:
```yaml
- name: Refresh sitemap + ping IndexNow
  run: |
    python seo/tools/generate_sitemap.py --write-to-docs
    # Only submit URLs once per day to respect rate limits:
    if [ "${{ matrix.locale }}" = "en" ]; then
      python seo/tools/submit_indexnow.py --all || true   # non-fatal
    fi
```
Benefit: a bug in the sitemap code can't break publishing. Worst case the
step fails, publish already succeeded, you re-run just the SEO job.

**Option B — Port into `src/ai_press_review/publish/`.**
Copy `generate_sitemap.build_sitemap()` into
`src/ai_press_review/publish/sitemap.py` and call it from `publish_episode()`
right after `_write_index(kept)`. Simpler but couples SEO to the publish
critical path.

**Option C — Hybrid (recommended).**
Wire sitemap into the pipeline (Option B — small + low-risk), but keep
IndexNow as its own post-publish workflow step (Option A) so API failures
don't block a release.

## The episode template changes

`templates/episode-schema-enhanced.html` is a **snippet**, not a full template,
so it can't drift from the live HTML/CSS. It documents exactly the two
`<script type="application/ld+json">` blocks to swap in, plus the one-line
change needed in `episode_brief.py` to pass a proper ISO 8601 duration.

Apply when ready:
1. Open `src/ai_press_review/publish/templates/episode-brief-template.html`.
2. Replace the existing single JSON-LD block (around lines 48–71) with the
   two blocks from `seo/templates/episode-schema-enhanced.html`.
3. Follow the "REQUIRED PIPELINE CHANGE" comment in that file (adds a
   `duration_iso` key in `_build_brief_data` and an `{{EPISODE_DURATION_ISO}}`
   placeholder in `generate_episode_brief`).

## What you still need to do manually (no code can do these for you)

See `SETUP.md` for:
1. Verify ownership of `podcast.aequitus.net` in Google Search Console.
2. Submit `https://podcast.aequitus.net/sitemap.xml` in GSC.
3. Same two steps for Bing Webmaster Tools (auto-federates to DuckDuckGo,
   Ecosia, Yahoo).
4. (Optional) Verify in Yandex Webmaster.
5. Submit the podcast RSS to Apple Podcasts, Spotify for Podcasters, YouTube
   Music (if not already done).
6. Submit the podcast to Podcast Index and Listen Notes (directory listings
   that Google uses as trust signals).
