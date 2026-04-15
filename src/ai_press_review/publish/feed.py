from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

from ..models import PublishedEpisode
from ..settings import DOCS_DIR, load_settings
from ..state import load_episode_history, save_episode_history
from ..storage.r2 import delete_key
from ..utils import utcnow


def publish_episode(
    episode: PublishedEpisode,
    source_fingerprints: list[str],
    source_titles: list[str],
    *,
    script: str | None = None,
    key_claims: list[dict] | None = None,
    grounding_report: dict | None = None,
) -> None:
    history = load_episode_history()
    episodes = history.get('episodes', [])
    payload = episode.to_dict()
    payload['source_fingerprints'] = source_fingerprints
    payload['source_titles'] = source_titles
    if script is not None:
        payload['script'] = script
    if key_claims is not None:
        payload['key_claims'] = key_claims
    if grounding_report is not None:
        payload['grounding_report'] = grounding_report
    payload['source_count'] = len(source_fingerprints)
    payload['domain_count'] = _count_domains(source_titles)
    episodes.insert(0, payload)

    settings = load_settings()
    cutoff = utcnow() - timedelta(days=settings.retention_days)

    kept = []
    for item in episodes:
        published_at = datetime.fromisoformat(item['published_at'])
        if published_at >= cutoff:
            kept.append(item)
        else:
            try:
                key = item['audio_url'].replace(settings.public_audio_base_url.rstrip('/') + '/', '')
                delete_key(key)
            except Exception:
                pass
            # Remove stale per-episode transcript pages as well.
            _remove_episode_artifacts(item.get('slug', ''))

    history['episodes'] = kept
    save_episode_history(history)
    _write_transcripts(kept)
    _write_feed(kept)
    _write_index(kept)
    _write_how_it_works()
    _write_sitemap(kept)
    _write_robots()


def _count_domains(source_titles: list[str]) -> int:
    """Best-effort domain count — if only titles are available, we can't
    compute it exactly, so we leave this as a placeholder the pipeline
    may override later."""
    return 0


def _remove_episode_artifacts(slug: str) -> None:
    if not slug:
        return
    episode_dir = DOCS_DIR / 'episodes' / slug
    if episode_dir.exists():
        for child in episode_dir.iterdir():
            try:
                child.unlink()
            except Exception:
                pass
        try:
            episode_dir.rmdir()
        except Exception:
            pass


def _write_transcripts(episodes: list[dict]) -> None:
    """Regenerate per-episode transcript artifacts (VTT + HTML) for
    every retained episode. Cheap enough at our scale (≤10 episodes)."""
    from .transcript import write_transcript_artifacts

    settings = load_settings()
    for ep in episodes:
        script = ep.get('script') or ''
        if not script:
            continue
        try:
            urls = write_transcript_artifacts(
                docs_dir=DOCS_DIR,
                slug=ep['slug'],
                script=script,
                duration_seconds=int(ep.get('duration_seconds') or 0),
                episode_meta={
                    'title': ep['title'],
                    'summary': ep.get('summary', ''),
                    'published_at': ep.get('published_at', ''),
                    'audio_url': ep.get('audio_url', ''),
                },
                site_base_url=_base_url(settings),
                feed_url=_feed_url(settings),
                cover_url=_absolute(settings, settings.cover_image_path),
                author=settings.podcast_author,
                language=settings.podcast_language,
                key_claims=ep.get('key_claims') or [],
                grounding_coverage=(ep.get('grounding_report') or {}).get('coverage_ratio'),
                source_count=ep.get('source_count', 0),
                domain_count=ep.get('domain_count', 0),
            )
            ep['transcript_vtt_url'] = urls['vtt_url']
            ep['episode_page_url'] = urls['html_url']
        except Exception:
            # Transcript generation is best-effort — never block publish.
            pass


# ── helpers ──────────────────────────────────────────────────────────────────

def _base_url(settings) -> str:
    return settings.site_base_url.rstrip('/')


def _absolute(settings, path: str) -> str:
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return f"{_base_url(settings)}/{path.lstrip('/')}"


def _feed_url(settings) -> str:
    return settings.rss_feed_url or f"{_base_url(settings)}/podcast-feed.xml"


def _secondary_category_xml(settings) -> str:
    if not settings.category_secondary:
        return ''
    if settings.category_secondary.strip().lower() == 'artificial intelligence':
        return '<itunes:category text="Technology"><itunes:category text="Artificial Intelligence" /></itunes:category>'
    return f'<itunes:category text="{escape(settings.category_secondary)}" />'


# ── RSS feed ─────────────────────────────────────────────────────────────────

_PODCAST_NS = 'https://podcastindex.org/namespace/1.0'


def _channel_guid(settings) -> str:
    """Stable channel GUID per Podcasting 2.0 spec. Deterministic UUIDv5
    derived from the podcast feed URL so it stays identical across
    regenerations but changes if the operator forks/moves the feed."""
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, _feed_url(settings)))


def _podcast_person_xml(settings) -> str:
    return (
        f'<podcast:person role="host" group="cast">'
        f'{escape(settings.podcast_author)}'
        '</podcast:person>'
    )


def _write_feed(episodes: list[dict]) -> None:
    settings = load_settings()
    feed_url = _feed_url(settings)
    cover_url = _absolute(settings, settings.cover_image_path)
    description = settings.podcast_description_long or settings.podcast_description_short
    last_build = format_datetime(utcnow())

    items = []
    for ep in episodes:
        pub_date = format_datetime(datetime.fromisoformat(ep['published_at']))
        transcript_tag = ''
        if ep.get('transcript_vtt_url'):
            transcript_tag = (
                f'<podcast:transcript url="{escape(ep["transcript_vtt_url"])}" '
                f'type="text/vtt" rel="captions" />'
            )
        episode_page = ep.get('episode_page_url') or ep.get('source_manifest_url')
        duration_tag = ''
        if ep.get('duration_seconds'):
            duration_tag = f'<itunes:duration>{int(ep["duration_seconds"])}</itunes:duration>'
        items.append(
            f"<item><title>{escape(ep['title'])}</title>"
            f"<description>{escape(ep['summary'])}</description>"
            f"<guid isPermaLink=\"false\">{escape(ep['audio_url'])}</guid>"
            f"<pubDate>{pub_date}</pubDate>"
            f'<enclosure url="{escape(ep["audio_url"])}" length="{ep["audio_bytes"]}" type="audio/mpeg" />'
            f"<itunes:summary>{escape(ep['summary'])}</itunes:summary>"
            f'<itunes:image href="{escape(cover_url)}" />'
            f"<itunes:explicit>{'true' if settings.explicit else 'false'}</itunes:explicit>"
            f"{duration_tag}"
            f"{transcript_tag}"
            f"{_podcast_person_xml(settings)}"
            f"<link>{escape(episode_page)}</link></item>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" '
        'xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:atom="http://www.w3.org/2005/Atom" '
        f'xmlns:podcast="{_PODCAST_NS}">'
        '<channel>'
        f"<title>{escape(settings.podcast_title)}</title>"
        f"<link>{escape(_base_url(settings))}</link>"
        f'<atom:link href="{escape(feed_url)}" rel="self" type="application/rss+xml" />'
        f"<language>{escape(settings.podcast_language)}</language>"
        f"<lastBuildDate>{last_build}</lastBuildDate>"
        '<generator>ai-press-review</generator>'
        # Podcasting 2.0 channel-level
        f'<podcast:guid>{_channel_guid(settings)}</podcast:guid>'
        '<podcast:medium>podcast</podcast:medium>'
        '<podcast:locked>no</podcast:locked>'
        f'{_podcast_person_xml(settings)}'
        f"<itunes:author>{escape(settings.podcast_author)}</itunes:author>"
        f"<itunes:subtitle>{escape(settings.podcast_subtitle)}</itunes:subtitle>"
        f"<itunes:summary>{escape(settings.podcast_description_short)}</itunes:summary>"
        f"<description>{escape(description)}</description>"
        '<itunes:type>episodic</itunes:type>'
        f"<itunes:explicit>{'true' if settings.explicit else 'false'}</itunes:explicit>"
        '<itunes:owner>'
        f"<itunes:name>{escape(settings.podcast_author)}</itunes:name>"
        f"<itunes:email>{escape(settings.podcast_email)}</itunes:email>"
        '</itunes:owner>'
        f'<itunes:image href="{escape(cover_url)}" />'
        f'<image><url>{escape(cover_url)}</url>'
        f"<title>{escape(settings.podcast_title)}</title>"
        f"<link>{escape(_base_url(settings))}</link></image>"
        f'<itunes:category text="{escape(settings.category_primary)}" />'
        f'{_secondary_category_xml(settings)}'
        f"{''.join(items)}"
        '</channel></rss>'
    )
    (DOCS_DIR / 'podcast-feed.xml').write_text(xml, encoding='utf-8')


# ── HTML landing page ────────────────────────────────────────────────────────

def _json_ld(settings, episodes: list[dict]) -> str:
    base = _base_url(settings)
    cover_url = _absolute(settings, settings.cover_image_path)
    description = settings.podcast_description_long or settings.podcast_description_short

    episode_nodes = []
    for ep in episodes[:10]:
        episode_nodes.append({
            '@type': 'PodcastEpisode',
            'name': ep['title'],
            'description': ep['summary'],
            'datePublished': ep['published_at'],
            'url': ep['audio_url'],
            'associatedMedia': {
                '@type': 'MediaObject',
                'contentUrl': ep['audio_url'],
                'encodingFormat': 'audio/mpeg',
            },
        })

    data = {
        '@context': 'https://schema.org',
        '@type': 'PodcastSeries',
        'name': settings.podcast_title,
        'url': base,
        'description': description,
        'image': cover_url,
        'inLanguage': settings.podcast_language,
        'author': {'@type': 'Person', 'name': settings.podcast_author},
        'webFeed': _feed_url(settings),
    }
    if episode_nodes:
        data['episode'] = episode_nodes

    return json.dumps(data, ensure_ascii=False)


def _subscribe_buttons_html(settings, feed_url: str) -> str:
    """Inline subscribe links. RSS always shown; other platforms hidden
    until the operator adds a URL in config/podcast.yaml."""
    parts: list[str] = []
    if settings.apple_podcasts_url:
        parts.append(f"<a href='{escape(settings.apple_podcasts_url)}' rel='noopener' target='_blank'>Apple Podcasts</a>")
    if settings.spotify_url:
        parts.append(f"<a href='{escape(settings.spotify_url)}' rel='noopener' target='_blank'>Spotify</a>")
    if settings.youtube_url:
        parts.append(f"<a href='{escape(settings.youtube_url)}' rel='noopener' target='_blank'>YouTube</a>")
    parts.append(f"<a href='{escape(feed_url)}'>RSS</a>")
    return "<span class='dot'>&middot;</span>".join(parts)


def _arch_bars_svg(n: int = 30, width: int = 320, baseline: int = 78,
                   max_h: int = 70, min_h: int = 8) -> str:
    """Render the waveform-arch SVG used inside the banner. Bars get
    progressively taller toward the center then back down, evoking a
    podcast waveform shaped as an arch."""
    bars = []
    center = (n - 1) / 2
    for i in range(n):
        normalized = abs(i - center) / center
        height = min_h + (max_h - min_h) * (1 - normalized ** 1.4)
        x = (i + 0.5) * (width / n)
        y_top = baseline - height
        bars.append(f'<line x1="{x:.1f}" y1="{baseline}" x2="{x:.1f}" y2="{y_top:.1f}" />')
    return (
        f'<svg class="banner-arch" viewBox="0 0 {width} {baseline + 4}" '
        'aria-hidden="true" role="presentation">'
        '<g stroke="#BF8520" stroke-width="2.4" stroke-linecap="round" fill="none">'
        f'{"".join(bars)}'
        '</g>'
        '</svg>'
    )


def _shared_css() -> str:
    """Single source of truth for the dark editorial palette + Garamond
    typography. Used by both the landing page and the methodology page
    so they look like one site."""
    return (
        ":root{"
        "--bg:#071028;"
        "--bg-soft:#0c1934;"
        "--bg-card:#0f1e3d;"
        "--ink:#F4ECDC;"
        "--ink-soft:#B5A892;"
        "--ink-muted:#7F7560;"
        "--rule:rgba(191,133,32,.22);"
        "--rule-strong:rgba(191,133,32,.45);"
        "--gold:#D9A24A;"
        "--gold-soft:#BF8520;"
        "--gold-dark:#8C601A;"
        "}"
        "*{box-sizing:border-box}"
        "html,body{margin:0;padding:0}"
        "body{font-family:'EB Garamond','Garamond','Cormorant Garamond',Georgia,serif;"
        "background:var(--bg);color:var(--ink);line-height:1.6;"
        "font-size:18px;-webkit-font-smoothing:antialiased}"
        "a{color:var(--gold);text-decoration:none;border-bottom:1px solid transparent;"
        "transition:border-color .15s,color .15s,background .15s}"
        "a:hover{color:#EBC172;border-bottom-color:var(--gold)}"
        # Banner (shared)
        ".banner{background:var(--bg);padding:3.4rem 1.25rem 2.4rem;text-align:center;"
        "position:relative;overflow:hidden}"
        ".banner::before{content:'';position:absolute;inset:0;pointer-events:none;"
        "background:radial-gradient(circle at 50% 60%,rgba(217,162,74,.12) 0%,rgba(7,16,40,0) 60%)}"
        ".banner::after{content:'';position:absolute;inset:0;pointer-events:none;"
        "background:repeating-radial-gradient(circle at 50% 110%,transparent 0,transparent 80px,"
        "rgba(217,162,74,.05) 81px,rgba(217,162,74,.05) 82px)}"
        ".banner-inner{position:relative;z-index:1;max-width:760px;margin:0 auto}"
        ".banner-arch{display:block;width:min(320px,55vw);height:auto;margin:0 auto 1.1rem;opacity:.95}"
        ".banner-title{font-family:'EB Garamond',Garamond,Georgia,serif;font-weight:700;"
        "font-variant:small-caps;letter-spacing:.32em;color:var(--gold);"
        "font-size:clamp(1.55rem,4vw,2.5rem);margin:0;padding-left:.32em;line-height:1.1}"
        ".banner-rule{width:90px;height:1px;background:var(--gold);border:0;"
        "margin:.85rem auto .55rem;opacity:.55}"
        ".banner-author{font-family:'EB Garamond',Garamond,Georgia,serif;font-variant:small-caps;"
        "letter-spacing:.32em;color:var(--gold);font-size:.78rem;margin:0;padding-left:.32em;opacity:.85}"
        ".banner-title a{color:var(--gold);border-bottom:none}"
        ".banner-title a:hover{color:#EBC172;border-bottom:none}"
        # Page nav (small links under banner across pages)
        ".pagenav{position:relative;z-index:1;text-align:center;padding:.85rem 1rem 0;"
        "background:var(--bg);border-bottom:1px solid var(--rule)}"
        ".pagenav a{display:inline-block;margin:0 .9rem;padding-bottom:.85rem;"
        "font-variant:small-caps;letter-spacing:.18em;font-size:.78rem;color:var(--ink-soft)}"
        ".pagenav a:hover{color:var(--gold);border-bottom:1px solid var(--gold)}"
        ".pagenav a.active{color:var(--gold)}"
        # Footer (shared)
        "footer{margin-top:3rem;padding:1.4rem 1rem 1.6rem;border-top:1px solid var(--rule);"
        "text-align:center;color:var(--ink-muted);font-size:.85rem}"
        "footer .sep{margin:0 .5rem;color:var(--gold);opacity:.6}"
        "footer a{color:var(--gold)}"
    )


def _render_banner_html(settings) -> str:
    """Banner header reused on every page."""
    return (
        "<header class='banner'>"
        "<div class='banner-inner'>"
        f"{_arch_bars_svg()}"
        f"<h1 class='banner-title'><a href='/'>{escape(settings.podcast_title)}</a></h1>"
        "<hr class='banner-rule' />"
        f"<p class='banner-author'>{escape(settings.podcast_author)}</p>"
        "</div>"
        "</header>"
    )


def _render_pagenav(active: str, feed_url: str) -> str:
    """Small navigation bar shown under the banner on every page."""
    def cls(name: str) -> str:
        return " class='active'" if name == active else ""
    return (
        "<nav class='pagenav'>"
        f"<a href='/'{cls('home')}>Home</a>"
        f"<a href='/how-it-works.html'{cls('how')}>How it works</a>"
        f"<a href='{escape(feed_url)}'>RSS</a>"
        "</nav>"
    )


def _render_footer(settings, feed_url: str) -> str:
    return (
        "<footer>"
        f"Hosted by {escape(settings.podcast_author)}"
        f"<span class='sep'>&middot;</span><a href='{escape(feed_url)}'>RSS feed</a>"
        f"<span class='sep'>&middot;</span><a href='/how-it-works.html'>How it works</a>"
        "</footer>"
    )


def _render_head(settings, *, page_title: str, page_description: str,
                 canonical_path: str, extra_css: str = '') -> str:
    base = _base_url(settings)
    cover_url = _absolute(settings, settings.cover_image_path)
    cover_rel = settings.cover_image_path
    feed_url = _feed_url(settings)
    keywords = (
        'AI podcast, artificial intelligence, generative AI, LLM, '
        'AI news, AI research, AI use cases, AI tools, weak signals, '
        'AI for business, daily AI briefing'
    )
    canonical = f"{base}{canonical_path}"
    return (
        "<head>"
        "<meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(page_title)}</title>"
        f"<meta name='description' content='{escape(page_description)}'>"
        f"<meta name='keywords' content='{escape(keywords)}'>"
        f"<meta name='author' content='{escape(settings.podcast_author)}'>"
        "<meta name='robots' content='index,follow,max-image-preview:large'>"
        "<meta name='theme-color' content='#071028'>"
        f"<link rel='canonical' href='{escape(canonical)}'>"
        f"<link rel='alternate' type='application/rss+xml' title='{escape(settings.podcast_title)} RSS' href='{escape(feed_url)}'>"
        f"<link rel='icon' type='image/png' href='{escape(cover_rel)}'>"
        f"<link rel='apple-touch-icon' href='{escape(cover_rel)}'>"
        "<meta property='og:type' content='website'>"
        f"<meta property='og:site_name' content='{escape(settings.podcast_title)}'>"
        f"<meta property='og:title' content='{escape(page_title)}'>"
        f"<meta property='og:description' content='{escape(page_description)}'>"
        f"<meta property='og:url' content='{escape(canonical)}'>"
        f"<meta property='og:image' content='{escape(cover_url)}'>"
        "<meta property='og:image:alt' content='AI Press Review cover'>"
        f"<meta property='og:locale' content='{escape(settings.podcast_language)}'>"
        "<meta name='twitter:card' content='summary_large_image'>"
        f"<meta name='twitter:title' content='{escape(page_title)}'>"
        f"<meta name='twitter:description' content='{escape(page_description)}'>"
        f"<meta name='twitter:image' content='{escape(cover_url)}'>"
        "<link rel='preconnect' href='https://fonts.googleapis.com'>"
        "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
        "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap'>"
        f"<style>{_shared_css()}{extra_css}</style>"
        "</head>"
    )


def _episode_card(ep: dict, base: str) -> str:
    episode_link = ep.get('episode_page_url') or f"{base}/episodes/{ep.get('slug', '')}/"
    pub_label = (ep.get('published_at') or '')[:10]
    duration = ''
    if ep.get('duration_seconds'):
        duration = f" &nbsp;&middot;&nbsp; {int(ep['duration_seconds']) // 60} min"
    return (
        f"<article class='card'>"
        f"<p class='card-meta'>{escape(pub_label)}{duration}</p>"
        f"<h3><a href='{escape(episode_link)}'>{escape(ep['title'])}</a></h3>"
        f"<p class='card-summary'>{escape(ep['summary'])}</p>"
        f"<p class='card-links'>"
        f"<a href='{escape(episode_link)}'>Transcript &amp; episode page</a> "
        f"<span class='dot'>&middot;</span> "
        f"<a href='{escape(ep['audio_url'])}'>Listen</a> "
        f"<span class='dot'>&middot;</span> "
        f"<a href='{escape(ep['source_manifest_url'])}'>Sources</a>"
        f"</p>"
        f"</article>"
    )


_HOME_EXTRA_CSS = (
    # Intro block (zone visible sous le banner)
    ".intro{padding:2.4rem 1.25rem 2rem;text-align:center;"
    "border-bottom:1px solid var(--rule);"
    "background:linear-gradient(180deg,rgba(217,162,74,.025) 0%,transparent 100%)}"
    ".intro-inner{max-width:680px;margin:0 auto}"
    ".intro .tagline{font-family:'EB Garamond',serif;font-style:italic;"
    "font-size:clamp(1.35rem,3vw,1.75rem);color:var(--ink);"
    "margin:0 0 .6rem;line-height:1.35;font-weight:500}"
    ".intro .description{color:var(--ink-soft);font-size:1.02rem;line-height:1.55;"
    "margin:0 0 1.4rem;max-width:580px;margin-left:auto;margin-right:auto}"
    ".intro .tagline-note{font-size:.78rem;color:var(--gold);text-align:center;"
    "margin:0 0 1.6rem;font-variant:small-caps;letter-spacing:.28em;opacity:.85}"
    ".intro .subscribe{display:flex;flex-wrap:wrap;justify-content:center;"
    "gap:.55rem;margin:0 0 1.4rem}"
    ".intro .subscribe .label{display:none}"
    ".intro .subscribe a{display:inline-flex;align-items:center;padding:.55rem 1.1rem;"
    "border:1px solid var(--rule-strong);border-radius:999px;color:var(--gold);"
    "font-size:.92rem;font-weight:500;letter-spacing:.02em;background:rgba(217,162,74,.04);"
    "border-bottom:1px solid var(--rule-strong)}"
    ".intro .subscribe a:hover{background:rgba(217,162,74,.12);"
    "color:#EBC172;border-color:var(--gold)}"
    ".intro .subscribe .dot{display:none}"
    ".intro .hiw-link{display:inline-block;margin:0;font-size:.85rem;"
    "font-variant:small-caps;letter-spacing:.22em;color:var(--ink-soft);"
    "padding:.4rem .9rem;border-bottom:1px solid var(--rule)}"
    ".intro .hiw-link:hover{color:var(--gold);border-bottom-color:var(--gold)}"
    # Page wrap
    ".wrap{max-width:760px;margin:0 auto;padding:2.5rem 1.25rem 3rem}"
    ".sect-head{font-family:'EB Garamond',serif;font-weight:700;font-variant:small-caps;"
    "letter-spacing:.24em;color:var(--gold);font-size:.95rem;text-align:center;"
    "margin:0 0 1.6rem}"
    # Episode cards
    ".card{background:var(--bg-card);border:1px solid var(--rule);border-radius:4px;"
    "padding:1.4rem 1.6rem;margin:0 0 1.1rem;"
    "transition:border-color .2s,box-shadow .2s,transform .2s}"
    ".card:hover{border-color:var(--gold-soft);box-shadow:0 8px 28px rgba(0,0,0,.35);"
    "transform:translateY(-1px)}"
    ".card.empty{text-align:center;border-style:dashed;background:transparent}"
    ".card-meta{font-variant:small-caps;letter-spacing:.18em;font-size:.78rem;"
    "color:var(--gold);margin:0 0 .35rem;opacity:.9}"
    ".card h3{font-family:'EB Garamond',serif;font-weight:700;color:var(--ink);"
    "font-size:1.45rem;line-height:1.25;margin:0 0 .55rem}"
    ".card h3 a{color:var(--ink);border-bottom:none}"
    ".card h3 a:hover{color:var(--gold);border-bottom:none}"
    ".card-summary{margin:0 0 .8rem;color:var(--ink-soft);font-size:1rem;line-height:1.55}"
    ".card-links{margin:0;font-size:.88rem;color:var(--ink-muted)}"
    ".card-links a{color:var(--gold)}"
    ".card-links .dot{margin:0 .35rem;color:var(--gold);opacity:.55}"
    # Mobile
    "@media (max-width:560px){"
    ".intro{padding:2rem 1rem 1.6rem}"
    ".intro .tagline{font-size:1.25rem}"
    ".intro .subscribe a{font-size:.85rem;padding:.45rem .9rem}"
    ".wrap{padding:2rem 1rem 2rem}"
    ".card{padding:1.2rem 1.2rem}"
    ".card h3{font-size:1.25rem}"
    "}"
)


def _write_index(episodes: list[dict]) -> None:
    settings = load_settings()
    base = _base_url(settings)
    description = settings.podcast_description_short or settings.podcast_description_long
    long_desc = settings.podcast_description_long or description
    feed_url = _feed_url(settings)

    cards = [_episode_card(ep, base) for ep in episodes]
    empty = (
        "<div class='card empty'>"
        "<p class='card-meta'>Coming soon</p>"
        "<h3>First episode publishing within days.</h3>"
        "<p class='card-summary'>Subscribe via Apple, Spotify, YouTube, or RSS to be notified.</p>"
        "</div>"
    )
    subscribe_html = _subscribe_buttons_html(settings, feed_url)

    json_ld = _json_ld(settings, episodes)
    page_title = f"{settings.podcast_title} — {settings.podcast_subtitle}"

    head = _render_head(
        settings,
        page_title=page_title,
        page_description=description,
        canonical_path='/',
        extra_css=_HOME_EXTRA_CSS,
    )

    html = (
        "<!doctype html>"
        f"<html lang='{escape(settings.podcast_language)}'>"
        + head
        + f"<script type='application/ld+json'>{json_ld}</script>"
        + "<body>"
        + _render_banner_html(settings)
        + _render_pagenav('home', feed_url)
        + "<section class='intro'>"
        + "<div class='intro-inner'>"
        + f"<p class='tagline'>{escape(settings.podcast_subtitle)}</p>"
        + f"<p class='description'>{escape(long_desc)}</p>"
        + "<p class='tagline-note'>An editorial podcast &middot; Daily, 7&thinsp;AM CET</p>"
        + f"<div class='subscribe'>{subscribe_html}</div>"
        + "<a class='hiw-link' href='/how-it-works.html'>How it works &rarr;</a>"
        + "</div>"
        + "</section>"
        + "<div class='wrap'>"
        + "<h2 class='sect-head'>Latest episodes</h2>"
        + "<main>"
        + (''.join(cards) if cards else empty)
        + "</main>"
        + "</div>"
        + _render_footer(settings, feed_url)
        + "</body></html>"
    )
    (DOCS_DIR / 'index.html').write_text(html, encoding='utf-8')


_HOW_EXTRA_CSS = (
    ".wrap{max-width:740px;margin:0 auto;padding:2.5rem 1.25rem 3rem}"
    ".page-lead{text-align:center;font-style:italic;color:var(--ink-soft);"
    "font-size:1.15rem;margin:0 0 2.4rem;line-height:1.5}"
    ".section{margin-bottom:2.6rem}"
    ".section .num{font-variant:small-caps;letter-spacing:.28em;font-size:.78rem;"
    "color:var(--gold);margin:0 0 .5rem;display:block}"
    ".section h2{font-family:'EB Garamond',serif;font-weight:700;color:var(--ink);"
    "font-size:1.6rem;margin:0 0 1rem;line-height:1.25}"
    ".section p{margin:0 0 .9rem;color:var(--ink-soft);font-size:1.02rem;"
    "line-height:1.65}"
    ".section p strong{color:var(--ink);font-weight:600}"
    "table.tiers{width:100%;border-collapse:collapse;margin:1rem 0 .5rem;"
    "font-size:.95rem;background:var(--bg-card);border:1px solid var(--rule)}"
    "table.tiers th,table.tiers td{padding:.7rem .9rem;text-align:left;"
    "border-bottom:1px solid var(--rule);vertical-align:top}"
    "table.tiers th{font-variant:small-caps;letter-spacing:.18em;color:var(--gold);"
    "font-weight:600;font-size:.78rem;background:var(--bg-soft)}"
    "table.tiers td.weight{color:var(--gold);font-variant:small-caps;letter-spacing:.1em;"
    "white-space:nowrap;font-weight:600}"
    "table.tiers td.examples{color:var(--ink-soft);font-size:.92rem;font-style:italic}"
    "ul.exclusions{margin:0 0 .9rem;padding-left:1.2rem;color:var(--ink-soft)}"
    "ul.exclusions li{margin:.4rem 0;line-height:1.5}"
    ".pillars{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));"
    "gap:.85rem;margin:1rem 0}"
    ".pillars .pillar{padding:.95rem 1.1rem;background:var(--bg-card);"
    "border:1px solid var(--rule);border-radius:4px;font-size:.92rem;"
    "color:var(--ink-soft)}"
    ".pillars .pillar strong{display:block;color:var(--gold);font-size:.85rem;"
    "font-variant:small-caps;letter-spacing:.16em;margin-bottom:.3rem}"
    ".author-card{padding:1.4rem 1.6rem;background:var(--bg-card);"
    "border:1px solid var(--rule);border-radius:4px;margin:1rem 0}"
    ".author-card .name{font-family:'EB Garamond',serif;font-weight:700;color:var(--ink);"
    "font-size:1.2rem;margin:0 0 .25rem}"
    ".author-card .tag{font-variant:small-caps;letter-spacing:.18em;font-size:.75rem;"
    "color:var(--gold);margin:0 0 .8rem}"
    ".section-rule{display:block;width:60px;height:1px;background:var(--gold-soft);"
    "border:0;margin:0 0 1.3rem;opacity:.5}"
    "@media (max-width:560px){"
    ".wrap{padding:2rem 1rem 2rem}"
    ".section h2{font-size:1.35rem}"
    "table.tiers{font-size:.85rem}"
    "table.tiers th,table.tiers td{padding:.5rem .55rem}"
    "}"
)


def _write_how_it_works() -> None:
    settings = load_settings()
    feed_url = _feed_url(settings)
    page_title = f"How it works — {settings.podcast_title}"
    page_desc = (
        "How AI Press Review selects, weights, and verifies sources. "
        "Editorial method behind the daily AI briefing."
    )

    head = _render_head(
        settings,
        page_title=page_title,
        page_description=page_desc,
        canonical_path='/how-it-works.html',
        extra_css=_HOW_EXTRA_CSS,
    )

    body = (
        _render_banner_html(settings)
        + _render_pagenav('how', feed_url)
        + "<div class='wrap'>"
        + "<p class='page-lead'>40+ sources. 15 minutes. What matters in AI today &mdash; "
          "and exactly how each episode is built.</p>"
        # 01
        + "<section class='section'>"
        + "<hr class='section-rule' />"
        + "<span class='num'>01 &middot; Who this is for</span>"
        + "<h2>Built for professionals whose work is affected by AI</h2>"
        + "<p>AI Press Review is built for finance, banking, legal, healthcare, consulting "
          "and enterprise technology professionals. Smart, time-poor, and exposed to AI shifts "
          "without the bandwidth to monitor 40 sources daily.</p>"
        + "<p>Each episode is designed for a morning commute or a focused 15-minute break. "
          "You don't need a technical background. You need to know what changed, what it "
          "means for your sector, and what signal is worth tracking next week.</p>"
        + "</section>"
        # 02
        + "<section class='section'>"
        + "<hr class='section-rule' />"
        + "<span class='num'>02 &middot; How sources are selected and weighted</span>"
        + "<h2>40+ sources, weighted by editorial standards</h2>"
        + "<p><strong>40+ is a minimum threshold, not a target.</strong> Each episode draws "
          "from at least forty global sources gathered in the 12 hours preceding publication. "
          "Sources are not treated equally. Each carries a weight score based on editorial "
          "standards, domain authority, and primary-source proximity.</p>"
        + "<table class='tiers'>"
        + "<thead><tr><th>Tier</th><th>Weight</th><th>Examples</th><th>Rationale</th></tr></thead>"
        + "<tbody>"
        + "<tr><td>Primary / Official</td>"
          "<td class='weight'>2.0&times;</td>"
          "<td class='examples'>openai.com, deepmind.com, anthropic.com, arxiv.org</td>"
          "<td>Official announcements, peer-reviewed research</td></tr>"
        + "<tr><td>Tier-1 Press</td>"
          "<td class='weight'>1.5&times;</td>"
          "<td class='examples'>reuters.com, ft.com, mit.edu, nature.com</td>"
          "<td>Editorial standards, original reporting</td></tr>"
        + "<tr><td>Specialist Tech Press</td>"
          "<td class='weight'>1.0&times;</td>"
          "<td class='examples'>techcrunch.com, wired.com, venturebeat.com</td>"
          "<td>Industry coverage, verified editorially</td></tr>"
        + "</tbody></table>"
        + "<p>Each episode's source manifest &mdash; the actual domains and articles used "
          "&mdash; is published alongside the episode page.</p>"
        + "</section>"
        # 03
        + "<section class='section'>"
        + "<hr class='section-rule' />"
        + "<span class='num'>03 &middot; What we exclude, and why</span>"
        + "<h2>Editorial discipline is also what you leave out</h2>"
        + "<ul class='exclusions'>"
        + "<li><strong>Regulatory speculation and policy rumors</strong> &mdash; unverified "
          "regulatory moves produce noise that is almost always revised. We wait for official filings.</li>"
        + "<li><strong>Unverified announcements without independent corroboration</strong> &mdash; "
          "if only one source carries a claim, it doesn't air.</li>"
        + "<li><strong>Opinion and editorial commentary</strong> &mdash; AI Press Review reports "
          "what happened, not what commentators think about it. Interpretation is yours.</li>"
        + "<li><strong>Funding rounds below $50M and pre-seed announcements</strong> &mdash; "
          "capital events dominate AI coverage and crowd out operational signal.</li>"
        + "<li><strong>Engagement-optimized content</strong> &mdash; social media posts, "
          "thought-leadership, and content farms are excluded regardless of virality.</li>"
        + "</ul>"
        + "</section>"
        # 04
        + "<section class='section'>"
        + "<hr class='section-rule' />"
        + "<span class='num'>04 &middot; How episodes are structured</span>"
        + "<h2>Six pillars, one continuous narrative</h2>"
        + "<div class='pillars'>"
        + "<div class='pillar'><strong>AI News</strong>Verified announcements from labs, companies, institutions.</div>"
        + "<div class='pillar'><strong>Research &amp; Breakthroughs</strong>Peer-reviewed publications and lab releases.</div>"
        + "<div class='pillar'><strong>Use Cases</strong>Documented enterprise and sector deployments.</div>"
        + "<div class='pillar'><strong>Tools &amp; Practice</strong>Practitioner releases, APIs, frameworks.</div>"
        + "<div class='pillar'><strong>Weak Signals</strong>Early patterns not yet in mainstream coverage.</div>"
        + "<div class='pillar'><strong>Education</strong>Concepts and context for non-technical audiences.</div>"
        + "</div>"
        + "<p><strong>Weekly recap (Saturdays).</strong> Every Saturday episode steps back from "
          "daily news to identify the five trends that defined the week &mdash; connecting dots "
          "across daily episodes and flagging what will likely matter next week.</p>"
        + "</section>"
        # 05
        + "<section class='section'>"
        + "<hr class='section-rule' />"
        + "<span class='num'>05 &middot; Claim &rarr; source grounding</span>"
        + "<h2>Every factual claim is verified against its source</h2>"
        + "<p>After the script is generated, every numerical or named claim is automatically "
          "matched against the cited source's content. The per-episode coverage ratio "
          "&mdash; for instance, <em>14&thinsp;/&thinsp;15 claims verified</em> &mdash; is "
          "published openly on each episode page.</p>"
        + "<p>This is the anti-hallucination guarantee of an AI-produced briefing.</p>"
        + "</section>"
        # 06
        + "<section class='section'>"
        + "<hr class='section-rule' />"
        + "<span class='num'>06 &middot; About the host</span>"
        + "<div class='author-card'>"
        + f"<p class='name'>{escape(settings.podcast_author)}</p>"
        + "<p class='tag'>Senior global trade solutions professional &middot; AI practitioner &middot; Paris</p>"
        + "<p>Twenty years in front-office banking and trade finance. Executive Master in "
          "Artificial Intelligence, Institut Mines-T&eacute;l&eacute;com (2025). AI Press Review "
          "is an extension of a daily professional practice &mdash; monitoring AI developments "
          "across finance, enterprise and research &mdash; structured into a format I would "
          "actually want to listen to. I am responsible for the editorial decisions, source "
          "weighting, and quality of every episode.</p>"
        + "</div>"
        + "</section>"
        # 07
        + "<section class='section'>"
        + "<hr class='section-rule' />"
        + "<span class='num'>07 &middot; Feedback and corrections</span>"
        + "<h2>Substantive feedback is read and applied</h2>"
        + "<p>If you identify a factual error, a source that should be excluded, or a domain "
          "underrepresented in coverage, please write directly. All substantive feedback is "
          f"reviewed; corrections are applied in the following episode where warranted. "
          f"<a href='mailto:{escape(settings.podcast_email)}'>{escape(settings.podcast_email)}</a></p>"
        + "</section>"
        + "</div>"
        + _render_footer(settings, feed_url)
    )

    html = (
        "<!doctype html>"
        f"<html lang='{escape(settings.podcast_language)}'>"
        + head
        + "<body>"
        + body
        + "</body></html>"
    )
    (DOCS_DIR / 'how-it-works.html').write_text(html, encoding='utf-8')

# ── sitemap.xml & robots.txt ─────────────────────────────────────────────────

def _write_sitemap(episodes: list[dict]) -> None:
    settings = load_settings()
    base = _base_url(settings)
    feed_url = _feed_url(settings)

    if episodes:
        last_pub = max(ep['published_at'] for ep in episodes)
        lastmod = datetime.fromisoformat(last_pub).astimezone(timezone.utc).date().isoformat()
    else:
        lastmod = utcnow().date().isoformat()

    urls = [
        ('', 'daily', '1.0', lastmod),
        ('how-it-works.html', 'monthly', '0.7', lastmod),
        ('podcast-feed.xml', 'daily', '0.9', lastmod),
    ]
    # Per-episode transcript pages — indexable content is the real SEO lever.
    for ep in episodes:
        slug = ep.get('slug')
        if not slug:
            continue
        ep_date = (ep.get('published_at') or lastmod)[:10]
        urls.append((f'episodes/{slug}/', 'weekly', '0.8', ep_date))
    url_nodes = ''.join(
        f'<url><loc>{escape(base)}/{escape(path)}</loc>'
        f'<lastmod>{lastmod}</lastmod>'
        f'<changefreq>{freq}</changefreq>'
        f'<priority>{prio}</priority></url>'
        for path, freq, prio, lastmod in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f'{url_nodes}'
        '</urlset>'
    )
    (DOCS_DIR / 'sitemap.xml').write_text(xml, encoding='utf-8')


def _write_robots() -> None:
    settings = load_settings()
    base = _base_url(settings)
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    (DOCS_DIR / 'robots.txt').write_text(content, encoding='utf-8')
