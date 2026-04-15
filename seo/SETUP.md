# SEO setup — manual steps

Code can only do half the work. The rest is engine-side ownership
verification, directory submissions, and a few config knobs nobody can
script for you. Do these in order; each step unblocks the next.

Site: `https://podcast.aequitus.net`

---

## 1. Google Search Console (priority #1)

**Why:** Google won't surface your content in Discover / News / Podcast
results without a verified Search Console property. GSC is also where you
see indexing errors, crawl stats, and core-web-vitals data.

1. Go to <https://search.google.com/search-console>.
2. Add a property → choose **URL prefix** → enter
   `https://podcast.aequitus.net/`.
3. Verify ownership. Easiest method for a GitHub Pages site with a custom
   domain: **HTML tag**.
   - GSC will give you a `<meta name="google-site-verification" content="...">`
     tag.
   - Paste it into the `<head>` of `src/ai_press_review/publish/templates/index-template.html`
     (EN) and `index-template-fr.html` (FR). Commit. Wait for the next deploy.
   - Click **Verify** in GSC.
4. Once verified: **Sitemaps** → submit `sitemap.xml`.
5. **URL inspection** → paste `https://podcast.aequitus.net/` → "Request
   indexing". Repeat for `/fr/` and 1–2 recent episode URLs.

**Bonus for a podcast property:**
- In GSC, `Enhancements → Podcast` will appear once Google parses your
  `PodcastEpisode` schema. After you apply
  `seo/templates/episode-schema-enhanced.html`, re-inspect one episode URL to
  trigger re-parse.

---

## 2. Bing Webmaster Tools

**Why:** Bing powers DuckDuckGo, Ecosia, Brave Search, Yahoo — verifying
once federates to all of them.

1. Go to <https://www.bing.com/webmasters>.
2. **Add site** → `https://podcast.aequitus.net/`.
3. Easiest: **Import from Google Search Console** (reuses step 1's
   verification). Otherwise paste their `<meta name="msvalidate.01" ...>` tag
   into both index templates the same way.
4. **Sitemaps** → submit `https://podcast.aequitus.net/sitemap.xml`.
5. **URL submission** → paste recent URLs. Bing's quota is generous
   (10,000/day) so this is essentially unlimited for a podcast site.

---

## 3. IndexNow (automated post-publish pinging)

**Why:** tells Bing and Yandex about new episodes the second they deploy,
instead of waiting 1–7 days for the crawler.

Setup (one-time):
1. Copy the key file into the live site root:
   ```bash
   cp seo/static/ecc8dffbb048713bbab441ddaee8958e.txt docs/
   ```
2. Commit & push. Wait for GitHub Pages to deploy.
3. Verify the file is reachable:
   ```bash
   curl https://podcast.aequitus.net/ecc8dffbb048713bbab441ddaee8958e.txt
   # → should print: ecc8dffbb048713bbab441ddaee8958e
   ```

Every release:
```bash
python seo/tools/submit_indexnow.py --all
```
Or wire this into `.github/workflows/approve-release.yml` (see
`seo/README.md` → "Integration paths").

---

## 4. Yandex Webmaster (optional, 5 min)

Useful if you have any audience in Eastern Europe or Central Asia. Yandex
also accepts IndexNow so step 3 already covers indexing — this step just
unlocks the diagnostics dashboard.

1. <https://webmaster.yandex.com> → **Add site**.
2. Verify via meta tag (same pattern as GSC).
3. **Indexing → Sitemap files** → add `/sitemap.xml`.

---

## 5. Podcast directory submissions (trust signals)

Google uses podcast directory listings as authority signals. The podcast
should already be on the big three; double-check:

- **Apple Podcasts Connect** — <https://podcastsconnect.apple.com>. Submit
  `https://podcast.aequitus.net/podcast-feed.xml` if not already listed. The
  existing subscribe link on the homepage (`podcasts.apple.com/us/podcast/...`)
  suggests this is done.
- **Spotify for Podcasters** — <https://podcasters.spotify.com>. Same.
- **YouTube Music** — automatic via Spotify sync if the RSS is valid (and
  it is: you already have itunes:type, enclosures, pubDate, etc.).
- **Amazon Music / Audible** — <https://podcasters.amazon.com>. Free, niche
  but real traffic.
- **Podcast Index** — <https://podcastindex.org/add>. Public-domain index
  used by a long tail of Android podcast apps and LLM training data.
- **Listen Notes** — <https://www.listennotes.com/submit-podcast/>. Google
  indexes Listen Notes, so adding the show there often surfaces episode
  pages in SERPs faster than direct crawling.

---

## 6. Ongoing monitoring (weekly, 5 min)

- **GSC → Coverage**: any page marked "Excluded — Duplicate without canonical"
  or "Crawled, not indexed"? That's a content-quality or canonical-tag bug.
- **GSC → Performance**: clicks by query → tells you which AI topics actually
  drive traffic. Feed that into editorial planning.
- **Bing WMT → SEO Reports**: Bing flags specific issues (missing H1s, long
  meta descriptions). Tends to be noisier than GSC but the signal is real.
- After applying `seo/templates/episode-schema-enhanced.html`: re-run
  <https://search.google.com/test/rich-results?url=https://podcast.aequitus.net/episodes/2026-04-15.html>
  to confirm PodcastEpisode + BreadcrumbList both parse.

---

## Quick "did I do all of this?" checklist

- [ ] GSC verified for `podcast.aequitus.net`
- [ ] GSC has `sitemap.xml` submitted, showing "Success"
- [ ] Bing WMT verified (or imported from GSC)
- [ ] Bing WMT has `sitemap.xml` submitted
- [ ] IndexNow key file deployed at `/ecc8dffbb048713bbab441ddaee8958e.txt`
- [ ] `generate_sitemap.py` runs on every publish (or a cron)
- [ ] Enhanced episode schema (`episode-schema-enhanced.html`) applied to
      `episode-brief-template.html`
- [ ] Rich Results Test passes on one recent episode URL
- [ ] Podcast listed on Apple, Spotify, YouTube Music
- [ ] Podcast listed on Podcast Index + Listen Notes
